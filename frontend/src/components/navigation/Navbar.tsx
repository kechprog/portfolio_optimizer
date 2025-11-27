import { useAuth0 } from '@auth0/auth0-react';
import { Link } from 'react-router-dom';
import { TrendingUp, LogIn, UserPlus, LayoutDashboard } from 'lucide-react';
import { UserMenu } from './UserMenu';

export const Navbar: React.FC = () => {
  const { isAuthenticated, loginWithRedirect } = useAuth0();

  const handleLogin = () => {
    loginWithRedirect({
      appState: { returnTo: '/dashboard' },
    });
  };

  const handleSignup = () => {
    loginWithRedirect({
      appState: { returnTo: '/dashboard' },
      authorizationParams: {
        screen_hint: 'signup',
      },
    });
  };

  return (
    <nav className="bg-surface border-b border-border sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-3">
            <div className="p-2 bg-accent-muted rounded-lg">
              <TrendingUp className="w-5 h-5 text-accent" />
            </div>
            <span className="text-lg font-semibold text-text-primary">
              Portfolio Optimizer
            </span>
          </Link>

          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <>
                <Link
                  to="/dashboard"
                  className="hidden sm:flex items-center gap-2 px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  <span>Dashboard</span>
                </Link>
                <UserMenu />
              </>
            ) : (
              <>
                <button
                  onClick={handleLogin}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors"
                >
                  <LogIn className="w-4 h-4" />
                  <span className="hidden sm:inline">Log In</span>
                </button>
                <button
                  onClick={handleSignup}
                  className="btn-primary"
                >
                  <UserPlus className="w-4 h-4" />
                  <span className="hidden sm:inline">Sign Up</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};
