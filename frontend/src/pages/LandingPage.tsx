import React from 'react';
import { HeroSection, FeaturesSection, TestimonialsSection, PricingSection } from '../components/landing';
import { Navbar } from '../components/navigation';

export const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-surface">
      <Navbar />
      <HeroSection />
      <FeaturesSection />
      <TestimonialsSection />
      <PricingSection />
      <footer className="py-8 border-t border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-text-muted">
            © {new Date().getFullYear()} Portfolio Optimizer. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
};
