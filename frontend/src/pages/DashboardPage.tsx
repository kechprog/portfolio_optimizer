import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { MainLayout, Panel, Header } from '../components/layout';
import { PerformanceChart } from '../components/charts';
import { AllocatorGrid, PortfolioInfo } from '../components/allocators';
import { ManualAllocatorModal, MPTAllocatorModal, ConfirmModal } from '../components/modals';
import { useTheme, useWebSocket } from '../hooks';
import {
  Allocator,
  AllocatorType,
  AllocatorResult,
  DateRange,
  ManualAllocatorConfig,
  MaxSharpeAllocatorConfig,
  MinVolatilityAllocatorConfig,
  ServerMessage,
  ConnectionStatus,
  ManualAllocator,
  MaxSharpeAllocator,
  MinVolatilityAllocator,
} from '../types';
import { defaultDateRange, getAllocatorName } from '../mock/data';

// Type guards for runtime type checking
function isManualAllocatorConfig(config: unknown): config is ManualAllocatorConfig {
  if (typeof config !== 'object' || config === null) return false;
  const c = config as Record<string, unknown>;
  return (
    typeof c.name === 'string' &&
    typeof c.allocations === 'object' &&
    c.allocations !== null
  );
}

function isMaxSharpeAllocatorConfig(config: unknown): config is MaxSharpeAllocatorConfig {
  if (typeof config !== 'object' || config === null) return false;
  const c = config as Record<string, unknown>;
  return (
    typeof c.name === 'string' &&
    Array.isArray(c.instruments) &&
    typeof c.allow_shorting === 'boolean' &&
    typeof c.use_adj_close === 'boolean'
  );
}

function isMinVolatilityAllocatorConfig(config: unknown): config is MinVolatilityAllocatorConfig {
  if (typeof config !== 'object' || config === null) return false;
  const c = config as Record<string, unknown>;
  return (
    typeof c.name === 'string' &&
    Array.isArray(c.instruments) &&
    typeof c.allow_shorting === 'boolean' &&
    typeof c.use_adj_close === 'boolean'
  );
}

export const DashboardPage: React.FC = () => {
  // Theme
  useTheme();

  // Auth0
  const { getAccessTokenSilently } = useAuth0();
  const [wsToken, setWsToken] = useState<string | undefined>();

  // Fetch token on mount
  useEffect(() => {
    const getToken = async () => {
      try {
        const token = await getAccessTokenSilently();
        setWsToken(token);
      } catch (error) {
        console.error('Failed to get access token:', error);
      }
    };
    getToken();
  }, [getAccessTokenSilently]);

  // WebSocket connection - only connect when we have a token
  const {
    status,
    error: wsError,
    createAllocator: wsCreateAllocator,
    updateAllocator: wsUpdateAllocator,
    deleteAllocator: wsDeleteAllocator,
    compute: wsCompute,
    setMessageHandler,
  } = useWebSocket({ token: wsToken, autoConnect: !!wsToken });

  // Core state - start empty, no mock data
  const [allocators, setAllocators] = useState<Allocator[]>([]);
  const [results, setResults] = useState<Record<string, AllocatorResult>>({});
  const [dateRange, setDateRange] = useState<DateRange>(defaultDateRange);
  const [includeDividends, setIncludeDividends] = useState(true);
  const [selectedAllocatorId, setSelectedAllocatorId] = useState<string | null>(null);
  const [isComputing, setIsComputing] = useState(false);
  const [computingProgress, setComputingProgress] = useState<{
    allocator_id: string;
    message: string;
    step: number;
    total_steps: number;
  } | null>(null);

  // Track pending computes to know when all are done
  const pendingComputesRef = useRef<Set<string>>(new Set());
  // Track timeout IDs for pending computes (5 minute timeout)
  const pendingTimeoutsRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Track enabled state locally (server doesn't track this)
  const [enabledIds, setEnabledIds] = useState<Set<string>>(new Set());

  // Ref to track latest allocatorsWithEnabled to avoid stale closures
  const allocatorsRef = useRef<Allocator[]>([]);

  // Modal state
  const [editingAllocator, setEditingAllocator] = useState<Allocator | null>(null);
  const [creatingAllocatorType, setCreatingAllocatorType] = useState<AllocatorType | null>(null);
  const [deletingAllocator, setDeletingAllocator] = useState<Allocator | null>(null);

  // Helper to create typed allocator from server data
  const createTypedAllocator = (
    id: string,
    allocatorType: string,
    config: Record<string, unknown>
  ): Allocator => {
    switch (allocatorType) {
      case 'manual':
        if (!isManualAllocatorConfig(config)) {
          throw new Error('Invalid manual allocator config received from server');
        }
        return {
          id,
          type: 'manual',
          config,
          enabled: false,
        };
      case 'max_sharpe':
        if (!isMaxSharpeAllocatorConfig(config)) {
          throw new Error('Invalid max sharpe allocator config received from server');
        }
        return {
          id,
          type: 'max_sharpe',
          config,
          enabled: false,
        };
      case 'min_volatility':
        if (!isMinVolatilityAllocatorConfig(config)) {
          throw new Error('Invalid min volatility allocator config received from server');
        }
        return {
          id,
          type: 'min_volatility',
          config,
          enabled: false,
        };
      default:
        throw new Error(`Unknown allocator type: ${allocatorType}`);
    }
  };

  // Helper to create typed allocator from server data (using useCallback to avoid stale closures)
  const createTypedAllocatorCallback = useCallback((
    id: string,
    allocatorType: string,
    config: Record<string, unknown>
  ): Allocator => {
    switch (allocatorType) {
      case 'manual':
        if (!isManualAllocatorConfig(config)) {
          throw new Error('Invalid manual allocator config received from server');
        }
        return {
          id,
          type: 'manual',
          config,
          enabled: false,
        };
      case 'max_sharpe':
        if (!isMaxSharpeAllocatorConfig(config)) {
          throw new Error('Invalid max sharpe allocator config received from server');
        }
        return {
          id,
          type: 'max_sharpe',
          config,
          enabled: false,
        };
      case 'min_volatility':
        if (!isMinVolatilityAllocatorConfig(config)) {
          throw new Error('Invalid min volatility allocator config received from server');
        }
        return {
          id,
          type: 'min_volatility',
          config,
          enabled: false,
        };
      default:
        throw new Error(`Unknown allocator type: ${allocatorType}`);
    }
  }, []);

  // Cleanup helper for pending computes
  const cleanupPendingCompute = useCallback((allocatorId: string) => {
    pendingComputesRef.current.delete(allocatorId);
    const timeout = pendingTimeoutsRef.current.get(allocatorId);
    if (timeout) {
      clearTimeout(timeout);
      pendingTimeoutsRef.current.delete(allocatorId);
    }
    if (pendingComputesRef.current.size === 0) {
      setIsComputing(false);
      setComputingProgress(null);
    }
  }, []);

  // Set up WebSocket message handler
  useEffect(() => {
    let isActive = true;

    setMessageHandler((message: ServerMessage) => {
      if (!isActive) return; // Prevent processing after unmount

      switch (message.type) {
        case 'allocator_created': {
          // Add the new allocator to state with server-assigned ID
          const newAllocator = createTypedAllocatorCallback(
            message.id,
            message.allocator_type,
            message.config
          );
          setAllocators(prev => [...prev, newAllocator]);
          break;
        }

        case 'allocator_updated': {
          // Update allocator config in state
          setAllocators(prev => prev.map(a => {
            if (a.id !== message.id) return a;
            // Preserve the type when updating config - use type guards for safe narrowing
            switch (a.type) {
              case 'manual':
                if (!isManualAllocatorConfig(message.config)) {
                  console.error('Invalid manual allocator config received from server');
                  return a;
                }
                return { ...a, config: message.config };
              case 'max_sharpe':
                if (!isMaxSharpeAllocatorConfig(message.config)) {
                  console.error('Invalid max sharpe allocator config received from server');
                  return a;
                }
                return { ...a, config: message.config };
              case 'min_volatility':
                if (!isMinVolatilityAllocatorConfig(message.config)) {
                  console.error('Invalid min volatility allocator config received from server');
                  return a;
                }
                return { ...a, config: message.config };
              default:
                console.warn(`Unknown allocator type received: ${(a as { type: string }).type}`);
                return a;
            }
          }));
          setEditingAllocator(null);
          break;
        }

        case 'allocators_list': {
          // Replace allocators state with server's list
          const serverAllocators = message.allocators.map((allocatorData) =>
            createTypedAllocatorCallback(
              allocatorData.id,
              allocatorData.type,
              allocatorData.config
            )
          );
          setAllocators(serverAllocators);
          break;
        }

        case 'allocator_deleted': {
          // Remove allocator from state
          setAllocators(prev => prev.filter(a => a.id !== message.id));
          setResults(prev => {
            const newResults = { ...prev };
            delete newResults[message.id];
            return newResults;
          });
          setEnabledIds(prev => {
            const next = new Set(prev);
            next.delete(message.id);
            return next;
          });
          break;
        }

        case 'progress': {
          setComputingProgress({
            allocator_id: message.allocator_id,
            message: message.message,
            step: message.step,
            total_steps: message.total_steps,
          });
          break;
        }

        case 'result': {
          // Store the result
          const result: AllocatorResult = {
            allocator_id: message.allocator_id,
            segments: message.segments,
            performance: message.performance,
          };
          setResults(prev => ({
            ...prev,
            [message.allocator_id]: result,
          }));

          // Track completion and clear timeout
          cleanupPendingCompute(message.allocator_id);
          break;
        }

        case 'error': {
          console.error('Server error:', message.message);
          // If error is for a compute, remove from pending and clear timeout
          if (message.allocator_id) {
            cleanupPendingCompute(message.allocator_id);
          }
          break;
        }
      }
    });

    // Cleanup function to prevent processing messages after unmount
    return () => {
      isActive = false;
      setMessageHandler(() => {});
    };
  }, [setMessageHandler, createTypedAllocatorCallback, cleanupPendingCompute]);

  // Cleanup pending computes on unmount
  useEffect(() => {
    return () => {
      // Clear all pending compute timeouts
      pendingTimeoutsRef.current.forEach(timeout => clearTimeout(timeout));
      pendingTimeoutsRef.current.clear();
      pendingComputesRef.current.clear();
    };
  }, []);

  // Merge enabled state into allocators for display (memoized to prevent unnecessary re-renders)
  const allocatorsWithEnabled = useMemo(() => allocators.map(a => ({
    ...a,
    enabled: enabledIds.has(a.id),
  })), [allocators, enabledIds]);

  // Update ref when allocatorsWithEnabled changes to avoid stale closures
  useEffect(() => {
    allocatorsRef.current = allocatorsWithEnabled;
  }, [allocatorsWithEnabled]);

  // Allocator CRUD operations
  const handleToggleAllocator = useCallback((id: string) => {
    setEnabledIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleConfigureAllocator = useCallback((id: string) => {
    const allocator = allocators.find(a => a.id === id);
    if (allocator) {
      setEditingAllocator({
        ...allocator,
        enabled: enabledIds.has(allocator.id),
      });
    }
  }, [allocators, enabledIds]);

  const handleDuplicateAllocator = useCallback((id: string) => {
    const allocator = allocators.find(a => a.id === id);
    if (!allocator) return;

    const newName = `${getAllocatorName({ ...allocator, enabled: false })} (copy)`;
    const newConfig = { ...allocator.config, name: newName };

    // Send to server - allocator_created message will add it to state
    wsCreateAllocator(allocator.type, newConfig as Allocator['config']);
  }, [allocators, wsCreateAllocator]);

  const handleDeleteAllocator = useCallback((id: string) => {
    const allocator = allocators.find(a => a.id === id);
    if (allocator) {
      setDeletingAllocator({
        ...allocator,
        enabled: enabledIds.has(allocator.id),
      });
    }
  }, [allocators, enabledIds]);

  const confirmDeleteAllocator = useCallback(() => {
    if (deletingAllocator) {
      const deletedId = deletingAllocator.id;

      // Send to server - allocator_deleted message will remove from state
      wsDeleteAllocator(deletedId);

      // Use functional form to get fresh state when checking if we need to change selection
      if (selectedAllocatorId === deletedId) {
        setSelectedAllocatorId(prev => {
          // Get fresh allocators from state at time of execution
          setAllocators(currentAllocators => {
            const remaining = currentAllocators.find(a => a.id !== deletedId);
            // Use setTimeout to update selection after state has settled
            setTimeout(() => setSelectedAllocatorId(remaining?.id || null), 0);
            return currentAllocators;
          });
          return prev;
        });
      }
      setDeletingAllocator(null);
    }
  }, [deletingAllocator, selectedAllocatorId, wsDeleteAllocator]);

  const handleCreateAllocator = useCallback((type: AllocatorType) => {
    setCreatingAllocatorType(type);
  }, []);

  // Save allocator (create or update)
  const handleSaveManualAllocator = useCallback((config: ManualAllocatorConfig) => {
    if (editingAllocator && editingAllocator.type === 'manual') {
      // Update existing - send to server
      wsUpdateAllocator(editingAllocator.id, config);
    } else if (creatingAllocatorType === 'manual') {
      // Create new - send to server
      wsCreateAllocator('manual', config);
      setCreatingAllocatorType(null);
    }
  }, [editingAllocator, creatingAllocatorType, wsUpdateAllocator, wsCreateAllocator]);

  const handleSaveMPTAllocator = useCallback((config: MaxSharpeAllocatorConfig | MinVolatilityAllocatorConfig) => {
    if (editingAllocator) {
      // Update existing - send to server
      wsUpdateAllocator(editingAllocator.id, config);
    } else if (creatingAllocatorType === 'max_sharpe') {
      wsCreateAllocator('max_sharpe', config);
      setCreatingAllocatorType(null);
    } else if (creatingAllocatorType === 'min_volatility') {
      wsCreateAllocator('min_volatility', config);
      setCreatingAllocatorType(null);
    }
  }, [editingAllocator, creatingAllocatorType, wsUpdateAllocator, wsCreateAllocator]);

  // Compute portfolios via WebSocket
  const handleCompute = useCallback(async () => {
    // Use ref to get latest allocators and avoid stale closure
    const enabledAllocators = allocatorsRef.current.filter(a => a.enabled);
    if (enabledAllocators.length === 0) return;
    if (status !== 'connected') {
      console.error('WebSocket not connected');
      return;
    }

    setIsComputing(true);
    pendingComputesRef.current.clear();
    // Clear any existing timeouts
    pendingTimeoutsRef.current.forEach(timeout => clearTimeout(timeout));
    pendingTimeoutsRef.current.clear();

    // Clear previous results for enabled allocators
    setResults(prev => {
      const newResults = { ...prev };
      enabledAllocators.forEach(a => delete newResults[a.id]);
      return newResults;
    });

    // Send compute request for each enabled allocator
    for (const allocator of enabledAllocators) {
      pendingComputesRef.current.add(allocator.id);

      // Set up 5-minute timeout for this compute
      const timeoutId = setTimeout(() => {
        console.warn(`Compute timeout for allocator ${allocator.id} after 5 minutes`);
        cleanupPendingCompute(allocator.id);
      }, 5 * 60 * 1000); // 5 minutes

      pendingTimeoutsRef.current.set(allocator.id, timeoutId);
      wsCompute(allocator.id, dateRange, includeDividends);
    }
  }, [dateRange, includeDividends, status, wsCompute, cleanupPendingCompute]);

  // Close modals
  const closeManualModal = () => {
    setEditingAllocator(null);
    setCreatingAllocatorType(null);
  };

  const closeMPTModal = () => {
    setEditingAllocator(null);
    setCreatingAllocatorType(null);
  };

  // Determine which modal to show
  const showManualModal =
    creatingAllocatorType === 'manual' ||
    (editingAllocator?.type === 'manual');

  const showMPTModal =
    creatingAllocatorType === 'max_sharpe' ||
    creatingAllocatorType === 'min_volatility' ||
    editingAllocator?.type === 'max_sharpe' ||
    editingAllocator?.type === 'min_volatility';

  const mptModalType = editingAllocator?.type === 'max_sharpe' || editingAllocator?.type === 'min_volatility'
    ? editingAllocator.type
    : (creatingAllocatorType as 'max_sharpe' | 'min_volatility');

  // Auto-select first enabled allocator
  useEffect(() => {
    const enabledAllocators = allocatorsWithEnabled.filter(a => a.enabled);
    if (enabledAllocators.length > 0 && !enabledAllocators.find(a => a.id === selectedAllocatorId)) {
      setSelectedAllocatorId(enabledAllocators[0].id);
    }
  }, [allocatorsWithEnabled, selectedAllocatorId]);

  // Connection status display
  const getStatusBanner = () => {
    if (status === 'connected') return null;

    const statusConfig: Record<Exclude<ConnectionStatus, 'connected'>, { bg: string; text: string; message: string }> = {
      connecting: { bg: 'bg-yellow-500', text: 'text-black', message: 'Connecting to server...' },
      reconnecting: { bg: 'bg-yellow-500', text: 'text-black', message: 'Connection lost. Reconnecting...' },
      disconnected: { bg: 'bg-gray-500', text: 'text-white', message: 'Disconnected from server' },
      error: { bg: 'bg-red-500', text: 'text-white', message: 'Connection failed. Please check if the backend is running.' },
    };

    const config = statusConfig[status];
    return (
      <div className={`${config.bg} ${config.text} text-center py-2 px-4 text-sm font-medium`}>
        {config.message}
        {wsError && <span className="ml-2">({wsError})</span>}
      </div>
    );
  };

  return (
    <>
      {/* Connection Status Banner */}
      {getStatusBanner()}

      <MainLayout
        header={
          <Header
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            includeDividends={includeDividends}
            onIncludeDividendsChange={setIncludeDividends}
            onCompute={handleCompute}
            isComputing={isComputing || status !== 'connected'}
            progress={computingProgress}
          />
        }
        chart={
          <Panel showFullscreen>
            <PerformanceChart
              results={results}
              allocators={allocatorsWithEnabled}
            />
          </Panel>
        }
        allocators={
          <AllocatorGrid
            allocators={allocatorsWithEnabled}
            onToggle={handleToggleAllocator}
            onConfigure={handleConfigureAllocator}
            onDuplicate={handleDuplicateAllocator}
            onDelete={handleDeleteAllocator}
            onCreate={handleCreateAllocator}
          />
        }
        portfolio={
          <Panel>
            <PortfolioInfo
              allocators={allocatorsWithEnabled}
              results={results}
              selectedAllocatorId={selectedAllocatorId}
              onSelectAllocator={setSelectedAllocatorId}
            />
          </Panel>
        }
      />

      {/* Manual Allocator Modal */}
      <ManualAllocatorModal
        isOpen={showManualModal}
        onClose={closeManualModal}
        allocator={editingAllocator?.type === 'manual' ? editingAllocator : null}
        onSave={handleSaveManualAllocator}
      />

      {/* MPT Allocator Modal */}
      <MPTAllocatorModal
        isOpen={showMPTModal}
        onClose={closeMPTModal}
        allocator={editingAllocator?.type === 'max_sharpe' || editingAllocator?.type === 'min_volatility' ? editingAllocator : null}
        allocatorType={mptModalType}
        onSave={handleSaveMPTAllocator}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={!!deletingAllocator}
        onClose={() => setDeletingAllocator(null)}
        onConfirm={confirmDeleteAllocator}
        title="Delete Allocator"
        message={`Are you sure you want to delete "${deletingAllocator ? getAllocatorName(deletingAllocator) : ''}"? This action cannot be undone.`}
        variant="danger"
        confirmText="Delete"
      />
    </>
  );
};
