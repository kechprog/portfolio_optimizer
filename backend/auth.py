"""
Auth0 JWT validation module for the backend.

This module provides functionality to validate Auth0 JWT tokens using RS256 algorithm.
It fetches and caches the JWKS (JSON Web Key Set) from Auth0 and validates incoming tokens.
"""

import httpx
from dataclasses import dataclass
from typing import Optional, List
from jose import jwt, JWTError
from cachetools import TTLCache
import config


# Cache for JWKS with 10 hour TTL (36000 seconds)
_jwks_cache = TTLCache(maxsize=1, ttl=36000)


@dataclass
class TokenPayload:
    """Decoded JWT token payload."""
    sub: str
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    permissions: Optional[List[str]] = None


class AuthError(Exception):
    """Exception raised for authentication errors."""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


async def get_jwks() -> dict:
    """
    Fetch and cache the JWKS from Auth0.

    The JWKS (JSON Web Key Set) contains the public keys used to verify JWT signatures.
    Results are cached for 10 hours to reduce API calls to Auth0.

    Returns:
        dict: The JWKS dictionary containing public keys.

    Raises:
        AuthError: If Auth0 is not configured or JWKS fetch fails.
    """
    if not config.AUTH0_JWKS_URL:
        raise AuthError("Auth0 is not configured", 500)

    # Check if JWKS is in cache
    if "jwks" in _jwks_cache:
        return _jwks_cache["jwks"]

    # Fetch JWKS from Auth0
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(config.AUTH0_JWKS_URL, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()

            # Cache the JWKS
            _jwks_cache["jwks"] = jwks
            return jwks

    except httpx.HTTPError as e:
        raise AuthError(f"Failed to fetch JWKS: {str(e)}", 500)
    except Exception as e:
        raise AuthError(f"Unexpected error fetching JWKS: {str(e)}", 500)


def _get_signing_key(jwks: dict, token: str) -> dict:
    """
    Find the matching RSA signing key from JWKS for the given token.

    Args:
        jwks: The JWKS dictionary containing public keys.
        token: The JWT token to find a matching key for.

    Returns:
        dict: The matching RSA key from the JWKS.

    Raises:
        AuthError: If no matching key is found or token header is invalid.
    """
    try:
        # Get the key ID from the token header
        unverified_header = jwt.get_unverified_header(token)

    except JWTError as e:
        raise AuthError(f"Invalid token header: {str(e)}")

    # Check if kid (key ID) is present
    if "kid" not in unverified_header:
        raise AuthError("Token header missing 'kid' field")

    # Find the matching key in JWKS
    kid = unverified_header["kid"]

    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            # Ensure it's an RSA key
            if key.get("kty") != "RSA":
                raise AuthError("Key type must be RSA")
            return key

    raise AuthError(f"No matching key found for kid: {kid}")


async def validate_token(token: str) -> TokenPayload:
    """
    Validate an Auth0 JWT token and return the decoded payload.

    This function:
    1. Fetches the JWKS from Auth0 (cached for 10 hours)
    2. Finds the matching signing key for the token
    3. Validates the token signature, expiration, audience, and issuer
    4. Returns the decoded token payload

    Args:
        token: The JWT token to validate (without "Bearer " prefix).

    Returns:
        TokenPayload: The decoded and validated token payload.

    Raises:
        AuthError: If token validation fails for any reason.
    """
    if not token:
        raise AuthError("No token provided")

    # Get JWKS
    jwks = await get_jwks()

    # Get the signing key
    signing_key = _get_signing_key(jwks, token)

    try:
        # Decode and validate the token
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=config.AUTH0_AUDIENCE,
            issuer=config.AUTH0_ISSUER,
        )

        # Extract relevant fields from payload
        return TokenPayload(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            email_verified=payload.get("email_verified"),
            permissions=payload.get("permissions", []),
        )

    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.JWTClaimsError as e:
        raise AuthError(f"Invalid token claims: {str(e)}")
    except JWTError as e:
        raise AuthError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise AuthError(f"Token validation failed: {str(e)}", 500)


def is_auth_configured() -> bool:
    """
    Check if Auth0 is properly configured.

    Returns:
        bool: True if both AUTH0_DOMAIN and AUTH0_AUDIENCE are set, False otherwise.
    """
    return bool(config.AUTH0_DOMAIN and config.AUTH0_AUDIENCE)
