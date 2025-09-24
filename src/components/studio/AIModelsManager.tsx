'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAPI } from '../hooks/useAPI';
import { GlowCard, TiltCard, RippleButton, MagneticButton } from '../InteractiveElements';

// AI Model types
interface AIModel {
  id: string;
  name: string;
  description: string;
  type: 'llm' | 'vision' | 'embedding' | 'classification' | 'regression' | 'clustering' | 'nlp' | 'custom';
  provider: 'openai' | 'anthropic' | 'huggingface' | 'local' | 'custom';
  status: 'active' | 'inactive' | 'training' | 'deploying' | 'error';
  version: string;
  created_at: string;
  last_used: string | null;
  metrics: {
    accuracy?: number;
    latency: number;
    throughput: number;
    cost_per_request: number;
    requests_count: number;
    error_rate: number;
    uptime_percentage: number;
  };
  configuration: {
    temperature?: number;
    max_tokens?: number;
    top_p?: number;
    frequency_penalty?: number;
    presence_penalty?: number;
    model_id: string;
    endpoint_url?: string;
    api_key_required: boolean;
  };
  endpoints: {
    inference: string;
    training?: string;
    evaluation?: string;
  };
  tags: string[];
  use_cases: string[];
  limitations: string[];
}

interface ModelExecution {
  id: string;
  model_id: string;
  input: any;
  output: any;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  duration?: number;
  cost?: number;
  metadata: Record<string, any>;
}

interface ModelBenchmark {
  id: string;
  model_id: string;
  test_name: string;
  metrics: {
    accuracy?: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
    latency: number;
    throughput: number;
    memory_usage: number;
  };
  test_data_size: number;
  timestamp: string;
}

// Model configurations
const MODEL_TYPE_CONFIGS = {
  llm: {
    name: 'Large Language Model',
    icon: '🧠',
    color: 'blue',
    description: 'Text generation and conversation models'
  },
  vision: {
    name: 'Computer Vision',
    icon: '👁️',
    color: 'purple',
    description: 'Image analysis and recognition models'
  },
  embedding: {
    name: 'Text Embedding',
    icon: '📊',
    color: 'green',
    description: 'Text to vector conversion models'
  },
  classification: {
    name: 'Classification',
    icon: '🏷️',
    color: 'orange',
    description: 'Data classification models'
  },
  regression: {
    name: 'Regression',
    icon: '📈',
    color: 'red',
    description: 'Numerical prediction models'
  },
  clustering: {
    name: 'Clustering',
    icon: '🎯',
    color: 'yellow',
    description: 'Data grouping and segmentation'
  },
  nlp: {
    name: 'NLP Processing',
    icon: '📝',
    color: 'cyan',
    description: 'Natural language processing models'
  },
  custom: {
    name: 'Custom Model',
    icon: '⚙️',
    color: 'gray',
    description: 'Custom trained models'
  }
};

const PROVIDER_CONFIGS = {
  openai: { name: 'OpenAI', icon: '🤖', color: 'green' },
  anthropic: { name: 'Anthropic', icon: '🔬', color: 'blue' },
  huggingface: { name: 'Hugging Face', icon: '🤗', color: 'yellow' },
  local: { name: 'Local', icon: '💻', color: 'purple' },
  custom: { name: 'Custom', icon: '🛠️', color: 'gray' }
};

// Utility classes
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// Status badge component
const StatusBadge: React.FC<{ status: AIModel['status'] }> = ({ status }) => {
  const statusConfig = {
    active: { label: 'Active', color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300', icon: '🟢' },
    inactive: { label: 'Inactive', color: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300', icon: '⚪' },
    training: { label: 'Training', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300', icon: '🔵' },
    deploying: { label: 'Deploying', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300', icon: '🟡' },
    error: { label: 'Error', color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300', icon: '🔴' }
  };

  const config = statusConfig[status];

  return (
    <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', config.color)}>
      <span className="mr-1">{config.icon}</span>
      {config.label}
    </span>
  );
};

// Model Card Component
const ModelCard: React.FC<{
  model: AIModel;
  onTest: (model: AIModel) => void;
  onConfigure: (model: AIModel) => void;
  onBenchmark: (model: AIModel) => void;
  onToggleStatus: (modelId: string) => void;
  onDelete: (modelId: string) => void;
}> = ({ model, onTest, onConfigure, onBenchmark, onToggleStatus, onDelete }) => {
  const typeConfig = MODEL_TYPE_CONFIGS[model.type];
  const providerConfig = PROVIDER_CONFIGS[model.provider];

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.3 }}
    >
      <TiltCard className="p-6 hover:shadow-xl transition-all duration-300">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={cn(
              'w-12 h-12 rounded-xl flex items-center justify-center text-2xl',
              `bg-${typeConfig.color}-100 text-${typeConfig.color}-600 dark:bg-${typeConfig.color}-900 dark:text-${typeConfig.color}-400`
            )}>
              {typeConfig.icon}
            </div>
            
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {model.name}
              </h3>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {typeConfig.name}
                </span>
                <span className="text-gray-300 dark:text-gray-600">•</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {providerConfig.icon} {providerConfig.name}
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <StatusBadge status={model.status} />
            <span className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded-full">
              v{model.version}
            </span>
          </div>
        </div>

        {/* Description */}
        <p className="text-gray-600 dark:text-gray-400 text-sm mb-4 line-clamp-2">
          {model.description}
        </p>

        {/* Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          <div className="text-center">
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              {model.metrics.latency.toFixed(0)}ms
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Latency</p>
          </div>
          
          <div className="text-center">
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              {model.metrics.throughput.toFixed(1)}/s
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Throughput</p>
          </div>
          
          <div className="text-center">
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              ${model.metrics.cost_per_request.toFixed(4)}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Cost/Request</p>
          </div>
        </div>

        {/* Performance Indicators */}
        <div className="space-y-2 mb-4">
          {/* Uptime */}
          <div>
            <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
              <span>Uptime</span>
              <span>{model.metrics.uptime_percentage.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
              <motion.div
                className="bg-green-500 h-1.5 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${model.metrics.uptime_percentage}%` }}
                transition={{ duration: 0.8, delay: 0.2 }}
              />
            </div>
          </div>
          
          {/* Error Rate */}
          <div>
            <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
              <span>Error Rate</span>
              <span>{model.metrics.error_rate.toFixed(2)}%</span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
              <motion.div
                className={cn(
                  'h-1.5 rounded-full',
                  model.metrics.error_rate > 5 ? 'bg-red-500' :
                  model.metrics.error_rate > 2 ? 'bg-yellow-500' :
                  'bg-green-500'
                )}
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(model.metrics.error_rate * 10, 100)}%` }}
                transition={{ duration: 0.8, delay: 0.4 }}
              />
            </div>
          </div>

          {/* Accuracy (if available) */}
          {model.metrics.accuracy !== undefined && (
            <div>
              <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
                <span>Accuracy</span>
                <span>{model.metrics.accuracy.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                <motion.div
                  className="bg-blue-500 h-1.5 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${model.metrics.accuracy}%` }}
                  transition={{ duration: 0.8, delay: 0.6 }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Usage Stats */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 mb-4">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {model.metrics.requests_count.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Total Requests</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Last used: {model.last_used ? new Date(model.last_used).toLocaleDateString() : 'Never'}
              </p>
            </div>
          </div>
        </div>

        {/* Tags */}
        {model.tags.length > 0 && (
          <div className="mb-4">
            <div className="flex flex-wrap gap-1">
              {model.tags.slice(0, 3).map(tag => (
                <span
                  key={tag}
                  className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs rounded-full"
                >
                  {tag}
                </span>
              ))}
              {model.tags.length > 3 && (
                <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs rounded-full">
                  +{model.tags.length - 3}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex space-x-2">
          <RippleButton
            onClick={() => onTest(model)}
            disabled={model.status !== 'active'}
            className={cn(
              'flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-colors',
              model.status === 'active'
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            )}
          >
            Test Model
          </RippleButton>
          
          <button
            onClick={() => onBenchmark(model)}
            disabled={model.status !== 'active'}
            className="px-3 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            title="Run benchmark"
          >
            📊
          </button>
          
          <button
            onClick={() => onConfigure(model)}
            className="px-3 py-2 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
            title="Configure"
          >
            ⚙️
          </button>
          
          <button
            onClick={() => onToggleStatus(model.id)}
            className={cn(
              'px-3 py-2 text-sm rounded-lg transition-colors',
              model.status === 'active' 
                ? 'bg-yellow-600 text-white hover:bg-yellow-700' 
                : 'bg-green-600 text-white hover:bg-green-700'
            )}
            title={model.status === 'active' ? 'Deactivate' : 'Activate'}
          >
            {model.status === 'active' ? '⏸️' : '▶️'}
          </button>
          
          <button
            onClick={() => onDelete(model.id)}
            className="px-3 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            title="Delete"
          >
            🗑️
          </button>
        </div>
      </TiltCard>
    </motion.div>
  );
};

// Model Testing Modal
const ModelTestModal: React.FC<{
  model: AIModel | null;
  isOpen: boolean;
  onClose: () => void;
  onExecute: (input: any) => void;
  execution: ModelExecution | null;
}> = ({ model, isOpen, onClose, onExecute, execution }) => {
  const [input, setInput] = useState('');
  const [testType, setTestType] = useState('inference');

  if (!isOpen || !model) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    let parsedInput;
    try {
      parsedInput = model.type === 'llm' || model.type === 'nlp' ? input : JSON.parse(input);
    } catch {
      parsedInput = input;
    }
    
    onExecute(parsedInput);
  };

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
        className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">{MODEL_TYPE_CONFIGS[model.type].icon}</span>
            <div>
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
                Test {model.name}
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                {MODEL_TYPE_CONFIGS[model.type].name}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            ✕
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Input Section */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Input
            </h3>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Test Type
                </label>
                <select
                  value={testType}
                  onChange={(e) => setTestType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                >
                  <option value="inference">Inference</option>
                  <option value="batch">Batch Processing</option>
                  <option value="streaming">Streaming</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {model.type === 'llm' || model.type === 'nlp' ? 'Text Input' : 'JSON Input'}
                </label>
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  rows={8}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white font-mono text-sm"
                  placeholder={
                    model.type === 'llm' ? 'Enter your prompt here...' :
                    model.type === 'vision' ? '{"image_url": "https://example.com/image.jpg"}' :
                    model.type === 'classification' ? '{"text": "Sample text to classify"}' :
                    '{"data": "your input data"}'
                  }
                  required
                />
              </div>
              
              <button
                type="submit"
                disabled={!input.trim() || execution?.status === 'running'}
                className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                {execution?.status === 'running' ? 'Processing...' : 'Run Test'}
              </button>
            </form>

            {/* Model Configuration Info */}
            <div className="mt-6 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                Model Configuration
              </h4>
              <div className="space-y-1 text-xs text-gray-600 dark:text-gray-400">
                <div>Model ID: <span className="font-mono">{model.configuration.model_id}</span></div>
                {model.configuration.temperature !== undefined && (
                  <div>Temperature: <span className="font-mono">{model.configuration.temperature}</span></div>
                )}
                {model.configuration.max_tokens !== undefined && (
                  <div>Max Tokens: <span className="font-mono">{model.configuration.max_tokens}</span></div>
                )}
                <div>Endpoint: <span className="font-mono">{model.endpoints.inference}</span></div>
              </div>
            </div>
          </div>

          {/* Output Section */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Output
            </h3>
            
            {execution ? (
              <div className="space-y-4">
                {/* Execution Status */}
                <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <div className={cn(
                      'w-2 h-2 rounded-full',
                      execution.status === 'running' ? 'bg-blue-500 animate-pulse' :
                      execution.status === 'completed' ? 'bg-green-500' :
                      execution.status === 'failed' ? 'bg-red-500' :
                      'bg-gray-400'
                    )} />
                    <span className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                      {execution.status}
                    </span>
                  </div>
                  
                  {execution.duration && (
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {execution.duration}ms
                    </span>
                  )}
                </div>

                {/* Output Content */}
                <div className="bg-gray-900 dark:bg-gray-950 rounded-lg p-4 min-h-[200px]">
                  {execution.status === 'running' && (
                    <div className="flex items-center space-x-2 text-gray-400">
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                      <span>Processing request...</span>
                    </div>
                  )}
                  
                  {execution.status === 'completed' && execution.output && (
                    <pre className="text-green-400 text-sm whitespace-pre-wrap font-mono">
                      {typeof execution.output === 'string' 
                        ? execution.output 
                        : JSON.stringify(execution.output, null, 2)
                      }
                    </pre>
                  )}
                  
                  {execution.status === 'failed' && (
                    <div className="text-red-400 text-sm">
                      <div className="font-semibold mb-2">Error:</div>
                      <div className="font-mono">{execution.metadata.error || 'Unknown error occurred'}</div>
                    </div>
                  )}
                </div>

                {/* Execution Metadata */}
                {execution.status === 'completed' && (
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="p-3 bg-blue-50 dark:bg-blue-900 rounded-lg">
                      <div className="text-blue-600 dark:text-blue-400 font-semibold">Duration</div>
                      <div className="text-gray-900 dark:text-white">{execution.duration}ms</div>
                    </div>
                    
                    {execution.cost && (
                      <div className="p-3 bg-green-50 dark:bg-green-900 rounded-lg">
                        <div className="text-green-600 dark:text-green-400 font-semibold">Cost</div>
                        <div className="text-gray-900 dark:text-white">${execution.cost.toFixed(6)}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                <div className="text-center text-gray-500 dark:text-gray-400">
                  <div className="text-4xl mb-2">🤖</div>
                  <p>Enter input and run test to see results</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

// Main AIModelsManager Component
export const AIModelsManager: React.FC<{
  projectId: string;
  isLoading?: boolean;
  activities?: any[];
}> = ({ projectId, isLoading, activities = [] }) => {
  const { apiCall } = useAPI();
  
  // Component state
  const [models, setModels] = useState<AIModel[]>([]);
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [testModel, setTestModel] = useState<AIModel | null>(null);
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [currentExecution, setCurrentExecution] = useState<ModelExecution | null>(null);

  // Mock models data
  const mockModels: AIModel[] = useMemo(() => [
    {
      id: 'model-1',
      name: 'GPT-4 Text Generator',
      description: 'Advanced language model for text generation, conversation, and code assistance',
      type: 'llm',
      provider: 'openai',
      status: 'active',
      version: '4.0.1',
      created_at: '2024-01-10T08:00:00Z',
      last_used: '2024-01-20T14:30:00Z',
      metrics: {
        accuracy: 92.5,
        latency: 850,
        throughput: 12.3,
        cost_per_request: 0.0025,
        requests_count: 15420,
        error_rate: 0.8,
        uptime_percentage: 99.7
      },
      configuration: {
        temperature: 0.7,
        max_tokens: 4096,
        top_p: 0.9,
        model_id: 'gpt-4-turbo',
        api_key_required: true
      },
      endpoints: {
        inference: 'https://api.openai.com/v1/chat/completions',
      },
      tags: ['text', 'conversation', 'code', 'analysis'],
      use_cases: ['Content generation', 'Code assistance', 'Data analysis', 'Customer support'],
      limitations: ['Token limits', 'Knowledge cutoff', 'Factual accuracy']
    },
    {
      id: 'model-2',
      name: 'CLIP Vision Analyzer',
      description: 'Computer vision model for image understanding and classification',
      type: 'vision',
      provider: 'huggingface',
      status: 'active',
      version: '1.2.3',
      created_at: '2024-01-12T10:00:00Z',
      last_used: '2024-01-19T16:45:00Z',
      metrics: {
        accuracy: 88.2,
        latency: 320,
        throughput: 45.6,
        cost_per_request: 0.0008,
        requests_count: 8750,
        error_rate: 2.1,
        uptime_percentage: 98.9
      },
      configuration: {
        model_id: 'openai/clip-vit-large-patch14',
        endpoint_url: 'https://api-inference.huggingface.co/models/openai/clip-vit-large-patch14',
        api_key_required: true
      },
      endpoints: {
        inference: 'https://api-inference.huggingface.co/models/openai/clip-vit-large-patch14'
      },
      tags: ['vision', 'classification', 'multimodal'],
      use_cases: ['Image classification', 'Content moderation', 'Visual search'],
      limitations: ['Image size limits', 'Processing speed', 'Specialized domains']
    },
    {
      id: 'model-3',
      name: 'Claude Anthropic Assistant',
      description: 'Constitutional AI assistant for safe and helpful conversations',
      type: 'llm',
      provider: 'anthropic',
      status: 'active',
      version: '3.5.2',
      created_at: '2024-01-15T12:00:00Z',
      last_used: '2024-01-20T11:20:00Z',
      metrics: {
        accuracy: 94.1,
        latency: 750,
        throughput: 8.7,
        cost_per_request: 0.0018,
        requests_count: 12380,
        error_rate: 0.5,
        uptime_percentage: 99.9
      },
      configuration: {
        temperature: 0.8,
        max_tokens: 8192,
        model_id: 'claude-3-sonnet-20240229',
        api_key_required: true
      },
      endpoints: {
        inference: 'https://api.anthropic.com/v1/messages'
      },
      tags: ['safe-ai', 'helpful', 'harmless', 'honest'],
      use_cases: ['Research assistance', 'Writing help', 'Analysis', 'Brainstorming'],
      limitations: ['Response length', 'Real-time data', 'Image generation']
    },
    {
      id: 'model-4',
      name: 'Sentiment Classifier',
      description: 'Custom trained model for sentiment analysis of customer feedback',
      type: 'classification',
      provider: 'local',
      status: 'training',
      version: '2.1.0',
      created_at: '2024-01-18T09:00:00Z',
      last_used: null,
      metrics: {
        accuracy: 89.7,
        latency: 120,
        throughput: 150.2,
        cost_per_request: 0.0001,
        requests_count: 0,
        error_rate: 0.0,
        uptime_percentage: 0
      },
      configuration: {
        model_id: 'sentiment-classifier-v2',
        endpoint_url: 'http://localhost:8080/predict',
        api_key_required: false
      },
      endpoints: {
        inference: 'http://localhost:8080/predict',
        training: 'http://localhost:8080/train',
        evaluation: 'http://localhost:8080/evaluate'
      },
      tags: ['sentiment', 'nlp', 'custom', 'feedback'],
      use_cases: ['Customer feedback analysis', 'Review processing', 'Social media monitoring'],
      limitations: ['Domain specific', 'Language limitations', 'Training data dependency']
    },
    {
      id: 'model-5',
      name: 'Embedding Generator',
      description: 'High-quality text embeddings for semantic search and similarity',
      type: 'embedding',
      provider: 'openai',
      status: 'active',
      version: '3.0.1',
      created_at: '2024-01-08T14:00:00Z',
      last_used: '2024-01-20T13:15:00Z',
      metrics: {
        latency: 180,
        throughput: 200.5,
        cost_per_request: 0.0002,
        requests_count: 45680,
        error_rate: 0.3,
        uptime_percentage: 99.8
      },
      configuration: {
        model_id: 'text-embedding-3-large',
        api_key_required: true
      },
      endpoints: {
        inference: 'https://api.openai.com/v1/embeddings'
      },
      tags: ['embeddings', 'search', 'similarity', 'vector'],
      use_cases: ['Semantic search', 'Document similarity', 'Clustering', 'Recommendation'],
      limitations: ['Context length', 'Language support', 'Embedding dimensions']
    }
  ], []);

  // Set mock data
  useEffect(() => {
    setModels(mockModels);
  }, [mockModels]);

  // Filter models
  const filteredModels = useMemo(() => {
    return models.filter(model => {
      const matchesSearch = model.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           model.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesType = selectedType === 'all' || model.type === selectedType;
      const matchesProvider = selectedProvider === 'all' || model.provider === selectedProvider;
      return matchesSearch && matchesType && matchesProvider;
    });
  }, [models, searchTerm, selectedType, selectedProvider]);

  // Model statistics
  const modelStats = useMemo(() => {
    const total = models.length;
    const active = models.filter(m => m.status === 'active').length;
    const training = models.filter(m => m.status === 'training').length;
    const errors = models.filter(m => m.status === 'error').length;
    const totalRequests = models.reduce((sum, m) => sum + m.metrics.requests_count, 0);
    const avgLatency = models.filter(m => m.metrics.latency > 0)
      .reduce((sum, m) => sum + m.metrics.latency, 0) / 
      (models.filter(m => m.metrics.latency > 0).length || 1);

    return { total, active, training, errors, totalRequests, avgLatency };
  }, [models]);

  // Test model
  const handleTestModel = useCallback(async (input: any) => {
    if (!testModel) return;

    const execution: ModelExecution = {
      id: `exec-${Date.now()}`,
      model_id: testModel.id,
      input,
      output: null,
      status: 'running',
      started_at: new Date().toISOString(),
      metadata: {}
    };

    setCurrentExecution(execution);

    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000 + Math.random() * 3000));

      // Mock response based on model type
      let output;
      if (testModel.type === 'llm') {
        output = `Based on your input "${input}", here's a detailed response generated by ${testModel.name}. This is a simulated response that demonstrates the model's capabilities for text generation and analysis.`;
      } else if (testModel.type === 'vision') {
        output = {
          predictions: [
            { class: 'cat', confidence: 0.95 },
            { class: 'animal', confidence: 0.87 },
            { class: 'pet', confidence: 0.76 }
          ]
        };
      } else if (testModel.type === 'classification') {
        output = {
          classification: 'positive',
          confidence: 0.89,
          scores: { positive: 0.89, negative: 0.08, neutral: 0.03 }
        };
      } else if (testModel.type === 'embedding') {
        output = {
          embedding: Array.from({ length: 1536 }, () => Math.random() - 0.5),
          dimensions: 1536
        };
      } else {
        output = { result: 'Success', processed: true };
      }

      const duration = Math.floor(testModel.metrics.latency + Math.random() * 200);
      const cost = testModel.metrics.cost_per_request * (0.8 + Math.random() * 0.4);

      setCurrentExecution({
        ...execution,
        output,
        status: 'completed',
        completed_at: new Date().toISOString(),
        duration,
        cost
      });

    } catch (error) {
      setCurrentExecution({
        ...execution,
        status: 'failed',
        completed_at: new Date().toISOString(),
        metadata: { error: 'Failed to process request' }
      });
    }
  }, [testModel]);

  // Toggle model status
  const handleToggleStatus = useCallback((modelId: string) => {
    setModels(prev => prev.map(model => 
      model.id === modelId 
        ? { 
            ...model, 
            status: model.status === 'active' ? 'inactive' : 'active' as const
          }
        : model
    ));
  }, []);

  return (
    <div className="h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              AI Models Manager
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Manage and monitor your AI models and endpoints
            </p>
          </div>
          
          <MagneticButton
            onClick={() => console.log('Add new model')}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
          >
            <span>➕</span>
            <span>Add Model</span>
          </MagneticButton>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-6">
          <div className="bg-blue-50 dark:bg-blue-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {modelStats.total}
            </div>
            <div className="text-sm text-blue-600 dark:text-blue-400">Total Models</div>
          </div>
          
          <div className="bg-green-50 dark:bg-green-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {modelStats.active}
            </div>
            <div className="text-sm text-green-600 dark:text-green-400">Active</div>
          </div>
          
          <div className="bg-yellow-50 dark:bg-yellow-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {modelStats.training}
            </div>
            <div className="text-sm text-yellow-600 dark:text-yellow-400">Training</div>
          </div>
          
          <div className="bg-red-50 dark:bg-red-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {modelStats.errors}
            </div>
            <div className="text-sm text-red-600 dark:text-red-400">Errors</div>
          </div>
          
          <div className="bg-purple-50 dark:bg-purple-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {(modelStats.totalRequests / 1000).toFixed(1)}K
            </div>
            <div className="text-sm text-purple-600 dark:text-purple-400">Total Requests</div>
          </div>
          
          <div className="bg-cyan-50 dark:bg-cyan-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">
              {Math.round(modelStats.avgLatency)}ms
            </div>
            <div className="text-sm text-cyan-600 dark:text-cyan-400">Avg Latency</div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search models..."
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
            {Object.entries(MODEL_TYPE_CONFIGS).map(([key, config]) => (
              <option key={key} value={key}>
                {config.icon} {config.name}
              </option>
            ))}
          </select>
          
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
          >
            <option value="all">All Providers</option>
            {Object.entries(PROVIDER_CONFIGS).map(([key, config]) => (
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
        ) : filteredModels.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            <AnimatePresence>
              {filteredModels.map(model => (
                <ModelCard
                  key={model.id}
                  model={model}
                  onTest={(model) => {
                    setTestModel(model);
                    setIsTestModalOpen(true);
                    setCurrentExecution(null);
                  }}
                  onConfigure={(model) => console.log('Configure:', model)}
                  onBenchmark={(model) => console.log('Benchmark:', model)}
                  onToggleStatus={handleToggleStatus}
                  onDelete={(id) => console.log('Delete:', id)}
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
            <div className="text-6xl mb-4">🤖</div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              No AI models found
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {searchTerm || selectedType !== 'all' || selectedProvider !== 'all'
                ? 'Try adjusting your search filters'
                : 'Add your first AI model to get started'
              }
            </p>
          </motion.div>
        )}
      </div>

      {/* Model Test Modal */}
      <AnimatePresence>
        {isTestModalOpen && (
          <ModelTestModal
            model={testModel}
            isOpen={isTestModalOpen}
            onClose={() => {
              setIsTestModalOpen(false);
              setTestModel(null);
              setCurrentExecution(null);
            }}
            onExecute={handleTestModel}
            execution={currentExecution}
          />
        )}
      </AnimatePresence>
    </div>
  );
};