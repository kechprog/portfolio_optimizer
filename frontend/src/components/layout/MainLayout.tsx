import React from 'react';

interface MainLayoutProps {
  header: React.ReactNode;
  chart: React.ReactNode;
  allocators: React.ReactNode;
  portfolio: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  header,
  chart,
  allocators,
  portfolio,
}) => {
  return (
    <div className="h-screen w-screen flex flex-col bg-surface overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-border">
        {header}
      </header>

      {/* Main content - scrollable on mobile, fixed grid on desktop */}
      <main className="flex-1 overflow-auto lg:overflow-hidden p-3 sm:p-4 lg:p-6">
        <div className="lg:h-full flex flex-col lg:grid lg:grid-cols-12 gap-3 sm:gap-4 lg:gap-6">
          {/* Left column - Chart and Allocators */}
          <div className="lg:col-span-8 flex flex-col gap-3 sm:gap-4 lg:gap-6 min-h-0">
            {/* Chart section */}
            <div className="h-[250px] sm:h-[300px] lg:flex-1 lg:h-auto min-h-[200px]">
              {chart}
            </div>

            {/* Allocators section */}
            <div className="flex-shrink-0">
              {allocators}
            </div>
          </div>

          {/* Right column - Portfolio details */}
          <div className="lg:col-span-4 min-h-[300px] lg:min-h-0 lg:h-full">
            {portfolio}
          </div>
        </div>
      </main>
    </div>
  );
};
