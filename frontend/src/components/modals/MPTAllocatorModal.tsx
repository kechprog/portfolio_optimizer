import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { Allocator, MPTAllocatorConfig, AllocatorType } from '../../types';
import './MPTAllocatorModal.css';

interface MPTAllocatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  allocator: Allocator | null;
  allocatorType: 'max_sharpe' | 'min_volatility';
  onSave: (config: MPTAllocatorConfig) => void;
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
  const [updateEnabled, setUpdateEnabled] = useState(false);
  const [updateIntervalValue, setUpdateIntervalValue] = useState(1);
  const [updateIntervalUnit, setUpdateIntervalUnit] = useState<'days' | 'weeks' | 'months'>('months');

  useEffect(() => {
    if (isOpen) {
      if (allocator && (allocator.type === 'max_sharpe' || allocator.type === 'min_volatility')) {
        const config = allocator.config as MPTAllocatorConfig;
        setName(config.name);
        const instrumentRows = config.instruments.map(ticker => ({
          id: crypto.randomUUID(),
          ticker,
        }));
        setInstruments(instrumentRows.length > 0 ? instrumentRows : [{ id: crypto.randomUUID(), ticker: '' }]);
        setAllowShorting(config.allow_shorting);
        setUseAdjClose(config.use_adj_close);
        setUpdateEnabled(config.update_enabled);
        setUpdateIntervalValue(config.update_interval_value || 1);
        setUpdateIntervalUnit(config.update_interval_unit || 'months');
      } else {
        const defaultName = allocatorType === 'max_sharpe' ? 'Max Sharpe Portfolio' : 'Min Volatility Portfolio';
        setName(defaultName);
        setInstruments([{ id: crypto.randomUUID(), ticker: '' }]);
        setAllowShorting(false);
        setUseAdjClose(true);
        setUpdateEnabled(false);
        setUpdateIntervalValue(1);
        setUpdateIntervalUnit('months');
      }
    }
  }, [isOpen, allocator, allocatorType]);

  const handleAddInstrument = () => {
    setInstruments([...instruments, { id: crypto.randomUUID(), ticker: '' }]);
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

    const config: MPTAllocatorConfig = {
      name: name.trim() || (allocatorType === 'max_sharpe' ? 'Max Sharpe Portfolio' : 'Min Volatility Portfolio'),
      instruments: tickerList,
      allow_shorting: allowShorting,
      use_adj_close: useAdjClose,
      update_enabled: updateEnabled,
      ...(updateEnabled && {
        update_interval_value: updateIntervalValue,
        update_interval_unit: updateIntervalUnit,
      }),
    };

    onSave(config);
    onClose();
  };

  const modalTitle = allocator
    ? `Edit ${allocatorType === 'max_sharpe' ? 'Max Sharpe' : 'Min Volatility'} Allocator`
    : `New ${allocatorType === 'max_sharpe' ? 'Max Sharpe' : 'Min Volatility'} Allocator`;

  const hasValidInstruments = instruments.some(row => row.ticker.trim() !== '');

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={modalTitle}>
      <div className="mpt-allocator-form">
        <div className="form-group">
          <label className="form-label" htmlFor="allocator-name">
            Allocator Name
          </label>
          <input
            id="allocator-name"
            type="text"
            className="form-input"
            placeholder={allocatorType === 'max_sharpe' ? 'e.g., Max Sharpe Portfolio' : 'e.g., Low Volatility'}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Instruments</label>
          <div className="instrument-rows">
            {instruments.map((row, index) => (
              <div key={row.id} className="instrument-row">
                <input
                  type="text"
                  className="form-input ticker-input"
                  placeholder="TICKER"
                  value={row.ticker}
                  onChange={(e) => handleTickerChange(row.id, e.target.value)}
                />
                <button
                  type="button"
                  className="btn-icon btn-remove"
                  onClick={() => handleRemoveInstrument(row.id)}
                  disabled={instruments.length === 1}
                  aria-label="Remove instrument"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
          <button type="button" className="btn btn-secondary btn-add" onClick={handleAddInstrument}>
            + Add Instrument
          </button>
        </div>

        <div className="form-group">
          <label className="form-label">Options</label>
          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                className="form-checkbox"
                checked={allowShorting}
                onChange={(e) => setAllowShorting(e.target.checked)}
              />
              <span>Allow Shorting</span>
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                className="form-checkbox"
                checked={useAdjClose}
                onChange={(e) => setUseAdjClose(e.target.checked)}
              />
              <span>Use Adjusted Close</span>
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                className="form-checkbox"
                checked={updateEnabled}
                onChange={(e) => setUpdateEnabled(e.target.checked)}
              />
              <span>Enable Periodic Updates</span>
            </label>
          </div>
        </div>

        {updateEnabled && (
          <div className="form-group">
            <label className="form-label">Update Interval</label>
            <div className="interval-inputs">
              <input
                type="number"
                className="form-input interval-value"
                min="1"
                value={updateIntervalValue}
                onChange={(e) => setUpdateIntervalValue(parseInt(e.target.value) || 1)}
              />
              <select
                className="form-input interval-unit"
                value={updateIntervalUnit}
                onChange={(e) => setUpdateIntervalUnit(e.target.value as 'days' | 'weeks' | 'months')}
              >
                <option value="days">Days</option>
                <option value="weeks">Weeks</option>
                <option value="months">Months</option>
              </select>
            </div>
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
            disabled={!name.trim() || !hasValidInstruments}
          >
            Save
          </button>
        </div>
      </div>
    </Modal>
  );
};
