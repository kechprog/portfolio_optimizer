import { Star } from 'lucide-react';

const testimonials = [
  {
    name: 'Sarah Chen',
    role: 'Individual Investor',
    avatar: 'SC',
    content: 'This platform transformed how I manage my portfolio. The backtesting feature gave me confidence in my investment decisions, and I\'ve seen consistent results.',
    rating: 5,
  },
  {
    name: 'Michael Rodriguez',
    role: 'Financial Advisor',
    avatar: 'MR',
    content: 'As a financial advisor, I recommend this tool to all my clients. The optimization algorithms are sophisticated yet easy to understand and implement.',
    rating: 5,
  },
  {
    name: 'Emily Thompson',
    role: 'Retirement Planner',
    avatar: 'ET',
    content: 'The min volatility strategy has been perfect for my retirement planning. I can sleep well knowing my portfolio is optimized for stability and growth.',
    rating: 5,
  },
];

export const TestimonialsSection: React.FC = () => {
  return (
    <section className="py-20 bg-surface-secondary">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-text-primary mb-4">
            Trusted by Investors Worldwide
          </h2>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
            See what our users have to say about their experience
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {testimonials.map((testimonial, index) => (
            <div
              key={index}
              className="card hover:shadow-lg transition-shadow duration-300"
            >
              <div className="flex items-center gap-1 mb-4">
                {Array.from({ length: testimonial.rating }).map((_, i) => (
                  <Star key={i} className="w-5 h-5 text-warning fill-warning" />
                ))}
              </div>

              <p className="text-text-secondary mb-6 leading-relaxed">
                "{testimonial.content}"
              </p>

              <div className="flex items-center gap-3 pt-4 border-t border-border">
                <div className="w-12 h-12 rounded-full bg-accent text-white flex items-center justify-center font-medium">
                  {testimonial.avatar}
                </div>
                <div>
                  <p className="font-semibold text-text-primary">
                    {testimonial.name}
                  </p>
                  <p className="text-sm text-text-muted">
                    {testimonial.role}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
