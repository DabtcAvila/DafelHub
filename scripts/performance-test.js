#!/usr/bin/env node

/**
 * DafelHub Performance Testing Suite
 * Automated performance testing and optimization utilities
 */

const fs = require('fs').promises;
const path = require('path');
const { execSync, spawn } = require('child_process');

class PerformanceTester {
  constructor(options = {}) {
    this.options = {
      baseUrl: 'http://localhost:3000',
      outputDir: './performance-reports',
      lighthouse: {
        runs: 5,
        desktop: true,
        mobile: true
      },
      targets: {
        performance: 95,
        accessibility: 95,
        bestPractices: 95,
        seo: 95,
        fcp: 1500,
        lcp: 2500,
        cls: 0.1,
        fid: 100,
        ttfb: 600
      },
      ...options
    };

    this.results = {
      lighthouse: [],
      customMetrics: {},
      recommendations: [],
      summary: {}
    };
  }

  async runFullSuite() {
    console.log('🚀 Starting DafelHub Performance Test Suite...\n');

    try {
      // Ensure output directory exists
      await this.ensureOutputDir();

      // 1. Run Lighthouse audits
      await this.runLighthouseTests();

      // 2. Run custom performance tests
      await this.runCustomTests();

      // 3. Analyze bundle sizes
      await this.analyzeBundleSizes();

      // 4. Test loading performance
      await this.testLoadingPerformance();

      // 5. Generate recommendations
      await this.generateRecommendations();

      // 6. Generate comprehensive report
      await this.generateReport();

      console.log('\n✅ Performance testing complete!');
      console.log(`📊 Reports saved to: ${this.options.outputDir}`);

    } catch (error) {
      console.error('❌ Performance testing failed:', error.message);
      process.exit(1);
    }
  }

  async ensureOutputDir() {
    try {
      await fs.mkdir(this.options.outputDir, { recursive: true });
    } catch (error) {
      console.error('Failed to create output directory:', error);
    }
  }

  async runLighthouseTests() {
    console.log('🔍 Running Lighthouse audits...');

    const urls = [
      this.options.baseUrl,
      `${this.options.baseUrl}/performance-dashboard.html`,
      `${this.options.baseUrl}/docs/`,
      `${this.options.baseUrl}/studio.html`
    ];

    for (const url of urls) {
      console.log(`  Testing: ${url}`);
      
      // Desktop test
      const desktopResult = await this.runLighthouse(url, 'desktop');
      this.results.lighthouse.push({
        url,
        device: 'desktop',
        ...desktopResult
      });

      // Mobile test  
      const mobileResult = await this.runLighthouse(url, 'mobile');
      this.results.lighthouse.push({
        url,
        device: 'mobile',
        ...mobileResult
      });
    }

    console.log('✅ Lighthouse audits completed\n');
  }

  async runLighthouse(url, device) {
    const config = {
      extends: 'lighthouse:default',
      settings: {
        onlyAudits: [
          'first-contentful-paint',
          'largest-contentful-paint',
          'cumulative-layout-shift',
          'total-blocking-time',
          'speed-index',
          'interactive',
          'server-response-time'
        ],
        emulatedFormFactor: device,
        throttling: device === 'mobile' ? {
          rttMs: 150,
          throughputKbps: 1638.4,
          requestLatencyMs: 0,
          downloadThroughputKbps: 0,
          uploadThroughputKbps: 0,
          cpuSlowdownMultiplier: 4
        } : {
          rttMs: 40,
          throughputKbps: 10240,
          requestLatencyMs: 0,
          downloadThroughputKbps: 0,
          uploadThroughputKbps: 0,
          cpuSlowdownMultiplier: 1
        }
      }
    };

    try {
      // Use lighthouse programmatically
      const lighthouse = require('lighthouse');
      const chromeLauncher = require('chrome-launcher');

      const chrome = await chromeLauncher.launch({ chromeFlags: ['--headless'] });
      const options = {
        logLevel: 'info',
        output: 'json',
        onlyCategories: ['performance'],
        port: chrome.port,
      };

      const runnerResult = await lighthouse(url, options, config);
      await chrome.kill();

      return {
        performance: runnerResult.lhr.categories.performance.score * 100,
        fcp: runnerResult.lhr.audits['first-contentful-paint'].numericValue,
        lcp: runnerResult.lhr.audits['largest-contentful-paint'].numericValue,
        cls: runnerResult.lhr.audits['cumulative-layout-shift'].numericValue,
        tbt: runnerResult.lhr.audits['total-blocking-time'].numericValue,
        si: runnerResult.lhr.audits['speed-index'].numericValue,
        tti: runnerResult.lhr.audits['interactive'].numericValue,
        ttfb: runnerResult.lhr.audits['server-response-time'].numericValue
      };
    } catch (error) {
      console.warn(`  Warning: Lighthouse test failed for ${url} (${device}):`, error.message);
      return {
        performance: 0,
        fcp: 0,
        lcp: 0,
        cls: 0,
        tbt: 0,
        si: 0,
        tti: 0,
        ttfb: 0,
        error: error.message
      };
    }
  }

  async runCustomTests() {
    console.log('🧪 Running custom performance tests...');

    // Test critical resource loading
    await this.testCriticalResources();

    // Test JavaScript execution time
    await this.testJavaScriptPerformance();

    // Test image optimization
    await this.testImageOptimization();

    // Test caching effectiveness
    await this.testCaching();

    console.log('✅ Custom performance tests completed\n');
  }

  async testCriticalResources() {
    console.log('  Testing critical resource loading...');

    const criticalResources = [
      '/favicon.svg',
      '/manifest.json',
      '/public/js/performance-monitor.js',
      '/public/sw.js'
    ];

    const results = [];
    
    for (const resource of criticalResources) {
      const start = Date.now();
      try {
        const response = await fetch(`${this.options.baseUrl}${resource}`);
        const loadTime = Date.now() - start;
        
        results.push({
          resource,
          loadTime,
          size: response.headers.get('content-length') || 'unknown',
          cached: response.headers.get('cache-control') ? true : false,
          compressed: response.headers.get('content-encoding') ? true : false,
          status: response.status
        });
      } catch (error) {
        results.push({
          resource,
          error: error.message,
          loadTime: Date.now() - start
        });
      }
    }

    this.results.customMetrics.criticalResources = results;
  }

  async testJavaScriptPerformance() {
    console.log('  Testing JavaScript performance...');

    try {
      // Analyze JavaScript files
      const jsFiles = await this.findJavaScriptFiles();
      const analysis = [];

      for (const file of jsFiles) {
        const stats = await fs.stat(file);
        const content = await fs.readFile(file, 'utf-8');
        
        analysis.push({
          file: path.relative(process.cwd(), file),
          size: stats.size,
          lines: content.split('\n').length,
          complexity: this.analyzeComplexity(content),
          hasSourceMap: content.includes('//# sourceMappingURL'),
          minified: this.isMinified(content)
        });
      }

      this.results.customMetrics.javascript = analysis;
    } catch (error) {
      console.warn('  Warning: JavaScript analysis failed:', error.message);
    }
  }

  async testImageOptimization() {
    console.log('  Testing image optimization...');

    try {
      const images = await this.findImageFiles();
      const analysis = [];

      for (const image of images) {
        const stats = await fs.stat(image);
        const ext = path.extname(image).toLowerCase();
        
        analysis.push({
          file: path.relative(process.cwd(), image),
          size: stats.size,
          format: ext,
          optimized: this.isOptimizedFormat(ext),
          oversized: stats.size > 500000 // >500KB
        });
      }

      this.results.customMetrics.images = analysis;
    } catch (error) {
      console.warn('  Warning: Image analysis failed:', error.message);
    }
  }

  async testCaching() {
    console.log('  Testing caching effectiveness...');

    const testUrls = [
      `${this.options.baseUrl}/`,
      `${this.options.baseUrl}/favicon.svg`,
      `${this.options.baseUrl}/public/js/performance-monitor.js`
    ];

    const results = [];

    for (const url of testUrls) {
      try {
        const response = await fetch(url);
        const cacheControl = response.headers.get('cache-control');
        const etag = response.headers.get('etag');
        const lastModified = response.headers.get('last-modified');

        results.push({
          url,
          hasCacheControl: !!cacheControl,
          hasETag: !!etag,
          hasLastModified: !!lastModified,
          cacheControl,
          cacheable: this.isCacheable(cacheControl)
        });
      } catch (error) {
        results.push({
          url,
          error: error.message
        });
      }
    }

    this.results.customMetrics.caching = results;
  }

  async analyzeBundleSizes() {
    console.log('📦 Analyzing bundle sizes...');

    try {
      const bundles = await this.findBundleFiles();
      const analysis = [];

      for (const bundle of bundles) {
        const stats = await fs.stat(bundle);
        
        analysis.push({
          file: path.relative(process.cwd(), bundle),
          size: stats.size,
          sizeKB: Math.round(stats.size / 1024),
          sizeMB: Math.round(stats.size / 1024 / 1024 * 100) / 100,
          oversized: stats.size > 250000, // >250KB
          type: this.getBundleType(bundle)
        });
      }

      this.results.customMetrics.bundles = analysis;
      console.log('✅ Bundle analysis completed\n');
    } catch (error) {
      console.warn('  Warning: Bundle analysis failed:', error.message);
    }
  }

  async testLoadingPerformance() {
    console.log('⚡ Testing loading performance...');

    const urls = [this.options.baseUrl];
    const results = [];

    for (const url of urls) {
      console.log(`  Testing: ${url}`);
      
      const metrics = await this.measureLoadingMetrics(url);
      results.push({
        url,
        ...metrics
      });
    }

    this.results.customMetrics.loading = results;
    console.log('✅ Loading performance tests completed\n');
  }

  async measureLoadingMetrics(url) {
    // This would typically use puppeteer or similar for real browser metrics
    // For now, we'll simulate with basic timing
    const start = Date.now();
    
    try {
      const response = await fetch(url);
      const ttfb = Date.now() - start;
      const content = await response.text();
      const totalTime = Date.now() - start;

      return {
        ttfb,
        totalTime,
        contentSize: content.length,
        status: response.status,
        redirected: response.redirected
      };
    } catch (error) {
      return {
        error: error.message,
        ttfb: Date.now() - start,
        totalTime: Date.now() - start
      };
    }
  }

  async generateRecommendations() {
    console.log('💡 Generating optimization recommendations...');

    const recommendations = [];

    // Analyze Lighthouse results
    const lighthouseIssues = this.analyzeLighthouseResults();
    recommendations.push(...lighthouseIssues);

    // Analyze custom metrics
    const customIssues = this.analyzeCustomMetrics();
    recommendations.push(...customIssues);

    this.results.recommendations = recommendations;
    console.log(`✅ Generated ${recommendations.length} recommendations\n`);
  }

  analyzeLighthouseResults() {
    const recommendations = [];
    const { targets } = this.options;

    this.results.lighthouse.forEach(result => {
      if (result.performance < targets.performance) {
        recommendations.push({
          type: 'performance',
          priority: 'high',
          message: `Performance score (${result.performance}) is below target (${targets.performance}) for ${result.url}`,
          suggestions: [
            'Optimize images and use modern formats',
            'Minimize and compress JavaScript/CSS',
            'Implement proper caching strategies',
            'Remove unused code'
          ]
        });
      }

      if (result.fcp > targets.fcp) {
        recommendations.push({
          type: 'loading',
          priority: 'high',
          message: `First Contentful Paint (${Math.round(result.fcp)}ms) exceeds target (${targets.fcp}ms)`,
          suggestions: [
            'Preload critical resources',
            'Optimize critical rendering path',
            'Reduce server response time',
            'Minimize render-blocking resources'
          ]
        });
      }

      if (result.lcp > targets.lcp) {
        recommendations.push({
          type: 'loading',
          priority: 'high',
          message: `Largest Contentful Paint (${Math.round(result.lcp)}ms) exceeds target (${targets.lcp}ms)`,
          suggestions: [
            'Optimize LCP element loading',
            'Preload LCP image',
            'Improve server response time',
            'Remove render-blocking resources'
          ]
        });
      }

      if (result.cls > targets.cls) {
        recommendations.push({
          type: 'stability',
          priority: 'medium',
          message: `Cumulative Layout Shift (${result.cls.toFixed(3)}) exceeds target (${targets.cls})`,
          suggestions: [
            'Include size attributes on images and video',
            'Reserve space for ads and embeds',
            'Avoid inserting content above existing content',
            'Use CSS transform animations'
          ]
        });
      }
    });

    return recommendations;
  }

  analyzeCustomMetrics() {
    const recommendations = [];

    // Check bundle sizes
    if (this.results.customMetrics.bundles) {
      this.results.customMetrics.bundles.forEach(bundle => {
        if (bundle.oversized) {
          recommendations.push({
            type: 'optimization',
            priority: 'medium',
            message: `Large bundle detected: ${bundle.file} (${bundle.sizeKB}KB)`,
            suggestions: [
              'Implement code splitting',
              'Remove unused dependencies',
              'Use tree shaking',
              'Consider lazy loading'
            ]
          });
        }
      });
    }

    // Check image optimization
    if (this.results.customMetrics.images) {
      const unoptimizedImages = this.results.customMetrics.images.filter(img => !img.optimized || img.oversized);
      
      if (unoptimizedImages.length > 0) {
        recommendations.push({
          type: 'images',
          priority: 'medium',
          message: `${unoptimizedImages.length} images need optimization`,
          suggestions: [
            'Convert images to WebP/AVIF format',
            'Implement responsive images',
            'Compress images without quality loss',
            'Use lazy loading for off-screen images'
          ]
        });
      }
    }

    // Check caching
    if (this.results.customMetrics.caching) {
      const uncachedResources = this.results.customMetrics.caching.filter(cache => !cache.cacheable);
      
      if (uncachedResources.length > 0) {
        recommendations.push({
          type: 'caching',
          priority: 'low',
          message: `${uncachedResources.length} resources have poor caching`,
          suggestions: [
            'Implement proper Cache-Control headers',
            'Use ETags for cache validation',
            'Set appropriate cache expiration times',
            'Consider using a CDN'
          ]
        });
      }
    }

    return recommendations;
  }

  async generateReport() {
    console.log('📋 Generating comprehensive report...');

    // Create summary
    this.results.summary = this.generateSummary();

    // Generate HTML report
    const htmlReport = this.generateHtmlReport();
    await fs.writeFile(
      path.join(this.options.outputDir, 'performance-report.html'),
      htmlReport
    );

    // Generate JSON report
    await fs.writeFile(
      path.join(this.options.outputDir, 'performance-report.json'),
      JSON.stringify(this.results, null, 2)
    );

    // Generate CSV summary
    const csvReport = this.generateCsvReport();
    await fs.writeFile(
      path.join(this.options.outputDir, 'performance-summary.csv'),
      csvReport
    );

    console.log('✅ Reports generated successfully');
  }

  generateSummary() {
    const lighthouse = this.results.lighthouse;
    const avgPerformance = lighthouse.reduce((sum, r) => sum + r.performance, 0) / lighthouse.length;
    const avgFCP = lighthouse.reduce((sum, r) => sum + r.fcp, 0) / lighthouse.length;
    const avgLCP = lighthouse.reduce((sum, r) => sum + r.lcp, 0) / lighthouse.length;
    const avgCLS = lighthouse.reduce((sum, r) => sum + r.cls, 0) / lighthouse.length;

    return {
      averagePerformanceScore: Math.round(avgPerformance),
      averageFCP: Math.round(avgFCP),
      averageLCP: Math.round(avgLCP),
      averageCLS: Math.round(avgCLS * 1000) / 1000,
      totalRecommendations: this.results.recommendations.length,
      highPriorityIssues: this.results.recommendations.filter(r => r.priority === 'high').length,
      testsRun: lighthouse.length,
      timestamp: new Date().toISOString()
    };
  }

  generateHtmlReport() {
    return `
<!DOCTYPE html>
<html>
<head>
    <title>DafelHub Performance Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2rem; }
        .header { text-align: center; margin-bottom: 2rem; }
        .summary { background: #f5f5f5; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; }
        .metric { display: inline-block; margin: 0.5rem; padding: 1rem; background: white; border-radius: 4px; }
        .good { border-left: 4px solid #16a34a; }
        .warning { border-left: 4px solid #d97706; }
        .poor { border-left: 4px solid #dc2626; }
        .recommendations { margin: 2rem 0; }
        .recommendation { padding: 1rem; margin: 0.5rem 0; border-radius: 4px; }
        .high { background: #fee2e2; }
        .medium { background: #fef3c7; }
        .low { background: #f0f9ff; }
        table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
        th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd; }
        th { background: #f5f5f5; }
    </style>
</head>
<body>
    <div class="header">
        <h1>DafelHub Performance Report</h1>
        <p>Generated on ${new Date().toLocaleString()}</p>
    </div>
    
    <div class="summary">
        <h2>Performance Summary</h2>
        <div class="metric ${this.results.summary.averagePerformanceScore >= 90 ? 'good' : this.results.summary.averagePerformanceScore >= 70 ? 'warning' : 'poor'}">
            <strong>Performance Score</strong><br>
            ${this.results.summary.averagePerformanceScore}/100
        </div>
        <div class="metric ${this.results.summary.averageFCP <= 1500 ? 'good' : this.results.summary.averageFCP <= 2500 ? 'warning' : 'poor'}">
            <strong>First Contentful Paint</strong><br>
            ${this.results.summary.averageFCP}ms
        </div>
        <div class="metric ${this.results.summary.averageLCP <= 2500 ? 'good' : this.results.summary.averageLCP <= 4000 ? 'warning' : 'poor'}">
            <strong>Largest Contentful Paint</strong><br>
            ${this.results.summary.averageLCP}ms
        </div>
        <div class="metric ${this.results.summary.averageCLS <= 0.1 ? 'good' : this.results.summary.averageCLS <= 0.25 ? 'warning' : 'poor'}">
            <strong>Cumulative Layout Shift</strong><br>
            ${this.results.summary.averageCLS}
        </div>
    </div>

    <div class="recommendations">
        <h2>Optimization Recommendations (${this.results.recommendations.length})</h2>
        ${this.results.recommendations.map(rec => `
            <div class="recommendation ${rec.priority}">
                <h3>${rec.type.toUpperCase()} - ${rec.priority.toUpperCase()} PRIORITY</h3>
                <p>${rec.message}</p>
                <ul>
                    ${rec.suggestions.map(s => `<li>${s}</li>`).join('')}
                </ul>
            </div>
        `).join('')}
    </div>

    <h2>Detailed Results</h2>
    <table>
        <thead>
            <tr>
                <th>URL</th>
                <th>Device</th>
                <th>Performance</th>
                <th>FCP (ms)</th>
                <th>LCP (ms)</th>
                <th>CLS</th>
                <th>TTI (ms)</th>
            </tr>
        </thead>
        <tbody>
            ${this.results.lighthouse.map(result => `
                <tr>
                    <td>${result.url}</td>
                    <td>${result.device}</td>
                    <td>${result.performance}</td>
                    <td>${Math.round(result.fcp)}</td>
                    <td>${Math.round(result.lcp)}</td>
                    <td>${result.cls.toFixed(3)}</td>
                    <td>${Math.round(result.tti)}</td>
                </tr>
            `).join('')}
        </tbody>
    </table>
</body>
</html>`;
  }

  generateCsvReport() {
    const headers = ['URL', 'Device', 'Performance', 'FCP', 'LCP', 'CLS', 'TTI', 'TBT', 'SI'];
    const rows = this.results.lighthouse.map(result => [
      result.url,
      result.device,
      result.performance,
      Math.round(result.fcp),
      Math.round(result.lcp),
      result.cls.toFixed(3),
      Math.round(result.tti),
      Math.round(result.tbt),
      Math.round(result.si)
    ]);

    return [headers, ...rows].map(row => row.join(',')).join('\n');
  }

  // Helper methods
  async findJavaScriptFiles() {
    return this.findFilesByPattern('**/*.js', ['node_modules', '.git']);
  }

  async findImageFiles() {
    return this.findFilesByPattern('**/*.{jpg,jpeg,png,gif,webp,svg}', ['node_modules', '.git']);
  }

  async findBundleFiles() {
    return this.findFilesByPattern('**/*.{js,css}', ['node_modules', '.git', 'src']);
  }

  async findFilesByPattern(pattern, ignore = []) {
    const glob = require('glob');
    return new Promise((resolve, reject) => {
      glob(pattern, { ignore: ignore.map(i => `**/${i}/**`) }, (err, files) => {
        if (err) reject(err);
        else resolve(files);
      });
    });
  }

  analyzeComplexity(content) {
    const cyclomaticComplexity = (content.match(/if\s*\(|while\s*\(|for\s*\(|catch\s*\(|\?\s*:/g) || []).length;
    const functionCount = (content.match(/function\s+\w+|=>\s*{|\w+\s*:\s*function/g) || []).length;
    return {
      cyclomatic: cyclomaticComplexity,
      functions: functionCount,
      score: cyclomaticComplexity + functionCount * 2
    };
  }

  isMinified(content) {
    const avgLineLength = content.split('\n').reduce((sum, line) => sum + line.length, 0) / content.split('\n').length;
    return avgLineLength > 80 && !content.includes('\n  '); // Long lines and no indentation
  }

  isOptimizedFormat(ext) {
    return ['.webp', '.avif', '.svg'].includes(ext);
  }

  isCacheable(cacheControl) {
    if (!cacheControl) return false;
    return cacheControl.includes('max-age') && !cacheControl.includes('no-cache');
  }

  getBundleType(filename) {
    if (filename.includes('.min.')) return 'minified';
    if (filename.includes('vendor') || filename.includes('lib')) return 'vendor';
    return 'application';
  }
}

// CLI Interface
if (require.main === module) {
  const args = process.argv.slice(2);
  const options = {};

  // Parse command line arguments
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i].replace('--', '');
    const value = args[i + 1];
    
    if (key === 'url') options.baseUrl = value;
    if (key === 'output') options.outputDir = value;
    if (key === 'runs') options.lighthouse.runs = parseInt(value);
  }

  const tester = new PerformanceTester(options);
  tester.runFullSuite().catch(error => {
    console.error('Performance testing failed:', error);
    process.exit(1);
  });
}

module.exports = PerformanceTester;