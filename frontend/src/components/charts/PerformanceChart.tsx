import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts';
import { AllocatorResult, Allocator } from '../../types';
import { CHART_COLORS, getAllocatorName } from '../../mock/data';

interface PerformanceChartProps {
  results: Record<string, AllocatorResult>;
  allocators: Allocator[];
}

interface ChartDataPoint {
  date: string;
  [key: string]: string | number;
}

interface Selection {
  anchorIndex: number;
  currentIndex: number;
  anchorX: number;
  currentX: number;
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ results, allocators }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoomRange, setZoomRange] = useState<{ start: number; end: number }>({ start: 0, end: 1 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef<{ x: number; range: { start: number; end: number } } | null>(null);

  // Selection state for left-click drag
  const [isSelecting, setIsSelecting] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  const chartAreaRef = useRef<{ left: number; right: number; width: number } | null>(null);

  const chartData = useMemo(() => {
    const enabledAllocators = allocators.filter((a) => a.enabled);

    if (enabledAllocators.length === 0) {
      return [];
    }

    const firstAllocatorResult = results[enabledAllocators[0].id];
    if (!firstAllocatorResult || !firstAllocatorResult.performance.dates.length) {
      return [];
    }

    const dates = firstAllocatorResult.performance.dates;

    const data: ChartDataPoint[] = dates.map((date, index) => {
      const point: ChartDataPoint = { date };

      enabledAllocators.forEach((allocator) => {
        const result = results[allocator.id];
        if (result && result.performance.cumulative_returns[index] !== undefined) {
          const allocatorName = getAllocatorName(allocator);
          point[allocatorName] = result.performance.cumulative_returns[index];
        }
      });

      return point;
    });

    return data;
  }, [results, allocators]);

  const enabledAllocatorNames = useMemo(() => {
    return allocators
      .filter((a) => a.enabled)
      .map((a) => getAllocatorName(a));
  }, [allocators]);

  // Reset zoom when data changes
  useEffect(() => {
    setZoomRange({ start: 0, end: 1 });
  }, [chartData.length]);

  // Calculate zoomed data
  const zoomedData = useMemo(() => {
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
        : Math.max(0.05, currentRange * (1 - zoomFactor)); // zoom in (min 5% of data)

      // Don't allow zooming out beyond 100%
      if (newRange >= 1) {
        return { start: 0, end: 1 };
      }

      // Get mouse position relative to chart for zoom center
      const container = containerRef.current;
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
    const container = containerRef.current;
    if (!container) return null;

    const containerRect = container.getBoundingClientRect();

    // Try multiple selectors to find the plot area
    // 1. CartesianGrid (most accurate for LineChart)
    const cartesianGrid = container.querySelector('.recharts-cartesian-grid');
    if (cartesianGrid) {
      const gridRect = cartesianGrid.getBoundingClientRect();
      return {
        left: gridRect.left - containerRect.left,
        right: 30, // default right margin
        width: gridRect.width,
      };
    }

    // 2. Try the clip path rect which defines the plot area
    const clipRect = container.querySelector('.recharts-surface defs clipPath rect');
    if (clipRect) {
      const x = parseFloat(clipRect.getAttribute('x') || '0');
      const clipWidth = parseFloat(clipRect.getAttribute('width') || '0');
      if (clipWidth > 0) {
        return { left: x, right: 30, width: clipWidth };
      }
    }

    // 3. Fallback: use known margins
    // LineChart margins: { top: 20, right: 30, left: 10, bottom: 10 }
    // YAxis takes approximately 50px
    const containerWidth = container.clientWidth;
    return {
      left: 60, // margin.left (10) + YAxis (~50)
      right: 30, // margin.right
      width: containerWidth - 60 - 30, // subtract left offset and right margin
    };
  }, []);

  // Initialize chartAreaRef on mount and when data changes
  useEffect(() => {
    const updateChartDimensions = () => {
      if (!containerRef.current || zoomedData.length === 0) return;
      const dims = getChartAreaDimensions();
      if (dims) {
        chartAreaRef.current = dims;
      }
    };

    // Small delay to let recharts render
    const timer = setTimeout(updateChartDimensions, 150);
    window.addEventListener('resize', updateChartDimensions);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', updateChartDimensions);
    };
  }, [zoomedData.length, getChartAreaDimensions]);

  // Helper to get data index from mouse X position
  const getDataIndexFromX = useCallback((clientX: number): number => {
    const container = containerRef.current;
    if (!container || zoomedData.length === 0) return -1;

    // Always get fresh dimensions
    const dims = getChartAreaDimensions();
    if (!dims || dims.width <= 0) return -1;

    const containerRect = container.getBoundingClientRect();
    const relativeX = clientX - containerRect.left - dims.left;
    const ratio = Math.max(0, Math.min(1, relativeX / dims.width));
    return Math.round(ratio * (zoomedData.length - 1));
  }, [zoomedData.length, getChartAreaDimensions]);

  // Handle mouse down for both selection (left) and pan (right)
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) { // Left click - start selection
      const index = getDataIndexFromX(e.clientX);
      if (index >= 0 && index < zoomedData.length) {
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
  }, [zoomRange, getDataIndexFromX, zoomedData.length]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    // Handle selection
    if (isSelecting && selection) {
      const index = getDataIndexFromX(e.clientX);
      if (index >= 0 && index < zoomedData.length) {
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

    const container = containerRef.current;
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
  }, [isPanning, isSelecting, selection, getDataIndexFromX, zoomedData.length]);

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

    if (isPanning || isSelecting) {
      window.addEventListener('mouseup', handleGlobalMouseUp);
      return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
    }
  }, [isPanning, isSelecting]);

  // Calculate selection data for display
  const selectionData = useMemo(() => {
    if (!selection || selection.anchorIndex === selection.currentIndex) return null;

    const startIdx = Math.min(selection.anchorIndex, selection.currentIndex);
    const endIdx = Math.max(selection.anchorIndex, selection.currentIndex);

    const startPoint = zoomedData[startIdx];
    const endPoint = zoomedData[endIdx];

    if (!startPoint || !endPoint) return null;

    const startDate = new Date(startPoint.date);
    const endDate = new Date(endPoint.date);

    // Calculate differences for each allocator
    const differences: { name: string; startValue: number; endValue: number; diff: number; color: string }[] = [];

    enabledAllocatorNames.forEach((name, index) => {
      const startValue = startPoint[name] as number;
      const endValue = endPoint[name] as number;
      if (typeof startValue === 'number' && typeof endValue === 'number') {
        differences.push({
          name,
          startValue,
          endValue,
          diff: endValue - startValue,
          color: CHART_COLORS[index % CHART_COLORS.length],
        });
      }
    });

    return {
      startDate,
      endDate,
      startIdx,
      endIdx,
      differences,
      x1: zoomedData[startIdx]?.date,
      x2: zoomedData[endIdx]?.date,
    };
  }, [selection, zoomedData, enabledAllocatorNames]);

  const formatXAxis = (dateStr: string, index: number) => {
    const totalPoints = zoomedData.length;
    const showEvery = Math.max(1, Math.floor(totalPoints / 10));

    if (index % showEvery !== 0) {
      return '';
    }

    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const formatYAxis = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const date = new Date(label);
      const formattedDate = date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });

      return (
        <div className="bg-surface-secondary border border-border rounded-lg p-3 shadow-lg">
          <p className="text-text-primary font-semibold mb-2">{formattedDate}</p>
          {payload.map((entry: any, index: number) => (
            <p
              key={index}
              className="text-sm"
              style={{ color: entry.color }}
            >
              {entry.name}: {entry.value.toFixed(2)}%
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  if (chartData.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-text-muted">
        <p>Enable an allocator and compute results to see performance data</p>
      </div>
    );
  }

  const isZoomed = zoomRange.start !== 0 || zoomRange.end !== 1;

  return (
    <div
      ref={containerRef}
      className={`w-full h-full relative select-none ${isPanning ? 'cursor-grabbing' : isSelecting ? 'cursor-crosshair' : isZoomed ? 'cursor-grab' : 'cursor-crosshair'}`}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onContextMenu={handleContextMenu}
      onClick={handleClick}
    >
      {/* Zoom indicator */}
      {isZoomed && (
        <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
          <span className="text-xs text-text-muted bg-surface-secondary/80 px-2 py-1 rounded">
            {Math.round((zoomRange.end - zoomRange.start) * 100)}% view
          </span>
          <button
            onClick={() => setZoomRange({ start: 0, end: 1 })}
            className="text-xs text-accent hover:text-accent-hover bg-surface-secondary/80 px-2 py-1 rounded"
          >
            Reset
          </button>
        </div>
      )}

      {/* Selection tooltip */}
      {selectionData && (
        <div className="absolute top-2 left-2 z-10 bg-surface-secondary border border-border rounded-lg p-3 shadow-lg max-w-xs">
          <div className="text-xs text-text-muted mb-2">
            {selectionData.startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            {' → '}
            {selectionData.endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          </div>
          <div className="space-y-1">
            {selectionData.differences.map((diff, index) => (
              <div key={index} className="flex items-center justify-between gap-3 text-sm">
                <span style={{ color: diff.color }} className="truncate">{diff.name}</span>
                <span className={`font-mono font-medium ${diff.diff >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {diff.diff >= 0 ? '+' : ''}{diff.diff.toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={zoomedData}
          margin={{ top: 20, right: 30, left: 10, bottom: 10 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--color-border)"
            opacity={0.5}
          />
          <XAxis
            dataKey="date"
            tickFormatter={formatXAxis}
            stroke="var(--color-text-muted)"
            style={{ fontSize: '12px' }}
            tick={{ fill: 'var(--color-text-muted)' }}
          />
          <YAxis
            tickFormatter={formatYAxis}
            stroke="var(--color-text-muted)"
            style={{ fontSize: '12px' }}
            tick={{ fill: 'var(--color-text-muted)' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{
              paddingTop: '16px',
              fontSize: '14px',
            }}
            formatter={(value) => (
              <span className="text-text-primary">{value}</span>
            )}
          />
          {/* Selection highlight area */}
          {selectionData && (
            <ReferenceArea
              x1={selectionData.x1}
              x2={selectionData.x2}
              fill="var(--color-accent)"
              fillOpacity={0.2}
              stroke="var(--color-accent)"
              strokeOpacity={0.5}
            />
          )}
          {enabledAllocatorNames.map((name, index) => (
            <Line
              key={name}
              type="monotone"
              dataKey={name}
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
              animationDuration={800}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PerformanceChart;
