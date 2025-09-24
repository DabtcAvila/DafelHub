'use client';

import React, { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAPI } from '../hooks/useAPI';

// Canvas types
interface CanvasElement {
  id: string;
  type: 'source' | 'transform' | 'sink' | 'condition' | 'join' | 'aggregate';
  name: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
  properties: Record<string, any>;
  connections: string[];
  status: 'idle' | 'running' | 'success' | 'error';
}

interface Connection {
  id: string;
  source: string;
  target: string;
  sourcePort: string;
  targetPort: string;
  active: boolean;
}

interface DragState {
  isDragging: boolean;
  dragElement: CanvasElement | null;
  offset: { x: number; y: number };
  startPosition: { x: number; y: number };
}

interface ComponentLibraryItem {
  type: CanvasElement['type'];
  name: string;
  icon: string;
  color: string;
  description: string;
  category: 'sources' | 'transforms' | 'sinks' | 'control';
  properties: Record<string, any>;
}

// Component Library
const COMPONENT_LIBRARY: ComponentLibraryItem[] = [
  // Sources
  {
    type: 'source',
    name: 'PostgreSQL Source',
    icon: '🐘',
    color: 'blue',
    description: 'Read data from PostgreSQL database',
    category: 'sources',
    properties: { table: '', query: '', batchSize: 1000 }
  },
  {
    type: 'source',
    name: 'MySQL Source',
    icon: '🐬',
    color: 'orange',
    description: 'Read data from MySQL database',
    category: 'sources',
    properties: { table: '', query: '', batchSize: 1000 }
  },
  {
    type: 'source',
    name: 'MongoDB Source',
    icon: '🍃',
    color: 'green',
    description: 'Read data from MongoDB collection',
    category: 'sources',
    properties: { collection: '', filter: '{}', limit: 1000 }
  },
  {
    type: 'source',
    name: 'File Source',
    icon: '📁',
    color: 'purple',
    description: 'Read data from file (CSV, JSON, Parquet)',
    category: 'sources',
    properties: { path: '', format: 'csv', separator: ',' }
  },
  {
    type: 'source',
    name: 'REST API Source',
    icon: '🌐',
    color: 'cyan',
    description: 'Fetch data from REST API endpoint',
    category: 'sources',
    properties: { url: '', method: 'GET', headers: '{}' }
  },
  
  // Transforms
  {
    type: 'transform',
    name: 'Filter',
    icon: '🔍',
    color: 'yellow',
    description: 'Filter rows based on conditions',
    category: 'transforms',
    properties: { condition: '', columns: [] }
  },
  {
    type: 'transform',
    name: 'Map',
    icon: '🔄',
    color: 'indigo',
    description: 'Transform data columns',
    category: 'transforms',
    properties: { mapping: '{}', newColumns: [] }
  },
  {
    type: 'aggregate',
    name: 'Aggregate',
    icon: '📊',
    color: 'pink',
    description: 'Group and aggregate data',
    category: 'transforms',
    properties: { groupBy: [], aggregations: '{}' }
  },
  {
    type: 'join',
    name: 'Join',
    icon: '🔗',
    color: 'teal',
    description: 'Join two data streams',
    category: 'transforms',
    properties: { joinType: 'inner', leftKey: '', rightKey: '' }
  },
  
  // Sinks
  {
    type: 'sink',
    name: 'PostgreSQL Sink',
    icon: '🐘',
    color: 'blue',
    description: 'Write data to PostgreSQL database',
    category: 'sinks',
    properties: { table: '', writeMode: 'append', batchSize: 1000 }
  },
  {
    type: 'sink',
    name: 'File Sink',
    icon: '💾',
    color: 'gray',
    description: 'Write data to file',
    category: 'sinks',
    properties: { path: '', format: 'csv', overwrite: false }
  },
  
  // Control Flow
  {
    type: 'condition',
    name: 'Condition',
    icon: '❓',
    color: 'red',
    description: 'Conditional branching logic',
    category: 'control',
    properties: { condition: '', truePort: 'yes', falsePort: 'no' }
  }
];

// Utility classes
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// Color mappings
const COLOR_CLASSES = {
  blue: 'bg-blue-500 border-blue-600 text-white',
  green: 'bg-green-500 border-green-600 text-white',
  orange: 'bg-orange-500 border-orange-600 text-white',
  purple: 'bg-purple-500 border-purple-600 text-white',
  cyan: 'bg-cyan-500 border-cyan-600 text-white',
  yellow: 'bg-yellow-500 border-yellow-600 text-white',
  indigo: 'bg-indigo-500 border-indigo-600 text-white',
  pink: 'bg-pink-500 border-pink-600 text-white',
  teal: 'bg-teal-500 border-teal-600 text-white',
  gray: 'bg-gray-500 border-gray-600 text-white',
  red: 'bg-red-500 border-red-600 text-white',
};

// Canvas Element Component
const CanvasElementComponent: React.FC<{
  element: CanvasElement;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onDrag: (id: string, position: { x: number; y: number }) => void;
  onConnect: (elementId: string, port: string) => void;
  scale: number;
}> = ({ element, isSelected, onSelect, onDrag, onConnect, scale }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  
  const library = COMPONENT_LIBRARY.find(c => c.type === element.type && c.name === element.name);
  const colorClass = library ? COLOR_CLASSES[library.color as keyof typeof COLOR_CLASSES] : COLOR_CLASSES.gray;

  const handleMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsDragging(true);
    setDragStart({
      x: e.clientX - element.position.x,
      y: e.clientY - element.position.y
    });
    onSelect(element.id);
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return;
    
    const newPosition = {
      x: Math.max(0, e.clientX - dragStart.x),
      y: Math.max(0, e.clientY - dragStart.y)
    };
    
    onDrag(element.id, newPosition);
  }, [isDragging, dragStart, element.id, onDrag]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const statusIndicator = {
    idle: '⚪',
    running: '🟡',
    success: '🟢',
    error: '🔴'
  };

  return (
    <motion.div
      layout
      style={{
        left: element.position.x,
        top: element.position.y,
        width: element.size.width,
        height: element.size.height,
      }}
      className={cn(
        'absolute cursor-move rounded-lg border-2 shadow-lg select-none',
        colorClass,
        isSelected ? 'ring-4 ring-blue-400 ring-opacity-50' : '',
        isDragging ? 'z-50 shadow-2xl' : 'z-10'
      )}
      onMouseDown={handleMouseDown}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      {/* Element Content */}
      <div className="p-3 h-full flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xl">{library?.icon || '⚙️'}</span>
          <div className="flex items-center space-x-1">
            <span className="text-sm">{statusIndicator[element.status]}</span>
          </div>
        </div>
        
        <div className="flex-1">
          <h4 className="font-semibold text-sm leading-tight mb-1">
            {element.name}
          </h4>
          <p className="text-xs opacity-75 line-clamp-2">
            {library?.description || 'Custom component'}
          </p>
        </div>
        
        {/* Connection ports */}
        <div className="flex justify-between mt-2">
          {/* Input port */}
          {element.type !== 'source' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onConnect(element.id, 'input');
              }}
              className="w-3 h-3 bg-white border-2 border-current rounded-full hover:scale-125 transition-transform"
              title="Input port"
            />
          )}
          
          {/* Output port */}
          {element.type !== 'sink' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onConnect(element.id, 'output');
              }}
              className="w-3 h-3 bg-white border-2 border-current rounded-full hover:scale-125 transition-transform ml-auto"
              title="Output port"
            />
          )}
        </div>
      </div>
    </motion.div>
  );
};

// Component Library Panel
const ComponentLibrary: React.FC<{
  onAddComponent: (component: ComponentLibraryItem) => void;
  isVisible: boolean;
  onToggle: () => void;
}> = ({ onAddComponent, isVisible, onToggle }) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('sources');
  
  const categories = {
    sources: { name: 'Data Sources', icon: '📥' },
    transforms: { name: 'Transforms', icon: '⚙️' },
    sinks: { name: 'Data Sinks', icon: '📤' },
    control: { name: 'Control Flow', icon: '🔀' }
  };
  
  const filteredComponents = COMPONENT_LIBRARY.filter(c => c.category === selectedCategory);

  return (
    <motion.div
      initial={{ x: -300 }}
      animate={{ x: isVisible ? 0 : -250 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="absolute left-0 top-0 h-full w-80 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 shadow-xl z-20"
    >
      {/* Toggle Button */}
      <button
        onClick={onToggle}
        className="absolute -right-12 top-4 w-12 h-12 bg-blue-600 text-white rounded-r-lg shadow-lg hover:bg-blue-700 transition-colors flex items-center justify-center"
        title="Toggle Component Library"
      >
        <span className="text-xl">{isVisible ? '←' : '📚'}</span>
      </button>

      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Component Library
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Drag components onto the canvas
        </p>
      </div>

      {/* Category Tabs */}
      <div className="flex overflow-x-auto border-b border-gray-200 dark:border-gray-700">
        {Object.entries(categories).map(([key, category]) => (
          <button
            key={key}
            onClick={() => setSelectedCategory(key)}
            className={cn(
              'flex-1 px-3 py-2 text-sm font-medium transition-colors whitespace-nowrap',
              selectedCategory === key
                ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            )}
          >
            <span className="mr-1">{category.icon}</span>
            {category.name}
          </button>
        ))}
      </div>

      {/* Components */}
      <div className="p-4 space-y-3 overflow-y-auto" style={{ height: 'calc(100vh - 160px)' }}>
        {filteredComponents.map((component, index) => (
          <motion.button
            key={`${component.type}-${component.name}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => onAddComponent(component)}
            className="w-full p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-500 dark:hover:border-blue-400 hover:shadow-md transition-all text-left group"
          >
            <div className="flex items-start space-x-3">
              <div className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0',
                COLOR_CLASSES[component.color as keyof typeof COLOR_CLASSES]
              )}>
                {component.icon}
              </div>
              
              <div className="flex-1 min-w-0">
                <h4 className="font-medium text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400">
                  {component.name}
                </h4>
                <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
                  {component.description}
                </p>
              </div>
            </div>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
};

// Properties Panel
const PropertiesPanel: React.FC<{
  selectedElement: CanvasElement | null;
  onUpdateProperties: (elementId: string, properties: Record<string, any>) => void;
  onDelete: (elementId: string) => void;
}> = ({ selectedElement, onUpdateProperties, onDelete }) => {
  const [properties, setProperties] = useState<Record<string, any>>({});

  useEffect(() => {
    if (selectedElement) {
      setProperties(selectedElement.properties);
    }
  }, [selectedElement]);

  const handlePropertyChange = (key: string, value: any) => {
    const newProperties = { ...properties, [key]: value };
    setProperties(newProperties);
    if (selectedElement) {
      onUpdateProperties(selectedElement.id, newProperties);
    }
  };

  if (!selectedElement) {
    return (
      <div className="w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <div className="text-4xl mb-4">🔧</div>
          <h3 className="text-lg font-semibold mb-2">Properties Panel</h3>
          <p className="text-sm">Select a component to edit its properties</p>
        </div>
      </div>
    );
  }

  const library = COMPONENT_LIBRARY.find(c => 
    c.type === selectedElement.type && c.name === selectedElement.name
  );

  return (
    <div className="w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">{library?.icon || '⚙️'}</span>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {selectedElement.name}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {library?.description}
              </p>
            </div>
          </div>
          
          <button
            onClick={() => onDelete(selectedElement.id)}
            className="p-2 text-red-600 hover:bg-red-100 dark:hover:bg-red-900 rounded-lg transition-colors"
            title="Delete component"
          >
            🗑️
          </button>
        </div>
      </div>

      {/* Properties */}
      <div className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-4">
          {/* Basic Properties */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Component Name
            </label>
            <input
              type="text"
              value={selectedElement.name}
              onChange={(e) => {
                // Update element name
                onUpdateProperties(selectedElement.id, { ...properties, name: e.target.value });
              }}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
            />
          </div>

          {/* Dynamic Properties */}
          {Object.entries(library?.properties || {}).map(([key, defaultValue]) => (
            <div key={key}>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 capitalize">
                {key.replace(/([A-Z])/g, ' $1').trim()}
              </label>
              
              {typeof defaultValue === 'boolean' ? (
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={properties[key] || false}
                    onChange={(e) => handlePropertyChange(key, e.target.checked)}
                    className="mr-2"
                  />
                  Enable {key}
                </label>
              ) : typeof defaultValue === 'number' ? (
                <input
                  type="number"
                  value={properties[key] || defaultValue}
                  onChange={(e) => handlePropertyChange(key, parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                />
              ) : (
                <textarea
                  value={properties[key] || defaultValue}
                  onChange={(e) => handlePropertyChange(key, e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white resize-none"
                  placeholder={`Enter ${key}...`}
                />
              )}
            </div>
          ))}
          
          {/* Status Information */}
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <h4 className="font-semibold text-gray-900 dark:text-white mb-3">Status Information</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">Status:</span>
                <span className={cn(
                  'text-sm font-medium',
                  selectedElement.status === 'success' ? 'text-green-600' :
                  selectedElement.status === 'error' ? 'text-red-600' :
                  selectedElement.status === 'running' ? 'text-yellow-600' :
                  'text-gray-600'
                )}>
                  {selectedElement.status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">Position:</span>
                <span className="text-sm font-mono">
                  ({selectedElement.position.x}, {selectedElement.position.y})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">Size:</span>
                <span className="text-sm font-mono">
                  {selectedElement.size.width} × {selectedElement.size.height}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Main Canvas Component
export const Canvas: React.FC<{
  projectId: string;
  isLoading?: boolean;
  activities?: any[];
}> = ({ projectId, isLoading, activities = [] }) => {
  const { apiCall } = useAPI();
  
  // Canvas state
  const [elements, setElements] = useState<CanvasElement[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [libraryVisible, setLibraryVisible] = useState(true);
  const [canvasScale, setCanvasScale] = useState(1);
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 });
  const [isConnecting, setIsConnecting] = useState<string | null>(null);
  
  const canvasRef = useRef<HTMLDivElement>(null);

  // Load canvas data
  useEffect(() => {
    const loadCanvas = async () => {
      try {
        const response = await apiCall('GET', `/api/studio/canvas?project_id=${projectId}`);
        if (response.success && response.canvas) {
          setElements(response.canvas.elements || []);
          setConnections(response.canvas.connections || []);
        }
      } catch (error) {
        console.error('Failed to load canvas:', error);
      }
    };

    loadCanvas();
  }, [projectId, apiCall]);

  // Add component to canvas
  const handleAddComponent = useCallback((component: ComponentLibraryItem) => {
    const newElement: CanvasElement = {
      id: `element-${Date.now()}`,
      type: component.type,
      name: component.name,
      position: { 
        x: Math.random() * 400 + 200, 
        y: Math.random() * 300 + 100 
      },
      size: { width: 160, height: 100 },
      properties: { ...component.properties },
      connections: [],
      status: 'idle'
    };
    
    setElements(prev => [...prev, newElement]);
  }, []);

  // Update element position
  const handleElementDrag = useCallback((elementId: string, position: { x: number; y: number }) => {
    setElements(prev => prev.map(el => 
      el.id === elementId ? { ...el, position } : el
    ));
  }, []);

  // Update element properties
  const handleUpdateProperties = useCallback((elementId: string, properties: Record<string, any>) => {
    setElements(prev => prev.map(el => 
      el.id === elementId ? { ...el, properties: { ...el.properties, ...properties } } : el
    ));
  }, []);

  // Delete element
  const handleDeleteElement = useCallback((elementId: string) => {
    setElements(prev => prev.filter(el => el.id !== elementId));
    setConnections(prev => prev.filter(conn => 
      conn.source !== elementId && conn.target !== elementId
    ));
    setSelectedElementId(null);
  }, []);

  // Handle canvas click
  const handleCanvasClick = useCallback(() => {
    setSelectedElementId(null);
    setIsConnecting(null);
  }, []);

  // Execute pipeline
  const handleExecutePipeline = useCallback(async () => {
    try {
      // Update all elements to running state
      setElements(prev => prev.map(el => ({ ...el, status: 'running' })));
      
      const response = await apiCall('POST', '/api/studio/execute', {
        project_id: projectId,
        code: JSON.stringify({ elements, connections }),
        language: 'pipeline',
        environment: 'production'
      });
      
      if (response.success) {
        // Simulate success/error states
        setTimeout(() => {
          setElements(prev => prev.map(el => ({ 
            ...el, 
            status: Math.random() > 0.8 ? 'error' : 'success' 
          })));
        }, 2000);
      }
    } catch (error) {
      setElements(prev => prev.map(el => ({ ...el, status: 'error' })));
      console.error('Pipeline execution failed:', error);
    }
  }, [projectId, elements, connections, apiCall]);

  const selectedElement = elements.find(el => el.id === selectedElementId);

  return (
    <div className="h-full flex bg-gray-100 dark:bg-gray-900 relative overflow-hidden">
      {/* Component Library */}
      <ComponentLibrary
        onAddComponent={handleAddComponent}
        isVisible={libraryVisible}
        onToggle={() => setLibraryVisible(!libraryVisible)}
      />

      {/* Main Canvas Area */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Pipeline Canvas
              </h3>
              
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {elements.length} components
                </span>
                <span className="text-gray-400">•</span>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {connections.length} connections
                </span>
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              {/* Scale Controls */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setCanvasScale(Math.max(0.5, canvasScale - 0.1))}
                  className="w-8 h-8 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 flex items-center justify-center text-sm"
                  title="Zoom out"
                >
                  −
                </button>
                <span className="text-sm font-mono min-w-12 text-center">
                  {Math.round(canvasScale * 100)}%
                </span>
                <button
                  onClick={() => setCanvasScale(Math.min(2, canvasScale + 0.1))}
                  className="w-8 h-8 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 flex items-center justify-center text-sm"
                  title="Zoom in"
                >
                  +
                </button>
              </div>

              {/* Actions */}
              <button
                onClick={handleExecutePipeline}
                disabled={elements.length === 0}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
              >
                <span>▶️</span>
                <span>Execute Pipeline</span>
              </button>
              
              <button
                onClick={() => {
                  setElements([]);
                  setConnections([]);
                  setSelectedElementId(null);
                }}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center space-x-2"
              >
                <span>🗑️</span>
                <span>Clear All</span>
              </button>
            </div>
          </div>
        </div>

        {/* Canvas */}
        <div 
          ref={canvasRef}
          className="flex-1 relative overflow-hidden cursor-crosshair"
          onClick={handleCanvasClick}
          style={{ 
            backgroundImage: 'radial-gradient(circle, #e5e7eb 1px, transparent 1px)',
            backgroundSize: '20px 20px',
            backgroundPosition: `${canvasOffset.x}px ${canvasOffset.y}px`
          }}
        >
          <div 
            className="absolute inset-0"
            style={{ 
              transform: `scale(${canvasScale}) translate(${canvasOffset.x}px, ${canvasOffset.y}px)`
            }}
          >
            {/* Render connections first */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              {connections.map(connection => {
                const sourceElement = elements.find(el => el.id === connection.source);
                const targetElement = elements.find(el => el.id === connection.target);
                
                if (!sourceElement || !targetElement) return null;
                
                const sourceX = sourceElement.position.x + sourceElement.size.width;
                const sourceY = sourceElement.position.y + sourceElement.size.height / 2;
                const targetX = targetElement.position.x;
                const targetY = targetElement.position.y + targetElement.size.height / 2;
                
                return (
                  <path
                    key={connection.id}
                    d={`M ${sourceX} ${sourceY} Q ${sourceX + 50} ${sourceY} ${targetX - 50} ${targetY} T ${targetX} ${targetY}`}
                    stroke={connection.active ? '#3B82F6' : '#9CA3AF'}
                    strokeWidth="2"
                    fill="none"
                    strokeDasharray={connection.active ? '0' : '5,5'}
                  />
                );
              })}
            </svg>

            {/* Render elements */}
            <AnimatePresence>
              {elements.map(element => (
                <CanvasElementComponent
                  key={element.id}
                  element={element}
                  isSelected={selectedElementId === element.id}
                  onSelect={setSelectedElementId}
                  onDrag={handleElementDrag}
                  onConnect={(elementId, port) => {
                    console.log('Connect:', elementId, port);
                    // TODO: Implement connection logic
                  }}
                  scale={canvasScale}
                />
              ))}
            </AnimatePresence>
          </div>
          
          {/* Empty state */}
          {elements.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="absolute inset-0 flex items-center justify-center"
            >
              <div className="text-center">
                <div className="text-6xl mb-4">🎨</div>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                  Empty Canvas
                </h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  Start building your data pipeline by dragging components from the library
                </p>
                <button
                  onClick={() => setLibraryVisible(true)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Open Component Library
                </button>
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* Properties Panel */}
      <PropertiesPanel
        selectedElement={selectedElement}
        onUpdateProperties={handleUpdateProperties}
        onDelete={handleDeleteElement}
      />
    </div>
  );
};