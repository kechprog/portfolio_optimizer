import React, { useMemo } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { CHART_COLORS } from '../../mock/data';

interface AllocationPieChartProps {
  weights: Record<string, number>;
  title?: string;
}

interface PieDataPoint {
  name: string;
  value: number;
  percentage: string;
  [key: string]: string | number;
}

const AllocationPieChart: React.FC<AllocationPieChartProps> = ({ weights, title }) => {
  // Transform weights into chart data
  const chartData = useMemo(() => {
    const data: PieDataPoint[] = Object.entries(weights)
      .filter(([_, value]) => value > 0)
      .map(([ticker, value]) => ({
        name: ticker,
        value: value * 100, // Convert to percentage
        percentage: `${(value * 100).toFixed(1)}%`,
      }))
      .sort((a, b) => b.value - a.value); // Sort by value descending

    return data;
  }, [weights]);

  // Custom label renderer
  const renderLabel = (props: any) => {
    return `${props.name} (${props.percentage})`;
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload as PieDataPoint;
      return (
        <div
          style={{
            backgroundColor: 'rgba(0, 0, 0, 0.9)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            padding: '12px',
            borderRadius: '4px',
          }}
        >
          <p style={{ color: '#fff', margin: '0 0 4px 0', fontWeight: 'bold' }}>
            {data.name}
          </p>
          <p style={{ color: payload[0].fill, margin: '0', fontSize: '14px' }}>
            Allocation: {data.percentage}
          </p>
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
      {title && (
        <h3
          style={{
            color: '#fff',
            marginBottom: '16px',
            fontSize: '18px',
            fontWeight: 600,
          }}
        >
          {title}
        </h3>
      )}
      <ResponsiveContainer width="100%" height={400}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={80}
            outerRadius={120}
            fill="#8884d8"
            dataKey="value"
            label={renderLabel}
            labelLine={{
              stroke: 'rgba(255, 255, 255, 0.5)',
              strokeWidth: 1,
            }}
            animationBegin={0}
            animationDuration={800}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${entry.name}`}
                fill={CHART_COLORS[index % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend
            verticalAlign="bottom"
            height={36}
            wrapperStyle={{
              fontSize: '14px',
              paddingTop: '20px',
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export default AllocationPieChart;
