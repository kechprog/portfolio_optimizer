// Allocator types
export type AllocatorType = 'manual' | 'max_sharpe' | 'min_volatility';

export interface ManualAllocatorConfig {
  name: string;
  allocations: Record<string, number>;
}

export interface MPTAllocatorConfig {
  name: string;
  instruments: string[];
  allow_shorting: boolean;
  use_adj_close: boolean;
  update_enabled: boolean;
  update_interval_value?: number;
  update_interval_unit?: 'days' | 'weeks' | 'months';
}

export type AllocatorConfig = ManualAllocatorConfig | MPTAllocatorConfig;

export interface Allocator {
  id: string;
  type: AllocatorType;
  config: AllocatorConfig;
  enabled: boolean;
}

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
