import React, { useState, useRef, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import { TrendingUp, Play, Calendar, DollarSign, ChevronLeft, ChevronRight } from 'lucide-react';
import { DateRange } from '../../types';

interface HeaderProps {
  dateRange: DateRange;
  onDateRangeChange: (range: DateRange) => void;
  includeDividends: boolean;
  onIncludeDividendsChange: (include: boolean) => void;
  onCompute: () => void;
  isComputing: boolean;
  progress?: {
    message: string;
    step: number;
    total_steps: number;
  } | null;
}

// Custom input component for DatePicker
const CustomDateInput = React.forwardRef<HTMLButtonElement, { value?: string; onClick?: () => void; title?: string }>(
  ({ value, onClick, title }, ref) => (
    <button
      type="button"
      className="input text-sm py-1.5 px-3 min-w-[130px] text-left flex items-center gap-2"
      onClick={onClick}
      ref={ref}
      title={title}
    >
      <Calendar className="w-4 h-4 text-text-secondary" />
      <span>{value}</span>
    </button>
  )
);
CustomDateInput.displayName = 'CustomDateInput';

// Month names for autocomplete
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

// Custom header component for DatePicker
const CustomHeaderContent: React.FC<{
  date: Date;
  changeYear: (year: number) => void;
  changeMonth: (month: number) => void;
  decreaseMonth: () => void;
  increaseMonth: () => void;
  prevMonthButtonDisabled: boolean;
  nextMonthButtonDisabled: boolean;
}> = ({
  date,
  changeYear,
  changeMonth,
  decreaseMonth,
  increaseMonth,
  prevMonthButtonDisabled,
  nextMonthButtonDisabled,
}) => {
  const [monthInput, setMonthInput] = useState(MONTHS[date.getMonth()]);
  const [yearInput, setYearInput] = useState(date.getFullYear().toString());
  const [showMonthDropdown, setShowMonthDropdown] = useState(false);
  const [showYearDropdown, setShowYearDropdown] = useState(false);
  const [isTypingMonth, setIsTypingMonth] = useState(false);
  const [isTypingYear, setIsTypingYear] = useState(false);
  const [highlightedMonthIndex, setHighlightedMonthIndex] = useState(-1);
  const [highlightedYearIndex, setHighlightedYearIndex] = useState(-1);
  const monthInputRef = useRef<HTMLInputElement>(null);
  const yearInputRef = useRef<HTMLInputElement>(null);
  const monthDropdownRef = useRef<HTMLDivElement>(null);
  const yearDropdownRef = useRef<HTMLDivElement>(null);

  // Generate year range (current year +/- 50 years)
  const currentYear = new Date().getFullYear();
  const YEARS = Array.from({ length: 101 }, (_, i) => currentYear - 50 + i);

  // Update inputs when date changes externally
  useEffect(() => {
    setMonthInput(MONTHS[date.getMonth()]);
    setYearInput(date.getFullYear().toString());
  }, [date]);

  // Show all months when not typing, filter when typing
  const displayedMonths = isTypingMonth
    ? MONTHS.filter(month => month.toLowerCase().startsWith(monthInput.toLowerCase()))
    : MONTHS;

  // Show all years when not typing, filter when typing
  const displayedYears = isTypingYear
    ? YEARS.filter(year => year.toString().includes(yearInput))
    : YEARS;

  // Handle month input change (user is typing)
  const handleMonthInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setMonthInput(value);
    setIsTypingMonth(true);
    setShowMonthDropdown(true);

    // Auto-select if exact match
    const exactMatch = MONTHS.findIndex(m => m.toLowerCase() === value.toLowerCase());
    if (exactMatch !== -1) {
      changeMonth(exactMatch);
    }
  };

  // Handle month focus - show dropdown with all options
  const handleMonthFocus = () => {
    setShowMonthDropdown(true);
    setShowYearDropdown(false);
    setIsTypingMonth(false);
    setHighlightedMonthIndex(-1);
    monthInputRef.current?.select();
  };

  // Handle month selection from dropdown
  const handleMonthSelect = (month: string, index: number) => {
    setMonthInput(month);
    changeMonth(index);
    setShowMonthDropdown(false);
    setIsTypingMonth(false);
    setHighlightedMonthIndex(-1);
  };

  // Handle year input change (user is typing)
  const handleYearInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setYearInput(value);
    setIsTypingYear(true);
    setShowYearDropdown(true);
    setHighlightedYearIndex(-1);

    const year = parseInt(value, 10);
    if (!isNaN(year) && year >= 1900 && year <= 2100) {
      changeYear(year);
    }
  };

  // Handle year focus - show dropdown with all options
  const handleYearFocus = () => {
    setShowYearDropdown(true);
    setShowMonthDropdown(false);
    setIsTypingYear(false);
    setHighlightedYearIndex(-1);
    yearInputRef.current?.select();
  };

  // Handle year selection from dropdown
  const handleYearSelect = (year: number) => {
    setYearInput(year.toString());
    changeYear(year);
    setShowYearDropdown(false);
    setIsTypingYear(false);
    setHighlightedYearIndex(-1);
  };

  // Handle keyboard navigation for month dropdown
  const handleMonthKeyDown = (e: React.KeyboardEvent) => {
    if (!showMonthDropdown || displayedMonths.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedMonthIndex(prev =>
        prev < displayedMonths.length - 1 ? prev + 1 : 0
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedMonthIndex(prev =>
        prev > 0 ? prev - 1 : displayedMonths.length - 1
      );
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const indexToSelect = highlightedMonthIndex >= 0 ? highlightedMonthIndex : 0;
      const month = displayedMonths[indexToSelect];
      const monthIndex = MONTHS.indexOf(month);
      handleMonthSelect(month, monthIndex);
    } else if (e.key === 'Escape') {
      setShowMonthDropdown(false);
      setIsTypingMonth(false);
      setHighlightedMonthIndex(-1);
      setMonthInput(MONTHS[date.getMonth()]);
    }
  };

  // Handle keyboard navigation for year dropdown
  const handleYearKeyDown = (e: React.KeyboardEvent) => {
    if (!showYearDropdown || displayedYears.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedYearIndex(prev =>
        prev < displayedYears.length - 1 ? prev + 1 : 0
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedYearIndex(prev =>
        prev > 0 ? prev - 1 : displayedYears.length - 1
      );
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const indexToSelect = highlightedYearIndex >= 0 ? highlightedYearIndex : 0;
      handleYearSelect(displayedYears[indexToSelect]);
    } else if (e.key === 'Escape') {
      setShowYearDropdown(false);
      setIsTypingYear(false);
      setHighlightedYearIndex(-1);
      setYearInput(date.getFullYear().toString());
    }
  };

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedMonthIndex >= 0 && monthDropdownRef.current) {
      const item = monthDropdownRef.current.children[highlightedMonthIndex] as HTMLElement;
      item?.scrollIntoView({ block: 'nearest' });
    }
  }, [highlightedMonthIndex]);

  useEffect(() => {
    if (highlightedYearIndex >= 0 && yearDropdownRef.current) {
      const item = yearDropdownRef.current.children[highlightedYearIndex] as HTMLElement;
      item?.scrollIntoView({ block: 'nearest' });
    }
  }, [highlightedYearIndex]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      // Month dropdown
      if (
        monthDropdownRef.current &&
        !monthDropdownRef.current.contains(e.target as Node) &&
        monthInputRef.current &&
        !monthInputRef.current.contains(e.target as Node)
      ) {
        setShowMonthDropdown(false);
        setIsTypingMonth(false);
        setMonthInput(MONTHS[date.getMonth()]);
      }
      // Year dropdown
      if (
        yearDropdownRef.current &&
        !yearDropdownRef.current.contains(e.target as Node) &&
        yearInputRef.current &&
        !yearInputRef.current.contains(e.target as Node)
      ) {
        setShowYearDropdown(false);
        setIsTypingYear(false);
        setYearInput(date.getFullYear().toString());
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [date]);

  return (
    <div className="flex items-center justify-between gap-2 px-2 pb-2">
      <button
        type="button"
        onClick={decreaseMonth}
        disabled={prevMonthButtonDisabled}
        className="p-1.5 rounded-lg hover:bg-surface-tertiary text-text-secondary hover:text-text-primary transition-colors disabled:opacity-30"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-2 flex-1 justify-center">
        {/* Month Input with Dropdown */}
        <div className="relative">
          <input
            ref={monthInputRef}
            type="text"
            value={monthInput}
            onChange={handleMonthInputChange}
            onFocus={handleMonthFocus}
            onKeyDown={handleMonthKeyDown}
            className="w-24 px-2 py-1 text-sm font-medium bg-surface border border-border rounded-md text-text-primary focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent cursor-pointer"
          />
          {showMonthDropdown && displayedMonths.length > 0 && (
            <div
              ref={monthDropdownRef}
              className="absolute top-full left-0 mt-1 w-32 bg-surface-secondary border border-border rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto"
            >
              {displayedMonths.map((month, idx) => {
                const monthIndex = MONTHS.indexOf(month);
                const isSelected = monthIndex === date.getMonth();
                const isHighlighted = idx === highlightedMonthIndex;
                return (
                  <button
                    key={month}
                    type="button"
                    onClick={() => handleMonthSelect(month, monthIndex)}
                    className={`w-full px-3 py-1.5 text-left text-sm transition-colors ${
                      isSelected
                        ? 'bg-accent text-white'
                        : isHighlighted
                        ? 'bg-surface-tertiary text-text-primary'
                        : 'text-text-primary hover:bg-surface-tertiary'
                    }`}
                  >
                    {month}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Year Input with Dropdown */}
        <div className="relative">
          <input
            ref={yearInputRef}
            type="text"
            value={yearInput}
            onChange={handleYearInputChange}
            onFocus={handleYearFocus}
            onKeyDown={handleYearKeyDown}
            className="w-16 px-2 py-1 text-sm font-medium bg-surface border border-border rounded-md text-text-primary text-center focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent cursor-pointer"
          />
          {showYearDropdown && displayedYears.length > 0 && (
            <div
              ref={yearDropdownRef}
              className="absolute top-full left-1/2 -translate-x-1/2 mt-1 w-20 bg-surface-secondary border border-border rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto"
            >
              {displayedYears.map((year, idx) => {
                const isSelected = year === date.getFullYear();
                const isHighlighted = idx === highlightedYearIndex;
                return (
                  <button
                    key={year}
                    type="button"
                    onClick={() => handleYearSelect(year)}
                    className={`w-full px-3 py-1.5 text-center text-sm transition-colors ${
                      isSelected
                        ? 'bg-accent text-white'
                        : isHighlighted
                        ? 'bg-surface-tertiary text-text-primary'
                        : 'text-text-primary hover:bg-surface-tertiary'
                    }`}
                  >
                    {year}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={increaseMonth}
        disabled={nextMonthButtonDisabled}
        className="p-1.5 rounded-lg hover:bg-surface-tertiary text-text-secondary hover:text-text-primary transition-colors disabled:opacity-30"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
};

// Wrapper function for renderCustomHeader prop
const renderCustomHeader = (props: {
  date: Date;
  changeYear: (year: number) => void;
  changeMonth: (month: number) => void;
  decreaseMonth: () => void;
  increaseMonth: () => void;
  prevMonthButtonDisabled: boolean;
  nextMonthButtonDisabled: boolean;
}) => <CustomHeaderContent {...props} />;

// Parse date string to Date object
const parseDate = (dateStr: string): Date => {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
};

// Format Date object to string
const formatDate = (date: Date | null): string => {
  if (!date) return '';
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export const Header: React.FC<HeaderProps> = ({
  dateRange,
  onDateRangeChange,
  includeDividends,
  onIncludeDividendsChange,
  onCompute,
  isComputing,
  progress,
}) => {
  return (
    <div className="px-4 lg:px-6 py-3 flex flex-wrap items-center justify-between gap-4">
      {/* Logo/Title */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-accent-muted rounded-lg">
          <TrendingUp className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Portfolio Optimizer</h1>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Date Range */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted font-medium">Fit:</span>
            <DatePicker
              selected={parseDate(dateRange.fit_start_date)}
              onChange={(date) => date && onDateRangeChange({ ...dateRange, fit_start_date: formatDate(date) })}
              onMonthChange={(date) => {
                // Auto-save when month/year changes via header navigation
                const current = parseDate(dateRange.fit_start_date);
                const newDate = new Date(date.getFullYear(), date.getMonth(), Math.min(current.getDate(), new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate()));
                onDateRangeChange({ ...dateRange, fit_start_date: formatDate(newDate) });
              }}
              customInput={<CustomDateInput title="Fit start date" />}
              dateFormat="yyyy-MM-dd"
              popperClassName="date-picker-popper"
              calendarClassName="custom-calendar"
              renderCustomHeader={renderCustomHeader}
            />
            <span className="text-text-muted">-</span>
            <DatePicker
              selected={parseDate(dateRange.fit_end_date)}
              onChange={(date) => date && onDateRangeChange({ ...dateRange, fit_end_date: formatDate(date) })}
              onMonthChange={(date) => {
                const current = parseDate(dateRange.fit_end_date);
                const newDate = new Date(date.getFullYear(), date.getMonth(), Math.min(current.getDate(), new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate()));
                onDateRangeChange({ ...dateRange, fit_end_date: formatDate(newDate) });
              }}
              customInput={<CustomDateInput title="Fit end date" />}
              dateFormat="yyyy-MM-dd"
              popperClassName="date-picker-popper"
              calendarClassName="custom-calendar"
              renderCustomHeader={renderCustomHeader}
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted font-medium">Test:</span>
            <DatePicker
              selected={parseDate(dateRange.test_end_date)}
              onChange={(date) => date && onDateRangeChange({ ...dateRange, test_end_date: formatDate(date) })}
              onMonthChange={(date) => {
                const current = parseDate(dateRange.test_end_date);
                const newDate = new Date(date.getFullYear(), date.getMonth(), Math.min(current.getDate(), new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate()));
                onDateRangeChange({ ...dateRange, test_end_date: formatDate(newDate) });
              }}
              customInput={<CustomDateInput title="Test end date" />}
              dateFormat="yyyy-MM-dd"
              popperClassName="date-picker-popper"
              calendarClassName="custom-calendar"
              renderCustomHeader={renderCustomHeader}
            />
          </div>
        </div>

        {/* Dividends Toggle */}
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={includeDividends}
            onChange={(e) => onIncludeDividendsChange(e.target.checked)}
            className="w-4 h-4 rounded border-border text-accent focus:ring-accent"
          />
          <DollarSign className="w-4 h-4 text-text-muted" />
          <span className="text-sm text-text-secondary">Dividends</span>
        </label>

        {/* Compute Button */}
        <button
          onClick={onCompute}
          disabled={isComputing}
          className="btn-primary"
        >
          {isComputing ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>{progress?.message || 'Computing...'}</span>
              {progress && (
                <span className="text-white/70">
                  ({progress.step}/{progress.total_steps})
                </span>
              )}
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              <span>Compute</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
