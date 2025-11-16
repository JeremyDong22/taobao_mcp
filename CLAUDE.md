# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a standalone Taobao/Tmall product scraper that extracts product information and outputs it as Markdown files. The scraper uses Playwright for browser automation, handles login requirements, and maintains persistent browser sessions to avoid repeated authentication.

## Running the Scraper

```bash
# Basic usage with product link
python3 scrape_to_markdown.py "【淘宝】假一赔四 https://e.tb.cn/h.StvCjJlWxkNatsx?tk=Jnvaf9roBSn"

# Using product ID directly
python3 scrape_to_markdown.py "752468272997"

# Using full product URL
python3 scrape_to_markdown.py "https://detail.tmall.com/item.htm?id=752468272997"
```

## Project Structure

```
taobao-agent/
├── scrape_to_markdown.py       # Main scraper (900+ lines, completely standalone)
├── user_data/                  # Browser profile and authentication state
│   └── chrome_profile/         # Playwright persistent context
├── product_info/               # Output: generated Markdown product files
└── knowledge/                  # Technical documentation
    ├── TAOBAO_PAGE_STRUCTURE.md
    └── TAOBAO_AB_TEST_INVESTIGATION.md
```

## Key Architecture Patterns

### Single-File Design
The entire scraper is contained in `scrape_to_markdown.py` with no external dependencies from a package structure. Everything is self-contained: selectors, link extraction, browser session management, scraping logic, and Markdown generation.

### Main Components (in scrape_to_markdown.py)

1. **TaobaoSelectors** (line 54): CSS selectors for all page elements
2. **TaobaoNavigationHelpers** (line 80): Tab navigation logic (reviews, params, details, etc.)
3. **TaobaoLinkExtractor** (line 98): Extracts product IDs from various link formats (short links, share links, direct URLs)
4. **TaobaoMarkdownScraper** (line 325): Main scraper orchestrator
   - `initialize()`: Sets up persistent browser session
   - `scrape_product()`: Complete workflow with login detection
   - `_scrape_basic_info()`: Title, price, store, thumbnail images
   - `_scrape_parameters()`: Product specifications (clicks params tab)
   - `_scrape_detail_images()`: Detail images from desc-root (clicks details tab)
   - `_scrape_reviews()`: User reviews and photos (clicks reviews tab)
   - `_scrape_qa()`: Q&A section
   - `save_markdown()`: Generates and saves Markdown output

### Browser Session Management

- Uses Playwright's `launch_persistent_context()` with user data directory
- Profile stored in `user_data/chrome_profile/`
- Headless mode is FALSE to allow manual QR code login when needed
- Session persists across script runs (no need to re-login each time)

### Login Flow Handling

The scraper automatically detects if Taobao redirects to login page (line 378-399):
1. Checks if URL contains `login.taobao.com` or `login.tmall.com`
2. Pauses and displays instructions for user to scan QR code
3. Waits up to 3 minutes for redirect back to product page
4. Continues scraping automatically after successful login

### Share Link Auto-Correction

Taobao share links (from WeChat, etc.) provide incomplete data. The scraper:
1. Detects share links via URL parameters (line 189-207)
2. Extracts product ID and rebuilds clean URL (line 210-221)
3. Reloads the page with clean URL to get full product data (line 404-415)

This is critical because share links often lack detail images required for product comparison.

### Tab Navigation Pattern

Taobao's product page uses a tab structure. The scraper must physically click tabs to load their content:
- Tab 0: Reviews (用户评价)
- Tab 1: Parameters (参数信息)
- Tab 2: Detail Images (图文详情) - CRITICAL for product comparison
- Tab 3: Shop Recommendations
- Tab 4: Also Viewed

Each scraping method clicks its respective tab before extracting data.

### Image Handling Strategy

**Thumbnail Images** (line 499-558):
- Multiple selector strategies to handle varying page structures
- Filters out placeholder images (2x2 pixels, spaceball.gif)
- Cleans URLs to remove size suffixes and get full-resolution images
- Checks multiple attributes: `src`, `data-src`, `data-ks-lazyload`

**Detail Images** (line 618-711):
- Most critical for AI product comparison feature
- Primary selector: `.desc-root img`
- Fallback selectors for alternative page structures
- Includes scrolling to trigger lazy-loaded images
- Logs warning if 0 detail images found (indicates data issue)

**Review Photos** (line 764-786):
- Extracted from review items
- URL cleaning to get full-size versions

## Critical Known Issues

### Taobao A/B Testing Problem

Taobao serves two different versions of product pages non-deterministically (see `knowledge/TAOBAO_AB_TEST_INVESTIGATION.md`):

- **Complete Version**: 22 detail images, full parameters, reviews
- **Simplified Version**: 3 images, 0 parameters, 0 reviews

This happens even with identical URLs and login state. The version is determined server-side during SSR. This is the most significant reliability challenge for the scraper.

**Current Status**: No solution implemented yet. DOM-based scraping cannot force complete version delivery.

**Potential Solutions to Explore**:
1. Cookie manipulation (`havana_lgc_exp` cookie may control assignment)
2. API endpoint discovery (bypass frontend A/B testing)
3. Retry logic with version detection
4. Header manipulation

## Selector Updates

When Taobao changes their page structure, update the class names in `TaobaoSelectors` (line 54). Common selectors that may change:
- `.mainTitle--R75fTcZL` (product title)
- `.text--LP7Wf49z` (price)
- `.desc-root` (detail images container)
- `.comments--ChxC7GEN` (reviews container)

Check `knowledge/TAOBAO_PAGE_STRUCTURE.md` for full selector documentation.

## Output Format

Markdown files saved to `product_info/` with structure:
- Basic info (ID, store, price, link, scrape time)
- Product images (thumbnails)
- Detail images
- Parameters table
- User reviews with photos
- Q&A section

## Dependencies

The scraper requires:
- `playwright` (async_playwright)
- `aiohttp` (for HTTP-based short link resolution)
- Standard library: `asyncio`, `pathlib`, `logging`, `urllib.parse`, `ssl`

No database dependencies (SQLAlchemy/Alembic removed from project).

## Path Configuration

All paths are relative to project root:
- Browser profile: `user_data/chrome_profile/` (line 340)
- Output directory: `product_info/` (line 836)

## Version Tracking

File header includes version number and detailed changelog. Update when making significant changes.
