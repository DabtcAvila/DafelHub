'use client';

import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '../hooks/useAuth';
import { GlowCard } from '../InteractiveElements';

// Settings types
interface StudioSettings {
  general: {
    theme: 'light' | 'dark' | 'auto';
    language: string;
    timezone: string;
    auto_save: boolean;
    auto_refresh_interval: number;
  };
  canvas: {
    grid_enabled: boolean;
    snap_to_grid: boolean;
    grid_size: number;
    default_zoom: number;
    auto_layout: boolean;
  };
  connections: {
    connection_timeout: number;
    max_pool_size: number;
    retry_attempts: number;
    health_check_interval: number;
  };
  security: {
    session_timeout: number;
    mfa_required: boolean;
    audit_logging: boolean;
    ip_whitelist_enabled: boolean;
    encryption_at_rest: boolean;
  };
  notifications: {
    email_enabled: boolean;
    push_enabled: boolean;
    error_alerts: boolean;
    performance_alerts: boolean;
    security_alerts: boolean;
  };
}

// Mock default settings
const DEFAULT_SETTINGS: StudioSettings = {
  general: {
    theme: 'auto',
    language: 'en',
    timezone: 'UTC',
    auto_save: true,
    auto_refresh_interval: 5000
  },
  canvas: {
    grid_enabled: true,
    snap_to_grid: true,
    grid_size: 20,
    default_zoom: 100,
    auto_layout: false
  },
  connections: {
    connection_timeout: 30,
    max_pool_size: 10,
    retry_attempts: 3,
    health_check_interval: 60
  },
  security: {
    session_timeout: 3600,
    mfa_required: false,
    audit_logging: true,
    ip_whitelist_enabled: false,
    encryption_at_rest: true
  },
  notifications: {
    email_enabled: true,
    push_enabled: false,
    error_alerts: true,
    performance_alerts: true,
    security_alerts: true
  }
};

export const SettingsPanel: React.FC<{
  projectId: string;
  isLoading?: boolean;
  activities?: any[];
}> = ({ projectId, isLoading, activities = [] }) => {
  const { user } = useAuth();
  const [settings, setSettings] = useState<StudioSettings>(DEFAULT_SETTINGS);
  const [activeTab, setActiveTab] = useState<keyof StudioSettings>('general');
  const [hasChanges, setHasChanges] = useState(false);

  // Settings tabs
  const settingsTabs = [
    { id: 'general', name: 'General', icon: '⚙️' },
    { id: 'canvas', name: 'Canvas', icon: '🎨' },
    { id: 'connections', name: 'Connections', icon: '🔗' },
    { id: 'security', name: 'Security', icon: '🔒' },
    { id: 'notifications', name: 'Notifications', icon: '🔔' }
  ] as const;

  // Update setting value
  const updateSetting = useCallback((section: keyof StudioSettings, key: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }));
    setHasChanges(true);
  }, []);

  // Save settings
  const handleSave = useCallback(async () => {
    try {
      // In a real app, this would call the API
      console.log('Saving settings:', settings);
      setHasChanges(false);
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  }, [settings]);

  // Reset settings
  const handleReset = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
    setHasChanges(false);
  }, []);

  // Render setting field
  const renderSettingField = (
    label: string,
    value: any,
    type: 'text' | 'number' | 'boolean' | 'select',
    section: keyof StudioSettings,
    key: string,
    options?: Array<{ value: any; label: string }>,
    description?: string
  ) => (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {label}
        </label>
        {type === 'boolean' && (
          <button
            onClick={() => updateSetting(section, key, !value)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              value ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                value ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        )}
      </div>
      
      {type !== 'boolean' && (
        <div>
          {type === 'select' && options ? (
            <select
              value={value}
              onChange={(e) => updateSetting(section, key, e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white text-sm"
            >
              {options.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : type === 'number' ? (
            <input
              type="number"
              value={value}
              onChange={(e) => updateSetting(section, key, parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white text-sm"
            />
          ) : (
            <input
              type="text"
              value={value}
              onChange={(e) => updateSetting(section, key, e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white text-sm"
            />
          )}
        </div>
      )}
      
      {description && (
        <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
      )}
    </div>
  );

  return (
    <div className="h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              Studio Settings
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Configure your DafelHub Studio preferences
            </p>
          </div>
          
          {hasChanges && (
            <div className="flex items-center space-x-3">
              <button
                onClick={handleReset}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Reset
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
              >
                <span>💾</span>
                <span>Save Changes</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Settings Tabs */}
        <div className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 p-4">
          <nav className="space-y-2">
            {settingsTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-left transition-colors ${
                  activeTab === tab.id
                    ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                <span className="text-lg">{tab.icon}</span>
                <span className="font-medium">{tab.name}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Settings Content */}
        <div className="flex-1 p-6 overflow-y-auto">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3 }}
            className="max-w-2xl"
          >
            {/* General Settings */}
            {activeTab === 'general' && (
              <GlowCard className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
                  General Preferences
                </h3>
                
                <div className="space-y-6">
                  {renderSettingField(
                    'Theme',
                    settings.general.theme,
                    'select',
                    'general',
                    'theme',
                    [
                      { value: 'light', label: 'Light' },
                      { value: 'dark', label: 'Dark' },
                      { value: 'auto', label: 'Auto (System)' }
                    ],
                    'Choose your preferred color scheme'
                  )}
                  
                  {renderSettingField(
                    'Language',
                    settings.general.language,
                    'select',
                    'general',
                    'language',
                    [
                      { value: 'en', label: 'English' },
                      { value: 'es', label: 'Spanish' },
                      { value: 'fr', label: 'French' },
                      { value: 'de', label: 'German' }
                    ]
                  )}
                  
                  {renderSettingField(
                    'Timezone',
                    settings.general.timezone,
                    'select',
                    'general',
                    'timezone',
                    [
                      { value: 'UTC', label: 'UTC' },
                      { value: 'America/New_York', label: 'Eastern Time' },
                      { value: 'America/Los_Angeles', label: 'Pacific Time' },
                      { value: 'Europe/London', label: 'London' },
                      { value: 'Europe/Paris', label: 'Paris' }
                    ]
                  )}
                  
                  {renderSettingField(
                    'Auto Save',
                    settings.general.auto_save,
                    'boolean',
                    'general',
                    'auto_save',
                    undefined,
                    'Automatically save your work'
                  )}
                  
                  {renderSettingField(
                    'Auto Refresh Interval (ms)',
                    settings.general.auto_refresh_interval,
                    'number',
                    'general',
                    'auto_refresh_interval',
                    undefined,
                    'How often to refresh real-time data'
                  )}
                </div>
              </GlowCard>
            )}

            {/* Canvas Settings */}
            {activeTab === 'canvas' && (
              <GlowCard className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
                  Canvas Configuration
                </h3>
                
                <div className="space-y-6">
                  {renderSettingField(
                    'Show Grid',
                    settings.canvas.grid_enabled,
                    'boolean',
                    'canvas',
                    'grid_enabled',
                    undefined,
                    'Display grid lines on canvas'
                  )}
                  
                  {renderSettingField(
                    'Snap to Grid',
                    settings.canvas.snap_to_grid,
                    'boolean',
                    'canvas',
                    'snap_to_grid',
                    undefined,
                    'Align components to grid when moving'
                  )}
                  
                  {renderSettingField(
                    'Grid Size (px)',
                    settings.canvas.grid_size,
                    'number',
                    'canvas',
                    'grid_size',
                    undefined,
                    'Size of grid cells in pixels'
                  )}
                  
                  {renderSettingField(
                    'Default Zoom (%)',
                    settings.canvas.default_zoom,
                    'number',
                    'canvas',
                    'default_zoom',
                    undefined,
                    'Default zoom level when opening canvas'
                  )}
                  
                  {renderSettingField(
                    'Auto Layout',
                    settings.canvas.auto_layout,
                    'boolean',
                    'canvas',
                    'auto_layout',
                    undefined,
                    'Automatically arrange components'
                  )}
                </div>
              </GlowCard>
            )}

            {/* Connection Settings */}
            {activeTab === 'connections' && (
              <GlowCard className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
                  Database Connections
                </h3>
                
                <div className="space-y-6">
                  {renderSettingField(
                    'Connection Timeout (seconds)',
                    settings.connections.connection_timeout,
                    'number',
                    'connections',
                    'connection_timeout',
                    undefined,
                    'Maximum time to wait for connection'
                  )}
                  
                  {renderSettingField(
                    'Max Pool Size',
                    settings.connections.max_pool_size,
                    'number',
                    'connections',
                    'max_pool_size',
                    undefined,
                    'Maximum number of pooled connections'
                  )}
                  
                  {renderSettingField(
                    'Retry Attempts',
                    settings.connections.retry_attempts,
                    'number',
                    'connections',
                    'retry_attempts',
                    undefined,
                    'Number of connection retry attempts'
                  )}
                  
                  {renderSettingField(
                    'Health Check Interval (seconds)',
                    settings.connections.health_check_interval,
                    'number',
                    'connections',
                    'health_check_interval',
                    undefined,
                    'How often to check connection health'
                  )}
                </div>
              </GlowCard>
            )}

            {/* Security Settings */}
            {activeTab === 'security' && (
              <GlowCard className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
                  Security Configuration
                </h3>
                
                <div className="space-y-6">
                  {renderSettingField(
                    'Session Timeout (seconds)',
                    settings.security.session_timeout,
                    'number',
                    'security',
                    'session_timeout',
                    undefined,
                    'Automatic logout after inactivity'
                  )}
                  
                  {renderSettingField(
                    'Require Multi-Factor Authentication',
                    settings.security.mfa_required,
                    'boolean',
                    'security',
                    'mfa_required',
                    undefined,
                    'Force MFA for all users'
                  )}
                  
                  {renderSettingField(
                    'Audit Logging',
                    settings.security.audit_logging,
                    'boolean',
                    'security',
                    'audit_logging',
                    undefined,
                    'Log all user activities'
                  )}
                  
                  {renderSettingField(
                    'IP Whitelist',
                    settings.security.ip_whitelist_enabled,
                    'boolean',
                    'security',
                    'ip_whitelist_enabled',
                    undefined,
                    'Restrict access to specific IP addresses'
                  )}
                  
                  {renderSettingField(
                    'Encryption at Rest',
                    settings.security.encryption_at_rest,
                    'boolean',
                    'security',
                    'encryption_at_rest',
                    undefined,
                    'Encrypt stored data and credentials'
                  )}
                </div>
              </GlowCard>
            )}

            {/* Notification Settings */}
            {activeTab === 'notifications' && (
              <GlowCard className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
                  Notification Preferences
                </h3>
                
                <div className="space-y-6">
                  {renderSettingField(
                    'Email Notifications',
                    settings.notifications.email_enabled,
                    'boolean',
                    'notifications',
                    'email_enabled',
                    undefined,
                    'Receive notifications via email'
                  )}
                  
                  {renderSettingField(
                    'Push Notifications',
                    settings.notifications.push_enabled,
                    'boolean',
                    'notifications',
                    'push_enabled',
                    undefined,
                    'Receive browser push notifications'
                  )}
                  
                  {renderSettingField(
                    'Error Alerts',
                    settings.notifications.error_alerts,
                    'boolean',
                    'notifications',
                    'error_alerts',
                    undefined,
                    'Notify when errors occur'
                  )}
                  
                  {renderSettingField(
                    'Performance Alerts',
                    settings.notifications.performance_alerts,
                    'boolean',
                    'notifications',
                    'performance_alerts',
                    undefined,
                    'Notify about performance issues'
                  )}
                  
                  {renderSettingField(
                    'Security Alerts',
                    settings.notifications.security_alerts,
                    'boolean',
                    'notifications',
                    'security_alerts',
                    undefined,
                    'Notify about security events'
                  )}
                </div>
              </GlowCard>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
};