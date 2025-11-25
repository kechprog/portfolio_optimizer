import React, { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Allocator, AllocatorResult } from '../../types';
import { getAllocatorName } from '../../mock/data';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface PortfolioInfoProps {
  allocators: Allocator[];
  results: Record<string, AllocatorResult>;
  selectedAllocatorId: string | null;
  onSelectAllocator: (id: string) => void;
}

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#00C49F', '#FFBB28', '#FF8042', '#0088FE'];

const PortfolioInfo: React.FC<PortfolioInfoProps> = ({
  allocators,
  results,
  selectedAllocatorId,
  onSelectAllocator,
}) => {
  const [currentSegmentIndex, setCurrentSegmentIndex] = useState(0);
  const [viewMode, setViewMode] = useState<'table' | 'chart'>('table');

  // Get the selected allocator
  const selectedAllocator = allocators.find((a) => a.id === selectedAllocatorId);
  const selectedResult = selectedAllocatorId ? results[selectedAllocatorId] : null;

  // Get current segment
  const currentSegment = selectedResult?.segments[currentSegmentIndex];

  // Navigate segments
  const handlePrevSegment = () => {
    if (currentSegmentIndex > 0) {
      setCurrentSegmentIndex(currentSegmentIndex - 1);
    }
  };

  const handleNextSegment = () => {
    if (selectedResult && currentSegmentIndex < selectedResult.segments.length - 1) {
      setCurrentSegmentIndex(currentSegmentIndex + 1);
    }
  };

  // Prepare pie chart data
  const pieData = useMemo(() => {
    if (!currentSegment) return [];
    return Object.entries(currentSegment.weights).map(([ticker, weight]) => ({
      name: ticker,
      value: weight * 100,
    }));
  }, [currentSegment]);

  // Get enabled allocators for dropdown
  const enabledAllocators = allocators.filter((a) => a.enabled);

  // Reset segment index when allocator changes
  React.useEffect(() => {
    setCurrentSegmentIndex(0);
  }, [selectedAllocatorId]);

  return (
    <div className="flex flex-col h-full bg-[#2b2b2b] border border-[#3c3c3c] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-[#3c3c3c] bg-[#252525]">
        <h2 className="text-lg font-semibold text-white mb-3">Portfolio Information</h2>

        {/* Allocator Selection */}
        {enabledAllocators.length > 0 ? (
          <select
            value={selectedAllocatorId || ''}
            onChange={(e) => onSelectAllocator(e.target.value)}
            className="w-full px-3 py-2 bg-[#1e1e1e] text-white border border-[#3c3c3c] rounded focus:outline-none focus:border-blue-500 transition-colors"
          >
            {enabledAllocators.map((allocator) => (
              <option key={allocator.id} value={allocator.id}>
                {getAllocatorName(allocator)}
              </option>
            ))}
          </select>
        ) : (
          <div className="text-gray-400 text-sm">No enabled allocators</div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {!selectedAllocator || !selectedResult ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            {enabledAllocators.length === 0
              ? 'Enable an allocator and run computation to view results'
              : 'Run computation to view results'}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Segment Navigation */}
            {selectedResult.segments.length > 1 && (
              <div className="flex items-center justify-between bg-[#252525] p-3 rounded">
                <button
                  onClick={handlePrevSegment}
                  disabled={currentSegmentIndex === 0}
                  className="p-2 hover:bg-[#3c3c3c] rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed text-white"
                >
                  <ChevronLeft size={20} />
                </button>

                <div className="text-center text-white">
                  <div className="text-sm font-medium">
                    Segment {currentSegmentIndex + 1} of {selectedResult.segments.length}
                  </div>
                  {currentSegment && (
                    <div className="text-xs text-gray-400 mt-1">
                      {currentSegment.start_date} to {currentSegment.end_date}
                    </div>
                  )}
                </div>

                <button
                  onClick={handleNextSegment}
                  disabled={currentSegmentIndex === selectedResult.segments.length - 1}
                  className="p-2 hover:bg-[#3c3c3c] rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed text-white"
                >
                  <ChevronRight size={20} />
                </button>
              </div>
            )}

            {/* Single Segment Date Range */}
            {selectedResult.segments.length === 1 && currentSegment && (
              <div className="bg-[#252525] p-3 rounded text-center">
                <div className="text-sm text-gray-400">
                  {currentSegment.start_date} to {currentSegment.end_date}
                </div>
              </div>
            )}

            {/* View Toggle */}
            <div className="flex gap-2 bg-[#252525] p-1 rounded">
              <button
                onClick={() => setViewMode('table')}
                className={`flex-1 px-4 py-2 rounded transition-colors font-medium ${
                  viewMode === 'table'
                    ? 'bg-[#0078d4] text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                Table
              </button>
              <button
                onClick={() => setViewMode('chart')}
                className={`flex-1 px-4 py-2 rounded transition-colors font-medium ${
                  viewMode === 'chart'
                    ? 'bg-[#0078d4] text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                Chart
              </button>
            </div>

            {/* Weights Display */}
            {currentSegment && (
              <>
                {viewMode === 'table' ? (
                  <div className="bg-[#252525] rounded overflow-hidden">
                    <table className="w-full">
                      <thead>
                        <tr className="bg-[#1e1e1e]">
                          <th className="px-4 py-3 text-left text-sm font-medium text-gray-300">
                            Ticker
                          </th>
                          <th className="px-4 py-3 text-right text-sm font-medium text-gray-300">
                            Allocation
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(currentSegment.weights).map(([ticker, weight], index) => (
                          <tr
                            key={ticker}
                            className={index % 2 === 0 ? 'bg-[#252525]' : 'bg-[#2b2b2b]'}
                          >
                            <td className="px-4 py-3 text-white font-medium">{ticker}</td>
                            <td className="px-4 py-3 text-right text-gray-300">
                              {(weight * 100).toFixed(2)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="bg-[#252525] rounded p-4">
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {pieData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(value: number) => `${value.toFixed(2)}%`}
                          contentStyle={{
                            backgroundColor: '#1e1e1e',
                            border: '1px solid #3c3c3c',
                            borderRadius: '4px',
                            color: '#fff',
                          }}
                        />
                        <Legend
                          wrapperStyle={{ color: '#fff' }}
                          formatter={(value) => <span style={{ color: '#fff' }}>{value}</span>}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PortfolioInfo;
