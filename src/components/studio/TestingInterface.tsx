'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAPI } from '../hooks/useAPI';
import { GlowCard, RippleButton, MagneticButton } from '../InteractiveElements';

// Testing types
interface TestSuite {
  id: string;
  name: string;
  description: string;
  type: 'unit' | 'integration' | 'e2e' | 'performance' | 'security';
  status: 'idle' | 'running' | 'passed' | 'failed' | 'cancelled';
  tests: Test[];
  created_at: string;
  last_run: string | null;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  duration: number;
  coverage?: number;
  tags: string[];
}

interface Test {
  id: string;
  name: string;
  description: string;
  status: 'idle' | 'running' | 'passed' | 'failed' | 'skipped';
  duration: number;
  error_message?: string;
  stack_trace?: string;
  assertions: TestAssertion[];
  metadata: Record<string, any>;
}

interface TestAssertion {
  id: string;
  description: string;
  expected: any;
  actual: any;
  passed: boolean;
  message?: string;
}

interface TestExecution {
  id: string;
  suite_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  started_at: string;
  completed_at?: string;
  duration?: number;
  results: TestResult[];
  logs: TestLog[];
  coverage_report?: CoverageReport;
}

interface TestResult {
  test_id: string;
  status: 'passed' | 'failed' | 'skipped';
  duration: number;
  error?: string;
  assertions: TestAssertion[];
}

interface TestLog {
  timestamp: string;
  level: 'debug' | 'info' | 'warn' | 'error';
  message: string;
  source?: string;
}

interface CoverageReport {
  total_lines: number;
  covered_lines: number;
  coverage_percentage: number;
  files: Array<{
    file: string;
    lines: number;
    covered: number;
    percentage: number;
  }>;
}

// Utility classes
const cn = (...classes: (string | undefined | false)[]) => classes.filter(Boolean).join(' ');

// Test status configurations
const TEST_STATUS_CONFIG = {
  idle: { color: 'gray', icon: '⚪', label: 'Idle' },
  running: { color: 'blue', icon: '🔵', label: 'Running' },
  passed: { color: 'green', icon: '🟢', label: 'Passed' },
  failed: { color: 'red', icon: '🔴', label: 'Failed' },
  skipped: { color: 'yellow', icon: '🟡', label: 'Skipped' },
  cancelled: { color: 'gray', icon: '⚫', label: 'Cancelled' }
};

const SUITE_TYPE_CONFIG = {
  unit: { name: 'Unit Tests', icon: '🧪', description: 'Test individual components' },
  integration: { name: 'Integration Tests', icon: '🔗', description: 'Test component interactions' },
  e2e: { name: 'End-to-End Tests', icon: '🎯', description: 'Test complete user workflows' },
  performance: { name: 'Performance Tests', icon: '⚡', description: 'Test system performance' },
  security: { name: 'Security Tests', icon: '🛡️', description: 'Test security vulnerabilities' }
};

// Test Suite Card Component
const TestSuiteCard: React.FC<{
  suite: TestSuite;
  onRun: (suiteId: string) => void;
  onView: (suite: TestSuite) => void;
  onEdit: (suite: TestSuite) => void;
  onDelete: (suiteId: string) => void;
  isRunning: boolean;
}> = ({ suite, onRun, onView, onEdit, onDelete, isRunning }) => {
  const statusConfig = TEST_STATUS_CONFIG[suite.status];
  const typeConfig = SUITE_TYPE_CONFIG[suite.type];
  
  const successRate = suite.total_tests > 0 ? (suite.passed_tests / suite.total_tests) * 100 : 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
    >
      <GlowCard className="p-6 hover:shadow-xl transition-all duration-300">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={cn(
              'w-12 h-12 rounded-lg flex items-center justify-center text-2xl',
              'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400'
            )}>
              {typeConfig.icon}
            </div>
            
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {suite.name}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {typeConfig.name} • {suite.total_tests} tests
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <span className={cn(
              'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
              statusConfig.color === 'green' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' :
              statusConfig.color === 'red' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300' :
              statusConfig.color === 'blue' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300' :
              statusConfig.color === 'yellow' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300' :
              'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300'
            )}>
              <span className="mr-1">{statusConfig.icon}</span>
              {statusConfig.label}
            </span>
          </div>
        </div>

        {/* Description */}
        <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
          {suite.description}
        </p>

        {/* Test Results Summary */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <div className="text-center">
            <p className="text-lg font-semibold text-green-600 dark:text-green-400">
              {suite.passed_tests}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Passed</p>
          </div>
          
          <div className="text-center">
            <p className="text-lg font-semibold text-red-600 dark:text-red-400">
              {suite.failed_tests}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Failed</p>
          </div>
          
          <div className="text-center">
            <p className="text-lg font-semibold text-yellow-600 dark:text-yellow-400">
              {suite.skipped_tests}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Skipped</p>
          </div>
          
          <div className="text-center">
            <p className="text-lg font-semibold text-gray-600 dark:text-gray-400">
              {suite.duration.toFixed(1)}s
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Duration</p>
          </div>
        </div>

        {/* Success Rate Bar */}
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-2">
            <span>Success Rate</span>
            <span>{successRate.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <motion.div
              className={cn(
                'h-2 rounded-full transition-all duration-500',
                successRate >= 90 ? 'bg-green-500' :
                successRate >= 70 ? 'bg-yellow-500' :
                'bg-red-500'
              )}
              initial={{ width: 0 }}
              animate={{ width: `${successRate}%` }}
            />
          </div>
        </div>

        {/* Coverage (if available) */}
        {suite.coverage !== undefined && (
          <div className="mb-4">
            <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-2">
              <span>Code Coverage</span>
              <span>{suite.coverage.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <motion.div
                className="bg-purple-500 h-2 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${suite.coverage}%` }}
                transition={{ delay: 0.2 }}
              />
            </div>
          </div>
        )}

        {/* Tags */}
        {suite.tags.length > 0 && (
          <div className="mb-4">
            <div className="flex flex-wrap gap-2">
              {suite.tags.map(tag => (
                <span
                  key={tag}
                  className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs rounded-full"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex space-x-2">
          <RippleButton
            onClick={() => onRun(suite.id)}
            disabled={isRunning}
            className={cn(
              'flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-colors',
              isRunning ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700',
              'text-white'
            )}
          >
            {isRunning ? 'Running...' : '▶️ Run Tests'}
          </RippleButton>
          
          <button
            onClick={() => onView(suite)}
            className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            View
          </button>
          
          <button
            onClick={() => onEdit(suite)}
            className="px-3 py-2 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Edit
          </button>
          
          <button
            onClick={() => onDelete(suite.id)}
            className="px-3 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Delete
          </button>
        </div>

        {/* Last Run Info */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
          Last run: {suite.last_run ? new Date(suite.last_run).toLocaleString() : 'Never'}
        </div>
      </GlowCard>
    </motion.div>
  );
};

// Test Execution Monitor
const TestExecutionMonitor: React.FC<{
  execution: TestExecution | null;
  onCancel: () => void;
  isVisible: boolean;
}> = ({ execution, onCancel, isVisible }) => {
  if (!isVisible || !execution) return null;

  const completedTests = execution.results.length;
  const totalTests = execution.results.length + 
    (execution.status === 'running' ? 1 : 0);
  const progress = totalTests > 0 ? (completedTests / totalTests) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="fixed bottom-6 right-6 w-96 bg-white dark:bg-gray-800 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 z-50"
    >
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Test Execution
          </h3>
          <div className="flex items-center space-x-2">
            <div className={cn(
              'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
              execution.status === 'running' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300' :
              execution.status === 'completed' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' :
              execution.status === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300' :
              'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300'
            )}>
              {execution.status}
            </div>
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Progress */}
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-2">
            <span>Progress</span>
            <span>{completedTests}/{totalTests} tests</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <motion.div
              className="bg-blue-500 h-2 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Results Summary */}
        {execution.results.length > 0 && (
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="text-center">
              <p className="text-sm font-semibold text-green-600 dark:text-green-400">
                {execution.results.filter(r => r.status === 'passed').length}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Passed</p>
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-red-600 dark:text-red-400">
                {execution.results.filter(r => r.status === 'failed').length}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Failed</p>
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-yellow-600 dark:text-yellow-400">
                {execution.results.filter(r => r.status === 'skipped').length}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Skipped</p>
            </div>
          </div>
        )}

        {/* Recent Logs */}
        {execution.logs.length > 0 && (
          <div className="mb-4">
            <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">
              Recent Logs
            </h4>
            <div className="bg-gray-900 dark:bg-gray-950 rounded-lg p-3 max-h-32 overflow-y-auto">
              {execution.logs.slice(-5).map((log, index) => (
                <div key={index} className="text-xs font-mono text-gray-300 mb-1">
                  <span className="text-gray-500">[{log.timestamp}]</span>
                  <span className={cn(
                    'ml-2',
                    log.level === 'error' ? 'text-red-400' :
                    log.level === 'warn' ? 'text-yellow-400' :
                    log.level === 'info' ? 'text-blue-400' :
                    'text-gray-400'
                  )}>
                    {log.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex space-x-2">
          {execution.status === 'running' && (
            <button
              onClick={onCancel}
              className="flex-1 py-2 px-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
            >
              Cancel
            </button>
          )}
          
          {execution.status === 'completed' && (
            <button
              onClick={() => {/* View full report */}}
              className="flex-1 py-2 px-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
            >
              View Report
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
};

// Main TestingInterface Component
export const TestingInterface: React.FC<{
  projectId: string;
  isLoading?: boolean;
  activities?: any[];
}> = ({ projectId, isLoading, activities = [] }) => {
  const { apiCall } = useAPI();
  
  // Testing state
  const [testSuites, setTestSuites] = useState<TestSuite[]>([]);
  const [currentExecution, setCurrentExecution] = useState<TestExecution | null>(null);
  const [selectedType, setSelectedType] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showMonitor, setShowMonitor] = useState(false);

  // Mock test suites data
  const mockTestSuites: TestSuite[] = useMemo(() => [
    {
      id: 'suite-1',
      name: 'API Integration Tests',
      description: 'Test all REST API endpoints and data validation',
      type: 'integration',
      status: 'passed',
      tests: [],
      created_at: '2024-01-15T10:00:00Z',
      last_run: '2024-01-20T14:30:00Z',
      total_tests: 23,
      passed_tests: 21,
      failed_tests: 2,
      skipped_tests: 0,
      duration: 45.2,
      coverage: 87.5,
      tags: ['api', 'backend', 'critical']
    },
    {
      id: 'suite-2',
      name: 'Database Connection Tests',
      description: 'Test database connectivity and query performance',
      type: 'unit',
      status: 'passed',
      tests: [],
      created_at: '2024-01-12T09:00:00Z',
      last_run: '2024-01-20T12:15:00Z',
      total_tests: 15,
      passed_tests: 15,
      failed_tests: 0,
      skipped_tests: 0,
      duration: 8.7,
      coverage: 92.3,
      tags: ['database', 'performance']
    },
    {
      id: 'suite-3',
      name: 'Authentication Flow Tests',
      description: 'Test user authentication and authorization flows',
      type: 'e2e',
      status: 'failed',
      tests: [],
      created_at: '2024-01-18T11:00:00Z',
      last_run: '2024-01-20T16:45:00Z',
      total_tests: 12,
      passed_tests: 8,
      failed_tests: 3,
      skipped_tests: 1,
      duration: 67.3,
      coverage: 78.9,
      tags: ['auth', 'security', 'e2e']
    },
    {
      id: 'suite-4',
      name: 'Performance Benchmarks',
      description: 'Load testing and performance benchmarks',
      type: 'performance',
      status: 'running',
      tests: [],
      created_at: '2024-01-19T14:00:00Z',
      last_run: '2024-01-20T17:00:00Z',
      total_tests: 8,
      passed_tests: 3,
      failed_tests: 0,
      skipped_tests: 0,
      duration: 0,
      coverage: 65.4,
      tags: ['performance', 'load-test']
    },
    {
      id: 'suite-5',
      name: 'Security Vulnerability Tests',
      description: 'Security scanning and vulnerability assessment',
      type: 'security',
      status: 'idle',
      tests: [],
      created_at: '2024-01-20T08:00:00Z',
      last_run: null,
      total_tests: 18,
      passed_tests: 0,
      failed_tests: 0,
      skipped_tests: 0,
      duration: 0,
      tags: ['security', 'vulnerability']
    }
  ], []);

  // Set mock data
  useEffect(() => {
    setTestSuites(mockTestSuites);
  }, [mockTestSuites]);

  // Filter test suites
  const filteredSuites = useMemo(() => {
    return testSuites.filter(suite => {
      const matchesSearch = suite.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           suite.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesType = selectedType === 'all' || suite.type === selectedType;
      return matchesSearch && matchesType;
    });
  }, [testSuites, searchTerm, selectedType]);

  // Test statistics
  const testStats = useMemo(() => {
    const total = testSuites.length;
    const running = testSuites.filter(s => s.status === 'running').length;
    const passed = testSuites.filter(s => s.status === 'passed').length;
    const failed = testSuites.filter(s => s.status === 'failed').length;
    const totalTests = testSuites.reduce((sum, s) => sum + s.total_tests, 0);
    const passedTests = testSuites.reduce((sum, s) => sum + s.passed_tests, 0);
    const failedTests = testSuites.reduce((sum, s) => sum + s.failed_tests, 0);
    const avgCoverage = testSuites.filter(s => s.coverage !== undefined)
      .reduce((sum, s) => sum + (s.coverage || 0), 0) / 
      (testSuites.filter(s => s.coverage !== undefined).length || 1);

    return {
      total,
      running,
      passed,
      failed,
      totalTests,
      passedTests,
      failedTests,
      avgCoverage
    };
  }, [testSuites]);

  // Run test suite
  const handleRunTestSuite = useCallback(async (suiteId: string) => {
    const suite = testSuites.find(s => s.id === suiteId);
    if (!suite) return;

    // Create mock execution
    const execution: TestExecution = {
      id: `execution-${Date.now()}`,
      suite_id: suiteId,
      status: 'running',
      started_at: new Date().toISOString(),
      results: [],
      logs: [
        {
          timestamp: new Date().toISOString(),
          level: 'info',
          message: `Starting test suite: ${suite.name}`,
          source: 'runner'
        }
      ]
    };

    setCurrentExecution(execution);
    setShowMonitor(true);

    // Update suite status
    setTestSuites(prev => prev.map(s => 
      s.id === suiteId ? { ...s, status: 'running' as const } : s
    ));

    // Simulate test execution
    try {
      for (let i = 0; i < suite.total_tests; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000));
        
        const testPassed = Math.random() > 0.2; // 80% success rate
        
        const result: TestResult = {
          test_id: `test-${i}`,
          status: testPassed ? 'passed' : 'failed',
          duration: Math.random() * 2000,
          error: testPassed ? undefined : 'Assertion failed: expected true but got false',
          assertions: []
        };

        execution.results.push(result);
        execution.logs.push({
          timestamp: new Date().toISOString(),
          level: testPassed ? 'info' : 'error',
          message: `Test ${i + 1}: ${testPassed ? 'PASSED' : 'FAILED'}`,
          source: 'runner'
        });

        setCurrentExecution({ ...execution });
      }

      // Complete execution
      execution.status = 'completed';
      execution.completed_at = new Date().toISOString();
      execution.duration = Date.now() - new Date(execution.started_at).getTime();

      const passedCount = execution.results.filter(r => r.status === 'passed').length;
      const failedCount = execution.results.filter(r => r.status === 'failed').length;

      // Update suite with results
      setTestSuites(prev => prev.map(s => 
        s.id === suiteId ? {
          ...s,
          status: failedCount > 0 ? 'failed' as const : 'passed' as const,
          passed_tests: passedCount,
          failed_tests: failedCount,
          last_run: new Date().toISOString(),
          duration: execution.duration! / 1000
        } : s
      ));

      setCurrentExecution(execution);

    } catch (error) {
      execution.status = 'failed';
      setCurrentExecution(execution);
      
      setTestSuites(prev => prev.map(s => 
        s.id === suiteId ? { ...s, status: 'failed' as const } : s
      ));
    }
  }, [testSuites]);

  // Cancel execution
  const handleCancelExecution = useCallback(() => {
    if (currentExecution) {
      setCurrentExecution({ ...currentExecution, status: 'cancelled' });
      setTestSuites(prev => prev.map(s => 
        s.id === currentExecution.suite_id ? { ...s, status: 'idle' as const } : s
      ));
    }
    setShowMonitor(false);
  }, [currentExecution]);

  return (
    <div className="h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              Testing Interface
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Automated testing suite for your project
            </p>
          </div>
          
          <div className="flex items-center space-x-3">
            <MagneticButton
              onClick={() => {/* Run all tests */}}
              className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors flex items-center space-x-2"
            >
              <span>▶️</span>
              <span>Run All Tests</span>
            </MagneticButton>
            
            <button className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2">
              <span>➕</span>
              <span>New Suite</span>
            </button>
          </div>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 mb-6">
          <div className="bg-blue-50 dark:bg-blue-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {testStats.total}
            </div>
            <div className="text-sm text-blue-600 dark:text-blue-400">Total Suites</div>
          </div>
          
          <div className="bg-yellow-50 dark:bg-yellow-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {testStats.running}
            </div>
            <div className="text-sm text-yellow-600 dark:text-yellow-400">Running</div>
          </div>
          
          <div className="bg-green-50 dark:bg-green-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {testStats.passed}
            </div>
            <div className="text-sm text-green-600 dark:text-green-400">Passed</div>
          </div>
          
          <div className="bg-red-50 dark:bg-red-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {testStats.failed}
            </div>
            <div className="text-sm text-red-600 dark:text-red-400">Failed</div>
          </div>
          
          <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">
              {testStats.totalTests}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Total Tests</div>
          </div>
          
          <div className="bg-green-50 dark:bg-green-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {testStats.passedTests}
            </div>
            <div className="text-sm text-green-600 dark:text-green-400">Passed Tests</div>
          </div>
          
          <div className="bg-red-50 dark:bg-red-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {testStats.failedTests}
            </div>
            <div className="text-sm text-red-600 dark:text-red-400">Failed Tests</div>
          </div>
          
          <div className="bg-purple-50 dark:bg-purple-900 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {testStats.avgCoverage.toFixed(1)}%
            </div>
            <div className="text-sm text-purple-600 dark:text-purple-400">Avg Coverage</div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search test suites..."
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
            {Object.entries(SUITE_TYPE_CONFIG).map(([key, config]) => (
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
        ) : filteredSuites.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            <AnimatePresence>
              {filteredSuites.map(suite => (
                <TestSuiteCard
                  key={suite.id}
                  suite={suite}
                  onRun={handleRunTestSuite}
                  onView={(suite) => console.log('View suite:', suite)}
                  onEdit={(suite) => console.log('Edit suite:', suite)}
                  onDelete={(id) => console.log('Delete suite:', id)}
                  isRunning={suite.status === 'running'}
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
            <div className="text-6xl mb-4">🧪</div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              No test suites found
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {searchTerm || selectedType !== 'all' 
                ? 'Try adjusting your search filters'
                : 'Create your first test suite to get started'
              }
            </p>
            {(!searchTerm && selectedType === 'all') && (
              <button className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors">
                Create Test Suite
              </button>
            )}
          </motion.div>
        )}
      </div>

      {/* Test Execution Monitor */}
      <AnimatePresence>
        {showMonitor && (
          <TestExecutionMonitor
            execution={currentExecution}
            onCancel={handleCancelExecution}
            isVisible={showMonitor}
          />
        )}
      </AnimatePresence>
    </div>
  );
};