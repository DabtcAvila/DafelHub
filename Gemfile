# 💎 DafelHub Jekyll Dependencies
# Optimized Gemfile for GitHub Pages deployment

source "https://rubygems.org"

# Jekyll core with GitHub Pages compatibility
gem "github-pages", "~> 228", group: :jekyll_plugins
gem "jekyll", "~> 3.9.3"

# Performance and optimization plugins
group :jekyll_plugins do
  gem "jekyll-feed", "~> 0.15"
  gem "jekyll-sitemap", "~> 1.4"
  gem "jekyll-seo-tag", "~> 2.8"
  gem "jekyll-minifier"
  gem "jekyll-compress-images"
  gem "jekyll-babel"
  gem "jekyll-autoprefixer"
  gem "jekyll-paginate"
  gem "jekyll-redirect-from"
  gem "jekyll-gist"
  gem "jekyll-github-metadata"
  gem "jekyll-relative-links"
  gem "jekyll-optional-front-matter"
  gem "jekyll-readme-index"
  gem "jekyll-default-layout"
  gem "jekyll-titles-from-headings"
end

# Development dependencies
group :development do
  gem "webrick", "~> 1.8"
  gem "wdm", "~> 0.1.1" if Gem.win_platform?
  gem "tzinfo-data", platforms: [:mingw, :mswin, :x64_mingw, :jruby]
end

# Performance monitoring
group :test do
  gem "html-proofer", "~> 4.4"
  gem "rspec", "~> 3.12"
end

# Windows and JRuby
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end

# Lock `http_parser.rb` gem to `v0.6.x` on JRuby builds
gem "http_parser.rb", "~> 0.6.0", :platforms => [:jruby]