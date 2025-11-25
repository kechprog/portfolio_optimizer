// Allocator types
export type AllocatorType = 'manual' | 'max_sharpe' | 'min_volatility';

// Shared types
export interface UpdateInterval {
  value: number;
  unit: 'days' | 'weeks' | 'months';
}

// Manual Allocator Config
export interface ManualAllocatorConfig {
  name: string;
  allocations: Record<string, number>;
}

// Max Sharpe Allocator Config
export interface MaxSharpeAllocatorConfig {
  name: string;
  instruments: string[];
  allow_shorting: boolean;
  use_adj_close: boolean;
  update_interval?: UpdateInterval | null;
}

// Min Volatility Allocator Config
export interface MinVolatilityAllocatorConfig {
  name: string;
  instruments: string[];
  allow_shorting: boolean;
  use_adj_close: boolean;
  update_interval?: UpdateInterval | null;
  // Target annual return (e.g., 0.1 for 10%) - null/undefined means pure min volatility
  target_return?: number | null;
}

export type AllocatorConfig = ManualAllocatorConfig | MaxSharpeAllocatorConfig | MinVolatilityAllocatorConfig;

// Typed allocator interfaces
export interface ManualAllocator {
  id: string;
  type: 'manual';
  config: ManualAllocatorConfig;
  enabled: boolean;
}

export interface MaxSharpeAllocator {
  id: string;
  type: 'max_sharpe';
  config: MaxSharpeAllocatorConfig;
  enabled: boolean;
}

export interface MinVolatilityAllocator {
  id: string;
  type: 'min_volatility';
  config: MinVolatilityAllocatorConfig;
  enabled: boolean;
}

export type Allocator = ManualAllocator | MaxSharpeAllocator | MinVolatilityAllocator;

// Portfolio segment
export interface PortfolioSegment {
  start_date: string;
  end_date: string;
  weights: Record<string, number>;
}

// Performance data
export interface PerformanceData {
  dates: string[];
  cumulative_returns: number[];
}

// Allocator result (after computation)
export interface AllocatorResult {
  allocator_id: string;
  segments: PortfolioSegment[];
  performance: PerformanceData;
}

// UI state
export interface DateRange {
  fit_start_date: string;
  fit_end_date: string;
  test_end_date: string;
}

export interface AppState {
  allocators: Allocator[];
  results: Record<string, AllocatorResult>;
  dateRange: DateRange;
  includeDividends: boolean;
  selectedAllocatorId: string | null;
  isComputing: boolean;
  computingProgress: {
    allocator_id: string;
    message: string;
    step: number;
    total_steps: number;
  } | null;
}

// Chart data point
export interface ChartDataPoint {
  date: string;
  [allocatorName: string]: string | number;
}
