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
    <section className="relative overflow-hidden bg-gradient-to-br from-accent/10 via-surface to-surface py-16 sm:py-24 lg:py-32">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(59,130,246,0.1),transparent_50%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_80%,rgba(59,130,246,0.05),transparent_50%)]" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-accent-muted rounded-full mb-4 sm:mb-6">
            <TrendingUp className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-accent" />
            <span className="text-xs sm:text-sm font-medium text-accent">Smart Portfolio Management</span>
          </div>

          <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-text-primary mb-4 sm:mb-6 leading-tight">
            Optimize Your Investment
            <br className="hidden sm:block" />
            <span className="sm:hidden"> </span>
            <span className="text-accent">Portfolio with AI</span>
          </h1>

          <p className="text-base sm:text-lg lg:text-xl text-text-secondary max-w-3xl mx-auto mb-8 sm:mb-10 px-2">
            Leverage advanced algorithms and modern portfolio theory to maximize returns
            while minimizing risk. Backtest strategies, rebalance portfolios, and make
            data-driven investment decisions.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
            {!isAuthenticated ? (
              <>
                <button
                  onClick={handleGetStarted}
                  className="btn-primary text-base sm:text-lg px-6 sm:px-8 py-3 sm:py-4 group w-full sm:w-auto"
                >
                  <span>Get Started Free</span>
                  <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5 group-hover:translate-x-1 transition-transform" />
                </button>
                <button
                  onClick={handleLogin}
                  className="btn-secondary text-base sm:text-lg px-6 sm:px-8 py-3 sm:py-4 w-full sm:w-auto"
                >
                  Log In
                </button>
              </>
            ) : (
              <a
                href="/dashboard"
                className="btn-primary text-base sm:text-lg px-6 sm:px-8 py-3 sm:py-4 group w-full sm:w-auto"
              >
                <span>Go to Dashboard</span>
                <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5 group-hover:translate-x-1 transition-transform" />
              </a>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
