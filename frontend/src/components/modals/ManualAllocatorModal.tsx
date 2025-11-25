import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { Plus, X } from 'lucide-react';
import { Allocator, ManualAllocatorConfig } from '../../types';

interface ManualAllocatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  allocator: Allocator | null;
  onSave: (config: ManualAllocatorConfig) => void;
}

interface AllocationRow {
  id: string;
  ticker: string;
  allocation: number;
}

export const ManualAllocatorModal: React.FC<ManualAllocatorModalProps> = ({
  isOpen,
  onClose,
  allocator,
  onSave,
}) => {
  const [name, setName] = useState('');
  const [rows, setRows] = useState<AllocationRow[]>([
    { id: crypto.randomUUID(), ticker: '', allocation: 0 },
  ]);

  useEffect(() => {
    if (isOpen) {
      if (allocator && allocator.type === 'manual') {
        const config = allocator.config as ManualAllocatorConfig;
        setName(config.name);
        const allocationRows = Object.entries(config.allocations).map(([ticker, allocation]) => ({
          id: crypto.randomUUID(),
          ticker,
          allocation: allocation * 100,
        }));
        setRows(allocationRows.length > 0 ? allocationRows : [{ id: crypto.randomUUID(), ticker: '', allocation: 0 }]);
      } else {
        setName('');
        setRows([{ id: crypto.randomUUID(), ticker: '', allocation: 0 }]);
      }
    }
  }, [isOpen, allocator]);

  const handleAddRow = () => {
    setRows([...rows, { id: crypto.randomUUID(), ticker: '', allocation: 0 }]);
  };

  const handleRemoveRow = (id: string) => {
    if (rows.length > 1) {
      setRows(rows.filter(row => row.id !== id));
    }
  };

  const handleTickerChange = (id: string, ticker: string) => {
    setRows(rows.map(row => row.id === id ? { ...row, ticker: ticker.toUpperCase() } : row));
  };

  const handleAllocationChange = (id: string, allocation: string) => {
    const value = parseFloat(allocation) || 0;
    setRows(rows.map(row => row.id === id ? { ...row, allocation: value } : row));
  };

  const calculateSum = () => {
    return rows.reduce((sum, row) => sum + row.allocation, 0);
  };

  const handleSave = () => {
    const allocations: Record<string, number> = {};
    rows.forEach(row => {
      if (row.ticker.trim()) {
        allocations[row.ticker.trim()] = row.allocation / 100;
      }
    });

    const config: ManualAllocatorConfig = {
      name: name.trim() || 'Manual Allocator',
      allocations,
    };

    onSave(config);
    onClose();
  };

  const sum = calculateSum();
  const isValidSum = Math.abs(sum - 100) < 0.01;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={allocator ? 'Edit Manual Allocator' : 'New Manual Allocator'}>
      <div className="flex flex-col gap-5">
        {/* Name Input */}
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-2" htmlFor="allocator-name">
            Allocator Name
          </label>
          <input
            id="allocator-name"
            type="text"
            className="input"
            placeholder="e.g., Conservative Mix"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* Allocations */}
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-2">
            Allocations
          </label>
          <div className="flex flex-col gap-2">
            {rows.map((row) => (
              <div key={row.id} className="flex items-center gap-3">
                <input
                  type="text"
                  className="input flex-1 uppercase"
                  placeholder="TICKER"
                  value={row.ticker}
                  onChange={(e) => handleTickerChange(row.id, e.target.value)}
                />
                <div className="relative flex-1">
                  <input
                    type="number"
                    className="input pr-8"
                    placeholder="0"
                    min="0"
                    max="100"
                    step="0.01"
                    value={row.allocation || ''}
                    onChange={(e) => handleAllocationChange(row.id, e.target.value)}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted text-sm pointer-events-none">
                    %
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveRow(row.id)}
                  disabled={rows.length === 1}
                  className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-danger-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  aria-label="Remove instrument"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={handleAddRow}
            className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-lg border border-dashed border-border hover:border-accent text-text-secondary hover:text-accent transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Instrument
          </button>
        </div>

        {/* Sum Display */}
        <div className="flex items-center justify-between p-4 rounded-lg bg-surface-tertiary">
          <span className="text-sm font-medium text-text-secondary">Total Allocation:</span>
          <span className={`text-lg font-semibold ${isValidSum ? 'text-success' : 'text-danger'}`}>
            {sum.toFixed(2)}%
          </span>
        </div>

        {/* Warning */}
        {!isValidSum && (
          <div className="p-3 rounded-lg bg-warning-muted border border-warning/30 text-warning text-sm">
            Warning: Total allocation is not 100%. The allocator will still be saved.
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-tertiary transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={!name.trim() || rows.every(row => !row.ticker.trim())}
            className="px-5 py-2.5 rounded-lg font-medium bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Save
          </button>
        </div>
      </div>
    </Modal>
  );
};
