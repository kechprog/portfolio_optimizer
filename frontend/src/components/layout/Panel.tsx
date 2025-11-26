import React, { useRef } from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';
import { useFullscreen } from '../../hooks';

interface PanelProps {
  children: React.ReactNode;
  className?: string;
  showFullscreen?: boolean;
}

export const Panel: React.FC<PanelProps> = ({
  children,
  className = '',
  showFullscreen = false,
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const { isFullscreen, toggleFullscreen } = useFullscreen(panelRef);

  return (
    <div
      ref={panelRef}
      className={`
        bg-surface-secondary rounded-xl border border-border
        flex flex-col h-full relative
        ${isFullscreen ? 'fixed inset-0 z-50 rounded-none overflow-hidden' : ''}
        ${className}
      `}
    >
      {/* Fullscreen button */}
      {showFullscreen && (
        <button
          onClick={toggleFullscreen}
          className="absolute top-2 right-2 sm:top-3 sm:right-3 p-2.5 sm:p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-tertiary transition-all duration-200 z-10 bg-surface-secondary/80 backdrop-blur-sm min-w-[44px] min-h-[44px] sm:min-w-0 sm:min-h-0 flex items-center justify-center"
          title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
        >
          {isFullscreen ? (
            <Minimize2 className="w-5 h-5 sm:w-4 sm:h-4" />
          ) : (
            <Maximize2 className="w-5 h-5 sm:w-4 sm:h-4" />
          )}
        </button>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto p-3 sm:p-4">
        {children}
      </div>
    </div>
  );
};
