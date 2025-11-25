import { Allocator, AllocatorResult, DateRange, ManualAllocator, MaxSharpeAllocator, MinVolatilityAllocator } from '../types';

// Generate dates for performance data
function generateDates(startDate: string, endDate: string): string[] {
  const dates: string[] = [];
  const current = new Date(startDate);
  const end = new Date(endDate);

  while (current <= end) {
    // Skip weekends
    if (current.getDay() !== 0 && current.getDay() !== 6) {
      dates.push(current.toISOString().split('T')[0]);
    }
    current.setDate(current.getDate() + 1);
  }
  return dates;
}

// Generate realistic cumulative returns with some randomness
function generateReturns(dates: string[], volatility: number, trend: number): number[] {
  const returns: number[] = [0];
  for (let i = 1; i < dates.length; i++) {
    const dailyReturn = (Math.random() - 0.5) * volatility + trend;
    returns.push(returns[i - 1] + dailyReturn);
  }
  return returns;
}

// Mock allocators with proper types
const manualAllocator: ManualAllocator = {
  id: 'alloc-1',
  type: 'manual',
  config: {
    name: 'Conservative Mix',
    allocations: { 'AAPL': 0.3, 'MSFT': 0.3, 'GOOG': 0.2, 'BND': 0.2 },
  },
  enabled: true,
};

const maxSharpeAllocator: MaxSharpeAllocator = {
  id: 'alloc-2',
  type: 'max_sharpe',
  config: {
    name: 'Max Sharpe Portfolio',
    instruments: ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'NVDA'],
    allow_shorting: false,
    use_adj_close: true,
  },
  enabled: true,
};

const minVolatilityAllocator: MinVolatilityAllocator = {
  id: 'alloc-3',
  type: 'min_volatility',
  config: {
    name: 'Low Volatility',
    instruments: ['AAPL', 'MSFT', 'JNJ', 'PG', 'KO'],
    allow_shorting: false,
    use_adj_close: true,
    update_interval: { value: 1, unit: 'months' },
    target_return: null,
  },
  enabled: false,
};

export const mockAllocators: Allocator[] = [
  manualAllocator,
  maxSharpeAllocator,
  minVolatilityAllocator,
];

// Default date range
export const defaultDateRange: DateRange = {
  fit_start_date: '2023-01-01',
  fit_end_date: '2023-12-31',
  test_end_date: '2024-06-01',
};

// Generate mock results
const testDates = generateDates('2024-01-01', '2024-06-01');

export const mockResults: Record<string, AllocatorResult> = {
  'alloc-1': {
    allocator_id: 'alloc-1',
    segments: [
      {
        start_date: '2023-01-01',
        end_date: '2024-06-01',
        weights: { 'AAPL': 0.30, 'MSFT': 0.30, 'GOOG': 0.20, 'BND': 0.20 },
      },
    ],
    performance: {
      dates: testDates,
      cumulative_returns: generateReturns(testDates, 1.5, 0.08),
    },
  },
  'alloc-2': {
    allocator_id: 'alloc-2',
    segments: [
      {
        start_date: '2024-01-01',
        end_date: '2024-01-15',
        weights: { 'AAPL': 0.35, 'MSFT': 0.28, 'GOOG': 0.15, 'AMZN': 0.12, 'NVDA': 0.10 },
      },
      {
        start_date: '2024-01-15',
        end_date: '2024-02-01',
        weights: { 'AAPL': 0.30, 'MSFT': 0.32, 'GOOG': 0.18, 'AMZN': 0.10, 'NVDA': 0.10 },
      },
      {
        start_date: '2024-02-01',
        end_date: '2024-02-15',
        weights: { 'AAPL': 0.28, 'MSFT': 0.30, 'GOOG': 0.20, 'AMZN': 0.12, 'NVDA': 0.10 },
      },
      {
        start_date: '2024-02-15',
        end_date: '2024-03-01',
        weights: { 'AAPL': 0.32, 'MSFT': 0.25, 'GOOG': 0.18, 'AMZN': 0.15, 'NVDA': 0.10 },
      },
      {
        start_date: '2024-03-01',
        end_date: '2024-03-15',
        weights: { 'AAPL': 0.25, 'MSFT': 0.30, 'GOOG': 0.22, 'AMZN': 0.13, 'NVDA': 0.10 },
      },
      {
        start_date: '2024-03-15',
        end_date: '2024-04-01',
        weights: { 'AAPL': 0.28, 'MSFT': 0.28, 'GOOG': 0.20, 'AMZN': 0.14, 'NVDA': 0.10 },
      },
      {
        start_date: '2024-04-01',
        end_date: '2024-04-15',
        weights: { 'AAPL': 0.30, 'MSFT': 0.26, 'GOOG': 0.19, 'AMZN': 0.15, 'NVDA': 0.10 },
      },
      {
        start_date: '2024-04-15',
        end_date: '2024-05-01',
        weights: { 'AAPL': 0.33, 'MSFT': 0.25, 'GOOG': 0.17, 'AMZN': 0.12, 'NVDA': 0.13 },
      },
      {
        start_date: '2024-05-01',
        end_date: '2024-05-15',
        weights: { 'AAPL': 0.29, 'MSFT': 0.27, 'GOOG': 0.21, 'AMZN': 0.11, 'NVDA': 0.12 },
      },
      {
        start_date: '2024-05-15',
        end_date: '2024-06-01',
        weights: { 'AAPL': 0.31, 'MSFT': 0.26, 'GOOG': 0.18, 'AMZN': 0.13, 'NVDA': 0.12 },
      },
    ],
    performance: {
      dates: testDates,
      cumulative_returns: generateReturns(testDates, 2.0, 0.12),
    },
  },
  'alloc-3': {
    allocator_id: 'alloc-3',
    segments: [
      {
        start_date: '2023-01-01',
        end_date: '2024-03-01',
        weights: { 'AAPL': 0.25, 'MSFT': 0.25, 'JNJ': 0.20, 'PG': 0.15, 'KO': 0.15 },
      },
      {
        start_date: '2024-03-01',
        end_date: '2024-06-01',
        weights: { 'AAPL': 0.28, 'MSFT': 0.22, 'JNJ': 0.22, 'PG': 0.14, 'KO': 0.14 },
      },
    ],
    performance: {
      dates: testDates,
      cumulative_returns: generateReturns(testDates, 1.0, 0.06),
    },
  },
};

// Chart colors for allocators
export const CHART_COLORS = [
  '#8884d8', // Purple
  '#82ca9d', // Green
  '#ffc658', // Yellow
  '#ff7300', // Orange
  '#00C49F', // Teal
  '#FFBB28', // Gold
  '#FF8042', // Coral
  '#0088FE', // Blue
];

// Get allocator name from config
export function getAllocatorName(allocator: Allocator): string {
  return allocator.config.name;
}

// Get allocator type display name
export function getAllocatorTypeDisplay(type: string): string {
  switch (type) {
    case 'manual':
      return 'Manual Allocator';
    case 'max_sharpe':
      return 'Max Sharpe';
    case 'min_volatility':
      return 'Min Volatility';
    default:
      return type;
  }
}
