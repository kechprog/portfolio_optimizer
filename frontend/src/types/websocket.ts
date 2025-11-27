// WebSocket message types for portfolio optimizer
// These types match the backend schemas defined in backend/schemas.py

// Connection status
export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'error';

// ============================================================================
// Client -> Server Messages
// ============================================================================

export interface CreateAllocatorMessage {
  type: 'create_allocator';
  allocator_type: string;
  config: Record<string, unknown>;
}

export interface UpdateAllocatorMessage {
  type: 'update_allocator';
  id: string;
  config: Record<string, unknown>;
}

export interface DeleteAllocatorMessage {
  type: 'delete_allocator';
  id: string;
}

export interface ListAllocatorsMessage {
  type: 'list_allocators';
}

export interface ComputeMessage {
  type: 'compute';
  allocator_id: string;
  fit_start_date: string;
  fit_end_date: string;
  test_end_date: string;
  include_dividends: boolean;
  current_allocator: number;  // 1-indexed
  total_allocators: number;
}

// Union type for all client messages
export type ClientMessage =
  | CreateAllocatorMessage
  | UpdateAllocatorMessage
  | DeleteAllocatorMessage
  | ListAllocatorsMessage
  | ComputeMessage;

// ============================================================================
// Server -> Client Messages
// ============================================================================

export interface AllocatorCreatedMessage {
  type: 'allocator_created';
  id: string;
  allocator_type: string;
  config: Record<string, unknown>;
}

export interface AllocatorUpdatedMessage {
  type: 'allocator_updated';
  id: string;
  config: Record<string, unknown>;
}

export interface AllocatorDeletedMessage {
  type: 'allocator_deleted';
  id: string;
}

export interface AllocatorsListMessage {
  type: 'allocators_list';
  allocators: Array<{
    id: string;
    type: string;  // Backend returns "type", not "allocator_type"
    config: Record<string, unknown>;
  }>;
}

export type ProgressPhase = 'fetching' | 'optimizing' | 'metrics' | 'complete' | 'cached';

export interface ProgressMessage {
  type: 'progress';
  allocator_id: string;
  allocator_name: string;  // Human-readable name for display
  phase: ProgressPhase;
  current: number;  // Which allocator (1-indexed)
  total: number;    // Total enabled allocators
  segment?: number;        // Current segment for periodic rebalancing
  total_segments?: number; // Total segments
}

export interface ResultMessage {
  type: 'result';
  allocator_id: string;
  segments: Array<{
    start_date: string;
    end_date: string;
    weights: Record<string, number>;
  }>;
  performance: {
    dates: string[];
    cumulative_returns: number[];
    stats?: {
      total_return: number;
      annualized_return: number;
      volatility: number;
      sharpe_ratio: number;
      max_drawdown: number;
    };
  };
}

export type ErrorCategory = 'validation' | 'network' | 'compute' | 'auth' | 'database' | 'system';
export type ErrorSeverity = 'error' | 'warning';

export interface ErrorMessage {
  type: 'error';
  message: string;
  code: string;
  category: ErrorCategory;
  severity: ErrorSeverity;
  allocator_id?: string;
  recoverable: boolean;
}

// Union type for all server messages
export type ServerMessage =
  | AllocatorCreatedMessage
  | AllocatorUpdatedMessage
  | AllocatorDeletedMessage
  | AllocatorsListMessage
  | ProgressMessage
  | ResultMessage
  | ErrorMessage;
