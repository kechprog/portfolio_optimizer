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
          className="absolute top-3 right-3 btn-icon z-10 bg-surface-secondary/80 backdrop-blur-sm"
          title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
        >
          {isFullscreen ? (
            <Minimize2 className="w-4 h-4" />
          ) : (
            <Maximize2 className="w-4 h-4" />
          )}
        </button>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {children}
      </div>
    </div>
  );
};
