import React, { useMemo } from 'react';
import {
    ComposedChart,
    Line,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    Area
} from 'recharts';

interface ProductivityChartProps {
    data: any[];
    pageKey: string | null;
}

export const ProductivityChart: React.FC<ProductivityChartProps> = ({ data, pageKey }) => {
    // Only show for 'rpt_press' (Extrusion Report) or pages with relevant fields
    if (!data || data.length === 0 || pageKey !== 'rpt_press') return null;

    // Aggregate data by date
    const chartData = useMemo(() => {
        const aggregated: Record<string, { date: string; weight: number; yieldSum: number; count: number }> = {};

        data.forEach(row => {
            const date = row['일자'];
            // Clean weight: remove commas, parse float
            const weightStr = String(row['적합 중량'] || '0').replace(/,/g, '');
            const weight = parseFloat(weightStr) || 0;
            
            const yieldStr = String(row['수율'] || '0').replace(/,/g, '');
            const yieldVal = parseFloat(yieldStr) || 0;

            if (date) {
                if (!aggregated[date]) {
                    aggregated[date] = { date, weight: 0, yieldSum: 0, count: 0 };
                }
                aggregated[date].weight += weight;
                aggregated[date].yieldSum += yieldVal;
                aggregated[date].count += 1;
            }
        });

        // Convert to array and calculate average yield
        return Object.values(aggregated)
            .map(item => ({
                date: item.date,
                weight: item.weight,
                yieldAvg: item.count > 0 ? (item.yieldSum / item.count).toFixed(1) : 0
            }))
            .sort((a, b) => a.date.localeCompare(b.date)); // Sort by date
    }, [data]);

    if (chartData.length === 0) return null;

    return (
        <div style={{
            margin: '0 1.5rem 1rem 1.5rem',
            padding: '1.5rem',
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--card-radius)',
            border: '1px solid var(--border-color)',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
        }}>
            <h3 style={{ margin: '0 0 1rem 0', color: 'var(--text-primary)', fontSize: '1.1rem' }}>
                📊 생산성 및 수율 트렌드 (Productivity Trend)
            </h3>
            <div style={{ width: '100%', height: 350 }}>
                <ResponsiveContainer>
                    <ComposedChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
                        <XAxis 
                            dataKey="date" 
                            stroke="var(--text-secondary)" 
                            fontSize={12} 
                            tickMargin={10}
                        />
                        <YAxis 
                            yAxisId="left" 
                            stroke="var(--state-success)" 
                            fontSize={12}
                            label={{ value: '생산량 (kg)', angle: -90, position: 'insideLeft', fill: 'var(--text-secondary)' }}
                        />
                        <YAxis 
                            yAxisId="right" 
                            orientation="right" 
                            stroke="var(--accent-main)" 
                            fontSize={12}
                            domain={[0, 100]}
                            label={{ value: '수율 (%)', angle: 90, position: 'insideRight', fill: 'var(--text-secondary)' }}
                        />
                        <Tooltip 
                            contentStyle={{ 
                                backgroundColor: 'var(--bg-primary)', 
                                borderColor: 'var(--border-color)', 
                                color: 'var(--text-primary)' 
                            }} 
                        />
                        <Legend wrapperStyle={{ paddingTop: '10px' }} />
                        <Bar 
                            yAxisId="left" 
                            dataKey="weight" 
                            name="적합 중량 (kg)" 
                            fill="var(--state-success)" 
                            barSize={30} 
                            radius={[4, 4, 0, 0]} 
                            fillOpacity={0.8}
                        />
                        <Line 
                            yAxisId="right" 
                            type="monotone" 
                            dataKey="yieldAvg" 
                            name="평균 수율 (%)" 
                            stroke="var(--accent-main)" 
                            strokeWidth={3} 
                            dot={{ r: 4, fill: 'var(--accent-main)' }}
                            activeDot={{ r: 6 }}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
