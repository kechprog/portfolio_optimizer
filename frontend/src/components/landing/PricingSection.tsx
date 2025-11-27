import { useAuth0 } from '@auth0/auth0-react';
import { Check, Zap } from 'lucide-react';

const plans = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    description: 'Perfect for getting started',
    features: [
      'Up to 5 portfolio allocators',
      'Basic optimization (Max Sharpe)',
      'Historical backtesting',
      'Performance analytics',
      'Community support',
    ],
    cta: 'Get Started',
    featured: false,
  },
  {
    name: 'Pro',
    price: '$19',
    period: 'per month',
    description: 'For serious investors',
    features: [
      'Unlimited portfolio allocators',
      'All optimization strategies',
      'Advanced backtesting',
      'Real-time rebalancing alerts',
      'Export reports (PDF, CSV)',
      'Priority email support',
      'API access',
    ],
    cta: 'Start Free Trial',
    featured: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: 'contact us',
    description: 'For teams and institutions',
    features: [
      'Everything in Pro',
      'Multi-user collaboration',
      'Custom optimization models',
      'Dedicated account manager',
      'SLA guarantee',
      'Custom integrations',
      'White-label options',
    ],
    cta: 'Contact Sales',
    featured: false,
  },
];

export const PricingSection: React.FC = () => {
  const { loginWithRedirect, isAuthenticated } = useAuth0();

  const handlePlanClick = (planName: string) => {
    if (planName === 'Enterprise') {
      window.location.href = 'mailto:sales@portfoliooptimizer.com';
    } else if (!isAuthenticated) {
      loginWithRedirect({
        appState: { returnTo: '/dashboard' },
        authorizationParams: {
          screen_hint: 'signup',
        },
      });
    } else {
      window.location.href = '/dashboard';
    }
  };

  return (
    <section className="py-20 bg-surface">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-text-primary mb-4">
            Simple, Transparent Pricing
          </h2>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
            Choose the plan that fits your investment strategy
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`card relative ${
                plan.featured
                  ? 'ring-2 ring-accent shadow-xl scale-105'
                  : ''
              }`}
            >
              {plan.featured && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <div className="bg-accent text-white px-4 py-1 rounded-full text-sm font-medium flex items-center gap-1">
                    <Zap className="w-4 h-4" />
                    <span>Most Popular</span>
                  </div>
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold text-text-primary mb-2">
                  {plan.name}
                </h3>
                <p className="text-text-muted text-sm mb-4">
                  {plan.description}
                </p>
                <div className="flex items-baseline justify-center gap-2">
                  <span className="text-4xl font-bold text-text-primary">
                    {plan.price}
                  </span>
                  <span className="text-text-muted">
                    {plan.period}
                  </span>
                </div>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature, featureIndex) => (
                  <li key={featureIndex} className="flex items-start gap-3">
                    <div className="p-1 bg-success-muted rounded-full flex-shrink-0 mt-0.5">
                      <Check className="w-3 h-3 text-success" />
                    </div>
                    <span className="text-text-secondary text-sm">
                      {feature}
                    </span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handlePlanClick(plan.name)}
                className={`w-full ${
                  plan.featured ? 'btn-primary' : 'btn-secondary'
                }`}
              >
                {plan.cta}
              </button>
            </div>
          ))}
        </div>

        <p className="text-center text-text-muted text-sm mt-12">
          All plans include a 14-day free trial. No credit card required.
        </p>
      </div>
    </section>
  );
};
