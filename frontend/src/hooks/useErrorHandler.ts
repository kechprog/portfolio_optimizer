import { useCallback } from 'react';
import { useToast } from '../contexts/ToastContext';
import { ErrorMessage, ErrorCategory } from '../types/websocket';

function getCategoryTitle(category: ErrorCategory): string {
  const titles: Record<ErrorCategory, string> = {
    validation: 'Validation Error',
    network: 'Network Error',
    compute: 'Computation Error',
    auth: 'Authentication Error',
    database: 'Database Error',
    system: 'System Error'
  };
  return titles[category] || 'Error';
}

export function useErrorHandler() {
  const { addToast } = useToast();

  const handleError = useCallback((error: ErrorMessage) => {
    const title = getCategoryTitle(error.category);
    const toastType = error.severity === 'warning' ? 'warning' : 'error';

    addToast({
      type: toastType,
      title,
      message: error.message,
      code: error.code
    });
  }, [addToast]);

  return { handleError };
}
