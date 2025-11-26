import React, { useRef } from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';
import { useFullscreen } from '../../hooks';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  showFullscreen?: boolean;
  headerContent?: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  showFullscreen = false,
  headerContent,
}) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const { isFullscreen, toggleFullscreen } = useFullscreen(cardRef);

  return (
    <div
      ref={cardRef}
      className={`
        bg-surface-secondary rounded-xl border border-border
        flex flex-col h-full overflow-hidden
        ${isFullscreen ? 'fixed inset-0 z-50 rounded-none' : ''}
        ${className}
      `}
    >
      {/* Header with actions */}
      {(showFullscreen || headerContent) && (
        <div className="flex-shrink-0 flex items-center justify-between px-4 py-2 border-b border-border">
          <div className="flex-1">
            {headerContent}
          </div>
          {showFullscreen && (
            <button
              onClick={toggleFullscreen}
              className="btn-icon"
              title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
            >
              {isFullscreen ? (
                <Minimize2 className="w-4 h-4" />
              ) : (
                <Maximize2 className="w-4 h-4" />
              )}
            </button>
          )}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {children}
      </div>
    </div>
  );
};
