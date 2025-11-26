import React, { useMemo, useState, useRef, useCallback, useEffect } from 'react';
import { Download, Check, TrendingUp, TrendingDown, Activity, BarChart3, RefreshCw, Target, Maximize2, Minimize2 } from 'lucide-react';
import { Allocator, AllocatorResult, PerformanceStats } from '../../types';
import { getAllocatorName } from '../../mock/data';
import { useFullscreen } from '../../hooks';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts';

interface Selection {
  anchorIndex: number;
  currentIndex: number;
  anchorX: number;
  currentX: number;
}

interface PortfolioInfoProps {
  allocators: Allocator[];
  results: Record<string, AllocatorResult>;
  selectedAllocatorId: string | null;
  onSelectAllocator: (id: string) => void;
}

const COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#f472b6', '#fb923c', '#2dd4bf', '#818cf8', '#4ade80'];

interface ChartDataPoint {
  date: string;
  [instrument: string]: string | number;
}

interface PortfolioStats {
  totalReturn: number;
  annualizedReturn: number;
  volatility: number;
  sharpeRatio: number;
  maxDrawdown: number;
  rebalances: number;
}

// Get portfolio statistics from backend-computed stats
function getStats(result: AllocatorResult): PortfolioStats {
  const { performance, segments } = result;
  const backendStats = performance.stats;

  // Use backend-computed stats if available
  if (backendStats) {
    return {
      totalReturn: backendStats.total_return,
      annualizedReturn: backendStats.annualized_return,
      volatility: backendStats.volatility,
      sharpeRatio: backendStats.sharpe_ratio,
      maxDrawdown: backendStats.max_drawdown,
      rebalances: segments.length,
    };
  }

  // Fallback to frontend calculation if backend stats not available
  const { dates, cumulative_returns } = performance;
  const totalReturn = cumulative_returns[cumulative_returns.length - 1] || 0;

  let yearsElapsed = 0;
  if (dates.length >= 2) {
    const startDate = new Date(dates[0]);
    const endDate = new Date(dates[dates.length - 1]);
    const msPerDay = 1000 * 60 * 60 * 24;
    const calendarDays = (endDate.getTime() - startDate.getTime()) / msPerDay;
    yearsElapsed = calendarDays / 365.25;
  }

  const annualizedReturn = yearsElapsed > 0
    ? (Math.pow(1 + totalReturn / 100, 1 / yearsElapsed) - 1) * 100
    : 0;

  return {
    totalReturn,
    annualizedReturn,
    volatility: 0,
    sharpeRatio: 0,
    maxDrawdown: 0,
    rebalances: segments.length,
  };
}

// Stat card component
interface StatCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  colorClass?: string;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, icon, colorClass = 'text-text-primary' }) => (
  <div className="bg-surface-secondary rounded-lg p-3 flex flex-col gap-1">
    <div className="flex items-center gap-2 text-text-muted">
      {icon}
      <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
    </div>
    <div className={`text-lg font-semibold font-mono ${colorClass}`}>
      {value}
    </div>
  </div>
);

const PortfolioInfo: React.FC<PortfolioInfoProps> = ({
  allocators,
  results,
  selectedAllocatorId,
  onSelectAllocator,
}) => {
  const [copied, setCopied] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const { isFullscreen, toggleFullscreen } = useFullscreen(chartRef);
  const [zoomRange, setZoomRange] = useState<{ start: number; end: number }>({ start: 0, end: 1 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef<{ x: number; range: { start: number; end: number } } | null>(null);

  // Selection state for left-click drag
  const [isSelecting, setIsSelecting] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  const chartAreaRef = useRef<{ left: number; right: number; width: number } | null>(null);

  const selectedAllocator = allocators.find((a) => a.id === selectedAllocatorId);
  const selectedResult = selectedAllocatorId ? results[selectedAllocatorId] : null;

  // Get portfolio statistics (from backend)
  const stats = useMemo(() => {
    if (!selectedResult) return null;
    return getStats(selectedResult);
  }, [selectedResult]);

  // Get all unique instruments across all segments
  const allInstruments = useMemo(() => {
    if (!selectedResult) return [];
    const instruments = new Set<string>();
    selectedResult.segments.forEach((segment) => {
      Object.keys(segment.weights).forEach((ticker) => instruments.add(ticker));
    });
    return Array.from(instruments).sort();
  }, [selectedResult]);

  // Transform segments into chart data points
  const chartData = useMemo(() => {
    if (!selectedResult || selectedResult.segments.length === 0) return [];

    const data: ChartDataPoint[] = [];

    selectedResult.segments.forEach((segment, index) => {
      // Add start point of segment
      const startPoint: ChartDataPoint = { date: segment.start_date };
      allInstruments.forEach((inst) => {
        startPoint[inst] = (segment.weights[inst] || 0) * 100;
      });
      data.push(startPoint);

      // Add end point of segment (if it's the last segment or if next segment starts on different date)
      const isLastSegment = index === selectedResult.segments.length - 1;
      const nextSegment = selectedResult.segments[index + 1];

      if (isLastSegment || (nextSegment && nextSegment.start_date !== segment.end_date)) {
        const endPoint: ChartDataPoint = { date: segment.end_date };
        allInstruments.forEach((inst) => {
          endPoint[inst] = (segment.weights[inst] || 0) * 100;
        });
        data.push(endPoint);
      }
    });

    return data;
  }, [selectedResult, allInstruments]);

  // Reset zoom when data changes
  useEffect(() => {
    setZoomRange({ start: 0, end: 1 });
  }, [chartData.length, selectedAllocatorId]);

  // Calculate zoomed data
  const zoomedChartData = useMemo(() => {
    if (chartData.length === 0) return [];
    const startIndex = Math.floor(zoomRange.start * chartData.length);
    const endIndex = Math.ceil(zoomRange.end * chartData.length);
    return chartData.slice(startIndex, Math.max(endIndex, startIndex + 2));
  }, [chartData, zoomRange]);

  // Handle wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();

    const zoomFactor = 0.1;
    const delta = e.deltaY > 0 ? 1 : -1; // 1 = zoom out, -1 = zoom in

    setZoomRange(prev => {
      const currentRange = prev.end - prev.start;
      const newRange = delta > 0
        ? Math.min(1, currentRange * (1 + zoomFactor)) // zoom out
        : Math.max(0.1, currentRange * (1 - zoomFactor)); // zoom in (min 10% of data)

      // Don't allow zooming out beyond 100%
      if (newRange >= 1) {
        return { start: 0, end: 1 };
      }

      // Get mouse position relative to chart for zoom center
      const container = chartContainerRef.current;
      if (!container) return prev;

      const rect = container.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left) / rect.width;

      // Calculate new start/end centered on mouse position
      const center = prev.start + (prev.end - prev.start) * mouseX;
      let newStart = center - newRange * mouseX;
      let newEnd = center + newRange * (1 - mouseX);

      // Clamp to valid range
      if (newStart < 0) {
        newStart = 0;
        newEnd = newRange;
      }
      if (newEnd > 1) {
        newEnd = 1;
        newStart = 1 - newRange;
      }

      return { start: newStart, end: newEnd };
    });
  }, []);

  // Helper to get chart plot area dimensions
  const getChartAreaDimensions = useCallback(() => {
    const container = chartContainerRef.current;
    if (!container) return null;

    const containerRect = container.getBoundingClientRect();

    // Try multiple selectors to find the plot area
    // 1. CartesianGrid (most accurate but may not exist in AreaChart)
    const cartesianGrid = container.querySelector('.recharts-cartesian-grid');
    if (cartesianGrid) {
      const gridRect = cartesianGrid.getBoundingClientRect();
      return {
        left: gridRect.left - containerRect.left,
        width: gridRect.width,
      };
    }

    // 2. Try the clip path rect which defines the plot area
    const clipRect = container.querySelector('.recharts-surface defs clipPath rect');
    if (clipRect) {
      const x = parseFloat(clipRect.getAttribute('x') || '0');
      const clipWidth = parseFloat(clipRect.getAttribute('width') || '0');
      if (clipWidth > 0) {
        return { left: x, width: clipWidth };
      }
    }

    // 3. Try finding the area elements and calculate from their bounds
    const areaPath = container.querySelector('.recharts-area-area');
    if (areaPath) {
      const pathRect = areaPath.getBoundingClientRect();
      return {
        left: pathRect.left - containerRect.left,
        width: pathRect.width,
      };
    }

    // 4. Fallback: use known margins (YAxis width: 40, margin.right: 8)
    const containerWidth = container.clientWidth;
    return {
      left: 40,
      width: containerWidth - 40 - 8,
    };
  }, []);

  // Helper to get data index from mouse X position
  const getDataIndexFromX = useCallback((clientX: number): number => {
    const container = chartContainerRef.current;
    if (!container || zoomedChartData.length === 0) return -1;

    // Always get fresh dimensions
    const dims = getChartAreaDimensions();
    if (!dims || dims.width <= 0) return -1;

    const containerRect = container.getBoundingClientRect();
    const relativeX = clientX - containerRect.left - dims.left;
    const ratio = Math.max(0, Math.min(1, relativeX / dims.width));
    return Math.round(ratio * (zoomedChartData.length - 1));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomedChartData.length]);

  // Handle mouse down for both selection (left) and pan (right)
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) { // Left click - start selection
      const index = getDataIndexFromX(e.clientX);
      if (index >= 0 && index < zoomedChartData.length) {
        setIsSelecting(true);
        setSelection({
          anchorIndex: index,
          currentIndex: index,
          anchorX: e.clientX,
          currentX: e.clientX,
        });
      }
    } else if (e.button === 2) { // Right click - pan
      e.preventDefault();
      setIsPanning(true);
      panStartRef.current = {
        x: e.clientX,
        range: { ...zoomRange },
      };
    }
  }, [zoomRange, getDataIndexFromX, zoomedChartData.length]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    // Handle selection
    if (isSelecting && selection) {
      const index = getDataIndexFromX(e.clientX);
      if (index >= 0 && index < zoomedChartData.length) {
        setSelection(prev => prev ? {
          ...prev,
          currentIndex: index,
          currentX: e.clientX,
        } : null);
      }
      return;
    }

    // Handle panning
    if (!isPanning || !panStartRef.current) return;

    const container = chartContainerRef.current;
    if (!container) return;

    const rect = container.getBoundingClientRect();
    const deltaX = (e.clientX - panStartRef.current.x) / rect.width;
    const currentRange = panStartRef.current.range.end - panStartRef.current.range.start;

    // Calculate pan amount (negative because dragging right should move view left)
    const panAmount = -deltaX * currentRange;

    let newStart = panStartRef.current.range.start + panAmount;
    let newEnd = panStartRef.current.range.end + panAmount;

    // Clamp to valid range (can't pan outside data scope)
    if (newStart < 0) {
      newStart = 0;
      newEnd = currentRange;
    }
    if (newEnd > 1) {
      newEnd = 1;
      newStart = 1 - currentRange;
    }

    setZoomRange({ start: newStart, end: newEnd });
  }, [isPanning, isSelecting, selection, getDataIndexFromX, zoomedChartData.length]);

  const handleMouseUp = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) { // Left click - end selection
      setIsSelecting(false);
      // Keep selection visible until next click
    } else if (e.button === 2) {
      setIsPanning(false);
      panStartRef.current = null;
    }
  }, []);

  // Clear selection on click (not drag)
  const handleClick = useCallback((e: React.MouseEvent) => {
    if (selection && selection.anchorIndex === selection.currentIndex) {
      // It was a click, not a drag - clear selection
      setSelection(null);
    }
  }, [selection]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    // Prevent context menu when zoomed to allow panning
    if (zoomRange.start !== 0 || zoomRange.end !== 1) {
      e.preventDefault();
    }
  }, [zoomRange]);

  // Also handle mouse up outside the container
  useEffect(() => {
    const handleGlobalMouseUp = (e: MouseEvent) => {
      if (e.button === 0) {
        setIsSelecting(false);
      } else if (e.button === 2) {
        setIsPanning(false);
        panStartRef.current = null;
      }
    };

    // Always add listener when component is in interactive state
    window.addEventListener('mouseup', handleGlobalMouseUp);

    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, []); // Empty deps - listener is always active, handler updates via closure

  // Calculate selection data for display
  const selectionData = useMemo(() => {
    if (!selection || selection.anchorIndex === selection.currentIndex) return null;

    const startIdx = Math.min(selection.anchorIndex, selection.currentIndex);
    const endIdx = Math.max(selection.anchorIndex, selection.currentIndex);

    const startPoint = zoomedChartData[startIdx];
    const endPoint = zoomedChartData[endIdx];

    if (!startPoint || !endPoint) return null;

    const startDate = new Date(startPoint.date as string);
    const endDate = new Date(endPoint.date as string);

    // Calculate allocation differences for each instrument
    const differences: { name: string; startValue: number; endValue: number; diff: number; color: string }[] = [];

    allInstruments.forEach((instrument, index) => {
      const startValue = startPoint[instrument] as number;
      const endValue = endPoint[instrument] as number;
      if (typeof startValue === 'number' && typeof endValue === 'number') {
        differences.push({
          name: instrument,
          startValue,
          endValue,
          diff: endValue - startValue,
          color: COLORS[index % COLORS.length],
        });
      }
    });

    return {
      startDate,
      endDate,
      startIdx,
      endIdx,
      differences: differences.filter(d => Math.abs(d.diff) > 0.01), // Only show significant changes
      x1: zoomedChartData[startIdx]?.date,
      x2: zoomedChartData[endIdx]?.date,
    };
  }, [selection, zoomedChartData, allInstruments]);

  const isZoomed = zoomRange.start !== 0 || zoomRange.end !== 1;

  // Generate CSV and copy to clipboard
  const handleExport = async () => {
    if (!selectedResult || !selectedAllocator) return;

    // Build CSV header
    const headers = ['Start Date', 'End Date', ...allInstruments];
    const csvLines = [headers.join(',')];

    // Add data rows
    selectedResult.segments.forEach((segment) => {
      const row = [
        segment.start_date,
        segment.end_date,
        ...allInstruments.map((inst) => ((segment.weights[inst] || 0) * 100).toFixed(2)),
      ];
      csvLines.push(row.join(','));
    });

    const csv = csvLines.join('\n');

    try {
      await navigator.clipboard.writeText(csv);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  // Custom tooltip component
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || payload.length === 0) return null;

    return (
      <div className="bg-surface-secondary border border-border rounded-lg p-3 shadow-lg">
        <div className="text-sm font-medium text-text-primary mb-2">{label}</div>
        <div className="space-y-1">
          {payload
            .filter((entry: any) => entry.value > 0)
            .sort((a: any, b: any) => b.value - a.value)
            .map((entry: any, index: number) => (
              <div key={index} className="flex items-center justify-between gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-text-secondary">{entry.name}</span>
                </div>
                <span className="font-mono text-text-primary">{entry.value.toFixed(2)}%</span>
              </div>
            ))}
        </div>
      </div>
    );
  };

  const enabledAllocators = allocators.filter((a) => a.enabled);

  // Helper to format values with color
  const getReturnColor = (value: number) => {
    if (value > 0) return 'text-green-400';
    if (value < 0) return 'text-red-400';
    return 'text-text-primary';
  };

  return (
    <div className="flex flex-col h-full relative">
      {/* Toast notification for clipboard copy */}
      {copied && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100]">
          <div className="bg-green-600 text-white px-4 py-2.5 rounded-lg shadow-xl flex items-center gap-2 border border-green-500">
            <Check className="w-4 h-4" />
            <span className="text-sm font-medium">CSV copied to clipboard</span>
          </div>
        </div>
      )}

      {/* Header with allocator selection and export */}
      <div className="flex items-center gap-3 mb-4">
        {enabledAllocators.length > 0 ? (
          <select
            value={selectedAllocatorId || ''}
            onChange={(e) => onSelectAllocator(e.target.value)}
            className="input flex-1"
          >
            {enabledAllocators.map((allocator) => (
              <option key={allocator.id} value={allocator.id}>
                {getAllocatorName(allocator)}
              </option>
            ))}
          </select>
        ) : (
          <div className="text-text-muted text-sm flex-1">No enabled allocators</div>
        )}

        {selectedResult && (
          <button
            onClick={handleExport}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              copied
                ? 'bg-green-500/20 text-green-400'
                : 'bg-surface-tertiary text-text-secondary hover:text-text-primary hover:bg-surface-secondary'
            }`}
            title="Copy allocations as CSV"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4" />
                Copied
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                Export
              </>
            )}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 flex flex-col gap-4">
        {!selectedAllocator || !selectedResult ? (
          <div className="flex items-center justify-center h-full text-text-muted">
            {enabledAllocators.length === 0
              ? 'Enable an allocator and run computation'
              : 'Run computation to view results'}
          </div>
        ) : (
          <>
            {/* Stats Grid */}
            {stats && (
              <div className="grid grid-cols-3 gap-2">
                <StatCard
                  label="Total Return"
                  value={`${stats.totalReturn >= 0 ? '+' : ''}${stats.totalReturn.toFixed(2)}%`}
                  icon={stats.totalReturn >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                  colorClass={getReturnColor(stats.totalReturn)}
                />
                <StatCard
                  label="Annualized Return"
                  value={`${stats.annualizedReturn >= 0 ? '+' : ''}${stats.annualizedReturn.toFixed(2)}%`}
                  icon={<BarChart3 className="w-4 h-4" />}
                  colorClass={getReturnColor(stats.annualizedReturn)}
                />
                <StatCard
                  label="Volatility"
                  value={`${stats.volatility.toFixed(2)}%`}
                  icon={<Activity className="w-4 h-4" />}
                />
                <StatCard
                  label="Sharpe Ratio"
                  value={stats.sharpeRatio.toFixed(2)}
                  icon={<Target className="w-4 h-4" />}
                  colorClass={stats.sharpeRatio >= 1 ? 'text-green-400' : stats.sharpeRatio >= 0 ? 'text-yellow-400' : 'text-red-400'}
                />
                <StatCard
                  label="Max Drawdown"
                  value={`-${stats.maxDrawdown.toFixed(2)}%`}
                  icon={<TrendingDown className="w-4 h-4" />}
                  colorClass="text-red-400"
                />
                <StatCard
                  label="Rebalances"
                  value={stats.rebalances.toString()}
                  icon={<RefreshCw className="w-4 h-4" />}
                />
              </div>
            )}

            {/* Allocation Chart */}
            {chartData.length > 0 ? (
              <div
                ref={chartRef}
                className={`
                  flex-1 min-h-0 bg-surface-tertiary rounded-lg flex flex-col relative
                  ${isFullscreen ? 'fixed inset-0 z-50 rounded-none' : ''}
                `}
              >
                {/* Chart header with fullscreen button */}
                <div className="flex items-center justify-between px-2 pt-2">
                  <span className="text-xs text-text-muted font-medium">Allocation Over Time</span>
                  <div className="flex items-center gap-2">
                    {isZoomed && (
                      <>
                        <span className="text-xs text-text-muted">
                          {Math.round((zoomRange.end - zoomRange.start) * 100)}%
                        </span>
                        <button
                          onClick={() => setZoomRange({ start: 0, end: 1 })}
                          className="text-xs text-accent hover:text-accent-hover"
                        >
                          Reset
                        </button>
                      </>
                    )}
                    <button
                      onClick={toggleFullscreen}
                      className="btn-icon"
                      title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
                    >
                      {isFullscreen ? (
                        <Minimize2 className="w-4 h-4" />
                      ) : (
                        <Maximize2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
                {/* Selection tooltip */}
                {selectionData && (
                  <div className="absolute top-10 left-2 z-10 bg-surface-secondary border border-border rounded-lg p-3 shadow-lg max-w-xs">
                    <div className="text-xs text-text-muted mb-2">
                      {selectionData.startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                      {' → '}
                      {selectionData.endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </div>
                    {selectionData.differences.length > 0 ? (
                      <div className="space-y-1">
                        {selectionData.differences.map((diff, index) => (
                          <div key={index} className="flex items-center justify-between gap-3 text-sm">
                            <span style={{ color: diff.color }} className="truncate">{diff.name}</span>
                            <span className={`font-mono font-medium ${diff.diff >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {diff.diff >= 0 ? '+' : ''}{diff.diff.toFixed(1)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-text-muted">No allocation changes</div>
                    )}
                  </div>
                )}
                {/* Chart content */}
                <div
                  ref={chartContainerRef}
                  className={`flex-1 min-h-0 px-1 pb-1 select-none ${isPanning ? 'cursor-grabbing' : isSelecting ? 'cursor-crosshair' : isZoomed ? 'cursor-grab' : 'cursor-crosshair'}`}
                  onWheel={handleWheel}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onContextMenu={handleContextMenu}
                  onClick={handleClick}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={zoomedChartData}
                      margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                    >
                      <XAxis
                        dataKey="date"
                        tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                        axisLine={{ stroke: 'var(--color-border)' }}
                        tickLine={{ stroke: 'var(--color-border)' }}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                        axisLine={{ stroke: 'var(--color-border)' }}
                        tickLine={{ stroke: 'var(--color-border)' }}
                        tickFormatter={(value) => `${value}%`}
                        width={40}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend
                        wrapperStyle={{ paddingTop: '8px' }}
                        formatter={(value) => (
                          <span className="text-text-primary text-xs">{value}</span>
                        )}
                      />
                      {/* Selection highlight area */}
                      {selectionData && (
                        <ReferenceArea
                          x1={selectionData.x1}
                          x2={selectionData.x2}
                          fill="var(--color-accent)"
                          fillOpacity={0.3}
                          stroke="var(--color-accent)"
                          strokeOpacity={0.6}
                        />
                      )}
                      {allInstruments.map((instrument, index) => (
                        <Area
                          key={instrument}
                          type="stepAfter"
                          dataKey={instrument}
                          stackId="1"
                          stroke={COLORS[index % COLORS.length]}
                          fill={COLORS[index % COLORS.length]}
                          fillOpacity={0.8}
                        />
                      ))}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-text-muted">
                No allocation data available
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default PortfolioInfo;
