/**
 * DafelHub Enterprise Performance Monitoring System
 * Advanced Web Vitals tracking with real-time analytics
 * Target: <1.5s FCP, <2.5s LCP, <0.1 CLS, <100ms FID
 */

class PerformanceMonitor {
  constructor(options = {}) {
    this.options = {
      apiEndpoint: '/api/analytics',
      enableRealTimeReporting: true,
      memoryCheckInterval: 30000,
      performanceThresholds: {
        FCP: { good: 1500, needsImprovement: 2500, poor: 4000 },
        LCP: { good: 2500, needsImprovement: 4000, poor: 6000 },
        CLS: { good: 0.1, needsImprovement: 0.25, poor: 0.5 },
        FID: { good: 100, needsImprovement: 300, poor: 500 },
        TTFB: { good: 800, needsImprovement: 1800, poor: 3000 },
        INP: { good: 200, needsImprovement: 500, poor: 1000 }
      },
      ...options
    };

    this.metrics = new Map();
    this.observers = new Map();
    this.memoryStats = [];
    this.resourceTimings = [];
    this.isInitialized = false;
    
    this.init();
  }

  init() {
    if (typeof window === 'undefined' || this.isInitialized) return;
    
    try {
      this.setupWebVitalsTracking();
      this.setupMemoryMonitoring();
      this.setupResourceTimingAnalysis();
      this.setupNavigationTiming();
      this.setupCustomMetrics();
      this.startRealTimeMonitoring();
      
      this.isInitialized = true;
      console.log('🚀 DafelHub Performance Monitor initialized');
    } catch (error) {
      console.error('Performance Monitor initialization failed:', error);
    }
  }

  setupWebVitalsTracking() {
    // Enhanced First Contentful Paint (FCP) tracking
    this.observeMetric('paint', (entries) => {
      entries.forEach(entry => {
        if (entry.name === 'first-contentful-paint') {
          this.recordMetric('FCP', entry.startTime, entry);
        }
      });
    });

    // Enhanced Largest Contentful Paint (LCP) tracking
    this.observeMetric('largest-contentful-paint', (entries) => {
      const lastEntry = entries[entries.length - 1];
      if (lastEntry) {
        this.recordMetric('LCP', lastEntry.startTime, lastEntry);
      }
    });

    // Enhanced First Input Delay (FID) tracking
    this.observeMetric('first-input', (entries) => {
      entries.forEach(entry => {
        const fid = entry.processingStart - entry.startTime;
        this.recordMetric('FID', fid, entry);
      });
    });

    // Enhanced Cumulative Layout Shift (CLS) tracking
    let clsValue = 0;
    let clsEntries = [];
    
    this.observeMetric('layout-shift', (entries) => {
      entries.forEach(entry => {
        if (!entry.hadRecentInput) {
          clsValue += entry.value;
          clsEntries.push(entry);
        }
      });
    });

    // Report CLS on page visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden' && clsValue > 0) {
        this.recordMetric('CLS', clsValue, clsEntries);
      }
    });

    // Enhanced Time to First Byte (TTFB) tracking
    if (performance.timing) {
      const ttfb = performance.timing.responseStart - performance.timing.navigationStart;
      this.recordMetric('TTFB', ttfb);
    }

    // Interaction to Next Paint (INP) tracking
    this.setupINPTracking();
  }

  setupINPTracking() {
    let interactions = [];
    let interactionObserver;

    if ('PerformanceEventTiming' in window) {
      interactionObserver = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          if (entry.interactionId) {
            interactions.push({
              id: entry.interactionId,
              latency: entry.processingEnd - entry.startTime,
              entry
            });
          }
        });

        // Calculate INP as 98th percentile of interaction latencies
        if (interactions.length >= 10) {
          const latencies = interactions.map(i => i.latency).sort((a, b) => a - b);
          const p98Index = Math.floor(latencies.length * 0.98);
          const inp = latencies[p98Index] || latencies[latencies.length - 1];
          this.recordMetric('INP', inp);
        }
      });

      try {
        interactionObserver.observe({ type: 'event', buffered: true });
      } catch (e) {
        console.warn('INP tracking not supported:', e);
      }
    }
  }

  setupMemoryMonitoring() {
    if (!performance.memory) return;

    const checkMemory = () => {
      const memory = performance.memory;
      const memoryInfo = {
        usedJSHeapSize: memory.usedJSHeapSize,
        totalJSHeapSize: memory.totalJSHeapSize,
        jsHeapSizeLimit: memory.jsHeapSizeLimit,
        timestamp: Date.now(),
        usage: (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100
      };

      this.memoryStats.push(memoryInfo);
      
      // Keep only last 100 readings
      if (this.memoryStats.length > 100) {
        this.memoryStats.shift();
      }

      // Alert on high memory usage (>85%)
      if (memoryInfo.usage > 85) {
        this.reportPerformanceIssue('HIGH_MEMORY_USAGE', memoryInfo);
      }

      this.reportMemoryMetrics(memoryInfo);
    };

    // Check memory every 30 seconds
    setInterval(checkMemory, this.options.memoryCheckInterval);
    checkMemory(); // Initial check
  }

  setupResourceTimingAnalysis() {
    if (!performance.getEntriesByType) return;

    const analyzeResources = () => {
      const resources = performance.getEntriesByType('resource');
      const analysis = this.analyzeResourcePerformance(resources);
      
      this.resourceTimings.push({
        timestamp: Date.now(),
        analysis
      });

      this.reportResourceAnalysis(analysis);
    };

    // Analyze resources periodically
    setTimeout(analyzeResources, 5000); // After initial page load
    setInterval(analyzeResources, 60000); // Every minute
  }

  analyzeResourcePerformance(resources) {
    const analysis = {
      totalResources: resources.length,
      totalSize: 0,
      totalTransferSize: 0,
      slowResources: [],
      largeResources: [],
      cachedResources: [],
      compressionStats: {},
      resourceTypes: {},
      performanceIssues: []
    };

    resources.forEach(resource => {
      // Size analysis
      if (resource.transferSize !== undefined) {
        analysis.totalTransferSize += resource.transferSize;
        analysis.totalSize += resource.decodedBodySize || resource.transferSize;
      }

      // Timing analysis
      const loadTime = resource.responseEnd - resource.responseStart;
      if (loadTime > 1000) {
        analysis.slowResources.push({
          name: resource.name,
          loadTime,
          size: resource.transferSize
        });
      }

      // Size analysis
      if (resource.transferSize > 500000) { // >500KB
        analysis.largeResources.push({
          name: resource.name,
          size: resource.transferSize,
          loadTime
        });
      }

      // Cache analysis
      if (resource.transferSize === 0) {
        analysis.cachedResources.push(resource.name);
      }

      // Resource type analysis
      const type = this.getResourceType(resource);
      if (!analysis.resourceTypes[type]) {
        analysis.resourceTypes[type] = { count: 0, totalSize: 0 };
      }
      analysis.resourceTypes[type].count++;
      analysis.resourceTypes[type].totalSize += resource.transferSize || 0;
    });

    // Calculate compression ratio
    if (analysis.totalSize > 0) {
      analysis.compressionStats.ratio = 
        (analysis.totalSize - analysis.totalTransferSize) / analysis.totalSize;
      analysis.compressionStats.savedBytes = 
        analysis.totalSize - analysis.totalTransferSize;
    }

    // Identify performance issues
    if (analysis.slowResources.length > 5) {
      analysis.performanceIssues.push('TOO_MANY_SLOW_RESOURCES');
    }
    
    if (analysis.largeResources.length > 3) {
      analysis.performanceIssues.push('TOO_MANY_LARGE_RESOURCES');
    }

    if (analysis.compressionStats.ratio < 0.3) {
      analysis.performanceIssues.push('POOR_COMPRESSION');
    }

    return analysis;
  }

  setupNavigationTiming() {
    if (!performance.timing) return;

    const nav = performance.timing;
    const navigationMetrics = {
      dns: nav.domainLookupEnd - nav.domainLookupStart,
      tcp: nav.connectEnd - nav.connectStart,
      ssl: nav.secureConnectionStart ? nav.connectEnd - nav.secureConnectionStart : 0,
      ttfb: nav.responseStart - nav.navigationStart,
      download: nav.responseEnd - nav.responseStart,
      dom: nav.domContentLoadedEventEnd - nav.navigationStart,
      load: nav.loadEventEnd - nav.navigationStart
    };

    this.recordMetric('NAVIGATION_TIMING', navigationMetrics);
  }

  setupCustomMetrics() {
    // Track JavaScript errors
    window.addEventListener('error', (event) => {
      this.recordMetric('JS_ERROR', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        stack: event.error?.stack
      });
    });

    // Track unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.recordMetric('UNHANDLED_REJECTION', {
        reason: event.reason,
        stack: event.reason?.stack
      });
    });

    // Track long tasks
    if ('PerformanceObserver' in window) {
      try {
        const longTaskObserver = new PerformanceObserver((list) => {
          list.getEntries().forEach((entry) => {
            if (entry.duration > 50) { // Tasks longer than 50ms
              this.recordMetric('LONG_TASK', {
                duration: entry.duration,
                startTime: entry.startTime,
                name: entry.name
              });
            }
          });
        });
        longTaskObserver.observe({ entryTypes: ['longtask'] });
      } catch (e) {
        console.warn('Long task monitoring not supported:', e);
      }
    }
  }

  startRealTimeMonitoring() {
    if (!this.options.enableRealTimeReporting) return;

    // Real-time performance tracking
    setInterval(() => {
      const currentMetrics = this.getCurrentMetrics();
      this.reportRealTimeMetrics(currentMetrics);
    }, 5000); // Every 5 seconds

    // Performance budget monitoring
    setInterval(() => {
      this.checkPerformanceBudgets();
    }, 10000); // Every 10 seconds
  }

  observeMetric(type, callback) {
    if (!('PerformanceObserver' in window)) return;

    try {
      const observer = new PerformanceObserver((list) => {
        callback(list.getEntries());
      });

      observer.observe({ entryTypes: [type] });
      this.observers.set(type, observer);
    } catch (error) {
      console.warn(`Cannot observe ${type}:`, error);
    }
  }

  recordMetric(name, value, entry = null) {
    const timestamp = Date.now();
    const rating = this.getRating(name, value);
    
    const metric = {
      name,
      value,
      rating,
      timestamp,
      entry,
      url: window.location.pathname,
      userAgent: navigator.userAgent
    };

    this.metrics.set(name, metric);

    // Log in development
    if (process.env.NODE_ENV === 'development') {
      console.log(`📊 ${name}: ${typeof value === 'number' ? Math.round(value) : value}ms (${rating})`);
    }

    // Send to analytics
    this.reportMetric(metric);
  }

  getRating(metricName, value) {
    const thresholds = this.options.performanceThresholds[metricName];
    if (!thresholds) return 'unknown';

    if (typeof value === 'object') return 'info';

    if (value <= thresholds.good) return 'good';
    if (value <= thresholds.needsImprovement) return 'needs-improvement';
    return 'poor';
  }

  getCurrentMetrics() {
    return {
      webVitals: Object.fromEntries(this.metrics),
      memory: this.memoryStats[this.memoryStats.length - 1] || null,
      resources: this.resourceTimings[this.resourceTimings.length - 1] || null,
      timestamp: Date.now()
    };
  }

  checkPerformanceBudgets() {
    const issues = [];
    
    this.metrics.forEach((metric, name) => {
      if (metric.rating === 'poor') {
        issues.push({
          metric: name,
          value: metric.value,
          threshold: this.options.performanceThresholds[name]?.good || 'unknown',
          severity: 'high'
        });
      }
    });

    if (issues.length > 0) {
      this.reportPerformanceIssue('PERFORMANCE_BUDGET_EXCEEDED', { issues });
    }
  }

  getResourceType(resource) {
    if (resource.initiatorType) return resource.initiatorType;
    
    const url = resource.name.toLowerCase();
    if (url.includes('.js')) return 'script';
    if (url.includes('.css')) return 'stylesheet';
    if (url.match(/\.(jpg|jpeg|png|gif|webp|svg)/)) return 'img';
    if (url.match(/\.(woff|woff2|ttf|eot)/)) return 'font';
    return 'other';
  }

  async reportMetric(metric) {
    if (!this.options.apiEndpoint) return;

    try {
      await fetch(this.options.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'performance_metric',
          ...metric,
          sessionId: this.getSessionId(),
          buildId: window.BUILD_ID || 'unknown'
        })
      });
    } catch (error) {
      console.warn('Failed to report metric:', error);
    }
  }

  async reportMemoryMetrics(memoryInfo) {
    if (!this.options.apiEndpoint) return;

    try {
      await fetch(this.options.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'memory_metrics',
          ...memoryInfo,
          sessionId: this.getSessionId()
        })
      });
    } catch (error) {
      console.warn('Failed to report memory metrics:', error);
    }
  }

  async reportResourceAnalysis(analysis) {
    if (!this.options.apiEndpoint) return;

    try {
      await fetch(this.options.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'resource_analysis',
          analysis,
          sessionId: this.getSessionId(),
          timestamp: Date.now()
        })
      });
    } catch (error) {
      console.warn('Failed to report resource analysis:', error);
    }
  }

  async reportRealTimeMetrics(metrics) {
    if (!this.options.apiEndpoint) return;

    try {
      await fetch(this.options.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'realtime_metrics',
          metrics,
          sessionId: this.getSessionId()
        })
      });
    } catch (error) {
      console.warn('Failed to report real-time metrics:', error);
    }
  }

  async reportPerformanceIssue(type, data) {
    if (!this.options.apiEndpoint) return;

    try {
      await fetch(this.options.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'performance_issue',
          issueType: type,
          data,
          sessionId: this.getSessionId(),
          timestamp: Date.now(),
          url: window.location.href
        })
      });
    } catch (error) {
      console.warn('Failed to report performance issue:', error);
    }
  }

  getSessionId() {
    if (!this.sessionId) {
      this.sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    return this.sessionId;
  }

  // Public API methods
  getMetrics() {
    return Object.fromEntries(this.metrics);
  }

  getMemoryStats() {
    return this.memoryStats;
  }

  getResourceTimings() {
    return this.resourceTimings;
  }

  generateReport() {
    const metrics = this.getMetrics();
    const memory = this.getMemoryStats();
    const resources = this.getResourceTimings();

    return {
      summary: {
        totalMetrics: this.metrics.size,
        goodMetrics: Array.from(this.metrics.values()).filter(m => m.rating === 'good').length,
        poorMetrics: Array.from(this.metrics.values()).filter(m => m.rating === 'poor').length,
        memoryChecks: memory.length,
        resourceAnalyses: resources.length
      },
      webVitals: metrics,
      memoryUsage: memory,
      resourcePerformance: resources,
      timestamp: Date.now()
    };
  }

  destroy() {
    this.observers.forEach(observer => observer.disconnect());
    this.observers.clear();
    this.metrics.clear();
    this.memoryStats.length = 0;
    this.resourceTimings.length = 0;
    this.isInitialized = false;
  }
}

// Global initialization
if (typeof window !== 'undefined') {
  window.PerformanceMonitor = PerformanceMonitor;
  
  // Auto-initialize if not disabled
  if (!window.DISABLE_AUTO_PERFORMANCE_MONITORING) {
    window.performanceMonitor = new PerformanceMonitor();
  }
}

export default PerformanceMonitor;