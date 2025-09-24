/**
 * DafelHub Performance Optimization Utilities
 * Advanced performance optimization techniques and automated fixes
 */

class PerformanceOptimizer {
  constructor(options = {}) {
    this.options = {
      autoOptimize: false,
      enableImageOptimization: true,
      enableResourceHints: true,
      enableServiceWorkerOptimization: true,
      enablePrefetching: true,
      performanceTargets: {
        fcp: 1500,
        lcp: 2500,
        cls: 0.1,
        fid: 100,
        ttfb: 600
      },
      ...options
    };

    this.optimizations = {
      applied: [],
      available: [],
      failed: []
    };

    this.init();
  }

  init() {
    if (typeof window === 'undefined') return;

    // Detect available optimizations
    this.detectOptimizations();

    // Apply automatic optimizations if enabled
    if (this.options.autoOptimize) {
      this.applyAutomaticOptimizations();
    }

    console.log('🔧 Performance Optimizer initialized');
  }

  detectOptimizations() {
    this.optimizations.available = [];

    // Check for image optimization opportunities
    if (this.options.enableImageOptimization) {
      this.detectImageOptimizations();
    }

    // Check for resource hint opportunities
    if (this.options.enableResourceHints) {
      this.detectResourceHintOptimizations();
    }

    // Check for prefetching opportunities
    if (this.options.enablePrefetching) {
      this.detectPrefetchingOptimizations();
    }

    // Check for critical resource optimization
    this.detectCriticalResourceOptimizations();

    // Check for render blocking optimization
    this.detectRenderBlockingOptimizations();
  }

  detectImageOptimizations() {
    const images = document.querySelectorAll('img');
    const imageOptimizations = [];

    images.forEach((img, index) => {
      const rect = img.getBoundingClientRect();
      const naturalWidth = img.naturalWidth;
      const naturalHeight = img.naturalHeight;
      const displayWidth = rect.width;
      const displayHeight = rect.height;

      // Check for oversized images
      if (naturalWidth > displayWidth * 2 || naturalHeight > displayHeight * 2) {
        imageOptimizations.push({
          type: 'image_resize',
          element: img,
          issue: 'Image is larger than display size',
          recommendation: `Resize from ${naturalWidth}x${naturalHeight} to ${Math.round(displayWidth)}x${Math.round(displayHeight)}`,
          priority: 'medium',
          savings: this.estimateImageSavings(img, displayWidth, displayHeight)
        });
      }

      // Check for missing alt attributes
      if (!img.alt) {
        imageOptimizations.push({
          type: 'accessibility',
          element: img,
          issue: 'Missing alt attribute',
          recommendation: 'Add descriptive alt text for accessibility',
          priority: 'low'
        });
      }

      // Check for lazy loading opportunity
      if (!img.loading && rect.top > window.innerHeight) {
        imageOptimizations.push({
          type: 'lazy_loading',
          element: img,
          issue: 'Image is below fold but not lazy loaded',
          recommendation: 'Add loading="lazy" attribute',
          priority: 'medium',
          fix: () => this.enableImageLazyLoading(img)
        });
      }

      // Check for modern format opportunity
      if (img.src && !this.isModernImageFormat(img.src)) {
        imageOptimizations.push({
          type: 'modern_format',
          element: img,
          issue: 'Using legacy image format',
          recommendation: 'Convert to WebP or AVIF format',
          priority: 'medium'
        });
      }
    });

    this.optimizations.available.push(...imageOptimizations);
  }

  detectResourceHintOptimizations() {
    const hintOptimizations = [];
    const existingHints = new Set();

    // Check existing resource hints
    document.querySelectorAll('link[rel*="preload"], link[rel*="prefetch"], link[rel*="preconnect"]')
      .forEach(link => existingHints.add(link.href));

    // Analyze critical resources
    if (performance.getEntriesByType) {
      const resources = performance.getEntriesByType('resource');
      const criticalResources = resources.filter(resource => 
        resource.startTime < 2000 && // Loaded in first 2 seconds
        (resource.initiatorType === 'script' || resource.initiatorType === 'link')
      );

      criticalResources.forEach(resource => {
        if (!existingHints.has(resource.name)) {
          hintOptimizations.push({
            type: 'preload',
            url: resource.name,
            issue: 'Critical resource without preload hint',
            recommendation: `Add <link rel="preload" href="${resource.name}" as="${resource.initiatorType}">`,
            priority: 'high',
            fix: () => this.addResourceHint('preload', resource.name, resource.initiatorType)
          });
        }
      });
    }

    // Check for external domain preconnect opportunities
    const externalDomains = new Set();
    document.querySelectorAll('img[src*="//"], script[src*="//"], link[href*="//"]')
      .forEach(element => {
        const url = element.src || element.href;
        if (url && !url.startsWith(window.location.origin)) {
          const domain = new URL(url).origin;
          externalDomains.add(domain);
        }
      });

    externalDomains.forEach(domain => {
      if (!document.querySelector(`link[rel="preconnect"][href="${domain}"]`)) {
        hintOptimizations.push({
          type: 'preconnect',
          url: domain,
          issue: 'External domain without preconnect',
          recommendation: `Add <link rel="preconnect" href="${domain}">`,
          priority: 'medium',
          fix: () => this.addResourceHint('preconnect', domain)
        });
      }
    });

    this.optimizations.available.push(...hintOptimizations);
  }

  detectPrefetchingOptimizations() {
    const prefetchOptimizations = [];

    // Check for navigation prefetching opportunities
    const links = document.querySelectorAll('a[href^="/"], a[href^="./"]');
    const visibleLinks = Array.from(links).filter(link => {
      const rect = link.getBoundingClientRect();
      return rect.top < window.innerHeight * 1.5; // Within 1.5 viewport heights
    });

    visibleLinks.forEach(link => {
      if (!link.hasAttribute('rel') || !link.rel.includes('prefetch')) {
        prefetchOptimizations.push({
          type: 'prefetch_link',
          element: link,
          issue: 'Likely navigation target without prefetch',
          recommendation: 'Add prefetch for smooth navigation',
          priority: 'low',
          fix: () => this.enableLinkPrefetching(link)
        });
      }
    });

    this.optimizations.available.push(...prefetchOptimizations);
  }

  detectCriticalResourceOptimizations() {
    const criticalOptimizations = [];

    // Check for render-blocking CSS
    const stylesheets = document.querySelectorAll('link[rel="stylesheet"]:not([media])');
    stylesheets.forEach(stylesheet => {
      if (!stylesheet.media || stylesheet.media === 'all') {
        criticalOptimizations.push({
          type: 'critical_css',
          element: stylesheet,
          issue: 'Render-blocking stylesheet',
          recommendation: 'Inline critical CSS or use media attribute',
          priority: 'high'
        });
      }
    });

    // Check for render-blocking JavaScript
    const scripts = document.querySelectorAll('script[src]:not([async]):not([defer])');
    scripts.forEach(script => {
      if (!script.async && !script.defer) {
        criticalOptimizations.push({
          type: 'script_blocking',
          element: script,
          issue: 'Render-blocking JavaScript',
          recommendation: 'Add async or defer attribute',
          priority: 'high',
          fix: () => this.optimizeScriptLoading(script)
        });
      }
    });

    this.optimizations.available.push(...criticalOptimizations);
  }

  detectRenderBlockingOptimizations() {
    const renderOptimizations = [];

    // Check for missing viewport meta tag
    if (!document.querySelector('meta[name="viewport"]')) {
      renderOptimizations.push({
        type: 'viewport_meta',
        issue: 'Missing viewport meta tag',
        recommendation: 'Add <meta name="viewport" content="width=device-width, initial-scale=1">',
        priority: 'high',
        fix: () => this.addViewportMeta()
      });
    }

    // Check for missing charset declaration
    if (!document.querySelector('meta[charset]')) {
      renderOptimizations.push({
        type: 'charset_meta',
        issue: 'Missing charset declaration',
        recommendation: 'Add <meta charset="utf-8"> as first meta tag',
        priority: 'medium',
        fix: () => this.addCharsetMeta()
      });
    }

    // Check for large DOM size
    const domSize = document.querySelectorAll('*').length;
    if (domSize > 1500) {
      renderOptimizations.push({
        type: 'dom_size',
        issue: `Large DOM size (${domSize} elements)`,
        recommendation: 'Reduce DOM complexity and use virtualization for large lists',
        priority: 'medium'
      });
    }

    this.optimizations.available.push(...renderOptimizations);
  }

  async applyAutomaticOptimizations() {
    console.log('🔄 Applying automatic performance optimizations...');

    const autoFixableOptimizations = this.optimizations.available.filter(opt => opt.fix);
    
    for (const optimization of autoFixableOptimizations) {
      try {
        await optimization.fix();
        this.optimizations.applied.push(optimization);
        console.log(`✅ Applied: ${optimization.type}`);
      } catch (error) {
        this.optimizations.failed.push({
          ...optimization,
          error: error.message
        });
        console.warn(`❌ Failed to apply ${optimization.type}:`, error);
      }
    }

    console.log(`🎯 Applied ${this.optimizations.applied.length} optimizations automatically`);
  }

  // Optimization implementation methods
  enableImageLazyLoading(img) {
    if ('loading' in HTMLImageElement.prototype) {
      img.loading = 'lazy';
    } else {
      // Fallback for browsers without native lazy loading
      this.implementLazyLoadingFallback(img);
    }
  }

  implementLazyLoadingFallback(img) {
    if (!this.lazyLoadingObserver) {
      this.lazyLoadingObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            if (img.dataset.src) {
              img.src = img.dataset.src;
              img.removeAttribute('data-src');
              this.lazyLoadingObserver.unobserve(img);
            }
          }
        });
      });
    }

    img.dataset.src = img.src;
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    this.lazyLoadingObserver.observe(img);
  }

  addResourceHint(rel, href, as = null) {
    const link = document.createElement('link');
    link.rel = rel;
    link.href = href;
    if (as) link.as = as;
    document.head.appendChild(link);
  }

  enableLinkPrefetching(link) {
    // Use Intersection Observer to prefetch when link is visible
    if (!this.prefetchObserver) {
      this.prefetchObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const link = entry.target;
            this.prefetchResource(link.href);
            this.prefetchObserver.unobserve(link);
          }
        });
      });
    }

    this.prefetchObserver.observe(link);
  }

  prefetchResource(url) {
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = url;
    document.head.appendChild(link);
  }

  optimizeScriptLoading(script) {
    // Determine if script should be async or defer
    if (script.src && script.src.includes('analytics') || script.src.includes('tracking')) {
      script.async = true;
    } else {
      script.defer = true;
    }
  }

  addViewportMeta() {
    const viewport = document.createElement('meta');
    viewport.name = 'viewport';
    viewport.content = 'width=device-width, initial-scale=1';
    document.head.insertBefore(viewport, document.head.firstChild);
  }

  addCharsetMeta() {
    const charset = document.createElement('meta');
    charset.charset = 'utf-8';
    document.head.insertBefore(charset, document.head.firstChild);
  }

  // Utility methods
  estimateImageSavings(img, targetWidth, targetHeight) {
    const currentPixels = img.naturalWidth * img.naturalHeight;
    const targetPixels = targetWidth * targetHeight;
    const reduction = (currentPixels - targetPixels) / currentPixels;
    return {
      pixelReduction: reduction,
      estimatedSavingsPercent: Math.round(reduction * 100),
      estimatedSavingsKB: Math.round(reduction * 100) // Rough estimate
    };
  }

  isModernImageFormat(src) {
    return src.toLowerCase().match(/\.(webp|avif)$/);
  }

  // Public API methods
  getOptimizationReport() {
    return {
      available: this.optimizations.available.length,
      applied: this.optimizations.applied.length,
      failed: this.optimizations.failed.length,
      recommendations: this.optimizations.available.map(opt => ({
        type: opt.type,
        priority: opt.priority,
        issue: opt.issue,
        recommendation: opt.recommendation,
        canAutoFix: !!opt.fix
      }))
    };
  }

  async runOptimizationSuite() {
    console.log('🚀 Running complete optimization suite...');
    
    // Re-detect optimizations
    this.detectOptimizations();
    
    // Apply all available fixes
    await this.applyAutomaticOptimizations();
    
    // Generate report
    const report = this.getOptimizationReport();
    
    console.log('📊 Optimization Report:', report);
    return report;
  }

  async optimizeForTarget(metric, targetValue) {
    const optimizations = [];

    switch (metric) {
      case 'FCP':
        optimizations.push(
          ...this.optimizations.available.filter(opt => 
            ['preload', 'critical_css', 'script_blocking'].includes(opt.type)
          )
        );
        break;
      
      case 'LCP':
        optimizations.push(
          ...this.optimizations.available.filter(opt => 
            ['image_resize', 'preload', 'lazy_loading'].includes(opt.type)
          )
        );
        break;
      
      case 'CLS':
        optimizations.push(
          ...this.optimizations.available.filter(opt => 
            ['image_resize', 'dom_size'].includes(opt.type)
          )
        );
        break;
      
      case 'FID':
        optimizations.push(
          ...this.optimizations.available.filter(opt => 
            ['script_blocking', 'dom_size'].includes(opt.type)
          )
        );
        break;
    }

    // Apply metric-specific optimizations
    for (const optimization of optimizations) {
      if (optimization.fix) {
        try {
          await optimization.fix();
          this.optimizations.applied.push(optimization);
        } catch (error) {
          this.optimizations.failed.push({ ...optimization, error: error.message });
        }
      }
    }

    return optimizations.length;
  }

  // Advanced optimization methods
  async optimizeCriticalRenderingPath() {
    // Inline critical CSS
    const criticalCSS = await this.extractCriticalCSS();
    if (criticalCSS) {
      this.inlineCriticalCSS(criticalCSS);
    }

    // Defer non-critical CSS
    this.deferNonCriticalCSS();

    // Optimize font loading
    this.optimizeFontLoading();
  }

  async extractCriticalCSS() {
    // This would typically use tools like Critical or Penthouse
    // For now, we'll return null as this requires server-side processing
    console.log('Critical CSS extraction requires server-side processing');
    return null;
  }

  inlineCriticalCSS(css) {
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
  }

  deferNonCriticalCSS() {
    const stylesheets = document.querySelectorAll('link[rel="stylesheet"]');
    stylesheets.forEach(link => {
      if (!this.isCriticalCSS(link)) {
        link.rel = 'preload';
        link.as = 'style';
        link.onload = function() { this.rel = 'stylesheet'; };
      }
    });
  }

  isCriticalCSS(link) {
    // Determine if CSS is critical (simplified logic)
    return link.href.includes('critical') || 
           link.href.includes('inline') ||
           link.media !== 'all';
  }

  optimizeFontLoading() {
    // Add font-display: swap to @font-face rules
    const stylesheets = document.querySelectorAll('style');
    stylesheets.forEach(style => {
      if (style.textContent.includes('@font-face')) {
        style.textContent = style.textContent.replace(
          /@font-face\s*{([^}]*)}/g,
          '@font-face { $1; font-display: swap; }'
        );
      }
    });

    // Preload important fonts
    const fontUrls = this.extractFontUrls();
    fontUrls.forEach(url => {
      this.addResourceHint('preload', url, 'font');
    });
  }

  extractFontUrls() {
    const fontUrls = [];
    // Extract font URLs from stylesheets (simplified)
    document.querySelectorAll('link[href*="fonts"]').forEach(link => {
      fontUrls.push(link.href);
    });
    return fontUrls;
  }

  // Performance monitoring integration
  integrateWithMonitoring(performanceMonitor) {
    this.monitor = performanceMonitor;
    
    // Auto-optimize based on performance metrics
    performanceMonitor.metrics.forEach((metric, name) => {
      const target = this.options.performanceTargets[name.toLowerCase()];
      if (target && metric.value > target) {
        console.log(`🎯 Auto-optimizing for ${name} (${metric.value} > ${target})`);
        this.optimizeForTarget(name, target);
      }
    });
  }

  destroy() {
    if (this.lazyLoadingObserver) {
      this.lazyLoadingObserver.disconnect();
    }
    if (this.prefetchObserver) {
      this.prefetchObserver.disconnect();
    }
  }
}

// Global initialization
if (typeof window !== 'undefined') {
  window.PerformanceOptimizer = PerformanceOptimizer;
}

export default PerformanceOptimizer;