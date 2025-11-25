import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
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

const PerformanceChart: React.FC<PerformanceChartProps> = ({ results, allocators }) => {
  // Transform data for Recharts
  const chartData = useMemo(() => {
    // Get all enabled allocators
    const enabledAllocators = allocators.filter((a) => a.enabled);

    if (enabledAllocators.length === 0) {
      return [];
    }

    // Get the first enabled allocator's dates as reference
    const firstAllocatorResult = results[enabledAllocators[0].id];
    if (!firstAllocatorResult || !firstAllocatorResult.performance.dates.length) {
      return [];
    }

    const dates = firstAllocatorResult.performance.dates;

    // Create data points
    const data: ChartDataPoint[] = dates.map((date, index) => {
      const point: ChartDataPoint = { date };

      enabledAllocators.forEach((allocator) => {
        const result = results[allocator.id];
        if (result && result.performance.cumulative_returns[index] !== undefined) {
          const allocatorName = getAllocatorName(allocator);
          // Convert to percentage
          point[allocatorName] = result.performance.cumulative_returns[index];
        }
      });

      return point;
    });

    return data;
  }, [results, allocators]);

  // Get enabled allocator names for lines
  const enabledAllocatorNames = useMemo(() => {
    return allocators
      .filter((a) => a.enabled)
      .map((a) => getAllocatorName(a));
  }, [allocators]);

  // Format date for X-axis (show every Nth date to avoid crowding)
  const formatXAxis = (dateStr: string, index: number) => {
    const totalPoints = chartData.length;
    const showEvery = Math.max(1, Math.floor(totalPoints / 10));

    if (index % showEvery !== 0) {
      return '';
    }

    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Format Y-axis to show percentage
  const formatYAxis = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const date = new Date(label);
      const formattedDate = date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });

      return (
        <div
          style={{
            backgroundColor: 'rgba(0, 0, 0, 0.9)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            padding: '12px',
            borderRadius: '4px',
          }}
        >
          <p style={{ color: '#fff', margin: '0 0 8px 0', fontWeight: 'bold' }}>
            {formattedDate}
          </p>
          {payload.map((entry: any, index: number) => (
            <p
              key={index}
              style={{
                color: entry.color,
                margin: '4px 0',
                fontSize: '14px',
              }}
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
      <div
        style={{
          width: '100%',
          height: '400px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'rgba(255, 255, 255, 0.5)',
        }}
      >
        <p>No performance data available. Enable an allocator and compute results.</p>
      </div>
    );
  }

  return (
    <div style={{ width: '100%' }}>
      <h3
        style={{
          color: '#fff',
          marginBottom: '16px',
          fontSize: '18px',
          fontWeight: 600,
        }}
      >
        Portfolio Performance (Out-of-Sample)
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.1)" />
          <XAxis
            dataKey="date"
            tickFormatter={formatXAxis}
            stroke="rgba(255, 255, 255, 0.6)"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            tickFormatter={formatYAxis}
            stroke="rgba(255, 255, 255, 0.6)"
            style={{ fontSize: '12px' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{
              paddingTop: '20px',
              fontSize: '14px',
            }}
          />
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
