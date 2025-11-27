import { useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketService } from '../services';
import { ConnectionStatus, ServerMessage } from '../types/websocket';
import { AllocatorType, AllocatorConfig, DateRange } from '../types';

interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  token?: string;
}

interface DashboardSettingsUpdate {
  fit_start_date?: string;
  fit_end_date?: string;
  test_end_date?: string;
  include_dividends?: boolean;
}

interface UseWebSocketReturn {
  // State
  status: ConnectionStatus;
  error: string | null;

  // Actions
  connect: () => void;
  disconnect: () => void;
  createAllocator: (type: AllocatorType, config: AllocatorConfig) => void;
  updateAllocator: (id: string, config: AllocatorConfig) => void;
  deleteAllocator: (id: string) => void;
  listAllocators: () => void;
  compute: (allocatorId: string, dateRange: DateRange, includeDividends: boolean) => void;
  updateDashboardSettings: (settings: DashboardSettingsUpdate) => void;

  // Event registration
  setMessageHandler: (handler: (message: ServerMessage) => void) => void;
}

// Dynamically determine WebSocket URL based on current host
// Uses wss:// for https, ws:// for http
// In development, use VITE_WS_URL env var if set, otherwise use backend port 8000
const getDefaultWsUrl = (): string => {
  if (typeof window === 'undefined') return 'ws://localhost:8000/ws';

  // Check for explicit WebSocket URL (useful for development)
  const envWsUrl = import.meta.env.VITE_WS_URL;
  if (envWsUrl) return envWsUrl;

  // In development (Vite dev server), connect to backend on port 8000
  if (import.meta.env.DEV) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.hostname}:8000/ws`;
  }

  // In production, use same host (assumes backend serves frontend)
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws`;
};

const DEFAULT_URL = getDefaultWsUrl();

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const { url = DEFAULT_URL, autoConnect = true, token } = options;

  // State
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);

  // Refs
  const wsServiceRef = useRef<WebSocketService | null>(null);
  const messageHandlerRef = useRef<((message: ServerMessage) => void) | null>(null);
  const messageQueueRef = useRef<ServerMessage[]>([]);

  // Initialize WebSocketService
  useEffect(() => {
    wsServiceRef.current = new WebSocketService({
      url,
      token,
      onStatusChange: (newStatus) => {
        setStatus(newStatus);
        if (newStatus === 'connected') {
          setError(null);
        }
      },
      onMessage: (message: ServerMessage) => {
        // Validate message structure before accessing properties
        if (typeof message !== 'object' || message === null || typeof message.type !== 'string') {
          console.error('Invalid message received:', message);
          return;
        }

        // Handle error messages
        if (message.type === 'error') {
          setError(message.message);
        }

        // Call the user-provided message handler if set, otherwise queue the message
        if (messageHandlerRef.current) {
          messageHandlerRef.current(message);
        } else {
          // Queue messages received before handler is registered
          messageQueueRef.current.push(message);
        }
      },
      onError: (errorEvent) => {
        const errorMessage = errorEvent instanceof Error
          ? errorEvent.message
          : 'WebSocket connection error';
        setError(errorMessage);
      },
    });

    // Auto-connect if enabled and token is available (or autoConnect for unauthenticated mode)
    if (autoConnect && (token || token === undefined)) {
      wsServiceRef.current.connect();
    }

    // Cleanup on unmount or when dependencies change
    return () => {
      if (wsServiceRef.current) {
        wsServiceRef.current.disconnect();
        wsServiceRef.current = null;
      }
      // Don't clear messageHandlerRef - it's managed by the calling component
      // and should persist across reconnections
      messageQueueRef.current = [];
    };
  }, [url, autoConnect, token]);

  // Connection methods
  const connect = useCallback(() => {
    wsServiceRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    wsServiceRef.current?.disconnect();
  }, []);

  // Message handler registration
  const setMessageHandler = useCallback((handler: (message: ServerMessage) => void) => {
    messageHandlerRef.current = handler;

    // Process any queued messages that arrived before the handler was set
    if (messageQueueRef.current.length > 0) {
      const queuedMessages = [...messageQueueRef.current];
      messageQueueRef.current = [];
      queuedMessages.forEach(message => handler(message));
    }
  }, []);

  // Allocator management methods
  const createAllocator = useCallback((type: AllocatorType, config: AllocatorConfig) => {
    wsServiceRef.current?.send({
      type: 'create_allocator',
      allocator_type: type,
      config,
    });
  }, []);

  const updateAllocator = useCallback((id: string, config: AllocatorConfig) => {
    wsServiceRef.current?.send({
      type: 'update_allocator',
      id,
      config,
    });
  }, []);

  const deleteAllocator = useCallback((id: string) => {
    wsServiceRef.current?.send({
      type: 'delete_allocator',
      id,
    });
  }, []);

  const listAllocators = useCallback(() => {
    wsServiceRef.current?.send({
      type: 'list_allocators',
    });
  }, []);

  // Computation method
  const compute = useCallback((
    allocatorId: string,
    dateRange: DateRange,
    includeDividends: boolean
  ) => {
    wsServiceRef.current?.send({
      type: 'compute',
      allocator_id: allocatorId,
      fit_start_date: dateRange.fit_start_date,
      fit_end_date: dateRange.fit_end_date,
      test_end_date: dateRange.test_end_date,
      include_dividends: includeDividends,
    });
  }, []);

  // Dashboard settings update method
  const updateDashboardSettings = useCallback((settings: DashboardSettingsUpdate) => {
    wsServiceRef.current?.send({
      type: 'update_dashboard_settings',
      ...settings,
    });
  }, []);

  return {
    // State
    status,
    error,

    // Actions
    connect,
    disconnect,
    createAllocator,
    updateAllocator,
    deleteAllocator,
    listAllocators,
    compute,
    updateDashboardSettings,

    // Event registration
    setMessageHandler,
  };
}
