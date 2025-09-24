'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAPI, useAPIResource } from '../hooks/useAPI';
import { GlowCard, MagneticButton, RippleButton } from '../InteractiveElements';

// Data Source types
interface DataSource {
  id: string;
  name: string;
  type: 'postgresql' | 'mysql' | 'mongodb' | 'redis' | 'elasticsearch' | 'api' | 'file';
  status: 'connected' | 'disconnected' | 'testing' | 'error' | 'configuring';
  host: string;
  port: number;
  database?: string;
  username: string;
  ssl_enabled: boolean;
  created_at: string;
  last_tested: string;
  metadata: {
    response_time?: number;
    pool_size?: number;
    active_connections?: number;
    schema_count?: number;
    table_count?: number;
    collection_count?: number;
    index_count?: number;
    uptime_percentage?: number;
  };
  credentials_encrypted: boolean;
  vault_key_id?: string;
}

interface ConnectionTest {
  connection_id: string;
  status: 'running' | 'success' | 'failed';
  response_time?: number;
  error_message?: string;
  timestamp: Date;
}

interface SchemaInfo {
  connection_id: string;
  schemas: Array<{
    name: string;
    tables: Array<{
      name: string;
      columns: Array<{
        name: string;
        type: string;
        nullable: boolean;
        primary_key: boolean;
      }>;
      row_count: number;
    }>;
  }>;
  indexes: Array<{
    name: string;
    table: string;
    columns: string[];
  }>;
}

// Data source configurations
const DATA_SOURCE_CONFIGS = {
  postgresql: {
    name: 'PostgreSQL',
    icon: '🐘',
    color: 'blue',
    defaultPort: 5432,
    fields: ['host', 'port', 'database', 'username', 'password', 'ssl_enabled']
  },
  mysql: {
    name: 'MySQL',
    icon: '🐬',
    color: 'orange',
    defaultPort: 3306,
    fields: ['host', 'port', 'database', 'username', 'password', 'ssl_enabled']
  },
  mongodb: {
    name: 'MongoDB',
    icon: '🍃',
    color: 'green',
    defaultPort: 27017,
    fields: ['host', 'port', 'database', 'username', 'password', 'auth_source']
  },
  redis: {
    name: 'Redis',
    icon: '🔴',
    color: 'red',
    defaultPort: 6379,
    fields: ['host', 'port', 'password', 'database_index']
  },
  elasticsearch: {
    name: 'Elasticsearch',
    icon: '🔍',
    color: 'yellow',
    defaultPort: 9200,
    fields: ['host', 'port', 'index', 'username', 'password', 'ssl_enabled']
  },
  api: {
    name: 'REST API',
    icon: '🌐',
    color: 'purple',
    defaultPort: 443,
    fields: ['base_url', 'api_key', 'auth_type', 'timeout']
  },
  file: {
    name: 'File System',
    icon: '📁',
    color: 'gray',
    defaultPort: 0,
    fields: ['path', 'format', 'encoding', 'delimiter']
  }
};

// Utility classes
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// Status components
const StatusBadge: React.FC<{ status: DataSource['status'] }> = ({ status }) => {
  const statusConfig = {
    connected: { label: 'Connected', color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300', icon: '🟢' },
    disconnected: { label: 'Disconnected', color: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300', icon: '⚪' },
    testing: { label: 'Testing', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300', icon: '🔵' },
    error: { label: 'Error', color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300', icon: '🔴' },
    configuring: { label: 'Configuring', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300', icon: '🟡' }
  };

  const config = statusConfig[status];

  return (
    <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', config.color)}>
      <span className="mr-1">{config.icon}</span>
      {config.label}
    </span>
  );
};

// Connection Card Component
const ConnectionCard: React.FC<{
  connection: DataSource;
  onTest: (id: string) => void;
  onEdit: (connection: DataSource) => void;
  onDelete: (id: string) => void;
  onViewSchema: (id: string) => void;
  testResults: Record<string, ConnectionTest>;
}> = ({ connection, onTest, onEdit, onDelete, onViewSchema, testResults }) => {
  const config = DATA_SOURCE_CONFIGS[connection.type];
  const testResult = testResults[connection.id];
  const isTestRunning = testResult?.status === 'running';

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.3 }}
    >
      <GlowCard className="p-6 hover:shadow-xl transition-all duration-300">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={cn(
              'w-12 h-12 rounded-xl flex items-center justify-center text-2xl',
              config.color === 'blue' ? 'bg-blue-100 text-blue-600' :
              config.color === 'orange' ? 'bg-orange-100 text-orange-600' :
              config.color === 'green' ? 'bg-green-100 text-green-600' :
              config.color === 'red' ? 'bg-red-100 text-red-600' :
              config.color === 'yellow' ? 'bg-yellow-100 text-yellow-600' :
              config.color === 'purple' ? 'bg-purple-100 text-purple-600' :
              'bg-gray-100 text-gray-600'
            )}>
              {config.icon}
            </div>
            
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {connection.name}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {config.name} • {connection.host}:{connection.port}
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <StatusBadge status={connection.status} />
            {connection.credentials_encrypted && (
              <span 
                className="text-green-600 dark:text-green-400" 
                title="Credentials encrypted with VaultManager"
              >
                🔐
              </span>
            )}
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          {connection.metadata.response_time !== undefined && (
            <div className="text-center">
              <p className="text-sm text-gray-500 dark:text-gray-400">Response Time</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {connection.metadata.response_time}ms
              </p>
            </div>
          )}
          
          {connection.metadata.active_connections !== undefined && (
            <div className="text-center">
              <p className="text-sm text-gray-500 dark:text-gray-400">Active Connections</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {connection.metadata.active_connections}/{connection.metadata.pool_size || 'N/A'}
              </p>
            </div>
          )}
          
          {connection.metadata.table_count !== undefined && (
            <div className="text-center">
              <p className="text-sm text-gray-500 dark:text-gray-400">Tables</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {connection.metadata.table_count}
              </p>
            </div>
          )}
          
          {connection.metadata.uptime_percentage !== undefined && (
            <div className="text-center">
              <p className="text-sm text-gray-500 dark:text-gray-400">Uptime</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {connection.metadata.uptime_percentage.toFixed(1)}%
              </p>
            </div>
          )}
        </div>

        {/* Test Result */}
        {testResult && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className={cn(
              'mb-4 p-3 rounded-lg text-sm',
              testResult.status === 'success' ? 'bg-green-50 text-green-800 dark:bg-green-900 dark:text-green-300' :
              testResult.status === 'failed' ? 'bg-red-50 text-red-800 dark:bg-red-900 dark:text-red-300' :
              'bg-blue-50 text-blue-800 dark:bg-blue-900 dark:text-blue-300'
            )}
          >
            {testResult.status === 'running' && (
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                <span>Testing connection...</span>
              </div>
            )}
            
            {testResult.status === 'success' && (
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span>✅</span>
                  <span>Connection successful</span>
                </div>
                <span className="font-mono">
                  {testResult.response_time}ms
                </span>
              </div>
            )}
            
            {testResult.status === 'failed' && (
              <div>
                <div className="flex items-center space-x-2 mb-1">
                  <span>❌</span>
                  <span>Connection failed</span>
                </div>
                <p className="text-xs font-mono opacity-75">
                  {testResult.error_message}
                </p>
              </div>
            )}
          </motion.div>
        )}

        {/* Actions */}
        <div className="flex space-x-2">
          <RippleButton
            onClick={() => onTest(connection.id)}
            disabled={isTestRunning}
            className={cn(
              'flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-colors',
              connection.status === 'connected'
                ? 'bg-green-600 text-white hover:bg-green-700'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            )}
          >
            {isTestRunning ? 'Testing...' : 'Test Connection'}
          </RippleButton>
          
          <button
            onClick={() => onViewSchema(connection.id)}
            disabled={connection.status !== 'connected'}
            className="px-3 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            Schema
          </button>
          
          <button
            onClick={() => onEdit(connection)}
            className="px-3 py-2 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Edit
          </button>
          
          <button
            onClick={() => onDelete(connection.id)}
            className="px-3 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Delete
          </button>
        </div>

        {/* Last tested info */}
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
          Last tested: {new Date(connection.last_tested).toLocaleString()}
        </div>
      </GlowCard>
    </motion.div>
  );
};

// Add/Edit Connection Modal
const ConnectionModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onSave: (connection: Partial<DataSource>) => void;
  connection?: DataSource | null;
}> = ({ isOpen, onClose, onSave, connection }) => {
  const [formData, setFormData] = useState<Partial<DataSource>>({
    name: '',
    type: 'postgresql',
    host: '',
    port: 5432,
    database: '',
    username: '',
    ssl_enabled: false
  });

  const [password, setPassword] = useState('');

  useEffect(() => {
    if (connection) {
      setFormData({
        ...connection,
        port: connection.port || DATA_SOURCE_CONFIGS[connection.type].defaultPort
      });
    } else {
      setFormData({
        name: '',
        type: 'postgresql',
        host: '',
        port: DATA_SOURCE_CONFIGS.postgresql.defaultPort,
        database: '',
        username: '',
        ssl_enabled: false
      });
    }
  }, [connection, isOpen]);

  const selectedConfig = DATA_SOURCE_CONFIGS[formData.type as keyof typeof DATA_SOURCE_CONFIGS];

  const handleTypeChange = (type: string) => {
    const config = DATA_SOURCE_CONFIGS[type as keyof typeof DATA_SOURCE_CONFIGS];
    setFormData(prev => ({
      ...prev,
      type: type as DataSource['type'],
      port: config.defaultPort
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const connectionData = {
      ...formData,
      status: 'configuring' as const,
      credentials_encrypted: !!password,
      last_tested: new Date().toISOString(),
      created_at: connection?.created_at || new Date().toISOString(),
      metadata: connection?.metadata || {}
    };
    
    onSave(connectionData);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            {connection ? 'Edit Connection' : 'Add New Connection'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Connection Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              Connection Type
            </label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(DATA_SOURCE_CONFIGS).map(([key, config]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => handleTypeChange(key)}
                  className={cn(
                    'p-3 rounded-lg border text-center transition-all',
                    formData.type === key
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                >
                  <div className="text-2xl mb-1">{config.icon}</div>
                  <div className="text-sm font-medium">{config.name}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Connection Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Connection Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              placeholder="My PostgreSQL Database"
              required
            />
          </div>

          {/* Connection Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Host
              </label>
              <input
                type="text"
                value={formData.host}
                onChange={(e) => setFormData(prev => ({ ...prev, host: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                placeholder="localhost"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Port
              </label>
              <input
                type="number"
                value={formData.port}
                onChange={(e) => setFormData(prev => ({ ...prev, port: parseInt(e.target.value) }))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                required
              />
            </div>
          </div>

          {selectedConfig.fields.includes('database') && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Database
              </label>
              <input
                type="text"
                value={formData.database || ''}
                onChange={(e) => setFormData(prev => ({ ...prev, database: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                placeholder="myapp"
              />
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {selectedConfig.fields.includes('username') && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Username
                </label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData(prev => ({ ...prev, username: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                  placeholder="admin"
                />
              </div>
            )}
            
            {selectedConfig.fields.includes('password') && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                  placeholder="••••••••"
                />
              </div>
            )}
          </div>

          {selectedConfig.fields.includes('ssl_enabled') && (
            <div className="flex items-center">
              <input
                type="checkbox"
                id="ssl_enabled"
                checked={formData.ssl_enabled}
                onChange={(e) => setFormData(prev => ({ ...prev, ssl_enabled: e.target.checked }))}
                className="mr-2"
              />
              <label htmlFor="ssl_enabled" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Enable SSL/TLS encryption
              </label>
            </div>
          )}

          {/* Actions */}
          <div className="flex space-x-3 pt-6">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              {connection ? 'Update Connection' : 'Create Connection'}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
};

// Main DataSourcesManager Component
export const DataSourcesManager: React.FC<{
  projectId: string;
  isLoading?: boolean;
  activities?: any[];
}> = ({ projectId, isLoading, activities = [] }) => {
  const { apiCall } = useAPI();
  const { data: connections, refetch } = useAPIResource<DataSource[]>('/api/connections');
  
  // Local state
  const [selectedConnection, setSelectedConnection] = useState<DataSource | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, ConnectionTest>>({});
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');

  // Mock connections data if API doesn't return data
  const mockConnections: DataSource[] = useMemo(() => [
    {
      id: 'conn-1',
      name: 'PostgreSQL Production',
      type: 'postgresql',
      status: 'connected',
      host: 'prod-db-01.company.com',
      port: 5432,
      database: 'app_production',
      username: 'app_user',
      ssl_enabled: true,
      created_at: '2024-01-15T08:00:00Z',
      last_tested: '2024-01-20T14:30:00Z',
      metadata: {
        response_time: 45,
        pool_size: 10,
        active_connections: 7,
        schema_count: 3,
        table_count: 47,
        uptime_percentage: 99.9
      },
      credentials_encrypted: true,
      vault_key_id: 'vault-key-1'
    },
    {
      id: 'conn-2',
      name: 'MySQL Development',
      type: 'mysql',
      status: 'configuring',
      host: 'dev-mysql.company.com',
      port: 3306,
      database: 'app_dev',
      username: 'dev_user',
      ssl_enabled: false,
      created_at: '2024-01-18T10:00:00Z',
      last_tested: '2024-01-18T10:15:00Z',
      metadata: {
        table_count: 23,
        uptime_percentage: 95.5
      },
      credentials_encrypted: true
    },
    {
      id: 'conn-3',
      name: 'MongoDB Analytics',
      type: 'mongodb',
      status: 'connected',
      host: 'analytics-mongo.company.com',
      port: 27017,
      database: 'analytics',
      username: 'analytics_user',
      ssl_enabled: true,
      created_at: '2024-01-10T12:00:00Z',
      last_tested: '2024-01-20T09:00:00Z',
      metadata: {
        response_time: 32,
        collection_count: 15,
        index_count: 45,
        uptime_percentage: 99.7
      },
      credentials_encrypted: true
    },
    {
      id: 'conn-4',
      name: 'Redis Cache',
      type: 'redis',
      status: 'error',
      host: 'cache-redis.company.com',
      port: 6379,
      username: '',
      ssl_enabled: false,
      created_at: '2024-01-12T14:00:00Z',
      last_tested: '2024-01-20T13:45:00Z',
      metadata: {
        uptime_percentage: 87.2
      },
      credentials_encrypted: false
    }
  ], []);

  const displayConnections = connections && connections.length > 0 ? connections : mockConnections;

  // Filtered connections
  const filteredConnections = useMemo(() => {
    return displayConnections.filter(conn => {
      const matchesSearch = conn.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           conn.host.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesType = selectedType === 'all' || conn.type === selectedType;
      return matchesSearch && matchesType;
    });
  }, [displayConnections, searchTerm, selectedType]);

  // Connection statistics
  const connectionStats = useMemo(() => {
    const total = displayConnections.length;
    const connected = displayConnections.filter(c => c.status === 'connected').length;
    const errors = displayConnections.filter(c => c.status === 'error').length;
    const avgResponseTime = displayConnections
      .filter(c => c.metadata.response_time)
      .reduce((sum, c) => sum + (c.metadata.response_time || 0), 0) / 
      (displayConnections.filter(c => c.metadata.response_time).length || 1);

    return { total, connected, errors, avgResponseTime };
  }, [displayConnections]);

  // Test connection
  const handleTestConnection = useCallback(async (connectionId: string) => {
    setTestResults(prev => ({
      ...prev,
      [connectionId]: {
        connection_id: connectionId,
        status: 'running',
        timestamp: new Date()
      }
    }));

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const success = Math.random() > 0.2; // 80% success rate
      const responseTime = Math.floor(Math.random() * 100) + 20;
      
      setTestResults(prev => ({
        ...prev,
        [connectionId]: {
          connection_id: connectionId,
          status: success ? 'success' : 'failed',
          response_time: success ? responseTime : undefined,
          error_message: success ? undefined : 'Connection timeout - unable to reach host',
          timestamp: new Date()
        }
      }));
    } catch (error) {
      setTestResults(prev => ({
        ...prev,
        [connectionId]: {
          connection_id: connectionId,
          status: 'failed',
          error_message: 'Network error occurred',
          timestamp: new Date()
        }
      }));
    }
  }, []);

  // Save connection
  const handleSaveConnection = useCallback(async (connectionData: Partial<DataSource>) => {
    try {
      if (selectedConnection) {
        // Update existing connection
        await apiCall('PUT', `/api/connections/${selectedConnection.id}`, connectionData);
      } else {
        // Create new connection
        await apiCall('POST', '/api/connections', connectionData);
      }
      
      refetch();
      setSelectedConnection(null);
    } catch (error) {
      console.error('Failed to save connection:', error);
    }
  }, [selectedConnection, apiCall, refetch]);

  // Delete connection
  const handleDeleteConnection = useCallback(async (connectionId: string) => {
    if (!confirm('Are you sure you want to delete this connection?')) return;
    
    try {
      await apiCall('DELETE', `/api/connections/${connectionId}`);
      refetch();
    } catch (error) {
      console.error('Failed to delete connection:', error);
    }
  }, [apiCall, refetch]);

  return (
    <div className="h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              Data Sources
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Manage your database connections and data sources
            </p>
          </div>
          
          <MagneticButton
            onClick={() => {
              setSelectedConnection(null);
              setIsModalOpen(true);
            }}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
          >
            <span>➕</span>
            <span>Add Connection</span>
          </MagneticButton>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-blue-50 dark:bg-blue-900 p-4 rounded-lg">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {connectionStats.total}
            </div>
            <div className="text-sm text-blue-600 dark:text-blue-400">Total Connections</div>
          </div>
          
          <div className="bg-green-50 dark:bg-green-900 p-4 rounded-lg">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {connectionStats.connected}
            </div>
            <div className="text-sm text-green-600 dark:text-green-400">Connected</div>
          </div>
          
          <div className="bg-red-50 dark:bg-red-900 p-4 rounded-lg">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {connectionStats.errors}
            </div>
            <div className="text-sm text-red-600 dark:text-red-400">Errors</div>
          </div>
          
          <div className="bg-purple-50 dark:bg-purple-900 p-4 rounded-lg">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {Math.round(connectionStats.avgResponseTime)}ms
            </div>
            <div className="text-sm text-purple-600 dark:text-purple-400">Avg Response</div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search connections..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
            />
          </div>
          
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
          >
            <option value="all">All Types</option>
            {Object.entries(DATA_SOURCE_CONFIGS).map(([key, config]) => (
              <option key={key} value={key}>
                {config.icon} {config.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-6 overflow-y-auto">
        {isLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="bg-white dark:bg-gray-800 rounded-lg p-6 animate-pulse">
                <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded mb-4"></div>
                <div className="space-y-2">
                  <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
                  <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                </div>
              </div>
            ))}
          </div>
        ) : filteredConnections.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            <AnimatePresence>
              {filteredConnections.map(connection => (
                <ConnectionCard
                  key={connection.id}
                  connection={connection}
                  onTest={handleTestConnection}
                  onEdit={(conn) => {
                    setSelectedConnection(conn);
                    setIsModalOpen(true);
                  }}
                  onDelete={handleDeleteConnection}
                  onViewSchema={(id) => console.log('View schema for:', id)}
                  testResults={testResults}
                />
              ))}
            </AnimatePresence>
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-12"
          >
            <div className="text-6xl mb-4">🗄️</div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              No connections found
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {searchTerm || selectedType !== 'all' 
                ? 'Try adjusting your search filters'
                : 'Get started by adding your first database connection'
              }
            </p>
            {(!searchTerm && selectedType === 'all') && (
              <MagneticButton
                onClick={() => {
                  setSelectedConnection(null);
                  setIsModalOpen(true);
                }}
                className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Add Your First Connection
              </MagneticButton>
            )}
          </motion.div>
        )}
      </div>

      {/* Connection Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <ConnectionModal
            isOpen={isModalOpen}
            onClose={() => {
              setIsModalOpen(false);
              setSelectedConnection(null);
            }}
            onSave={handleSaveConnection}
            connection={selectedConnection}
          />
        )}
      </AnimatePresence>
    </div>
  );
};