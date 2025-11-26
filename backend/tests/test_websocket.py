"""
WebSocket Test Script for Portfolio Optimizer Backend

This script tests all WebSocket message types by connecting to the backend
server and verifying CRUD operations and compute functionality.

Usage:
    Ensure the backend server is running on localhost:8000, then run:
    python test_websocket.py
"""

import asyncio
import json
import websockets
from typing import Any


async def send_and_receive(ws, message: dict) -> dict:
    """Send a message and receive a single response."""
    await ws.send(json.dumps(message))
    response = json.loads(await ws.recv())
    return response


async def receive_until_complete(ws) -> list[dict]:
    """Receive messages until a result or error is received."""
    messages = []
    while True:
        response = json.loads(await ws.recv())
        messages.append(response)
        # Check if this is a final message (result or error)
        if response.get("type") in ["result", "error"]:
            break
        # Also break on non-progress messages that indicate completion
        if response.get("type") not in ["progress"]:
            break
    return messages


def print_separator(title: str):
    """Print a visual separator with a title."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_response(response: dict, indent: int = 2):
    """Pretty print a response dictionary."""
    print(json.dumps(response, indent=indent, default=str))


async def test_allocator_crud(ws) -> bool:
    """Test allocator CRUD operations."""
    print_separator("TEST: Allocator CRUD Operations")

    # 1. Create a manual allocator
    print("\n[1] Creating manual allocator...")
    create_msg = {
        "type": "create_allocator",
        "allocator_type": "manual",
        "config": {
            "name": "Test Manual",
            "allocations": {"AAPL": 0.6, "MSFT": 0.4}
        }
    }
    print(f"Sending: {json.dumps(create_msg, indent=2)}")
    response = await send_and_receive(ws, create_msg)
    print(f"Response:")
    print_response(response)

    if response.get("type") == "error":
        print(f"ERROR: Failed to create allocator: {response.get('message')}")
        return False

    allocator_id = response.get("allocator_id") or response.get("id")
    if not allocator_id:
        # Try to get it from the allocator data
        allocator_data = response.get("allocator", {})
        allocator_id = allocator_data.get("id")

    print(f"Created allocator with ID: {allocator_id}")

    # 2. List allocators and verify it's there
    print("\n[2] Listing allocators...")
    list_msg = {"type": "list_allocators"}
    response = await send_and_receive(ws, list_msg)
    print(f"Response:")
    print_response(response)

    allocators = response.get("allocators", [])
    found = any(
        a.get("id") == allocator_id or a.get("config", {}).get("name") == "Test Manual"
        for a in allocators
    )
    if not found:
        print("WARNING: Created allocator not found in list")
    else:
        print("SUCCESS: Allocator found in list")

    # 3. Update the allocator with new allocations
    print("\n[3] Updating allocator...")
    update_msg = {
        "type": "update_allocator",
        "id": allocator_id,
        "config": {
            "name": "Test Manual Updated",
            "allocations": {"AAPL": 0.5, "MSFT": 0.3, "GOOG": 0.2}
        }
    }
    print(f"Sending: {json.dumps(update_msg, indent=2)}")
    response = await send_and_receive(ws, update_msg)
    print(f"Response:")
    print_response(response)

    # 4. Delete the allocator
    print("\n[4] Deleting allocator...")
    delete_msg = {
        "type": "delete_allocator",
        "id": allocator_id
    }
    print(f"Sending: {json.dumps(delete_msg, indent=2)}")
    response = await send_and_receive(ws, delete_msg)
    print(f"Response:")
    print_response(response)

    # 5. Verify list is empty (or at least doesn't contain our allocator)
    print("\n[5] Verifying allocator was deleted...")
    response = await send_and_receive(ws, {"type": "list_allocators"})
    print(f"Response:")
    print_response(response)

    allocators = response.get("allocators", [])
    found = any(
        a.get("id") == allocator_id or a.get("config", {}).get("name") == "Test Manual Updated"
        for a in allocators
    )
    if found:
        print("WARNING: Allocator still found after deletion")
        return False
    else:
        print("SUCCESS: Allocator was properly deleted")

    print("\nCRUD Test: PASSED")
    return True


async def test_compute_manual(ws) -> bool:
    """Test compute with manual allocator."""
    print_separator("TEST: Compute with Manual Allocator")

    # 1. Create a manual allocator
    print("\n[1] Creating manual allocator for compute test...")
    create_msg = {
        "type": "create_allocator",
        "allocator_type": "manual",
        "config": {
            "name": "Compute Test Manual",
            "allocations": {"AAPL": 0.6, "MSFT": 0.4}
        }
    }
    response = await send_and_receive(ws, create_msg)
    print(f"Create response:")
    print_response(response)

    if response.get("type") == "error":
        print(f"ERROR: Failed to create allocator: {response.get('message')}")
        return False

    allocator_id = response.get("allocator_id") or response.get("id")
    if not allocator_id:
        allocator_data = response.get("allocator", {})
        allocator_id = allocator_data.get("id")

    # 2. Send compute request
    print("\n[2] Sending compute request...")
    compute_msg = {
        "type": "compute",
        "allocator_id": allocator_id,
        "fit_start_date": "2023-01-01",
        "fit_end_date": "2023-12-31",
        "test_end_date": "2024-06-01",
        "include_dividends": True
    }
    print(f"Sending: {json.dumps(compute_msg, indent=2)}")
    await ws.send(json.dumps(compute_msg))

    # 3. Receive progress messages and result
    print("\n[3] Receiving progress and results...")
    while True:
        response = json.loads(await ws.recv())

        if response.get("type") == "progress":
            progress = response.get("progress", 0)
            message = response.get("message", "")
            print(f"  Progress: {progress:.1%} - {message}")
        elif response.get("type") == "result":
            print("\nFinal Result:")
            print_response(response)
            break
        elif response.get("type") == "error":
            print(f"\nERROR: {response.get('message')}")
            # Clean up
            await send_and_receive(ws, {"type": "delete_allocator", "allocator_id": allocator_id})
            return False
        else:
            print(f"  Received: {response.get('type')}")
            print_response(response)
            if response.get("type") not in ["progress"]:
                break

    # Clean up
    print("\n[4] Cleaning up - deleting allocator...")
    await send_and_receive(ws, {"type": "delete_allocator", "allocator_id": allocator_id})

    print("\nManual Compute Test: PASSED")
    return True


async def test_compute_max_sharpe(ws) -> bool:
    """Test compute with max_sharpe allocator."""
    print_separator("TEST: Compute with Max Sharpe Allocator")

    # 1. Create a max_sharpe allocator
    print("\n[1] Creating max_sharpe allocator...")
    create_msg = {
        "type": "create_allocator",
        "allocator_type": "max_sharpe",
        "config": {
            "name": "Test MaxSharpe",
            "instruments": ["AAPL", "MSFT", "GOOG"],
            "allow_shorting": False,
            "use_adj_close": True,
            "update_enabled": False,
            "update_interval_value": 30,
            "update_interval_unit": "days"
        }
    }
    print(f"Sending: {json.dumps(create_msg, indent=2)}")
    response = await send_and_receive(ws, create_msg)
    print(f"Create response:")
    print_response(response)

    if response.get("type") == "error":
        print(f"ERROR: Failed to create allocator: {response.get('message')}")
        return False

    allocator_id = response.get("allocator_id") or response.get("id")
    if not allocator_id:
        allocator_data = response.get("allocator", {})
        allocator_id = allocator_data.get("id")

    # 2. Send compute request
    print("\n[2] Sending compute request...")
    compute_msg = {
        "type": "compute",
        "allocator_id": allocator_id,
        "fit_start_date": "2023-01-01",
        "fit_end_date": "2023-12-31",
        "test_end_date": "2024-06-01",
        "include_dividends": True
    }
    print(f"Sending: {json.dumps(compute_msg, indent=2)}")
    await ws.send(json.dumps(compute_msg))

    # 3. Receive progress messages and result
    print("\n[3] Receiving progress and results...")
    while True:
        response = json.loads(await ws.recv())

        if response.get("type") == "progress":
            progress = response.get("progress", 0)
            message = response.get("message", "")
            print(f"  Progress: {progress:.1%} - {message}")
        elif response.get("type") == "result":
            print("\nFinal Result:")
            print_response(response)
            break
        elif response.get("type") == "error":
            print(f"\nERROR: {response.get('message')}")
            # Clean up
            await send_and_receive(ws, {"type": "delete_allocator", "allocator_id": allocator_id})
            return False
        else:
            print(f"  Received: {response.get('type')}")
            print_response(response)
            if response.get("type") not in ["progress"]:
                break

    # Clean up
    print("\n[4] Cleaning up - deleting allocator...")
    await send_and_receive(ws, {"type": "delete_allocator", "allocator_id": allocator_id})

    print("\nMax Sharpe Compute Test: PASSED")
    return True


async def main():
    """Main test function."""
    print("\n" + "#" * 60)
    print("#  Portfolio Optimizer WebSocket Test Suite")
    print("#" * 60)
    print("\nConnecting to ws://localhost:8000/ws ...")

    try:
        async with websockets.connect("ws://localhost:8000/ws") as ws:
            print("Connected successfully!\n")

            results = {}

            # Test 1: CRUD operations
            try:
                results["CRUD"] = await test_allocator_crud(ws)
            except Exception as e:
                print(f"CRUD Test ERROR: {e}")
                results["CRUD"] = False

            # Test 2: Compute with manual allocator
            try:
                results["Manual Compute"] = await test_compute_manual(ws)
            except Exception as e:
                print(f"Manual Compute Test ERROR: {e}")
                results["Manual Compute"] = False

            # Test 3: Compute with max_sharpe allocator
            try:
                results["Max Sharpe Compute"] = await test_compute_max_sharpe(ws)
            except Exception as e:
                print(f"Max Sharpe Compute Test ERROR: {e}")
                results["Max Sharpe Compute"] = False

            # Summary
            print_separator("TEST SUMMARY")
            all_passed = True
            for test_name, passed in results.items():
                status = "PASSED" if passed else "FAILED"
                symbol = "[+]" if passed else "[-]"
                print(f"  {symbol} {test_name}: {status}")
                if not passed:
                    all_passed = False

            print("\n" + "-" * 40)
            if all_passed:
                print("  All tests PASSED!")
            else:
                print("  Some tests FAILED!")
            print("-" * 40 + "\n")

    except websockets.exceptions.ConnectionRefused:
        print("ERROR: Could not connect to WebSocket server.")
        print("Make sure the backend server is running on localhost:8000")
        print("\nTo start the server, run:")
        print("  cd backend && python main.py")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
