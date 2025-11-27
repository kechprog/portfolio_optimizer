import React from 'react';
import { HeroSection, FeaturesSection, ContactSection } from '../components/landing';
import { Navbar } from '../components/navigation';
import { useTheme } from '../hooks';

export const LandingPage: React.FC = () => {
  // Apply theme based on system settings
  useTheme();

  return (
    <div className="landing-layout bg-surface">
      <Navbar />
      <main>
        <HeroSection />
        <FeaturesSection />
        <ContactSection />
      </main>
      <footer className="py-8 border-t border-border bg-surface">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-sm text-text-muted">
              {new Date().getFullYear()} Portfolio Optimizer. All rights reserved.
            </p>
            <p className="text-sm text-text-muted italic">
              100% free because we haven't figured out how to charge you yet
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};
