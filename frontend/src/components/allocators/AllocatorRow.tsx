import React from 'react';
import { Settings, Copy, Trash2 } from 'lucide-react';
import { Allocator } from '../../types';
import { getAllocatorTypeDisplay } from '../../mock/data';

interface AllocatorRowProps {
  allocator: Allocator;
  onToggle: (id: string) => void;
  onConfigure: (id: string) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
  isEven: boolean;
}

const AllocatorRow: React.FC<AllocatorRowProps> = ({
  allocator,
  onToggle,
  onConfigure,
  onDuplicate,
  onDelete,
  isEven,
}) => {
  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 ${
        isEven ? 'bg-[#2b2b2b]' : 'bg-[#252525]'
      }`}
    >
      <input
        type="checkbox"
        checked={allocator.enabled}
        onChange={() => onToggle(allocator.id)}
        className="w-4 h-4 cursor-pointer accent-blue-500"
      />

      <div className="flex-1 min-w-0">
        <div className="font-medium text-white truncate">
          {allocator.config.name}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          <span className="inline-block px-2 py-0.5 bg-[#3c3c3c] rounded text-gray-300">
            {getAllocatorTypeDisplay(allocator.type)}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => onConfigure(allocator.id)}
          className="p-2 hover:bg-[#3c3c3c] rounded transition-colors text-gray-300 hover:text-white"
          title="Configure"
        >
          <Settings size={18} />
        </button>

        <button
          onClick={() => onDuplicate(allocator.id)}
          className="p-2 hover:bg-[#3c3c3c] rounded transition-colors text-gray-300 hover:text-white"
          title="Duplicate"
        >
          <Copy size={18} />
        </button>

        <button
          onClick={() => onDelete(allocator.id)}
          className="p-2 hover:bg-red-900/30 rounded transition-colors text-red-400 hover:text-red-300"
          title="Delete"
        >
          <Trash2 size={18} />
        </button>
      </div>
    </div>
  );
};

export default AllocatorRow;
