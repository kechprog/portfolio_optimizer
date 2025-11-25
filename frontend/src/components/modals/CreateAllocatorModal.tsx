import React, { useState } from 'react';
import { Modal } from './Modal';
import { Target, TrendingUp, Shield, ChevronRight } from 'lucide-react';
import { AllocatorType } from '../../types';

interface CreateAllocatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectType: (type: AllocatorType) => void;
}

interface AllocatorTypeInfo {
  type: AllocatorType;
  name: string;
  icon: typeof Target;
  color: string;
  bgColor: string;
  description: string;
  tooltip: string;
}

const ALLOCATOR_TYPES: AllocatorTypeInfo[] = [
  {
    type: 'manual',
    name: 'Manual Allocation',
    icon: Target,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10 hover:bg-blue-500/20',
    description: 'Define your own custom asset allocation',
    tooltip: 'Manually set the percentage allocation for each asset in your portfolio. Ideal for implementing specific investment strategies or replicating existing portfolios.',
  },
  {
    type: 'max_sharpe',
    name: 'Maximum Sharpe Ratio',
    icon: TrendingUp,
    color: 'text-green-400',
    bgColor: 'bg-green-500/10 hover:bg-green-500/20',
    description: 'Optimize for risk-adjusted returns',
    tooltip: 'Uses Modern Portfolio Theory to find the portfolio with the highest Sharpe ratio - the best risk-adjusted return. Balances expected returns against volatility.',
  },
  {
    type: 'min_volatility',
    name: 'Minimum Volatility',
    icon: Shield,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10 hover:bg-purple-500/20',
    description: 'Minimize portfolio risk',
    tooltip: 'Finds the portfolio with the lowest possible volatility. Ideal for conservative investors who prioritize capital preservation over maximum returns.',
  },
];

export const CreateAllocatorModal: React.FC<CreateAllocatorModalProps> = ({
  isOpen,
  onClose,
  onSelectType,
}) => {
  const [selectedType, setSelectedType] = useState<AllocatorType | null>(null);

  const handleSelect = (type: AllocatorType) => {
    setSelectedType(type);
  };

  const handleNext = () => {
    if (selectedType) {
      onSelectType(selectedType);
      setSelectedType(null);
      onClose();
    }
  };

  const handleClose = () => {
    setSelectedType(null);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Create New Allocator" size="md">
      <div className="flex flex-col gap-6">
        {/* Type Selection */}
        <div>
          <p className="text-text-secondary mb-4">
            Select the type of allocator you want to create:
          </p>

          <div className="flex flex-col gap-3">
            {ALLOCATOR_TYPES.map((allocatorType) => {
              const Icon = allocatorType.icon;
              const isSelected = selectedType === allocatorType.type;

              return (
                <div key={allocatorType.type} className="relative group">
                  <button
                    onClick={() => handleSelect(allocatorType.type)}
                    className={`
                      w-full flex items-center gap-4 p-4 rounded-xl border-2 transition-all duration-200
                      ${isSelected
                        ? 'border-accent bg-accent/10'
                        : 'border-border hover:border-border-hover bg-surface-tertiary/50'
                      }
                    `}
                  >
                    <div className={`p-3 rounded-xl ${allocatorType.bgColor} transition-colors`}>
                      <Icon className={`w-6 h-6 ${allocatorType.color}`} />
                    </div>
                    <div className="flex-1 text-left">
                      <h3 className="text-base font-semibold text-text-primary">
                        {allocatorType.name}
                      </h3>
                      <p className="text-sm text-text-muted mt-0.5">
                        {allocatorType.description}
                      </p>
                    </div>
                    {isSelected && (
                      <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    )}
                  </button>

                  {/* Tooltip */}
                  <div className="
                    absolute left-1/2 -translate-x-1/2 bottom-full mb-2
                    px-3 py-2 rounded-lg bg-surface-tertiary border border-border shadow-lg
                    text-sm text-text-secondary max-w-xs
                    opacity-0 invisible group-hover:opacity-100 group-hover:visible
                    transition-all duration-200 z-50
                    pointer-events-none
                  ">
                    {allocatorType.tooltip}
                    {/* Tooltip arrow */}
                    <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-8 border-r-8 border-t-8 border-l-transparent border-r-transparent border-t-border" />
                    <div className="absolute left-1/2 -translate-x-1/2 top-full -mt-px w-0 h-0 border-l-[7px] border-r-[7px] border-t-[7px] border-l-transparent border-r-transparent border-t-surface-tertiary" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <button
            onClick={handleClose}
            className="px-4 py-2.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-tertiary transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleNext}
            disabled={!selectedType}
            className={`
              flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all
              ${selectedType
                ? 'bg-accent text-white hover:bg-accent-hover'
                : 'bg-surface-tertiary text-text-muted cursor-not-allowed'
              }
            `}
          >
            Next
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </Modal>
  );
};
