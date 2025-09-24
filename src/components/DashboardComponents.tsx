'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth, withAuth } from './hooks/useAuth';
import { useAPI, useAPIResource, API_ENDPOINTS } from './hooks/useAPI';
import { 
  useRealTimeMetrics, 
  useRealTimeActivity, 
  useRealTimeNotifications,
  useUserPresence 
} from './hooks/useRealTime';
import { 
  MagneticButton, 
  RippleButton, 
  TiltCard, 
  GlowCard, 
  FloatingActionButton 
} from './InteractiveElements';

// Types
interface DashboardMetric {
  id: string;
  title: string;
  value: number | string;
  change: number;
  trend: 'up' | 'down' | 'stable';
  color: 'blue' | 'green' | 'yellow' | 'red' | 'purple';
  icon: string;
  unit?: string;
  format?: 'number' | 'percentage' | 'currency' | 'time' | 'bytes';
}

interface Project {
  id: string;
  name: string;
  status: 'active' | 'building' | 'deployed' | 'error';
  framework: string;
  last_deployed: string;
  deployments_count: number;
  uptime: number;
}

interface Connection {
  id: string;
  name: string;
  type: string;
  status: 'connected' | 'disconnected' | 'error';
  host: string;
  last_tested: string;
  response_time?: number;
}

// Utility functions
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

const formatValue = (value: number | string, format?: string, unit?: string): string => {
  if (typeof value === 'string') return value;
  
  switch (format) {
    case 'percentage':
      return `${value.toFixed(1)}%`;
    case 'currency':
      return `$${value.toLocaleString()}`;
    case 'time':
      return `${value.toFixed(0)}ms`;
    case 'bytes':
      const bytes = value;
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    default:
      return value.toLocaleString() + (unit ? ` ${unit}` : '');
  }
};

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 }
};

const chartVariants = {
  hidden: { scale: 0 },
  visible: { 
    scale: 1, 
    transition: { 
      type: 'spring',
      stiffness: 100,
      damping: 15 
    }
  }
};

// Metric Card Component
const MetricCard: React.FC<{ metric: DashboardMetric }> = ({ metric }) => {
  const colorClasses = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    yellow: 'from-yellow-500 to-yellow-600',
    red: 'from-red-500 to-red-600',
    purple: 'from-purple-500 to-purple-600',
  };

  const trendIcons = {
    up: '📈',
    down: '📉',
    stable: '➡️'
  };

  const trendColors = {
    up: 'text-green-600 dark:text-green-400',
    down: 'text-red-600 dark:text-red-400',
    stable: 'text-gray-600 dark:text-gray-400'
  };

  return (
    <motion.div variants={itemVariants}>
      <GlowCard className="p-6 hover:scale-105 transition-transform duration-200">
        <div className="flex items-center justify-between mb-4">
          <div className={cn(
            'w-12 h-12 rounded-lg bg-gradient-to-r flex items-center justify-center text-2xl',
            colorClasses[metric.color]
          )}>
            {metric.icon}
          </div>
          <div className={cn('flex items-center space-x-1 text-sm', trendColors[metric.trend])}>
            <span>{trendIcons[metric.trend]}</span>
            <span>{Math.abs(metric.change).toFixed(1)}%</span>
          </div>
        </div>
        
        <div>
          <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
            {metric.title}
          </h3>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {formatValue(metric.value, metric.format, metric.unit)}
          </p>
        </div>
      </GlowCard>
    </motion.div>
  );
};

// Real-time Chart Component
const RealTimeChart: React.FC<{
  title: string;
  data: Array<{ timestamp: Date; value: number }>;
  color: string;
  unit?: string;
}> = ({ title, data, color, unit }) => {
  const maxValue = Math.max(...data.map(d => d.value), 1);
  const minValue = Math.min(...data.map(d => d.value), 0);
  const range = maxValue - minValue || 1;

  // Create SVG path for the line chart
  const pathData = data.map((point, index) => {
    const x = (index / (data.length - 1)) * 300;
    const y = 60 - ((point.value - minValue) / range) * 60;
    return index === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
  }).join(' ');

  return (
    <motion.div
      variants={chartVariants}
      className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6"
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        {title}
      </h3>
      
      <div className="flex items-end justify-between mb-4">
        <div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {data.length > 0 ? formatValue(data[data.length - 1].value, undefined, unit) : '0'}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400">Current</p>
        </div>
        
        <div className="text-right">
          <p className="text-lg font-semibold text-gray-700 dark:text-gray-300">
            {formatValue(maxValue, undefined, unit)}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400">Peak</p>
        </div>
      </div>

      <div className="relative">
        <svg
          width="100%"
          height="80"
          viewBox="0 0 300 80"
          className="overflow-visible"
        >
          {/* Grid lines */}
          <defs>
            <linearGradient id={`gradient-${color}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={color} stopOpacity="0.3" />
              <stop offset="100%" stopColor={color} stopOpacity="0.05" />
            </linearGradient>
          </defs>
          
          {/* Grid */}
          {[0, 1, 2, 3].map(i => (
            <line
              key={i}
              x1="0"
              y1={15 * i + 10}
              x2="300"
              y2={15 * i + 10}
              stroke="currentColor"
              strokeOpacity="0.1"
              strokeWidth="1"
            />
          ))}
          
          {/* Area under curve */}
          <path
            d={`${pathData} L 300 80 L 0 80 Z`}
            fill={`url(#gradient-${color})`}
          />
          
          {/* Line */}
          <motion.path
            d={pathData}
            fill="none"
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.5, ease: 'easeOut' }}
          />
          
          {/* Data points */}
          {data.map((point, index) => {
            const x = (index / (data.length - 1)) * 300;
            const y = 60 - ((point.value - minValue) / range) * 60;
            
            return (
              <motion.circle
                key={index}
                cx={x}
                cy={y}
                r="3"
                fill={color}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: (index / data.length) * 1.5, duration: 0.3 }}
                className="cursor-pointer"
              >
                <title>{`${formatValue(point.value, undefined, unit)} at ${point.timestamp.toLocaleTimeString()}`}</title>
              </motion.circle>
            );
          })}
        </svg>
      </div>
    </motion.div>
  );
};

// Activity Feed Component
const ActivityFeed: React.FC = () => {
  const { activities } = useRealTimeActivity();
  const displayActivities = activities.slice(0, 10);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Recent Activity
        </h3>
      </div>
      
      <div className="max-h-96 overflow-y-auto">
        <AnimatePresence>
          {displayActivities.map((activity, index) => (
            <motion.div
              key={activity.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ delay: index * 0.05 }}
              className="px-6 py-3 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                  <span className="text-blue-600 dark:text-blue-400 text-sm">
                    {activity.username.charAt(0).toUpperCase()}
                  </span>
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {activity.username}
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {activity.action}
                    </span>
                    <span className="text-sm text-blue-600 dark:text-blue-400">
                      {activity.resource}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {new Date(activity.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {displayActivities.length === 0 && (
          <div className="px-6 py-8 text-center">
            <p className="text-gray-500 dark:text-gray-400">No recent activity</p>
          </div>
        )}
      </div>
    </div>
  );
};

// Projects Overview Component
const ProjectsOverview: React.FC = () => {
  const { data: projects, isLoading } = useAPIResource<Project[]>(API_ENDPOINTS.PROJECTS.LIST);

  const projectStats = useMemo(() => {
    if (!projects) return { total: 0, active: 0, deployed: 0, errors: 0 };
    
    return {
      total: projects.length,
      active: projects.filter(p => p.status === 'active').length,
      deployed: projects.filter(p => p.status === 'deployed').length,
      errors: projects.filter(p => p.status === 'error').length,
    };
  }, [projects]);

  const statusColors = {
    active: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
    building: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
    deployed: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    error: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300',
  };

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/4"></div>
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Projects Overview
          </h3>
          <div className="flex items-center space-x-4 text-sm">
            <span className="text-gray-500 dark:text-gray-400">
              {projectStats.active} active
            </span>
            <span className="text-gray-500 dark:text-gray-400">
              {projectStats.deployed} deployed
            </span>
            {projectStats.errors > 0 && (
              <span className="text-red-500 dark:text-red-400">
                {projectStats.errors} errors
              </span>
            )}
          </div>
        </div>
      </div>
      
      <div className="max-h-64 overflow-y-auto">
        {projects && projects.slice(0, 5).map((project, index) => (
          <motion.div
            key={project.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="px-6 py-4 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center text-white font-semibold">
                  {project.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                    {project.name}
                  </h4>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {project.framework} • {project.deployments_count} deployments
                  </p>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                <span className={cn(
                  'inline-flex px-2 py-1 text-xs font-semibold rounded-full',
                  statusColors[project.status]
                )}>
                  {project.status}
                </span>
                
                <div className="text-right text-xs text-gray-500 dark:text-gray-400">
                  <div>Uptime: {project.uptime.toFixed(1)}%</div>
                  <div>Last: {new Date(project.last_deployed).toLocaleDateString()}</div>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
        
        {projects && projects.length === 0 && (
          <div className="px-6 py-8 text-center">
            <p className="text-gray-500 dark:text-gray-400">No projects found</p>
          </div>
        )}
      </div>
    </div>
  );
};

// Connections Status Component
const ConnectionsStatus: React.FC = () => {
  const { data: connections, isLoading } = useAPIResource<Connection[]>(API_ENDPOINTS.CONNECTIONS.LIST);

  const connectionStats = useMemo(() => {
    if (!connections) return { total: 0, connected: 0, disconnected: 0, errors: 0 };
    
    return {
      total: connections.length,
      connected: connections.filter(c => c.status === 'connected').length,
      disconnected: connections.filter(c => c.status === 'disconnected').length,
      errors: connections.filter(c => c.status === 'error').length,
    };
  }, [connections]);

  const statusIcons = {
    connected: '🟢',
    disconnected: '🟡',
    error: '🔴',
  };

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Database Connections
          </h3>
          <div className="flex items-center space-x-2">
            <span className="text-sm text-green-600 dark:text-green-400">
              {connectionStats.connected} connected
            </span>
            {connectionStats.errors > 0 && (
              <span className="text-sm text-red-600 dark:text-red-400">
                {connectionStats.errors} errors
              </span>
            )}
          </div>
        </div>
      </div>
      
      <div className="max-h-48 overflow-y-auto">
        {connections && connections.slice(0, 4).map((connection, index) => (
          <motion.div
            key={connection.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="px-6 py-3 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <span className="text-lg">
                  {statusIcons[connection.status]}
                </span>
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                    {connection.name}
                  </h4>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {connection.type} • {connection.host}
                  </p>
                </div>
              </div>
              
              <div className="text-right text-xs text-gray-500 dark:text-gray-400">
                {connection.response_time && (
                  <div>{connection.response_time}ms</div>
                )}
                <div>
                  {new Date(connection.last_tested).toLocaleTimeString()}
                </div>
              </div>
            </div>
          </motion.div>
        ))}
        
        {connections && connections.length === 0 && (
          <div className="px-6 py-8 text-center">
            <p className="text-gray-500 dark:text-gray-400">No connections configured</p>
          </div>
        )}
      </div>
    </div>
  );
};

// Online Users Component
const OnlineUsers: React.FC = () => {
  const { onlineUsers } = useUserPresence();
  const { user } = useAuth();

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Online Users ({onlineUsers.length})
        </h3>
      </div>
      
      <div className="p-4">
        <div className="flex flex-wrap gap-2">
          {onlineUsers.slice(0, 8).map((userId, index) => (
            <motion.div
              key={userId}
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.1 }}
              className="relative"
            >
              <div className="w-10 h-10 rounded-full bg-gradient-to-r from-green-400 to-blue-500 flex items-center justify-center text-white font-medium text-sm">
                {userId === user?.user_id ? 'You' : userId.slice(0, 2).toUpperCase()}
              </div>
              <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-green-400 border-2 border-white rounded-full"></div>
            </motion.div>
          ))}
          
          {onlineUsers.length > 8 && (
            <div className="w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-gray-600 dark:text-gray-400 text-xs font-medium">
              +{onlineUsers.length - 8}
            </div>
          )}
        </div>
        
        {onlineUsers.length === 0 && (
          <p className="text-gray-500 dark:text-gray-400 text-center py-4">
            No users online
          </p>
        )}
      </div>
    </div>
  );
};

// Main Dashboard Component
const DashboardComponent: React.FC = () => {
  const { user } = useAuth();
  const { metrics, history } = useRealTimeMetrics();
  const { notifications, unreadCount } = useRealTimeNotifications();

  // Mock metrics - in real app, these would come from APIs
  const dashboardMetrics: DashboardMetric[] = [
    {
      id: 'active_users',
      title: 'Active Users',
      value: metrics?.activeUsers || 0,
      change: 12.5,
      trend: 'up',
      color: 'blue',
      icon: '👥',
      format: 'number'
    },
    {
      id: 'system_load',
      title: 'System Load',
      value: metrics?.systemLoad || 0,
      change: -5.2,
      trend: 'down',
      color: 'green',
      icon: '⚡',
      format: 'percentage'
    },
    {
      id: 'response_time',
      title: 'Avg Response Time',
      value: metrics?.responseTime || 0,
      change: 8.1,
      trend: 'up',
      color: 'yellow',
      icon: '🚀',
      format: 'time'
    },
    {
      id: 'error_rate',
      title: 'Error Rate',
      value: metrics?.errorRate || 0,
      change: -15.3,
      trend: 'down',
      color: 'red',
      icon: '🚨',
      format: 'percentage'
    },
    {
      id: 'api_calls',
      title: 'API Calls',
      value: metrics?.apiCalls || 0,
      change: 23.7,
      trend: 'up',
      color: 'purple',
      icon: '📊',
      format: 'number'
    },
    {
      id: 'memory_usage',
      title: 'Memory Usage',
      value: metrics?.memoryUsage || 0,
      change: 3.2,
      trend: 'up',
      color: 'blue',
      icon: '💾',
      format: 'bytes'
    }
  ];

  // Prepare chart data
  const chartData = useMemo(() => ({
    systemLoad: history.map(h => ({ timestamp: h.timestamp, value: h.systemLoad })),
    responseTime: history.map(h => ({ timestamp: h.timestamp, value: h.responseTime })),
    apiCalls: history.map(h => ({ timestamp: h.timestamp, value: h.apiCalls })),
    errorRate: history.map(h => ({ timestamp: h.timestamp, value: h.errorRate }))
  }), [history]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                Welcome back, {user?.full_name || user?.username}! 👋
              </h1>
              <p className="text-gray-600 dark:text-gray-400">
                Here's what's happening with your DafelHub projects
              </p>
            </div>
            
            {unreadCount > 0 && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="relative"
              >
                <RippleButton className="bg-gradient-to-r from-blue-600 to-purple-600">
                  Notifications
                </RippleButton>
                <div className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
                  {unreadCount}
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>

        {/* Metrics Grid */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-8"
        >
          {dashboardMetrics.map(metric => (
            <MetricCard key={metric.id} metric={metric} />
          ))}
        </motion.div>

        {/* Charts Row */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8"
        >
          <RealTimeChart
            title="System Load"
            data={chartData.systemLoad}
            color="#3B82F6"
            unit="%"
          />
          <RealTimeChart
            title="Response Time"
            data={chartData.responseTime}
            color="#10B981"
            unit="ms"
          />
          <RealTimeChart
            title="API Calls"
            data={chartData.apiCalls}
            color="#8B5CF6"
          />
          <RealTimeChart
            title="Error Rate"
            data={chartData.errorRate}
            color="#EF4444"
            unit="%"
          />
        </motion.div>

        {/* Bottom Row */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 lg:grid-cols-3 gap-8"
        >
          <div className="lg:col-span-1 space-y-8">
            <OnlineUsers />
            <ConnectionsStatus />
          </div>
          
          <div className="lg:col-span-1">
            <ProjectsOverview />
          </div>
          
          <div className="lg:col-span-1">
            <ActivityFeed />
          </div>
        </motion.div>

        {/* Floating Action Button for Quick Actions */}
        <FloatingActionButton
          position="bottom-right"
          icon="⚡"
          size="lg"
          onClick={() => {
            // Quick actions menu
            console.log('Quick actions');
          }}
        />
      </div>
    </div>
  );
};

// Export with auth protection
export const DashboardComponents = withAuth(DashboardComponent);

export default DashboardComponents;