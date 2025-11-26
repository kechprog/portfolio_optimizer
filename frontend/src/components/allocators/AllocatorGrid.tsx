import React, { useState } from 'react';
import { Settings, Copy, Trash2, Plus, Target, TrendingUp, Shield } from 'lucide-react';
import { Allocator, AllocatorType } from '../../types';
import { getAllocatorName, getAllocatorTypeDisplay } from '../../mock/data';
import { CreateAllocatorModal } from '../modals/CreateAllocatorModal';

interface AllocatorGridProps {
  allocators: Allocator[];
  onToggle: (id: string) => void;
  onConfigure: (id: string) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
  onCreate: (type: AllocatorType) => void;
}

const ALLOCATOR_TYPE_CONFIG: Record<AllocatorType, { icon: typeof Target; color: string; bgColor: string; borderColor: string }> = {
  manual: { icon: Target, color: 'text-blue-400', bgColor: 'bg-blue-500/10', borderColor: 'border-blue-500/30' },
  max_sharpe: { icon: TrendingUp, color: 'text-green-400', bgColor: 'bg-green-500/10', borderColor: 'border-green-500/30' },
  min_volatility: { icon: Shield, color: 'text-purple-400', bgColor: 'bg-purple-500/10', borderColor: 'border-purple-500/30' },
};

const AllocatorCard: React.FC<{
  allocator: Allocator;
  onToggle: (id: string) => void;
  onConfigure: (id: string) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
}> = ({ allocator, onToggle, onConfigure, onDuplicate, onDelete }) => {
  const config = ALLOCATOR_TYPE_CONFIG[allocator.type];
  const Icon = config.icon;

  return (
    <div
      className={`
        group relative bg-surface-tertiary/50 rounded-xl border-2 transition-all duration-200
        p-5 hover:bg-surface-tertiary
        ${allocator.enabled
          ? `${config.borderColor} ring-1 ring-accent/20`
          : 'border-transparent hover:border-border'
        }
      `}
    >
      {/* Header Row */}
      <div className="flex items-start gap-4">
        {/* Checkbox */}
        <label className="relative flex items-center cursor-pointer mt-1">
          <input
            type="checkbox"
            checked={allocator.enabled}
            onChange={() => onToggle(allocator.id)}
            className="sr-only peer"
          />
          <div className={`
            w-5 h-5 rounded-md border-2 transition-all duration-200
            flex items-center justify-center
            ${allocator.enabled
              ? 'bg-accent border-accent'
              : 'border-border bg-surface hover:border-accent/50'
            }
          `}>
            {allocator.enabled && (
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </label>

        {/* Icon */}
        <div className={`p-3 rounded-xl ${config.bgColor} flex-shrink-0`}>
          <Icon className={`w-6 h-6 ${config.color}`} />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-text-primary truncate">
            {getAllocatorName(allocator)}
          </h3>
          <span className={`text-sm font-medium ${config.color}`}>
            {getAllocatorTypeDisplay(allocator.type)}
          </span>
        </div>
      </div>

      {/* Actions - always visible on larger screens, hover on smaller */}
      <div className="flex items-center gap-1 mt-4 pt-4 border-t border-border/50">
        <button
          onClick={() => onConfigure(allocator.id)}
          className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors text-sm"
          title="Configure"
        >
          <Settings className="w-4 h-4" />
          <span>Edit</span>
        </button>
        <button
          onClick={() => onDuplicate(allocator.id)}
          className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors text-sm"
          title="Duplicate"
        >
          <Copy className="w-4 h-4" />
          <span>Copy</span>
        </button>
        <button
          onClick={() => onDelete(allocator.id)}
          className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-text-secondary hover:text-danger hover:bg-danger-muted transition-colors text-sm"
          title="Delete"
        >
          <Trash2 className="w-4 h-4" />
          <span>Delete</span>
        </button>
      </div>
    </div>
  );
};

const AddAllocatorCard: React.FC<{
  onClick: () => void;
}> = ({ onClick }) => {
  return (
    <button
      onClick={onClick}
      className={`
        flex flex-col items-center justify-center gap-4 p-6
        bg-surface-tertiary/30 rounded-xl border-2 border-dashed border-border
        hover:border-accent hover:bg-accent/5
        transition-all duration-200 cursor-pointer min-h-[160px]
      `}
    >
      <div className="p-4 rounded-full bg-accent/10">
        <Plus className="w-7 h-7 text-accent" />
      </div>
      <span className="text-base font-medium text-text-secondary">
        Add Allocator
      </span>
    </button>
  );
};

const AllocatorGrid: React.FC<AllocatorGridProps> = ({
  allocators,
  onToggle,
  onConfigure,
  onDuplicate,
  onDelete,
  onCreate,
}) => {
  const [showCreateModal, setShowCreateModal] = useState(false);

  const handleSelectType = (type: AllocatorType) => {
    onCreate(type);
    setShowCreateModal(false);
  };

  return (
    <>
      <div className="bg-surface-secondary rounded-xl border border-border p-5">
        {/* Grid of allocators - scrollable when exceeding 2 rows */}
        <div className="max-h-[400px] overflow-y-auto overflow-x-hidden pr-1">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {allocators.map((allocator) => (
              <AllocatorCard
                key={allocator.id}
                allocator={allocator}
                onToggle={onToggle}
                onConfigure={onConfigure}
                onDuplicate={onDuplicate}
                onDelete={onDelete}
              />
            ))}

            {/* Add Button */}
            <AddAllocatorCard onClick={() => setShowCreateModal(true)} />
          </div>
        </div>

        {/* Empty state */}
        {allocators.length === 0 && (
          <p className="text-center text-text-muted text-sm mt-2">
            Click the button above to create your first allocator
          </p>
        )}
      </div>

      {/* Create Allocator Modal */}
      <CreateAllocatorModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSelectType={handleSelectType}
      />
    </>
  );
};

export default AllocatorGrid;
