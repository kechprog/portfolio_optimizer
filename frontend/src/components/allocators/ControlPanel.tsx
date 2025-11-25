import React from 'react';
import { Play } from 'lucide-react';
import { DateRange } from '../../types';

interface ControlPanelProps {
  dateRange: DateRange;
  onDateRangeChange: (dateRange: DateRange) => void;
  includeDividends: boolean;
  onIncludeDividendsChange: (value: boolean) => void;
  onCompute: () => void;
  isComputing: boolean;
  progress: {
    allocator_id: string;
    message: string;
    step: number;
    total_steps: number;
  } | null;
}

const ControlPanel: React.FC<ControlPanelProps> = ({
  dateRange,
  onDateRangeChange,
  includeDividends,
  onIncludeDividendsChange,
  onCompute,
  isComputing,
  progress,
}) => {
  const handleDateChange = (field: keyof DateRange, value: string) => {
    onDateRangeChange({
      ...dateRange,
      [field]: value,
    });
  };

  const progressPercentage = progress
    ? Math.round((progress.step / progress.total_steps) * 100)
    : 0;

  return (
    <div className="flex flex-col gap-4 p-4 bg-[#2b2b2b] border border-[#3c3c3c] rounded-lg">
      <h2 className="text-lg font-semibold text-white">Control Panel</h2>

      {/* Fit & Plot Button */}
      <button
        onClick={onCompute}
        disabled={isComputing}
        className={`flex items-center justify-center gap-2 w-full px-6 py-4 font-semibold text-lg rounded transition-colors ${
          isComputing
            ? 'bg-gray-600 cursor-not-allowed text-gray-300'
            : 'bg-[#0078d4] hover:bg-[#106ebe] text-white'
        }`}
      >
        <Play size={24} />
        {isComputing ? 'COMPUTING...' : 'FIT & PLOT'}
      </button>

      {/* Progress Bar */}
      {isComputing && progress && (
        <div className="space-y-2">
          <div className="w-full bg-[#1e1e1e] rounded-full h-3 overflow-hidden">
            <div
              className="bg-[#0078d4] h-full transition-all duration-300 rounded-full"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
          <div className="text-sm text-gray-300 text-center">
            {progress.message} ({progress.step}/{progress.total_steps})
          </div>
        </div>
      )}

      {/* Include Dividends Checkbox */}
      <label className="flex items-center gap-2 text-white cursor-pointer hover:bg-[#3c3c3c] p-2 rounded transition-colors">
        <input
          type="checkbox"
          checked={includeDividends}
          onChange={(e) => onIncludeDividendsChange(e.target.checked)}
          className="w-4 h-4 cursor-pointer accent-blue-500"
        />
        <span>Include Dividends</span>
      </label>

      {/* Date Range Inputs */}
      <div className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Fit Start Date
          </label>
          <input
            type="date"
            value={dateRange.fit_start_date}
            onChange={(e) => handleDateChange('fit_start_date', e.target.value)}
            className="w-full px-3 py-2 bg-[#1e1e1e] text-white border border-[#3c3c3c] rounded focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Fit End Date
          </label>
          <input
            type="date"
            value={dateRange.fit_end_date}
            onChange={(e) => handleDateChange('fit_end_date', e.target.value)}
            className="w-full px-3 py-2 bg-[#1e1e1e] text-white border border-[#3c3c3c] rounded focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Test End Date
          </label>
          <input
            type="date"
            value={dateRange.test_end_date}
            onChange={(e) => handleDateChange('test_end_date', e.target.value)}
            className="w-full px-3 py-2 bg-[#1e1e1e] text-white border border-[#3c3c3c] rounded focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;
