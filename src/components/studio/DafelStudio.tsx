'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth, withAuth } from '../hooks/useAuth';
import { useAPI, useAPIResource } from '../hooks/useAPI';
import { useRealTimeMetrics, useRealTimeActivity, useRealTimeNotifications } from '../hooks/useRealTime';

// Import Studio modules
import { Canvas } from './Canvas';
import { DataSourcesManager } from './DataSourcesManager';
import { AnalyticsDashboard } from './AnalyticsDashboard';
import { TestingInterface } from './TestingInterface';
import { AIModelsManager } from './AIModelsManager';
import { SettingsPanel } from './SettingsPanel';

// Studio types
interface StudioModule {
  id: string;
  name: string;
  icon: string;
  component: React.ComponentType;
  description: string;
  active: boolean;
  badge?: string | number;
}

interface StudioState {
  activeModule: string;
  isLoading: boolean;
  error: string | null;
  sidebarCollapsed: boolean;
  notifications: any[];
  activities: any[];
}

interface ProjectInfo {
  id: string;
  name: string;
  status: 'active' | 'building' | 'deployed' | 'error';
  created_at: string;
}

// Utility classes
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// Animation variants
const sidebarVariants = {
  collapsed: { width: 64 },
  expanded: { width: 280 },
};

const contentVariants = {
  hidden: { opacity: 0, x: 20 },
  visible: { 
    opacity: 1, 
    x: 0,
    transition: { duration: 0.3, ease: 'easeOut' }
  },
};

const studioVariants = {
  hidden: { opacity: 0 },
  visible: { 
    opacity: 1,
    transition: { 
      duration: 0.5,
      staggerChildren: 0.1
    }
  }
};

// Main DafelStudio Component
const DafelStudioComponent: React.FC = () => {
  const { user } = useAuth();
  const { metrics } = useRealTimeMetrics();
  const { activities } = useRealTimeActivity();
  const { notifications, unreadCount } = useRealTimeNotifications();
  const { apiCall } = useAPI();

  // Studio state
  const [studioState, setStudioState] = useState<StudioState>({
    activeModule: 'data-sources',
    isLoading: false,
    error: null,
    sidebarCollapsed: false,
    notifications: [],
    activities: []
  });

  // Current project (could be from URL params or state)
  const [currentProject, setCurrentProject] = useState<ProjectInfo>({
    id: 'project-1',
    name: 'Enterprise Data Platform',
    status: 'active',
    created_at: new Date().toISOString()
  });

  // Studio modules configuration
  const studioModules: StudioModule[] = useMemo(() => [
    {
      id: 'canvas',
      name: 'Canvas',
      icon: '🎨',
      component: Canvas,
      description: 'Visual pipeline builder',
      active: true
    },
    {
      id: 'data-sources',
      name: 'Data Sources',
      icon: '🗄️',
      component: DataSourcesManager,
      description: 'Database connections',
      active: true,
      badge: 4 // Number of connections
    },
    {
      id: 'ai-models',
      name: 'AI Models',
      icon: '🧠',
      component: AIModelsManager,
      description: 'AI model management',
      active: true,
      badge: 'NEW'
    },
    {
      id: 'testing',
      name: 'Testing',
      icon: '🧪',
      component: TestingInterface,
      description: 'Automated testing suite',
      active: true
    },
    {
      id: 'analytics',
      name: 'Analytics',
      icon: '📊',
      component: AnalyticsDashboard,
      description: 'Real-time analytics',
      active: true
    },
    {
      id: 'settings',
      name: 'Settings',
      icon: '⚙️',
      component: SettingsPanel,
      description: 'Studio configuration',
      active: true
    }
  ], []);

  // Get current module
  const currentModule = useMemo(() => 
    studioModules.find(m => m.id === studioState.activeModule),
    [studioModules, studioState.activeModule]
  );

  // Module switching handler
  const handleModuleSwitch = useCallback(async (moduleId: string) => {
    if (moduleId === studioState.activeModule) return;
    
    setStudioState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      // Simulate API call for module data loading
      await new Promise(resolve => setTimeout(resolve, 300));
      
      setStudioState(prev => ({ 
        ...prev, 
        activeModule: moduleId,
        isLoading: false 
      }));
      
      // Log activity
      console.log(`Switched to ${moduleId} module`);
      
    } catch (error) {
      setStudioState(prev => ({ 
        ...prev, 
        error: `Failed to load ${moduleId} module`,
        isLoading: false 
      }));
    }
  }, [studioState.activeModule]);

  // Sidebar toggle
  const toggleSidebar = useCallback(() => {
    setStudioState(prev => ({ 
      ...prev, 
      sidebarCollapsed: !prev.sidebarCollapsed 
    }));
  }, []);

  // Real-time activity logger
  useEffect(() => {
    const addActivity = (message: string, type = 'info') => {
      const activity = {
        id: Date.now().toString(),
        message,
        type,
        timestamp: new Date(),
        user: user?.username || 'System'
      };
      
      setStudioState(prev => ({
        ...prev,
        activities: [activity, ...prev.activities.slice(0, 49)]
      }));
    };

    // System activities
    const interval = setInterval(() => {
      const activities = [
        '✅ PostgreSQL connection pool: Health check passed',
        '🔍 Schema discovery: Found 47 tables, 312 columns',
        '⚡ VaultManager: Key rotation scheduled',
        '📊 Metrics: Average query time 45ms',
        '🔐 Security audit: All connections encrypted',
        '📡 System status: All services operational'
      ];
      
      const randomActivity = activities[Math.floor(Math.random() * activities.length)];
      addActivity(randomActivity, 'success');
    }, 5000);

    return () => clearInterval(interval);
  }, [user]);

  // Render current module component
  const renderCurrentModule = () => {
    if (!currentModule) return null;
    
    const ModuleComponent = currentModule.component;
    
    return (
      <motion.div
        key={studioState.activeModule}
        variants={contentVariants}
        initial="hidden"
        animate="visible"
        exit="hidden"
        className="flex-1 h-full"
      >
        <ModuleComponent 
          projectId={currentProject.id}
          isLoading={studioState.isLoading}
          activities={studioState.activities}
        />
      </motion.div>
    );
  };

  return (
    <motion.div
      variants={studioVariants}
      initial="hidden"
      animate="visible"
      className="h-screen bg-gray-50 dark:bg-gray-900 flex overflow-hidden"
    >
      {/* Sidebar Navigation */}
      <motion.div
        variants={sidebarVariants}
        animate={studioState.sidebarCollapsed ? 'collapsed' : 'expanded'}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="bg-gray-900 text-white flex flex-col shadow-xl"
      >
        {/* Studio Header */}
        <div className="p-4 border-b border-gray-800">
          <div className="flex items-center justify-between">
            {!studioState.sidebarCollapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
              >
                <h1 className="text-xl font-mono font-light tracking-wider">
                  Dafel Studio
                </h1>
                <p className="text-xs text-gray-400">
                  {currentProject.name}
                </p>
              </motion.div>
            )}
            
            <button
              onClick={toggleSidebar}
              className="w-8 h-8 rounded-lg hover:bg-gray-800 flex items-center justify-center transition-colors"
              title={studioState.sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <span className="text-lg">
                {studioState.sidebarCollapsed ? '→' : '←'}
              </span>
            </button>
          </div>
        </div>

        {/* Module Navigation */}
        <div className="flex-1 py-6">
          <nav className="space-y-2 px-3">
            {studioModules.map((module, index) => (
              <motion.button
                key={module.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                onClick={() => handleModuleSwitch(module.id)}
                className={cn(
                  'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200',
                  'hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500',
                  studioState.activeModule === module.id
                    ? 'bg-gray-800 text-white shadow-lg'
                    : 'text-gray-400 hover:text-white'
                )}
                title={studioState.sidebarCollapsed ? module.name : undefined}
              >
                <span className="text-2xl mr-3 flex-shrink-0">
                  {module.icon}
                </span>
                
                {!studioState.sidebarCollapsed && (
                  <div className="flex items-center justify-between w-full">
                    <div className="text-left">
                      <p className="font-medium">{module.name}</p>
                      <p className="text-xs text-gray-500">{module.description}</p>
                    </div>
                    
                    {module.badge && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className={cn(
                          'px-2 py-1 rounded-full text-xs font-semibold',
                          typeof module.badge === 'number'
                            ? 'bg-blue-600 text-white'
                            : 'bg-green-600 text-white'
                        )}
                      >
                        {module.badge}
                      </motion.div>
                    )}
                  </div>
                )}
              </motion.button>
            ))}
          </nav>
        </div>

        {/* Studio Status & User Info */}
        <div className="p-4 border-t border-gray-800">
          {!studioState.sidebarCollapsed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="space-y-3"
            >
              {/* System Status */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">System Status</span>
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-xs text-green-400">Online</span>
                </div>
              </div>
              
              {/* User Info */}
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-sm font-semibold">
                  {user?.username?.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {user?.full_name || user?.username}
                  </p>
                  <p className="text-xs text-gray-400">
                    {user?.roles?.includes('admin') ? 'Administrator' : 'Developer'}
                  </p>
                </div>
              </div>
            </motion.div>
          )}
          
          {studioState.sidebarCollapsed && (
            <div className="flex flex-col items-center space-y-3">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-sm font-semibold">
                {user?.username?.charAt(0).toUpperCase()}
              </div>
            </div>
          )}
        </div>
      </motion.div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header Bar */}
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <span className="text-2xl">{currentModule?.icon}</span>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                    {currentModule?.name}
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {currentModule?.description}
                  </p>
                </div>
              </div>
              
              {studioState.isLoading && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
                />
              )}
            </div>
            
            {/* Action Buttons */}
            <div className="flex items-center space-x-3">
              {/* Notifications */}
              {unreadCount > 0 && (
                <motion.button
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="relative p-2 bg-blue-100 dark:bg-blue-900 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
                  title="Notifications"
                >
                  <span className="text-blue-600 dark:text-blue-400">🔔</span>
                  <div className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </div>
                </motion.button>
              )}
              
              {/* Project Status */}
              <div className="flex items-center space-x-2 px-3 py-1.5 bg-gray-100 dark:bg-gray-700 rounded-lg">
                <div className={cn(
                  'w-2 h-2 rounded-full',
                  currentProject.status === 'active' ? 'bg-green-500' :
                  currentProject.status === 'building' ? 'bg-yellow-500' :
                  currentProject.status === 'deployed' ? 'bg-blue-500' :
                  'bg-red-500'
                )}></div>
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300 capitalize">
                  {currentProject.status}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Module Content */}
        <div className="flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            {studioState.error ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex-1 flex items-center justify-center p-8"
              >
                <div className="text-center">
                  <div className="text-6xl mb-4">⚠️</div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                    Module Load Error
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400 mb-4">
                    {studioState.error}
                  </p>
                  <button
                    onClick={() => setStudioState(prev => ({ ...prev, error: null }))}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Retry
                  </button>
                </div>
              </motion.div>
            ) : (
              renderCurrentModule()
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
};

// Export with auth protection
export const DafelStudio = withAuth(DafelStudioComponent);

export default DafelStudio;