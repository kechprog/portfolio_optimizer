import {
  Hand,
  TrendingUp,
  ShieldCheck,
  LineChart,
  RefreshCw,
  BarChart3
} from 'lucide-react';

const features = [
  {
    icon: Hand,
    title: 'Manual Allocation',
    description: 'Create custom portfolio allocations with precise control over asset weights and distribution.',
  },
  {
    icon: TrendingUp,
    title: 'Max Sharpe Ratio',
    description: 'Optimize for maximum risk-adjusted returns using the Sharpe ratio optimization algorithm.',
  },
  {
    icon: ShieldCheck,
    title: 'Min Volatility',
    description: 'Minimize portfolio volatility while maintaining target returns for risk-averse investors.',
  },
  {
    icon: LineChart,
    title: 'Historical Backtesting',
    description: 'Test portfolio strategies against historical data to validate performance before investing.',
  },
  {
    icon: RefreshCw,
    title: 'Smart Rebalancing',
    description: 'Automatic portfolio rebalancing recommendations to maintain optimal asset allocation.',
  },
  {
    icon: BarChart3,
    title: 'Performance Analytics',
    description: 'Comprehensive metrics including returns, volatility, Sharpe ratio, and drawdown analysis.',
  },
];

export const FeaturesSection: React.FC = () => {
  return (
    <section className="py-20 bg-surface">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-text-primary mb-4">
            Powerful Features for Smart Investing
          </h2>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
            Everything you need to build, optimize, and manage your investment portfolio
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <div
                key={index}
                className="card hover:shadow-lg transition-shadow duration-300"
              >
                <div className="p-3 bg-accent-muted rounded-lg w-fit mb-4">
                  <Icon className="w-6 h-6 text-accent" />
                </div>
                <h3 className="text-xl font-semibold text-text-primary mb-2">
                  {feature.title}
                </h3>
                <p className="text-text-secondary">
                  {feature.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
