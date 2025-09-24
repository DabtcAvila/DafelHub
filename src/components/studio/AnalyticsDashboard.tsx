'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAPI } from '../hooks/useAPI';
import { useRealTimeMetrics } from '../hooks/useRealTime';
import { GlowCard, TiltCard } from '../InteractiveElements';

// Analytics types
interface MetricValue {
  timestamp: Date;
  value: number;
  metadata?: Record<string, any>;
}

interface AnalyticsMetric {
  id: string;
  name: string;
  description: string;
  unit: string;
  format: 'number' | 'percentage' | 'bytes' | 'duration' | 'currency';
  icon: string;
  color: string;
  category: 'performance' | 'usage' | 'business' | 'system';
  current_value: number;
  previous_value: number;
  change_percentage: number;
  trend: 'up' | 'down' | 'stable';
  history: MetricValue[];
  target?: number;
  threshold_warning?: number;
  threshold_critical?: number;
}

interface AnalyticsFilter {
  timeRange: '1h' | '6h' | '24h' | '7d' | '30d';
  category: 'all' | 'performance' | 'usage' | 'business' | 'system';
  groupBy: 'hour' | 'day' | 'week';
}

interface ChartConfig {
  type: 'line' | 'area' | 'bar' | 'pie';
  showGrid: boolean;
  showLegend: boolean;
  showTooltip: boolean;
  colors: string[];
}

// Utility functions
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

const formatValue = (value: number, format: string, unit?: string): string => {
  switch (format) {
    case 'percentage':
      return `${value.toFixed(1)}%`;
    case 'bytes':
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
      const i = Math.floor(Math.log(value) / Math.log(1024));
      return `${(value / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    case 'duration':
      if (value < 1000) return `${value.toFixed(0)}ms`;
      if (value < 60000) return `${(value / 1000).toFixed(1)}s`;
      return `${(value / 60000).toFixed(1)}m`;
    case 'currency':
      return `$${value.toLocaleString()}`;
    default:
      return value.toLocaleString() + (unit ? ` ${unit}` : '');
  }
};

const generateMockHistory = (days: number = 7): MetricValue[] => {
  const history: MetricValue[] = [];
  const now = new Date();
  
  for (let i = days * 24; i >= 0; i--) {
    const timestamp = new Date(now.getTime() - i * 60 * 60 * 1000);
    const baseValue = Math.sin(i * 0.1) * 20 + 50 + Math.random() * 10;
    
    history.push({
      timestamp,
      value: Math.max(0, baseValue),
      metadata: {
        day: timestamp.getDay(),
        hour: timestamp.getHours()
      }
    });
  }
  
  return history;
};

// Metric Card Component
const MetricCard: React.FC<{
  metric: AnalyticsMetric;
  onClick: (metric: AnalyticsMetric) => void;
}> = ({ metric, onClick }) => {
  const trendIcon = {
    up: '📈',
    down: '📉', 
    stable: '➡️'
  };

  const trendColor = {
    up: 'text-green-600 dark:text-green-400',
    down: 'text-red-600 dark:text-red-400',
    stable: 'text-gray-600 dark:text-gray-400'
  };

  const isWarning = metric.threshold_warning && metric.current_value >= metric.threshold_warning;
  const isCritical = metric.threshold_critical && metric.current_value >= metric.threshold_critical;

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={() => onClick(metric)}
    >
      <TiltCard className={cn(
        'p-6 cursor-pointer transition-all duration-300',
        isCritical ? 'ring-2 ring-red-500 bg-red-50 dark:bg-red-900' :
        isWarning ? 'ring-2 ring-yellow-500 bg-yellow-50 dark:bg-yellow-900' :
        'hover:shadow-xl'
      )}>
        <div className="flex items-start justify-between mb-4">
          <div className={cn(
            'w-12 h-12 rounded-lg flex items-center justify-center text-2xl',
            `bg-${metric.color}-100 text-${metric.color}-600 dark:bg-${metric.color}-900 dark:text-${metric.color}-400`
          )}>
            {metric.icon}
          </div>
          
          <div className="flex items-center space-x-1">
            <span className={cn('text-sm', trendColor[metric.trend])}>
              {trendIcon[metric.trend]}
            </span>
            <span className={cn('text-sm font-semibold', trendColor[metric.trend])}>
              {Math.abs(metric.change_percentage).toFixed(1)}%
            </span>
          </div>
        </div>

        <div className="mb-4">
          <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
            {metric.name}
          </h3>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {formatValue(metric.current_value, metric.format, metric.unit)}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
            {metric.description}
          </p>
        </div>

        {/* Mini Sparkline */}
        <div className="h-12 relative">
          <svg className="w-full h-full">
            <path
              d={metric.history.slice(-20).map((point, i) => {
                const x = (i / 19) * 100;
                const y = 100 - ((point.value / Math.max(...metric.history.slice(-20).map(p => p.value))) * 100);
                return i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
              }).join(' ')}
              fill="none"
              stroke={`var(--color-${metric.color}-500)`}
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
              className="opacity-60"
            />
          </svg>
        </div>

        {/* Target indicator */}
        {metric.target && (
          <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            Target: {formatValue(metric.target, metric.format, metric.unit)}
          </div>
        )}
      </TiltCard>
    </motion.div>
  );
};

// Real-time Chart Component
const RealTimeChart: React.FC<{
  metrics: AnalyticsMetric[];
  config: ChartConfig;
  timeRange: string;
}> = ({ metrics, config, timeRange }) => {
  const chartData = useMemo(() => {
    if (metrics.length === 0) return [];
    
    // Combine all metric histories into time series data
    const allTimestamps = new Set<number>();
    metrics.forEach(metric => {
      metric.history.forEach(point => allTimestamps.add(point.timestamp.getTime()));
    });
    
    return Array.from(allTimestamps)
      .sort((a, b) => a - b)
      .slice(-50) // Show last 50 data points
      .map(timestamp => {
        const point: any = { timestamp: new Date(timestamp) };
        
        metrics.forEach(metric => {
          const value = metric.history.find(h => 
            Math.abs(h.timestamp.getTime() - timestamp) < 60000 // Within 1 minute
          );
          point[metric.id] = value?.value || 0;
        });
        
        return point;
      });
  }, [metrics]);

  if (chartData.length === 0) {
    return (
      <div className="h-80 flex items-center justify-center bg-gray-50 dark:bg-gray-800 rounded-lg">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <div className="text-4xl mb-2">📊</div>
          <p>No data available</p>
        </div>
      </div>
    );
  }

  const maxValue = Math.max(...chartData.flatMap(d => 
    metrics.map(m => d[m.id] || 0)
  ));
  
  const minValue = Math.min(...chartData.flatMap(d => 
    metrics.map(m => d[m.id] || 0)
  ));
  
  const range = maxValue - minValue || 1;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Real-time Metrics
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Last {timeRange} • {chartData.length} data points
        </p>
      </div>
      
      {config.showLegend && (
        <div className="mb-4 flex flex-wrap gap-4">
          {metrics.map((metric, index) => (
            <div key={metric.id} className="flex items-center space-x-2">
              <div 
                className="w-3 h-3 rounded-full" 
                style={{ backgroundColor: config.colors[index % config.colors.length] }}
              />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {metric.name}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="relative h-64">
        <svg className="w-full h-full">
          {/* Grid lines */}
          {config.showGrid && (
            <g className="opacity-20">
              {[0, 1, 2, 3, 4].map(i => (
                <line
                  key={i}
                  x1="0"
                  y1={`${i * 25}%`}
                  x2="100%"
                  y2={`${i * 25}%`}
                  stroke="currentColor"
                />
              ))}
            </g>
          )}
          
          {/* Data lines */}
          {metrics.map((metric, metricIndex) => {
            const pathData = chartData.map((point, index) => {
              const x = (index / (chartData.length - 1)) * 100;
              const y = 100 - (((point[metric.id] - minValue) / range) * 100);
              return index === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
            }).join(' ');
            
            return (
              <g key={metric.id}>
                {/* Area fill for first metric */}
                {config.type === 'area' && metricIndex === 0 && (
                  <path
                    d={`${pathData} L 100 100 L 0 100 Z`}
                    fill={config.colors[metricIndex % config.colors.length]}
                    fillOpacity="0.1"
                  />
                )}
                
                {/* Line */}
                <motion.path
                  d={pathData}
                  fill="none"
                  stroke={config.colors[metricIndex % config.colors.length]}
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 1, delay: metricIndex * 0.2 }}
                />
                
                {/* Data points */}
                {chartData.map((point, index) => {
                  const x = (index / (chartData.length - 1)) * 100;
                  const y = 100 - (((point[metric.id] - minValue) / range) * 100);
                  
                  return (
                    <motion.circle
                      key={`${metric.id}-${index}`}
                      cx={`${x}%`}
                      cy={`${y}%`}
                      r="3"
                      fill={config.colors[metricIndex % config.colors.length]}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: (index / chartData.length) * 1 + metricIndex * 0.2 }}
                      className="cursor-pointer"
                    >
                      <title>
                        {metric.name}: {formatValue(point[metric.id], metric.format, metric.unit)}
                        {'\n'}
                        {point.timestamp.toLocaleString()}
                      </title>
                    </motion.circle>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
      
      {/* Current values */}
      <div className="mt-4 flex justify-between items-end">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Current Values</p>
          <div className="space-y-1">
            {metrics.map(metric => (
              <p key={metric.id} className="text-sm font-medium">
                {metric.name}: {formatValue(metric.current_value, metric.format, metric.unit)}
              </p>
            ))}
          </div>
        </div>
        
        <div className="text-right">
          <p className="text-sm text-gray-500 dark:text-gray-400">Range</p>
          <p className="text-sm font-mono">
            {formatValue(minValue, metrics[0]?.format || 'number')} - {formatValue(maxValue, metrics[0]?.format || 'number')}
          </p>
        </div>
      </div>
    </div>
  );
};

// Main AnalyticsDashboard Component
export const AnalyticsDashboard: React.FC<{
  projectId: string;
  isLoading?: boolean;
  activities?: any[];
}> = ({ projectId, isLoading, activities = [] }) => {
  const { apiCall } = useAPI();
  const { metrics: realtimeMetrics } = useRealTimeMetrics();
  
  // Dashboard state
  const [filters, setFilters] = useState<AnalyticsFilter>({
    timeRange: '24h',
    category: 'all',
    groupBy: 'hour'
  });
  
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
  const [chartConfig, setChartConfig] = useState<ChartConfig>({
    type: 'line',
    showGrid: true,
    showLegend: true,
    showTooltip: true,
    colors: ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4']
  });

  // Mock analytics data
  const analyticsMetrics: AnalyticsMetric[] = useMemo(() => [
    {
      id: 'api_requests',
      name: 'API Requests',
      description: 'Total API requests per hour',
      unit: 'req/h',
      format: 'number',
      icon: '📡',
      color: 'blue',
      category: 'performance',
      current_value: 1247,
      previous_value: 1156,
      change_percentage: 7.9,
      trend: 'up',
      history: generateMockHistory(7),
      target: 1500,
      threshold_warning: 2000,
      threshold_critical: 2500
    },
    {
      id: 'response_time',
      name: 'Avg Response Time',
      description: 'Average API response time',
      unit: 'ms',
      format: 'duration',
      icon: '⚡',
      color: 'green',
      category: 'performance',
      current_value: 245,
      previous_value: 287,
      change_percentage: -14.6,
      trend: 'down',
      history: generateMockHistory(7).map(h => ({ ...h, value: h.value * 10 + 200 })),
      target: 200,
      threshold_warning: 500,
      threshold_critical: 1000
    },
    {
      id: 'error_rate',
      name: 'Error Rate',
      description: 'Percentage of failed requests',
      unit: '%',
      format: 'percentage',
      icon: '🚨',
      color: 'red',
      category: 'performance',
      current_value: 2.1,
      previous_value: 1.8,
      change_percentage: 16.7,
      trend: 'up',
      history: generateMockHistory(7).map(h => ({ ...h, value: Math.max(0, h.value / 25) })),
      target: 1.0,
      threshold_warning: 3.0,
      threshold_critical: 5.0
    },
    {
      id: 'active_users',
      name: 'Active Users',
      description: 'Currently active users',
      unit: 'users',
      format: 'number',
      icon: '👥',
      color: 'purple',
      category: 'usage',
      current_value: 342,
      previous_value: 298,
      change_percentage: 14.8,
      trend: 'up',
      history: generateMockHistory(7).map(h => ({ ...h, value: h.value * 5 + 200 })),
      target: 500
    },
    {
      id: 'memory_usage',
      name: 'Memory Usage',
      description: 'System memory utilization',
      unit: 'MB',
      format: 'bytes',
      icon: '💾',
      color: 'yellow',
      category: 'system',
      current_value: 2147483648, // 2GB in bytes
      previous_value: 1879048192, // 1.75GB
      change_percentage: 14.3,
      trend: 'up',
      history: generateMockHistory(7).map(h => ({ ...h, value: h.value * 40000000 + 1000000000 })),
      threshold_warning: 3221225472, // 3GB
      threshold_critical: 4294967296 // 4GB
    },
    {
      id: 'revenue',
      name: 'Revenue',
      description: 'Daily revenue generated',
      unit: 'USD',
      format: 'currency',
      icon: '💰',
      color: 'green',
      category: 'business',
      current_value: 15420,
      previous_value: 14280,
      change_percentage: 8.0,
      trend: 'up',
      history: generateMockHistory(7).map(h => ({ ...h, value: h.value * 200 + 10000 })),
      target: 20000
    },
    {
      id: 'cpu_usage',
      name: 'CPU Usage',
      description: 'System CPU utilization',
      unit: '%',
      format: 'percentage',
      icon: '⚙️',
      color: 'orange',
      category: 'system',
      current_value: 67.4,
      previous_value: 72.1,
      change_percentage: -6.5,
      trend: 'down',
      history: generateMockHistory(7).map(h => ({ ...h, value: Math.max(0, Math.min(100, h.value + 30)) })),
      threshold_warning: 80,
      threshold_critical: 90
    },
    {
      id: 'database_connections',
      name: 'DB Connections',
      description: 'Active database connections',
      unit: 'conns',
      format: 'number',
      icon: '🗄️',
      color: 'cyan',
      category: 'system',
      current_value: 23,
      previous_value: 28,
      change_percentage: -17.9,
      trend: 'down',
      history: generateMockHistory(7).map(h => ({ ...h, value: Math.max(1, h.value / 2) })),
      threshold_warning: 50,
      threshold_critical: 80
    }
  ], []);

  // Filter metrics based on category
  const filteredMetrics = useMemo(() => {
    return analyticsMetrics.filter(metric => 
      filters.category === 'all' || metric.category === filters.category
    );
  }, [analyticsMetrics, filters.category]);

  // Get metrics for chart
  const chartMetrics = useMemo(() => {
    return analyticsMetrics.filter(metric => 
      selectedMetrics.includes(metric.id)
    );
  }, [analyticsMetrics, selectedMetrics]);

  // Handle metric selection
  const handleMetricClick = useCallback((metric: AnalyticsMetric) => {
    setSelectedMetrics(prev => 
      prev.includes(metric.id)
        ? prev.filter(id => id !== metric.id)
        : [...prev, metric.id]
    );
  }, []);

  // Category statistics
  const categoryStats = useMemo(() => {
    const stats: Record<string, { count: number; critical: number; warning: number }> = {
      all: { count: 0, critical: 0, warning: 0 },
      performance: { count: 0, critical: 0, warning: 0 },
      usage: { count: 0, critical: 0, warning: 0 },
      business: { count: 0, critical: 0, warning: 0 },
      system: { count: 0, critical: 0, warning: 0 }
    };

    analyticsMetrics.forEach(metric => {
      const isCritical = metric.threshold_critical && metric.current_value >= metric.threshold_critical;
      const isWarning = metric.threshold_warning && metric.current_value >= metric.threshold_warning;
      
      stats.all.count++;
      stats[metric.category].count++;
      
      if (isCritical) {
        stats.all.critical++;
        stats[metric.category].critical++;
      } else if (isWarning) {
        stats.all.warning++;
        stats[metric.category].warning++;
      }
    });

    return stats;
  }, [analyticsMetrics]);

  return (
    <div className="h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              Analytics Dashboard
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Real-time metrics and performance analytics
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4">
          {/* Time Range */}
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Time Range:
            </label>
            <select
              value={filters.timeRange}
              onChange={(e) => setFilters(prev => ({ ...prev, timeRange: e.target.value as any }))}
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
            >
              <option value="1h">Last Hour</option>
              <option value="6h">Last 6 Hours</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>

          {/* Category Filter */}
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Category:
            </label>
            <select
              value={filters.category}
              onChange={(e) => setFilters(prev => ({ ...prev, category: e.target.value as any }))}
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
            >
              <option value="all">All ({categoryStats.all.count})</option>
              <option value="performance">Performance ({categoryStats.performance.count})</option>
              <option value="usage">Usage ({categoryStats.usage.count})</option>
              <option value="business">Business ({categoryStats.business.count})</option>
              <option value="system">System ({categoryStats.system.count})</option>
            </select>
          </div>

          {/* Chart Type */}
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Chart:
            </label>
            <select
              value={chartConfig.type}
              onChange={(e) => setChartConfig(prev => ({ ...prev, type: e.target.value as any }))}
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
            >
              <option value="line">Line</option>
              <option value="area">Area</option>
              <option value="bar">Bar</option>
            </select>
          </div>

          {/* Alert Summary */}
          {(categoryStats[filters.category].critical > 0 || categoryStats[filters.category].warning > 0) && (
            <div className="flex items-center space-x-3 ml-auto">
              {categoryStats[filters.category].critical > 0 && (
                <div className="flex items-center space-x-1 px-2 py-1 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-300 rounded-full text-xs">
                  <span>🚨</span>
                  <span>{categoryStats[filters.category].critical} Critical</span>
                </div>
              )}
              {categoryStats[filters.category].warning > 0 && (
                <div className="flex items-center space-x-1 px-2 py-1 bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-300 rounded-full text-xs">
                  <span>⚠️</span>
                  <span>{categoryStats[filters.category].warning} Warning</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* Chart Section */}
        {chartMetrics.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <RealTimeChart
              metrics={chartMetrics}
              config={chartConfig}
              timeRange={filters.timeRange}
            />
          </motion.div>
        )}

        {/* Metrics Grid */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ staggerChildren: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
        >
          <AnimatePresence>
            {filteredMetrics.map(metric => (
              <motion.div
                key={metric.id}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.3 }}
                className={cn(
                  'relative',
                  selectedMetrics.includes(metric.id) && 'ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-900'
                )}
              >
                <MetricCard
                  metric={metric}
                  onClick={handleMetricClick}
                />
                
                {selectedMetrics.includes(metric.id) && (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="absolute -top-2 -right-2 w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold"
                  >
                    ✓
                  </motion.div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>

        {/* Instructions */}
        {chartMetrics.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-8 text-gray-500 dark:text-gray-400"
          >
            <div className="text-4xl mb-2">📊</div>
            <p className="text-lg font-medium mb-2">Select metrics to view chart</p>
            <p className="text-sm">Click on metric cards to add them to the chart visualization</p>
          </motion.div>
        )}
      </div>
    </div>
  );
};