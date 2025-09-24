/**
 * Lighthouse CI Configuration for DafelHub
 * Aggressive performance targets: <1.5s FCP, <2.5s LCP, <0.1 CLS, <100ms FID
 */

module.exports = {
  ci: {
    collect: {
      url: [
        'http://localhost:3000',
        'http://localhost:3000/performance-dashboard.html',
        'http://localhost:3000/docs/',
        'http://localhost:3000/studio.html'
      ],
      startServerCommand: 'npm run start',
      startServerReadyPattern: 'Local:   http://localhost:3000',
      numberOfRuns: 5, // Run multiple times for accuracy
      settings: {
        chromeFlags: ['--no-sandbox', '--disable-dev-shm-usage'],
        preset: 'desktop',
        throttling: {
          rttMs: 40,
          throughputKbps: 10240,
          requestLatencyMs: 0,
          downloadThroughputKbps: 0,
          uploadThroughputKbps: 0,
          cpuSlowdownMultiplier: 1
        },
        screenEmulation: {
          mobile: false,
          width: 1350,
          height: 940,
          deviceScaleFactor: 1,
          disabled: false
        },
        emulatedUserAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    },
    assert: {
      assertions: {
        // Performance Budget - Aggressive Targets
        'categories:performance': ['error', { minScore: 0.95 }], // 95+ performance score
        'categories:accessibility': ['error', { minScore: 0.95 }], // 95+ accessibility
        'categories:best-practices': ['error', { minScore: 0.95 }], // 95+ best practices
        'categories:seo': ['error', { minScore: 0.95 }], // 95+ SEO
        'categories:pwa': ['warn', { minScore: 0.8 }], // 80+ PWA (warning only)

        // Core Web Vitals - Ultra Strict Thresholds
        'first-contentful-paint': ['error', { maxNumericValue: 1500 }], // <1.5s FCP
        'largest-contentful-paint': ['error', { maxNumericValue: 2500 }], // <2.5s LCP
        'cumulative-layout-shift': ['error', { maxNumericValue: 0.1 }],   // <0.1 CLS
        'first-input-delay': ['error', { maxNumericValue: 100 }],         // <100ms FID
        'interactive': ['error', { maxNumericValue: 3500 }],              // <3.5s TTI
        'speed-index': ['error', { maxNumericValue: 2000 }],              // <2s Speed Index

        // Network and Loading Performance
        'server-response-time': ['error', { maxNumericValue: 600 }],      // <600ms TTFB
        'total-blocking-time': ['error', { maxNumericValue: 150 }],       // <150ms TBT
        'max-potential-fid': ['error', { maxNumericValue: 100 }],         // <100ms Max FID

        // Resource Optimization
        'unused-css-rules': ['warn', { maxLength: 2 }],                   // Max 2 unused CSS files
        'unused-javascript': ['warn', { maxLength: 3 }],                  // Max 3 unused JS files
        'uses-optimized-images': ['error', { maxLength: 0 }],             // All images optimized
        'uses-webp-images': ['warn', { maxLength: 5 }],                   // Prefer WebP images
        'uses-responsive-images': ['error', { maxLength: 0 }],            // Responsive images
        'offscreen-images': ['error', { maxLength: 0 }],                  // No offscreen images
        'render-blocking-resources': ['error', { maxLength: 1 }],         // Min render blocking

        // Compression and Caching
        'uses-text-compression': ['error', { maxLength: 0 }],             // Text compression required
        'uses-long-cache-ttl': ['warn', { minScore: 0.8 }],              // Long cache headers
        'efficient-animated-content': ['error', { maxLength: 0 }],        // No inefficient animations

        // JavaScript Performance
        'bootup-time': ['error', { maxNumericValue: 2000 }],              // <2s JS bootup time
        'mainthread-work-breakdown': ['error', { maxNumericValue: 2000 }], // <2s main thread work
        'third-party-summary': ['warn', { maxNumericValue: 2000 }],       // <2s third-party impact

        // Modern Best Practices
        'modern-image-formats': ['error', { maxLength: 0 }],              // Modern image formats
        'preload-lcp-image': ['error', { maxLength: 0 }],                 // Preload LCP image
        'uses-http2': ['warn', { minScore: 1 }],                          // HTTP/2 recommended
        'uses-passive-event-listeners': ['error', { minScore: 1 }],       // Passive listeners
        'no-document-write': ['error', { minScore: 1 }],                  // No document.write

        // Security and Privacy
        'is-on-https': ['error', { minScore: 1 }],                        // HTTPS required
        'no-vulnerable-libraries': ['error', { minScore: 1 }],            // No vulnerable libs
        'csp-xss': ['warn', { minScore: 1 }],                            // CSP for XSS protection
      }
    },
    upload: {
      target: 'temporary-public-storage', // For CI environments
      // For production, use:
      // target: 'lhci',
      // serverBaseUrl: 'https://your-lhci-server.com',
      // token: process.env.LHCI_TOKEN
    },
    server: {
      port: 9001,
      storage: {
        storageMethod: 'sql',
        sqlDialect: 'sqlite',
        sqlDatabasePath: './lighthouse-results.db'
      }
    },
    wizard: {
      // Disable wizard for CI
      enabled: false
    }
  }
};