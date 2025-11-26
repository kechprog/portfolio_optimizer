import { useState, useCallback, useEffect } from 'react';
import { MainLayout, Panel, Header } from './components/layout';
import { PerformanceChart } from './components/charts';
import { AllocatorGrid, PortfolioInfo } from './components/allocators';
import { ManualAllocatorModal, MPTAllocatorModal, ConfirmModal } from './components/modals';
import { useTheme } from './hooks';
import { Allocator, AllocatorType, AllocatorResult, DateRange, ManualAllocatorConfig, MaxSharpeAllocatorConfig, MinVolatilityAllocatorConfig } from './types';
import { mockAllocators, mockResults, defaultDateRange, getAllocatorName } from './mock/data';

function App() {
  // Theme
  useTheme();

  // Core state
  const [allocators, setAllocators] = useState<Allocator[]>(mockAllocators);
  const [results, setResults] = useState<Record<string, AllocatorResult>>(mockResults);
  const [dateRange, setDateRange] = useState<DateRange>(defaultDateRange);
  const [includeDividends, setIncludeDividends] = useState(true);
  const [selectedAllocatorId, setSelectedAllocatorId] = useState<string | null>(
    mockAllocators.length > 0 ? mockAllocators[0].id : null
  );
  const [isComputing, setIsComputing] = useState(false);
  const [computingProgress, setComputingProgress] = useState<{
    allocator_id: string;
    message: string;
    step: number;
    total_steps: number;
  } | null>(null);

  // Modal state
  const [editingAllocator, setEditingAllocator] = useState<Allocator | null>(null);
  const [creatingAllocatorType, setCreatingAllocatorType] = useState<AllocatorType | null>(null);
  const [deletingAllocator, setDeletingAllocator] = useState<Allocator | null>(null);

  // Generate unique ID
  const generateId = () => `alloc-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

  // Allocator CRUD operations
  const handleToggleAllocator = useCallback((id: string) => {
    setAllocators(prev => prev.map(a =>
      a.id === id ? { ...a, enabled: !a.enabled } : a
    ));
  }, []);

  const handleConfigureAllocator = useCallback((id: string) => {
    const allocator = allocators.find(a => a.id === id);
    if (allocator) {
      setEditingAllocator(allocator);
    }
  }, [allocators]);

  const handleDuplicateAllocator = useCallback((id: string) => {
    const allocator = allocators.find(a => a.id === id);
    if (!allocator) return;

    const newId = generateId();
    const newName = `${getAllocatorName(allocator)} (copy)`;

    let newAllocator: Allocator;
    switch (allocator.type) {
      case 'manual':
        newAllocator = {
          id: newId,
          type: 'manual',
          config: { ...allocator.config, name: newName },
          enabled: false,
        };
        break;
      case 'max_sharpe':
        newAllocator = {
          id: newId,
          type: 'max_sharpe',
          config: { ...allocator.config, name: newName },
          enabled: false,
        };
        break;
      case 'min_volatility':
        newAllocator = {
          id: newId,
          type: 'min_volatility',
          config: { ...allocator.config, name: newName },
          enabled: false,
        };
        break;
    }
    setAllocators(prev => [...prev, newAllocator]);
  }, [allocators]);

  const handleDeleteAllocator = useCallback((id: string) => {
    const allocator = allocators.find(a => a.id === id);
    if (allocator) {
      setDeletingAllocator(allocator);
    }
  }, [allocators]);

  const confirmDeleteAllocator = useCallback(() => {
    if (deletingAllocator) {
      setAllocators(prev => prev.filter(a => a.id !== deletingAllocator.id));
      setResults(prev => {
        const newResults = { ...prev };
        delete newResults[deletingAllocator.id];
        return newResults;
      });
      if (selectedAllocatorId === deletingAllocator.id) {
        setSelectedAllocatorId(allocators.find(a => a.id !== deletingAllocator.id)?.id || null);
      }
      setDeletingAllocator(null);
    }
  }, [deletingAllocator, selectedAllocatorId, allocators]);

  const handleCreateAllocator = useCallback((type: AllocatorType) => {
    setCreatingAllocatorType(type);
  }, []);

  // Save allocator (create or update)
  const handleSaveManualAllocator = useCallback((config: ManualAllocatorConfig) => {
    if (editingAllocator && editingAllocator.type === 'manual') {
      const updatedAllocator: Allocator = {
        id: editingAllocator.id,
        type: 'manual',
        config,
        enabled: editingAllocator.enabled,
      };
      setAllocators(prev => prev.map(a =>
        a.id === editingAllocator.id ? updatedAllocator : a
      ));
      setEditingAllocator(null);
    } else if (creatingAllocatorType === 'manual') {
      const newAllocator: Allocator = {
        id: generateId(),
        type: 'manual',
        config,
        enabled: false,
      };
      setAllocators(prev => [...prev, newAllocator]);
      setCreatingAllocatorType(null);
    }
  }, [editingAllocator, creatingAllocatorType]);

  const handleSaveMPTAllocator = useCallback((config: MaxSharpeAllocatorConfig | MinVolatilityAllocatorConfig) => {
    if (editingAllocator) {
      let updatedAllocator: Allocator;
      if (editingAllocator.type === 'max_sharpe') {
        updatedAllocator = {
          id: editingAllocator.id,
          type: 'max_sharpe',
          config: config as MaxSharpeAllocatorConfig,
          enabled: editingAllocator.enabled,
        };
      } else if (editingAllocator.type === 'min_volatility') {
        updatedAllocator = {
          id: editingAllocator.id,
          type: 'min_volatility',
          config: config as MinVolatilityAllocatorConfig,
          enabled: editingAllocator.enabled,
        };
      } else {
        return;
      }
      setAllocators(prev => prev.map(a =>
        a.id === editingAllocator.id ? updatedAllocator : a
      ));
      setEditingAllocator(null);
    } else if (creatingAllocatorType === 'max_sharpe') {
      const newAllocator: Allocator = {
        id: generateId(),
        type: 'max_sharpe',
        config: config as MaxSharpeAllocatorConfig,
        enabled: false,
      };
      setAllocators(prev => [...prev, newAllocator]);
      setCreatingAllocatorType(null);
    } else if (creatingAllocatorType === 'min_volatility') {
      const newAllocator: Allocator = {
        id: generateId(),
        type: 'min_volatility',
        config: config as MinVolatilityAllocatorConfig,
        enabled: false,
      };
      setAllocators(prev => [...prev, newAllocator]);
      setCreatingAllocatorType(null);
    }
  }, [editingAllocator, creatingAllocatorType]);

  // Compute portfolios (mock for now)
  const handleCompute = useCallback(async () => {
    setIsComputing(true);
    const enabledAllocators = allocators.filter(a => a.enabled);

    for (let i = 0; i < enabledAllocators.length; i++) {
      const allocator = enabledAllocators[i];
      setComputingProgress({
        allocator_id: allocator.id,
        message: `Computing ${getAllocatorName(allocator)}...`,
        step: i + 1,
        total_steps: enabledAllocators.length,
      });

      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setComputingProgress(null);
    setIsComputing(false);
  }, [allocators]);

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
    const enabledAllocators = allocators.filter(a => a.enabled);
    if (enabledAllocators.length > 0 && !enabledAllocators.find(a => a.id === selectedAllocatorId)) {
      setSelectedAllocatorId(enabledAllocators[0].id);
    }
  }, [allocators, selectedAllocatorId]);

  return (
    <>
      <MainLayout
        header={
          <Header
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            includeDividends={includeDividends}
            onIncludeDividendsChange={setIncludeDividends}
            onCompute={handleCompute}
            isComputing={isComputing}
            progress={computingProgress}
          />
        }
        chart={
          <Panel showFullscreen>
            <PerformanceChart
              results={results}
              allocators={allocators}
            />
          </Panel>
        }
        allocators={
          <AllocatorGrid
            allocators={allocators}
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
              allocators={allocators}
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
}

export default App;
