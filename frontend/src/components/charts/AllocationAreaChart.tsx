import React, { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { PortfolioSegment } from '../../types';
import { CHART_COLORS } from '../../mock/data';

interface AllocationAreaChartProps {
  segments: PortfolioSegment[];
}

interface AreaChartDataPoint {
  date: string;
  [ticker: string]: string | number;
}

const AllocationAreaChart: React.FC<AllocationAreaChartProps> = ({ segments }) => {
  // Transform segments into chart data
  const { chartData, tickers } = useMemo(() => {
    if (segments.length === 0) {
      return { chartData: [], tickers: [] };
    }

    // Collect all unique tickers
    const tickerSet = new Set<string>();
    segments.forEach((segment) => {
      Object.keys(segment.weights).forEach((ticker) => tickerSet.add(ticker));
    });
    const allTickers = Array.from(tickerSet).sort();

    // Create data points for each segment boundary
    const data: AreaChartDataPoint[] = [];

    segments.forEach((segment, index) => {
      const startPoint: AreaChartDataPoint = { date: segment.start_date };
      const endPoint: AreaChartDataPoint = { date: segment.end_date };

      // Add weights for this segment (convert to percentage)
      allTickers.forEach((ticker) => {
        const weight = segment.weights[ticker] || 0;
        startPoint[ticker] = weight * 100;
        endPoint[ticker] = weight * 100;
      });

      // Add start point only if it's the first segment or different from previous end
      if (index === 0) {
        data.push(startPoint);
      }

      // Always add end point
      data.push(endPoint);
    });

    return { chartData: data, tickers: allTickers };
  }, [segments]);

  // Format date for X-axis
  const formatXAxis = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
  };

  // Format Y-axis to show percentage
  const formatYAxis = (value: number) => {
    return `${value}%`;
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
          {payload
            .filter((entry: any) => entry.value > 0)
            .sort((a: any, b: any) => b.value - a.value)
            .map((entry: any, index: number) => (
              <p
                key={index}
                style={{
                  color: entry.fill,
                  margin: '4px 0',
                  fontSize: '14px',
                }}
              >
                {entry.name}: {entry.value.toFixed(1)}%
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
        <p>No allocation data available.</p>
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
        Allocation Over Time
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <AreaChart
          data={chartData}
          margin={{ top: 10, right: 30, left: 20, bottom: 5 }}
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
            domain={[0, 100]}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{
              paddingTop: '20px',
              fontSize: '14px',
            }}
          />
          {tickers.map((ticker, index) => (
            <Area
              key={ticker}
              type="monotone"
              dataKey={ticker}
              stackId="1"
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
              fillOpacity={0.7}
              animationDuration={1000}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default AllocationAreaChart;
