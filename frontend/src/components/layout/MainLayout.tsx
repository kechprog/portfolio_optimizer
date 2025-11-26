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

      {/* Main content */}
      <main className="flex-1 overflow-hidden p-4 lg:p-6">
        <div className="h-full grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6">
          {/* Left column - Chart and Allocators */}
          <div className="lg:col-span-8 flex flex-col gap-4 lg:gap-6 min-h-0">
            {/* Chart section - takes most of the space */}
            <div className="flex-1 min-h-[300px] overflow-visible">
              {chart}
            </div>

            {/* Allocators section */}
            <div className="flex-shrink-0">
              {allocators}
            </div>
          </div>

          {/* Right column - Portfolio details */}
          <div className="lg:col-span-4 min-h-0 overflow-hidden">
            {portfolio}
          </div>
        </div>
      </main>
    </div>
  );
};
