import React from 'react';
import { Modal } from './Modal';
import { AlertTriangle } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'primary';
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'primary',
}) => {
  const handleConfirm = () => {
    onConfirm();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <div className="flex flex-col gap-5">
        {variant === 'danger' && (
          <div className="flex items-center gap-3 p-3 rounded-lg bg-danger-muted">
            <AlertTriangle className="w-5 h-5 text-danger flex-shrink-0" />
            <p className="text-sm text-danger">This action cannot be undone.</p>
          </div>
        )}

        <p className="text-text-secondary leading-relaxed">{message}</p>

        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-tertiary transition-colors"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            className={`
              px-5 py-2.5 rounded-lg font-medium transition-colors
              ${variant === 'danger'
                ? 'bg-danger text-white hover:bg-danger/90'
                : 'bg-accent text-white hover:bg-accent-hover'
              }
            `}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </Modal>
  );
};
