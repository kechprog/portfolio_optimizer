import React from 'react';
import { AlertCircle, AlertTriangle, Info, X } from 'lucide-react';
import { Toast as ToastType } from '../../contexts/ToastContext';

interface ToastProps {
  toast: ToastType;
  onDismiss: () => void;
}

export const Toast: React.FC<ToastProps> = ({ toast, onDismiss }) => {
  const { type, title, message, code } = toast;

  const getTypeStyles = () => {
    switch (type) {
      case 'error':
        return {
          container: 'bg-red-900/90 border-red-700',
          icon: 'text-red-400',
          Icon: AlertCircle,
        };
      case 'warning':
        return {
          container: 'bg-amber-900/90 border-amber-700',
          icon: 'text-amber-400',
          Icon: AlertTriangle,
        };
      case 'info':
        return {
          container: 'bg-blue-900/90 border-blue-700',
          icon: 'text-blue-400',
          Icon: Info,
        };
    }
  };

  const { container, icon, Icon } = getTypeStyles();

  return (
    <div
      className={`${container} border rounded-lg shadow-lg p-4 min-w-[320px] max-w-md animate-slide-in-right`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`${icon} w-5 h-5 flex-shrink-0 mt-0.5`} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h4 className="text-white font-semibold text-sm">{title}</h4>
            <button
              onClick={onDismiss}
              className="text-gray-400 hover:text-white transition-colors flex-shrink-0"
              aria-label="Dismiss"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <p className="text-gray-300 text-sm break-words">{message}</p>

          {code && (
            <span className="inline-block mt-2 px-2 py-1 bg-gray-800/50 text-gray-300 text-xs font-mono rounded">
              {code}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
