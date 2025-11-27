import React, { useState, useEffect, useRef } from 'react';
import { Modal } from './Modal';
import { Plus, X } from 'lucide-react';
import { Allocator, MaxSharpeAllocatorConfig, MinVolatilityAllocatorConfig, UpdateInterval } from '../../types';

interface MPTAllocatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  allocator: Allocator | null;
  allocatorType: 'max_sharpe' | 'min_volatility';
  onSave: (config: MaxSharpeAllocatorConfig | MinVolatilityAllocatorConfig) => void;
}

interface InstrumentRow {
  id: string;
  ticker: string;
}

export const MPTAllocatorModal: React.FC<MPTAllocatorModalProps> = ({
  isOpen,
  onClose,
  allocator,
  allocatorType,
  onSave,
}) => {
  const [name, setName] = useState('');
  const [instruments, setInstruments] = useState<InstrumentRow[]>([
    { id: crypto.randomUUID(), ticker: '' },
  ]);
  const [allowShorting, setAllowShorting] = useState(false);
  const [useAdjClose, setUseAdjClose] = useState(true);
  const [focusNewRow, setFocusNewRow] = useState(false);
  const lastInputRef = useRef<HTMLInputElement>(null);

  // Update interval (null = disabled)
  const [updateInterval, setUpdateInterval] = useState<UpdateInterval | null>(null);

  // Min volatility specific - target return (null = disabled)
  const [targetReturn, setTargetReturn] = useState<number | null>(null);

  useEffect(() => {
    if (isOpen) {
      if (allocator && (allocator.type === 'max_sharpe' || allocator.type === 'min_volatility')) {
        const config = allocator.config;
        setName(config.name);
        const instrumentRows = config.instruments.map(ticker => ({
          id: crypto.randomUUID(),
          ticker,
        }));
        setInstruments(instrumentRows.length > 0 ? instrumentRows : [{ id: crypto.randomUUID(), ticker: '' }]);
        setAllowShorting(config.allow_shorting);
        setUseAdjClose(config.use_adj_close);
        setUpdateInterval(config.update_interval ?? null);

        // Min volatility specific
        if (allocator.type === 'min_volatility') {
          setTargetReturn(allocator.config.target_return ?? null);
        } else {
          setTargetReturn(null);
        }
      } else {
        const defaultName = allocatorType === 'max_sharpe' ? 'Max Sharpe Portfolio' : 'Min Volatility Portfolio';
        setName(defaultName);
        setInstruments([{ id: crypto.randomUUID(), ticker: '' }]);
        setAllowShorting(false);
        setUseAdjClose(true);
        setUpdateInterval(null);
        setTargetReturn(null);
      }
    }
  }, [isOpen, allocator, allocatorType]);

  const handleAddInstrument = () => {
    setInstruments([...instruments, { id: crypto.randomUUID(), ticker: '' }]);
    setFocusNewRow(true);
  };

  useEffect(() => {
    if (focusNewRow && lastInputRef.current) {
      lastInputRef.current.focus();
      setFocusNewRow(false);
    }
  }, [focusNewRow, instruments]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddInstrument();
    }
  };

  const handleRemoveInstrument = (id: string) => {
    if (instruments.length > 1) {
      setInstruments(instruments.filter(row => row.id !== id));
    }
  };

  const handleTickerChange = (id: string, ticker: string) => {
    setInstruments(instruments.map(row => row.id === id ? { ...row, ticker: ticker.toUpperCase() } : row));
  };

  const handleSave = () => {
    const tickerList = instruments
      .map(row => row.ticker.trim())
      .filter(ticker => ticker !== '');

    const baseConfig = {
      name: name.trim() || (allocatorType === 'max_sharpe' ? 'Max Sharpe Portfolio' : 'Min Volatility Portfolio'),
      instruments: tickerList,
      allow_shorting: allowShorting,
      use_adj_close: useAdjClose,
      update_interval: updateInterval,
    };

    if (allocatorType === 'min_volatility') {
      const config: MinVolatilityAllocatorConfig = {
        ...baseConfig,
        target_return: targetReturn,
      };
      onSave(config);
    } else {
      const config: MaxSharpeAllocatorConfig = baseConfig;
      onSave(config);
    }

    onClose();
  };

  const modalTitle = allocator
    ? `Edit ${allocatorType === 'max_sharpe' ? 'Max Sharpe' : 'Min Volatility'} Allocator`
    : `New ${allocatorType === 'max_sharpe' ? 'Max Sharpe' : 'Min Volatility'} Allocator`;

  const hasValidInstruments = instruments.some(row => row.ticker.trim() !== '');

  // Custom checkbox component
  const Checkbox = ({ checked, onChange, label }: { checked: boolean; onChange: (checked: boolean) => void; label: string }) => (
    <label className="flex items-center gap-3 cursor-pointer group">
      <div className="relative">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />
        <div className={`
          w-5 h-5 rounded-md border-2 transition-all duration-200
          flex items-center justify-center
          ${checked
            ? 'bg-accent border-accent'
            : 'border-border bg-surface group-hover:border-accent/50'
          }
        `}>
          {checked && (
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
      </div>
      <span className="text-sm text-text-primary">{label}</span>
    </label>
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={modalTitle}>
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
            placeholder={allocatorType === 'max_sharpe' ? 'e.g., Max Sharpe Portfolio' : 'e.g., Low Volatility'}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* Instruments */}
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-2">
            Instruments
          </label>
          <div className="max-h-[300px] overflow-y-auto pl-0.5 pt-0.5 pb-2 pr-1 -ml-0.5 -mt-0.5 -mr-1">
            <div className="flex flex-col gap-2">
              {instruments.map((row, index) => (
                <div key={row.id} className="flex items-center gap-3">
                  <input
                    type="text"
                    className="input flex-1 uppercase"
                    placeholder="TICKER"
                    value={row.ticker}
                    onChange={(e) => handleTickerChange(row.id, e.target.value)}
                    onKeyDown={handleKeyDown}
                    ref={index === instruments.length - 1 ? lastInputRef : undefined}
                  />
                  <button
                    type="button"
                    onClick={() => handleRemoveInstrument(row.id)}
                    disabled={instruments.length === 1}
                    className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-danger-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    aria-label="Remove instrument"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={handleAddInstrument}
            className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-lg border border-dashed border-border hover:border-accent text-text-secondary hover:text-accent transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Instrument
          </button>
        </div>

        {/* Options */}
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-3">
            Options
          </label>
          <div className="flex flex-col gap-3">
            <Checkbox
              checked={allowShorting}
              onChange={setAllowShorting}
              label="Allow Shorting"
            />
            <Checkbox
              checked={useAdjClose}
              onChange={setUseAdjClose}
              label="Use Adjusted Close"
            />
            <Checkbox
              checked={updateInterval !== null}
              onChange={(checked) => setUpdateInterval(checked ? { value: 1, unit: 'months' } : null)}
              label="Enable Periodic Updates"
            />
          </div>
        </div>

        {/* Update Interval */}
        {updateInterval && (
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Update Interval
            </label>
            <div className="flex items-center gap-3">
              <input
                type="number"
                className="input w-24"
                min="1"
                value={updateInterval.value}
                onChange={(e) => setUpdateInterval({ ...updateInterval, value: parseInt(e.target.value) || 1 })}
              />
              <select
                className="input flex-1"
                value={updateInterval.unit}
                onChange={(e) => setUpdateInterval({ ...updateInterval, unit: e.target.value as 'days' | 'weeks' | 'months' })}
              >
                <option value="days">Days</option>
                <option value="weeks">Weeks</option>
                <option value="months">Months</option>
              </select>
            </div>
          </div>
        )}

        {/* Min Volatility specific: Target Return */}
        {allocatorType === 'min_volatility' && (
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-3">
              Target Return
            </label>
            <div className="flex flex-col gap-3">
              <Checkbox
                checked={targetReturn !== null}
                onChange={(checked) => setTargetReturn(checked ? 10 : null)}
                label="Set Minimum Target Return"
              />
              {targetReturn !== null && (
                <div className="flex items-center gap-3 ml-8">
                  <input
                    type="number"
                    className="input w-24"
                    min="0"
                    max="100"
                    step="0.1"
                    value={targetReturn}
                    onChange={(e) => setTargetReturn(parseFloat(e.target.value) || 0)}
                  />
                  <span className="text-sm text-text-muted">% annual return</span>
                </div>
              )}
            </div>
            <p className="text-xs text-text-muted mt-2">
              When enabled, optimizes for minimum volatility while ensuring at least this target return.
            </p>
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
            disabled={!name.trim() || !hasValidInstruments}
            className="px-5 py-2.5 rounded-lg font-medium bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Save
          </button>
        </div>
      </div>
    </Modal>
  );
};
