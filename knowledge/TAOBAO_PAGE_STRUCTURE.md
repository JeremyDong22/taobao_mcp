# Taobao/Tmall Page Structure Technical Documentation

## Overview
This document explains the structure differences between Taobao/Tmall share links and normal product links, and how the scraper handles them.

## Page Types

### 1. Normal Product Links
These are standard desktop product page URLs that contain full product details.

**Characteristics:**
- Direct item URL format
- Full product information available
- Complete detail images in `.desc-root` container
- All tabs accessible (reviews, parameters, details)

**URL Examples:**
```
https://detail.tmall.com/item.htm?id=752468272997
https://item.taobao.com/item.htm?id=752468272997
```

### 2. Share Links
These are simplified mobile/share pages with limited functionality.

**Characteristics:**
- Contains share-specific URL parameters
- Simplified page structure for mobile viewing
- Missing or incomplete detail images
- Limited tab functionality
- NOT suitable for comprehensive product scraping

**URL Examples:**
```
https://detail.tmall.com/item.htm?id=752468272997&shareurl=1&tbSocialPopKey=xxx
https://item.taobao.com/item.htm?id=752468272997&app=chrome&cpp=1&tk=xxx
```

## Share Link Detection Parameters

The scraper automatically detects share links by checking for these URL parameters:

| Parameter | Description |
|-----------|-------------|
| `shareurl` | Share URL flag |
| `tbSocialPopKey` | Taobao social popup key |
| `app` | App source indicator |
| `cpp` | Cross-platform parameter |
| `short_name` | Short link identifier |
| `sp_tk` | Share token |
| `tk` | Token parameter |
| `suid` | Share user ID |
| `bxsign` | Box sign |
| `wxsign` | WeChat signature |
| `un` | User name |
| `ut_sk` | User tracking session key |
| `share_crt_v` | Share creation version |
| `sourceType` | Source type |
| `shareUniqueId` | Share unique identifier |

## Page Structure Differences

### Normal Product Page Structure
```
Product Page
├── Main Product Info (Tab 0)
│   ├── .mainTitle--R75fTcZL (title)
│   ├── .priceWrap--R3TrPIS6 (price)
│   ├── .skuWrapper--iKSsnB_s (variants)
│   └── Thumbnail images
│
├── Reviews (Tab 0 - 用户评价)
│   ├── .comments--ChxC7GEN (container)
│   └── .Comment--H5QmJwe9 (review items)
│
├── Parameters (Tab 1 - 参数信息)
│   ├── .emphasisParamsInfoWrap--b8752_wd (highlighted params)
│   └── .generalParamsInfoWrap--D5HQi4uU (general params)
│
├── Detail Images (Tab 2 - 图文详情)
│   └── .desc-root (CRITICAL for product comparison)
│       └── Multiple product detail images
│
└── Q&A (问大家)
    └── .askAnswerWrap--SOQkB8id
```

### Share Link Page Structure
```
Share Page (Simplified)
├── Basic Product Info
│   ├── Title (may be present)
│   ├── Price (may be present)
│   └── Thumbnail images (limited)
│
├── Limited or Missing Tabs
│   ├── Reviews - may be incomplete
│   ├── Parameters - may be missing
│   └── Detail Images - OFTEN MISSING ⚠️
│
└── .desc-root container
    └── May be empty or missing entirely
```

## Scraper Handling Strategy

### 1. Share Link Detection
```python
def is_share_link(url: str) -> bool:
    """Check if URL contains share parameters"""
    share_params = ['shareurl', 'tbSocialPopKey', 'app', 'cpp', ...]
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # Check if any share parameter exists
    for param in share_params:
        if param in query_params:
            return True
    return False
```

### 2. URL Cleaning
```python
def clean_share_url(url: str, product_id: str) -> str:
    """Remove all share parameters and build clean URL"""
    parsed = urlparse(url)
    platform = 'tmall' if 'tmall.com' in parsed.netloc else 'taobao'

    if platform == 'tmall':
        return f"https://detail.tmall.com/item.htm?id={product_id}"
    else:
        return f"https://item.taobao.com/item.htm?id={product_id}"
```

### 3. Automatic Retry Flow
```
User provides share link
    ↓
Navigate to URL
    ↓
Check if share link detected
    ↓
[If YES] Clean URL & Re-navigate
    ↓
Continue scraping with full page
```

### 4. Critical Validation
The scraper validates that detail images were successfully extracted:

```python
if len(detail_images) == 0:
    logger.error("CRITICAL: NO DETAIL IMAGES FOUND!")
    logger.error("CANNOT use for AI product comparison feature!")
```

**Why this matters:**
- Detail images (图文详情) are REQUIRED for AI product comparison
- Share links often don't have this section
- Without detail images, product comparison feature won't work

## Implementation Details

### Share Link Auto-Correction (in scrape_product.py)
```python
# After initial navigation
current_url = self.page.url
if is_share_link(current_url):
    logger.warning("Share link detected! Reloading clean URL...")
    clean_url = clean_share_url(current_url, product_id)
    await self.page.goto(clean_url, wait_until='domcontentloaded')
    logger.info("Reloaded with clean URL")
```

### Detail Image Extraction with Fallback Selectors
```python
# Primary selector
await self.page.wait_for_selector('.desc-root', timeout=10000)

# If primary fails, try alternatives
alternative_selectors = [
    ".description",
    ".detail-content",
    ".desc-content",
    "[class*='desc']",
    "[class*='detail-wrap']"
]
```

## Best Practices for Users

1. **Always prefer normal product links over share links**
   - Copy URL directly from browser address bar
   - Avoid using shared links from WeChat/social media

2. **Verify detail images are extracted**
   - Check console output: "✅ Found X detail images"
   - If 0 detail images, product cannot be used for comparison

3. **When share link is unavoidable**
   - The scraper will automatically clean and retry
   - Check final success message
   - Validate that detail images were found

## Troubleshooting

### Problem: "NO DETAIL IMAGES FOUND"
**Causes:**
1. Using a share/mobile link
2. Seller didn't upload detail images
3. Page structure changed

**Solutions:**
1. Try using direct PC browser URL
2. Verify product has detail images in browser
3. Update selectors if structure changed

### Problem: Share link parameters still present
**Cause:** URL cleaning logic needs updating

**Solution:** Add new share parameters to detection list

## Reference

### Key DOM Selectors
- Product title: `.mainTitle--R75fTcZL`
- Price: `.text--LP7Wf49z`
- Detail images container: `.desc-root`
- Reviews container: `.comments--ChxC7GEN`
- Parameters: `.emphasisParamsInfoWrap--b8752_wd`

### Browser Session
- User data stored in: `data/browser/chrome_profile/`
- Persistent login across runs
- Handles anti-bot detection

### Product Data Storage
- Images downloaded to: `data/images/{product_id}/`
- Categories: `thumbnails/`, `detail/`, `reviews/`
- Markdown format with image references

## Version History
- v1.0 (2025-11-16): Initial documentation
