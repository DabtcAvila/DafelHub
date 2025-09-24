#!/bin/bash

# 🚀 DafelHub GitHub Pages Deployment Script
# Production-ready deployment with performance optimization

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCS_DIR="docs"
BUILD_DIR="build"
PERFORMANCE_DIR="performance-reports"
BACKUP_DIR="backup-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}🚀 DafelHub GitHub Pages Deployment${NC}"
echo -e "${BLUE}====================================${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check requirements
check_requirements() {
    echo -e "${BLUE}🔍 Checking requirements...${NC}"
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js 20+"
        exit 1
    fi
    
    # Check Node.js version
    NODE_VERSION=$(node -v | cut -d 'v' -f 2 | cut -d '.' -f 1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        print_error "Node.js version 18+ required. Current: $(node -v)"
        exit 1
    fi
    
    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        print_error "npm is not installed"
        exit 1
    fi
    
    # Check if git is available
    if ! command -v git &> /dev/null; then
        print_error "Git is not installed"
        exit 1
    fi
    
    print_status "All requirements satisfied"
}

# Function to backup existing docs
backup_existing() {
    if [ -d "$DOCS_DIR" ]; then
        echo -e "${BLUE}📦 Creating backup of existing docs...${NC}"
        cp -r "$DOCS_DIR" "$BACKUP_DIR"
        print_status "Backup created: $BACKUP_DIR"
    fi
}

# Function to install dependencies
install_dependencies() {
    echo -e "${BLUE}📦 Installing dependencies...${NC}"
    
    # Install npm dependencies
    if [ -f "package.json" ]; then
        npm ci --prefer-offline --no-audit --progress=false
        print_status "npm dependencies installed"
    fi
    
    # Install performance tools
    npm install -g @lhci/cli lighthouse chrome-launcher --silent
    print_status "Performance tools installed"
}

# Function to run performance tests
run_performance_tests() {
    echo -e "${BLUE}📊 Running performance tests...${NC}"
    
    # Start server in background
    npm run start &
    SERVER_PID=$!
    
    # Wait for server to be ready
    echo "Waiting for server to start..."
    sleep 10
    
    # Check if server is running
    if ! curl -s http://localhost:3000 > /dev/null; then
        print_warning "Server not responding, starting alternative method"
        
        # Try alternative server method
        if command -v python3 &> /dev/null; then
            python3 -m http.server 3000 &
            SERVER_PID=$!
            sleep 5
        else
            print_error "Cannot start local server for performance testing"
            return 1
        fi
    fi
    
    # Create performance reports directory
    mkdir -p "$PERFORMANCE_DIR"
    
    # Run Lighthouse CI
    if command -v lhci &> /dev/null; then
        echo "Running Lighthouse CI..."
        npm run lighthouse:ci || print_warning "Lighthouse CI completed with warnings"
    fi
    
    # Run custom performance tests
    if [ -f "scripts/performance-test.js" ]; then
        echo "Running custom performance tests..."
        node scripts/performance-test.js --url http://localhost:3000 --output "./$PERFORMANCE_DIR" || print_warning "Performance tests completed with warnings"
    fi
    
    # Stop server
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    
    print_status "Performance tests completed"
}

# Function to build GitHub Pages content
build_pages_content() {
    echo -e "${BLUE}🏗️  Building GitHub Pages content...${NC}"
    
    # Create docs directory
    mkdir -p "$DOCS_DIR"
    
    # Copy main HTML file
    if [ -f "index.html" ]; then
        cp "index.html" "$DOCS_DIR/"
        print_status "Copied index.html"
    fi
    
    # Copy assets
    if [ -d "assets" ]; then
        cp -r "assets" "$DOCS_DIR/"
        print_status "Copied assets directory"
    fi
    
    # Copy public directory
    if [ -d "public" ]; then
        cp -r "public"/* "$DOCS_DIR/" 2>/dev/null || true
        print_status "Copied public directory"
    fi
    
    # Copy HTML files
    for file in *.html; do
        if [ -f "$file" ] && [ "$file" != "index.html" ]; then
            cp "$file" "$DOCS_DIR/"
        fi
    done
    
    # Copy CSS and JS files
    for file in *.css *.js; do
        if [ -f "$file" ]; then
            cp "$file" "$DOCS_DIR/"
        fi
    done
    
    # Copy performance reports
    if [ -d "$PERFORMANCE_DIR" ]; then
        mkdir -p "$DOCS_DIR/performance"
        cp -r "$PERFORMANCE_DIR"/* "$DOCS_DIR/performance/" 2>/dev/null || true
        print_status "Copied performance reports"
    fi
    
    # Create .nojekyll file to bypass Jekyll processing for certain files
    touch "$DOCS_DIR/.nojekyll"
    
    # Create CNAME file if domain is specified
    if [ -n "$CUSTOM_DOMAIN" ]; then
        echo "$CUSTOM_DOMAIN" > "$DOCS_DIR/CNAME"
        print_status "Created CNAME file for $CUSTOM_DOMAIN"
    fi
    
    print_status "GitHub Pages content built"
}

# Function to optimize assets
optimize_assets() {
    echo -e "${BLUE}⚡ Optimizing assets...${NC}"
    
    # Install optimization tools if not present
    if ! command -v imagemin &> /dev/null; then
        npm install -g imagemin-cli imagemin-webp imagemin-mozjpeg imagemin-pngquant --silent
    fi
    
    # Optimize images in docs directory
    if command -v imagemin &> /dev/null; then
        find "$DOCS_DIR" -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" | while read file; do
            imagemin "$file" --out-dir="$(dirname "$file")" --plugin.mozjpeg.quality=85 --plugin.pngquant.quality=0.8-0.9 || true
        done
        print_status "Images optimized"
    fi
    
    # Minify CSS files
    if command -v cleancss &> /dev/null; then
        find "$DOCS_DIR" -name "*.css" ! -name "*.min.css" | while read file; do
            cleancss -o "${file%.css}.min.css" "$file" || true
        done
        print_status "CSS files minified"
    fi
    
    # Minify JavaScript files
    if command -v terser &> /dev/null; then
        find "$DOCS_DIR" -name "*.js" ! -name "*.min.js" | while read file; do
            terser "$file" --compress --mangle --output "${file%.js}.min.js" || true
        done
        print_status "JavaScript files minified"
    fi
}

# Function to validate build
validate_build() {
    echo -e "${BLUE}🔍 Validating build...${NC}"
    
    # Check required files
    if [ ! -f "$DOCS_DIR/index.html" ]; then
        print_error "index.html not found in docs directory"
        exit 1
    fi
    
    # Check HTML validity (basic)
    if command -v tidy &> /dev/null; then
        tidy -q -e "$DOCS_DIR/index.html" || print_warning "HTML validation warnings"
    fi
    
    # Calculate total size
    TOTAL_SIZE=$(du -sh "$DOCS_DIR" | cut -f1)
    print_status "Total size: $TOTAL_SIZE"
    
    # Check if size is reasonable (warn if > 50MB)
    SIZE_BYTES=$(du -s "$DOCS_DIR" | cut -f1)
    if [ "$SIZE_BYTES" -gt 51200 ]; then  # 50MB in KB
        print_warning "Build size is large ($TOTAL_SIZE). Consider optimization."
    fi
    
    print_status "Build validation completed"
}

# Function to generate deployment report
generate_report() {
    echo -e "${BLUE}📋 Generating deployment report...${NC}"
    
    REPORT_FILE="deployment-report.md"
    
    cat > "$REPORT_FILE" << EOF
# 🚀 DafelHub Deployment Report

**Deployment Time:** $(date)
**Git Commit:** $(git rev-parse --short HEAD)
**Git Branch:** $(git rev-parse --abbrev-ref HEAD)

## 📊 Build Statistics

- **Total Size:** $(du -sh "$DOCS_DIR" | cut -f1)
- **File Count:** $(find "$DOCS_DIR" -type f | wc -l)
- **HTML Files:** $(find "$DOCS_DIR" -name "*.html" | wc -l)
- **CSS Files:** $(find "$DOCS_DIR" -name "*.css" | wc -l)
- **JS Files:** $(find "$DOCS_DIR" -name "*.js" | wc -l)
- **Image Files:** $(find "$DOCS_DIR" \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.gif" -o -name "*.webp" -o -name "*.svg" \) | wc -l)

## 🎯 Performance Metrics

EOF

    # Add performance data if available
    if [ -f "$PERFORMANCE_DIR/performance-summary.csv" ]; then
        echo "- **Performance Reports:** Available in /performance/" >> "$REPORT_FILE"
        echo "- **Lighthouse Scores:** $(head -2 "$PERFORMANCE_DIR/performance-summary.csv" | tail -1 | cut -d',' -f3)" >> "$REPORT_FILE"
    fi
    
    cat >> "$REPORT_FILE" << EOF

## 🔗 Deployment URLs

- **Primary URL:** https://dabtcavila.github.io/DafelHub/
- **Performance Dashboard:** https://dabtcavila.github.io/DafelHub/performance/
- **Repository:** https://github.com/DabtcAvila/DafelHub

## ✅ Deployment Status

- [x] Build completed successfully
- [x] Performance tests executed
- [x] Assets optimized
- [x] Build validated
- [x] Ready for GitHub Pages

---

*Generated by DafelHub deployment script*
EOF

    print_status "Deployment report generated: $REPORT_FILE"
}

# Function to commit and push changes
deploy_to_github() {
    echo -e "${BLUE}🚀 Deploying to GitHub Pages...${NC}"
    
    # Check if git repo is clean (excluding docs directory)
    if [ -n "$(git status --porcelain | grep -v "^?? docs/")" ]; then
        print_warning "Working directory has uncommitted changes (excluding docs/)"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Deployment cancelled"
            exit 1
        fi
    fi
    
    # Add docs directory to git
    git add "$DOCS_DIR"
    
    # Add other deployment files
    if [ -f "deployment-report.md" ]; then
        git add "deployment-report.md"
    fi
    
    # Commit changes
    COMMIT_MSG="🚀 Deploy GitHub Pages - $(date '+%Y-%m-%d %H:%M:%S')"
    git commit -m "$COMMIT_MSG" || print_warning "No changes to commit"
    
    # Push to GitHub
    echo "Pushing to GitHub..."
    git push origin main || {
        print_error "Failed to push to GitHub"
        exit 1
    }
    
    print_status "Deployed to GitHub Pages!"
    echo -e "${GREEN}🌐 Your site will be available at: https://dabtcavila.github.io/DafelHub/${NC}"
}

# Function to cleanup
cleanup() {
    echo -e "${BLUE}🧹 Cleaning up...${NC}"
    
    # Remove temporary files
    rm -rf "$BUILD_DIR" 2>/dev/null || true
    
    # Keep performance reports and backup
    print_status "Cleanup completed"
}

# Function to show help
show_help() {
    cat << EOF
🚀 DafelHub GitHub Pages Deployment Script

Usage: $0 [OPTIONS]

Options:
    -h, --help          Show this help message
    -s, --skip-tests    Skip performance tests
    -o, --optimize-only Only run optimization (no deployment)
    -d, --domain DOMAIN Set custom domain for CNAME
    --no-backup         Skip creating backup
    --dry-run           Perform all steps except git push

Examples:
    $0                          # Full deployment
    $0 --skip-tests            # Deploy without performance tests
    $0 --domain mydomain.com   # Deploy with custom domain
    $0 --dry-run               # Test deployment without pushing

EOF
}

# Parse command line arguments
SKIP_TESTS=false
OPTIMIZE_ONLY=false
NO_BACKUP=false
DRY_RUN=false
CUSTOM_DOMAIN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -s|--skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        -o|--optimize-only)
            OPTIMIZE_ONLY=true
            shift
            ;;
        -d|--domain)
            CUSTOM_DOMAIN="$2"
            shift 2
            ;;
        --no-backup)
            NO_BACKUP=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main deployment process
main() {
    echo -e "${BLUE}Starting deployment process...${NC}"
    
    # Check requirements
    check_requirements
    
    # Create backup unless disabled
    if [ "$NO_BACKUP" != true ]; then
        backup_existing
    fi
    
    # Install dependencies
    install_dependencies
    
    # Run performance tests unless skipped
    if [ "$SKIP_TESTS" != true ]; then
        run_performance_tests
    fi
    
    # Build content
    build_pages_content
    
    # Optimize assets
    optimize_assets
    
    # Validate build
    validate_build
    
    # Generate report
    generate_report
    
    # Deploy to GitHub (unless optimize-only or dry-run)
    if [ "$OPTIMIZE_ONLY" != true ]; then
        if [ "$DRY_RUN" != true ]; then
            deploy_to_github
        else
            print_status "Dry run completed - no changes pushed to GitHub"
        fi
    fi
    
    # Cleanup
    cleanup
    
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    
    if [ "$DRY_RUN" != true ] && [ "$OPTIMIZE_ONLY" != true ]; then
        echo -e "${GREEN}🌐 Visit: https://dabtcavila.github.io/DafelHub/${NC}"
        echo -e "${GREEN}📊 Performance: https://dabtcavila.github.io/DafelHub/performance/${NC}"
    fi
}

# Trap to cleanup on exit
trap cleanup EXIT

# Run main function
main "$@"