import { useAuth0 } from '@auth0/auth0-react';
import { TrendingUp, ArrowRight } from 'lucide-react';

export const HeroSection: React.FC = () => {
  const { loginWithRedirect, isAuthenticated } = useAuth0();

  const handleGetStarted = () => {
    loginWithRedirect({
      appState: { returnTo: '/dashboard' },
      authorizationParams: {
        screen_hint: 'signup',
      },
    });
  };

  const handleLogin = () => {
    loginWithRedirect({
      appState: { returnTo: '/dashboard' },
    });
  };

  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-accent/10 via-surface to-surface py-20 sm:py-32">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(59,130,246,0.1),transparent_50%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_80%,rgba(59,130,246,0.05),transparent_50%)]" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-accent-muted rounded-full mb-6">
            <TrendingUp className="w-4 h-4 text-accent" />
            <span className="text-sm font-medium text-accent">Smart Portfolio Management</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-text-primary mb-6">
            Optimize Your Investment
            <br />
            <span className="text-accent">Portfolio with AI</span>
          </h1>

          <p className="text-lg sm:text-xl text-text-secondary max-w-3xl mx-auto mb-10">
            Leverage advanced algorithms and modern portfolio theory to maximize returns
            while minimizing risk. Backtest strategies, rebalance portfolios, and make
            data-driven investment decisions.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            {!isAuthenticated ? (
              <>
                <button
                  onClick={handleGetStarted}
                  className="btn-primary text-lg px-8 py-4 group"
                >
                  <span>Get Started Free</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </button>
                <button
                  onClick={handleLogin}
                  className="btn-secondary text-lg px-8 py-4"
                >
                  Log In
                </button>
              </>
            ) : (
              <a
                href="/dashboard"
                className="btn-primary text-lg px-8 py-4 group"
              >
                <span>Go to Dashboard</span>
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </a>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
