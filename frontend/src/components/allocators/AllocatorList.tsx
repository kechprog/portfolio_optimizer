import React, { useState } from 'react';
import { Allocator, AllocatorType } from '../../types';
import { getAllocatorTypeDisplay } from '../../mock/data';
import AllocatorRow from './AllocatorRow';

interface AllocatorListProps {
  allocators: Allocator[];
  onToggle: (id: string) => void;
  onConfigure: (id: string) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
  onCreate: (type: AllocatorType) => void;
}

const AllocatorList: React.FC<AllocatorListProps> = ({
  allocators,
  onToggle,
  onConfigure,
  onDuplicate,
  onDelete,
  onCreate,
}) => {
  const [selectedType, setSelectedType] = useState<AllocatorType>('manual');

  const allocatorTypes: AllocatorType[] = ['manual', 'max_sharpe', 'min_volatility'];

  const handleCreate = () => {
    onCreate(selectedType);
  };

  return (
    <div className="flex flex-col h-full bg-[#2b2b2b] border border-[#3c3c3c] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-[#3c3c3c] bg-[#252525]">
        <h2 className="text-lg font-semibold text-white mb-3">Allocators</h2>
        <div className="flex gap-2">
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value as AllocatorType)}
            className="flex-1 px-3 py-2 bg-[#1e1e1e] text-white border border-[#3c3c3c] rounded focus:outline-none focus:border-blue-500 transition-colors"
          >
            {allocatorTypes.map((type) => (
              <option key={type} value={type}>
                {getAllocatorTypeDisplay(type)}
              </option>
            ))}
          </select>
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-[#28a745] hover:bg-[#218838] text-white font-medium rounded transition-colors whitespace-nowrap"
          >
            Create Allocator
          </button>
        </div>
      </div>

      {/* Allocator List */}
      <div className="flex-1 overflow-y-auto">
        {allocators.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            No allocators yet. Create one to get started.
          </div>
        ) : (
          <div>
            {allocators.map((allocator, index) => (
              <AllocatorRow
                key={allocator.id}
                allocator={allocator}
                onToggle={onToggle}
                onConfigure={onConfigure}
                onDuplicate={onDuplicate}
                onDelete={onDelete}
                isEven={index % 2 === 0}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AllocatorList;
