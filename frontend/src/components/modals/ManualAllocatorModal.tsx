import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { Allocator, ManualAllocatorConfig } from '../../types';
import './ManualAllocatorModal.css';

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
          allocation: allocation * 100, // Convert to percentage
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
        allocations[row.ticker.trim()] = row.allocation / 100; // Convert back to decimal
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
      <div className="manual-allocator-form">
        <div className="form-group">
          <label className="form-label" htmlFor="allocator-name">
            Allocator Name
          </label>
          <input
            id="allocator-name"
            type="text"
            className="form-input"
            placeholder="e.g., Conservative Mix"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Allocations</label>
          <div className="allocation-rows">
            {rows.map((row, index) => (
              <div key={row.id} className="allocation-row">
                <input
                  type="text"
                  className="form-input ticker-input"
                  placeholder="TICKER"
                  value={row.ticker}
                  onChange={(e) => handleTickerChange(row.id, e.target.value)}
                />
                <div className="allocation-input-wrapper">
                  <input
                    type="number"
                    className="form-input allocation-input"
                    placeholder="0"
                    min="0"
                    max="100"
                    step="0.01"
                    value={row.allocation || ''}
                    onChange={(e) => handleAllocationChange(row.id, e.target.value)}
                  />
                  <span className="allocation-unit">%</span>
                </div>
                <button
                  type="button"
                  className="btn-icon btn-remove"
                  onClick={() => handleRemoveRow(row.id)}
                  disabled={rows.length === 1}
                  aria-label="Remove instrument"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
          <button type="button" className="btn btn-secondary btn-add" onClick={handleAddRow}>
            + Add Instrument
          </button>
        </div>

        <div className="allocation-sum">
          <span className="sum-label">Total Allocation:</span>
          <span className={`sum-value ${isValidSum ? 'sum-valid' : 'sum-invalid'}`}>
            {sum.toFixed(2)}%
          </span>
        </div>

        {!isValidSum && (
          <div className="allocation-warning">
            Warning: Total allocation is not 100%. The allocator will still be saved.
          </div>
        )}

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={!name.trim() || rows.every(row => !row.ticker.trim())}
          >
            Save
          </button>
        </div>
      </div>
    </Modal>
  );
};
