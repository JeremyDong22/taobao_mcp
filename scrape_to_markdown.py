#!/usr/bin/env python3
"""
Standalone Taobao Product Scraper - Markdown Output
Version: 2.3
Created: 2025-11-16
Updated: 2025-11-17

Scrapes Taobao/Tmall products and outputs data as Markdown documents.
Images are displayed as links (not downloaded).
No database dependencies - completely standalone.

Changes in v2.3:
- Auto-click "Quick Entry" (快速进入) button when already logged in
- Handles Taobao's login confirmation page automatically
- Improved login detection to distinguish between new login vs confirmation

Changes in v2.2:
- Reorganized folder structure: separated user_data/ and product_info/
- Browser profile now saved in user_data/chrome_profile/
- Product markdown files now saved in product_info/

Changes in v2.1:
- Improved thumbnail image extraction with multiple selectors for main product gallery
- Added filtering for placeholder images (2x2 pixels, spaceball.gif, etc.)
- Enhanced image URL cleaning to remove size/quality suffixes and get full-resolution images
- Added data-src and data-ks-lazyload attribute support for lazy-loaded images
- Improved review photo extraction with better URL cleaning
- Added duplicate image detection
- Added login detection: if Taobao requires login, pauses and waits for user to scan QR code
- Increased page load wait times and added scrolling to trigger lazy-loaded content
- Added tab loading verification

Usage:
    python3 scrape_to_markdown.py "【淘宝】假一赔四 https://e.tb.cn/h.StvCjJlWxkNatsx?tk=Jnvaf9roBSn"
    python3 scrape_to_markdown.py "752468272997"
"""

import asyncio
import sys
import re
from pathlib import Path
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
import aiohttp
import ssl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


# ==================== SELECTORS ====================

class TaobaoSelectors:
    """CSS selectors for Taobao/Tmall product pages"""
    PRODUCT_TITLE = ".mainTitle--R75fTcZL"
    STORE_NAME = "#J_SiteNavOpenShop"
    PRICE_NUMBER = ".text--LP7Wf49z"
    SKU_VALUE_IMAGE_WRAP = ".valueItemImgWrap--ZvA2Cmim"
    TAB_TITLE_ITEM = ".tabTitleItem--z4AoobEz"
    COMMENTS_CONTAINER = ".comments--ChxC7GEN"
    REVIEW_ITEM = ".Comment--H5QmJwe9"
    REVIEW_USER_NAME = ".userName--KpyzGX2s"
    REVIEW_CONTENT = ".content--uonoOhaz"
    REVIEW_META = ".meta--PLijz6qf"
    REVIEW_PHOTO = ".photo--ZUITAPZq"
    EMPHASIS_PARAM_ITEM = ".emphasisParamsInfoItem--H5Qt3iog"
    EMPHASIS_PARAM_TITLE = ".emphasisParamsInfoItemTitle--IGClES8z"
    EMPHASIS_PARAM_SUBTITLE = ".emphasisParamsInfoItemSubTitle--Lzwb8yjJ"
    GENERAL_PARAM_ITEM = ".generalParamsInfoItem--qLqLDVWp"
    GENERAL_PARAM_TITLE = ".generalParamsInfoItemTitle--Fo9kKj5Z"
    GENERAL_PARAM_SUBTITLE = ".generalParamsInfoItemSubTitle--S4pgp6b9"
    DESC_ROOT = ".desc-root"
    QA_WRAP = ".askAnswerWrap--SOQkB8id"
    QA_ITEM = ".askAnswerItem--RJKHFPmt"
    QUESTION_TEXT = ".questionText--cClStSfJ"
    ANSWER = ".answer--GB6EGprf"


class TaobaoNavigationHelpers:
    """Tab navigation helpers"""
    TAB_INDEX = {
        'reviews': 0,
        'params': 1,
        'details': 2,
        'shop_recommend': 3,
        'also_viewed': 4
    }

    @staticmethod
    def get_tab_selector_by_index(index: int) -> str:
        return f"{TaobaoSelectors.TAB_TITLE_ITEM}:nth-child({index + 1})"

    @staticmethod
    def get_tab_selector_by_name(tab_name: str) -> str:
        index = TaobaoNavigationHelpers.TAB_INDEX.get(tab_name, 0)
        return TaobaoNavigationHelpers.get_tab_selector_by_index(index)


# ==================== LINK EXTRACTOR ====================

class TaobaoLinkExtractor:
    """Extract product IDs from various link formats"""
    PRODUCT_ID_PATTERN = r'\b(\d{12,13})\b'
    SHORT_LINK_PATTERN = r'https?://(?:e\.tb\.cn|s\.click\.taobao\.com)/[A-Za-z0-9\.]+(?:\?[^\s]*)?'
    DIRECT_LINK_PATTERN = r'https?://(?:item\.taobao\.com|detail\.tmall\.com|detail\.m\.tmall\.com|item\.m\.taobao\.com)/item\.htm\?(?:.*&)?id=(\d+)'

    @staticmethod
    async def extract_product_id(user_input: str, page=None) -> Optional[str]:
        """Extract product ID from various input formats"""
        if not user_input:
            return None

        user_input = user_input.strip()

        # Try direct link pattern first
        direct_match = re.search(TaobaoLinkExtractor.DIRECT_LINK_PATTERN, user_input)
        if direct_match:
            return direct_match.group(1)

        # Try raw product ID
        id_match = re.search(TaobaoLinkExtractor.PRODUCT_ID_PATTERN, user_input)
        if id_match:
            return id_match.group(1)

        # Try short link
        short_link_match = re.search(TaobaoLinkExtractor.SHORT_LINK_PATTERN, user_input)
        if short_link_match:
            short_url = short_link_match.group(0)

            if page:
                logger.info(f"🔗 Using browser to resolve short link: {short_url}")
                resolved_url = await TaobaoLinkExtractor.resolve_short_link_with_browser(short_url, page)
            else:
                logger.info(f"🔗 Using HTTP to resolve short link: {short_url}")
                resolved_url = await TaobaoLinkExtractor.resolve_short_link(short_url)

            if resolved_url:
                return await TaobaoLinkExtractor.extract_product_id(resolved_url, page)

        return None

    @staticmethod
    async def resolve_short_link_with_browser(short_url: str, page) -> Optional[str]:
        """Resolve short links using browser"""
        try:
            logger.info(f"   Navigating to short link...")
            await page.goto(short_url, wait_until='networkidle', timeout=15000)
            final_url = page.url
            logger.info(f"   ✅ Resolved to: {final_url}")
            return final_url
        except Exception as e:
            logger.warning(f"   ⚠️  Browser resolution failed: {e}")
            return None

    @staticmethod
    async def resolve_short_link(short_url: str, timeout: int = 5) -> Optional[str]:
        """Resolve short links using HTTP"""
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            timeout_config = aiohttp.ClientTimeout(total=timeout)
            connector = aiohttp.TCPConnector(ssl=ssl_context)

            async with aiohttp.ClientSession(timeout=timeout_config, connector=connector) as session:
                async with session.get(
                    short_url,
                    allow_redirects=True,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                    }
                ) as response:
                    final_url = str(response.url)
                    logger.info(f"   ✅ Resolved to: {final_url}")
                    return final_url
        except Exception as e:
            logger.warning(f"   ⚠️  HTTP resolution failed: {e}")
            return None

    @staticmethod
    def build_product_url(product_id: str, platform: str = 'tmall') -> str:
        """Build product URL from ID"""
        if platform.lower() == 'tmall':
            return f"https://detail.tmall.com/item.htm?id={product_id}"
        else:
            return f"https://item.taobao.com/item.htm?id={product_id}"


# ==================== UTILITY FUNCTIONS ====================

def is_share_link(url: str) -> bool:
    """Check if URL is a share link"""
    share_params = [
        'shareurl', 'tbSocialPopKey', 'app', 'cpp', 'short_name',
        'sp_tk', 'tk', 'suid', 'bxsign', 'wxsign', 'un', 'ut_sk',
        'share_crt_v', 'sourceType', 'shareUniqueId'
    ]

    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        for param in share_params:
            if param in query_params:
                return True

        return False
    except Exception:
        return False


def clean_share_url(url: str, product_id: str) -> str:
    """Remove share parameters and build clean URL"""
    try:
        parsed = urlparse(url)
        platform = 'tmall' if 'tmall.com' in parsed.netloc else 'taobao'

        if platform == 'tmall':
            return f"https://detail.tmall.com/item.htm?id={product_id}"
        else:
            return f"https://item.taobao.com/item.htm?id={product_id}"
    except Exception:
        return f"https://detail.tmall.com/item.htm?id={product_id}"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters"""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = filename.replace(' ', '_')
    if len(filename) > 100:
        filename = filename[:100]
    filename = filename.rstrip('. ')
    return filename


def generate_markdown(product_data: Dict) -> str:
    """Generate Markdown document from product data"""
    md = []

    # Title
    title = product_data.get('title', 'Unknown Product')
    md.append(f"# {title}\n")

    # Basic Information
    md.append("## 基本信息\n")
    md.append(f"- **商品ID**: {product_data.get('product_id', 'N/A')}")
    md.append(f"- **店铺**: {product_data.get('store_name', 'N/A')}")

    current_price = product_data.get('current_price')
    if current_price:
        md.append(f"- **价格**: ¥{current_price}")

    original_price = product_data.get('original_price')
    if original_price:
        md.append(f"- **原价**: ¥{original_price}")

    md.append(f"- **商品链接**: {product_data.get('product_url', 'N/A')}")
    md.append(f"- **抓取时间**: {product_data.get('scraped_at', 'N/A')}\n")

    # Thumbnail Images
    thumbnail_images = product_data.get('thumbnail_images', [])
    if thumbnail_images:
        md.append("## 商品图片\n")
        for idx, img in enumerate(thumbnail_images, 1):
            url = img.get('url', '')
            md.append(f"![缩略图{idx}]({url})")
        md.append("")

    # Detail Images
    detail_images = product_data.get('detail_images', [])
    if detail_images:
        md.append("## 详情图片\n")
        for idx, img in enumerate(detail_images, 1):
            url = img.get('url', '')
            md.append(f"![详情图{idx}]({url})")
        md.append("")

    # Parameters
    parameters = product_data.get('parameters', [])
    if parameters:
        md.append("## 参数信息\n")
        md.append("| 参数名 | 参数值 |")
        md.append("|--------|--------|")
        for param in parameters:
            name = param.get('param_name', '')
            value = param.get('param_value', '')
            md.append(f"| {name} | {value} |")
        md.append("")

    # Reviews
    reviews = product_data.get('reviews', [])
    if reviews:
        md.append("## 用户评价\n")
        for idx, review in enumerate(reviews, 1):
            md.append(f"### 评价{idx}\n")
            md.append(f"- **用户**: {review.get('username', 'N/A')}")
            md.append(f"- **日期**: {review.get('review_date', 'N/A')}")

            variant = review.get('product_variant')
            if variant:
                md.append(f"- **规格**: {variant}")

            content = review.get('review_text', '')
            if content:
                md.append(f"- **内容**: {content}")

            photos = review.get('photos', [])
            if photos:
                photo_links = ', '.join([f"[图片{i+1}]({url})" for i, url in enumerate(photos)])
                md.append(f"- **图片**: {photo_links}")

            md.append("")

    # Q&A
    qa_items = product_data.get('qa', [])
    if qa_items:
        md.append("## 问答\n")
        for idx, qa in enumerate(qa_items, 1):
            md.append(f"### Q{idx}: {qa.get('question', '')}\n")
            md.append(f"**A**: {qa.get('answer', '')}\n")

    return '\n'.join(md)


# ==================== MAIN SCRAPER ====================

class TaobaoMarkdownScraper:
    """Taobao product scraper with Markdown output"""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None

    async def initialize(self):
        """Initialize browser session"""
        logger.info("🌐 Initializing browser session...")

        playwright = await async_playwright().start()

        # Create browser profile directory
        profile_dir = Path("user_data/chrome_profile")
        profile_dir.mkdir(parents=True, exist_ok=True)

        self.browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )

        self.page = await self.browser.new_page()
        logger.info("✅ Browser initialized")

    async def close(self):
        """Clean up resources"""
        if self.browser:
            await self.browser.close()

    async def _handle_quick_entry_button(self) -> bool:
        """
        Check for and click the "Quick Entry" (快速进入) button if present.
        This appears when user is already logged in but Taobao needs confirmation.

        Returns:
            bool: True if button was found and clicked, False otherwise
        """
        quick_entry_selectors = [
            "#login > div.login-content.nc-outer-box > div > div.fm-btn > button",  # Precise CSS selector
            "button.fm-submit",  # Class-based selector
            "button:has-text('快速进入')",  # Text-based selector (fallback)
            "button[type='submit'].fm-button",  # Combination selector (fallback)
        ]

        for selector in quick_entry_selectors:
            try:
                quick_entry_btn = await self.page.query_selector(selector)
                if quick_entry_btn:
                    # Check if button text contains "快速进入"
                    btn_text = await quick_entry_btn.text_content()
                    if btn_text and "快速进入" in btn_text:
                        logger.info(f"   ✅ Found quick entry button, clicking automatically...")
                        await quick_entry_btn.click()
                        await asyncio.sleep(3)  # Wait for redirect
                        return True
            except Exception:
                continue

        return False

    async def scrape_product(self, user_input: str) -> Dict:
        """Complete product scraping workflow"""
        # Extract product ID
        logger.info("🔍 Extracting product ID...")
        extractor = TaobaoLinkExtractor()
        product_id = await extractor.extract_product_id(user_input, page=self.page)

        if not product_id:
            raise ValueError(f"❌ Could not extract product ID from: {user_input}")

        logger.info(f"✅ Found product: {product_id}")

        # Navigate to product page
        product_url = extractor.build_product_url(product_id, platform='tmall')
        logger.info(f"\n📊 Navigating to product page...")
        await self.page.goto(product_url, wait_until='domcontentloaded', timeout=60000)

        logger.info("⏳ Waiting for page to render...")
        await asyncio.sleep(3)

        # Check if redirected to login/confirmation page
        current_url = self.page.url
        if 'login.taobao.com' in current_url or 'login.tmall.com' in current_url:
            # Try to click quick entry button if present (user already logged in, just needs confirmation)
            logger.info("   Detected login/confirmation page...")
            quick_entry_clicked = await self._handle_quick_entry_button()

            # Check if we successfully bypassed the confirmation
            current_url = self.page.url
            if quick_entry_clicked and ('login.taobao.com' not in current_url and 'login.tmall.com' not in current_url):
                logger.info("   ✅ Successfully auto-confirmed login!")
            else:
                # Still on login page - need actual login
                logger.warning("\n🔒 LOGIN REQUIRED!")
                logger.warning("=" * 60)
                logger.warning("淘宝检测到自动化访问，需要登录验证。")
                logger.warning("请在打开的浏览器窗口中：")
                logger.warning("  1. 扫码登录（推荐）或使用其他登录方式")
                logger.warning("  2. 登录成功后，浏览器会自动跳转到商品页面")
                logger.warning("  3. 等待程序自动继续...")
                logger.warning("=" * 60)

                # Wait for user to login and be redirected to product page
                try:
                    await self.page.wait_for_function(
                        f"window.location.href.includes('detail.tmall.com') || window.location.href.includes('item.taobao.com')",
                        timeout=180000  # 3 minutes for user to login
                    )
                    logger.info("✅ 登录成功！继续抓取...")
                    await asyncio.sleep(3)
                except Exception as e:
                    raise Exception("登录超时或未成功跳转到商品页面") from e

        await self.page.wait_for_selector(TaobaoSelectors.PRODUCT_TITLE, state='attached', timeout=45000)

        # Check for share link
        current_url = self.page.url
        if is_share_link(current_url):
            logger.warning("\n⚠️  Share link detected! Loading full product page...")
            clean_url = clean_share_url(current_url, product_id)
            logger.info(f"   Clean URL: {clean_url}")

            await self.page.goto(clean_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            await self.page.wait_for_selector(TaobaoSelectors.PRODUCT_TITLE, state='attached', timeout=45000)
            logger.info("   ✅ Reloaded with clean URL")
        else:
            logger.info("✅ Clean product page loaded")

        # Initialize data
        scraped_data = {
            'product_id': product_id,
            'product_url': product_url,
            'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Scrape basic info
        logger.info("📷 Scraping main product info...")
        basic_info = await self._scrape_basic_info()
        scraped_data.update(basic_info)
        logger.info(f"✅ Title: {basic_info.get('title', 'N/A')[:50]}...")
        logger.info(f"✅ Price: ¥{basic_info.get('current_price', 'N/A')}")
        logger.info(f"✅ Found {len(basic_info.get('thumbnail_images', []))} thumbnail images")

        # Scrape parameters
        logger.info("\n📋 Scraping parameters...")
        parameters = await self._scrape_parameters()
        scraped_data['parameters'] = parameters
        logger.info(f"✅ Found {len(parameters)} parameters")

        # Scrape detail images
        logger.info("\n🖼️  Scraping detail images...")
        detail_images = await self._scrape_detail_images()
        scraped_data['detail_images'] = detail_images

        if len(detail_images) == 0:
            logger.warning("⚠️  WARNING: NO DETAIL IMAGES FOUND!")
        else:
            logger.info(f"✅ Found {len(detail_images)} detail images")

        # Scrape reviews
        logger.info("\n💬 Scraping reviews...")
        reviews = await self._scrape_reviews()
        scraped_data['reviews'] = reviews
        review_photo_count = sum(len(r.get('photos', [])) for r in reviews)
        logger.info(f"✅ Loaded {len(reviews)} reviews")
        logger.info(f"✅ Found {review_photo_count} review photos")

        # Scrape Q&A
        logger.info("\n❓ Scraping Q&A...")
        try:
            qa_items = await self._scrape_qa()
            scraped_data['qa'] = qa_items
            logger.info(f"✅ Found {len(qa_items)} Q&A items")
        except Exception as e:
            logger.warning(f"⚠️  No Q&A section: {e}")
            scraped_data['qa'] = []

        return scraped_data

    async def _scrape_basic_info(self) -> Dict:
        """Scrape basic product information"""
        data = {}

        try:
            # Title
            title_elem = await self.page.query_selector(TaobaoSelectors.PRODUCT_TITLE)
            if title_elem:
                data['title'] = await title_elem.text_content()

            # Store name
            store_elem = await self.page.query_selector(TaobaoSelectors.STORE_NAME)
            if store_elem:
                data['store_name'] = await store_elem.text_content()

            # Price
            price_numbers = await self.page.query_selector_all(TaobaoSelectors.PRICE_NUMBER)
            if price_numbers:
                prices = []
                for p in price_numbers:
                    text = await p.text_content()
                    try:
                        prices.append(float(text.strip()))
                    except ValueError:
                        pass

                if prices:
                    data['current_price'] = prices[0]
                    if len(prices) > 1:
                        data['original_price'] = prices[1]

            # Thumbnail images
            thumbnail_images = []

            # Try multiple selector strategies
            thumb_selectors = [
                # Main product image carousel/gallery
                ".mainPics--zjWRE6H0 img",
                ".smallPics--hcpgB5rG img",
                ".mainPic--qiVGhOsT img",
                ".picGallery img",
                ".J_ImgBooth",
                # SKU images
                f"{TaobaoSelectors.SKU_VALUE_IMAGE_WRAP} img",
                # Legacy selectors
                ".mainPic img",
                ".J_ThumbnailList img",
                "[class*='mainPic'] img",
                "[class*='gallery'] img"
            ]

            for selector in thumb_selectors:
                thumbs = await self.page.query_selector_all(selector)
                if thumbs:
                    for idx, thumb in enumerate(thumbs[:10]):
                        # Try multiple attributes
                        src = await thumb.get_attribute('src')
                        if not src or 'tps-2-2' in src:  # Skip 2x2 placeholder images
                            src = await thumb.get_attribute('data-src')
                        if not src or 'tps-2-2' in src:
                            src = await thumb.get_attribute('data-ks-lazyload')
                        if not src or 'tps-2-2' in src:
                            # Try to get from parent element's style or data attributes
                            parent = await thumb.evaluate_handle("el => el.parentElement")
                            if parent:
                                bg_image = await parent.evaluate("el => getComputedStyle(el).backgroundImage")
                                if bg_image and 'url(' in bg_image:
                                    src = bg_image.replace('url("', '').replace('")', '').replace("url('", "").replace("')", "")

                        if src and src.startswith('http') and 'tps-2-2' not in src:
                            # Clean up image URL to get high-res version
                            src = src.split('?')[0]  # Remove query params
                            # Remove all size/quality suffixes (handle .jpg_90x90q30.jpg_.webp format)
                            src = re.sub(r'\.jpg_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)
                            src = re.sub(r'_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)
                            src = re.sub(r'_\d+x\d+\.jpg$', '', src)
                            src = src.replace('_60x60', '').replace('_50x50', '').replace('_80x80', '').replace('_90x90', '').replace('_sum', '')

                            # Avoid duplicates
                            if not any(img['url'] == src for img in thumbnail_images):
                                thumbnail_images.append({
                                    'url': src,
                                    'sequence': idx,
                                    'type': 'thumbnail'
                                })

                    if thumbnail_images:  # If we found images, stop trying other selectors
                        break

            data['thumbnail_images'] = thumbnail_images

        except Exception as e:
            logger.error(f"Error scraping basic info: {e}")

        return data

    async def _scrape_parameters(self) -> List[Dict]:
        """Scrape product parameters"""
        parameters = []

        try:
            # Click parameters tab
            params_tab = await self.page.query_selector(
                TaobaoNavigationHelpers.get_tab_selector_by_name('params')
            )
            if params_tab:
                await params_tab.click()
                await self.page.wait_for_timeout(2000)

                # Emphasis parameters
                emphasis_items = await self.page.query_selector_all(
                    TaobaoSelectors.EMPHASIS_PARAM_ITEM
                )

                for item in emphasis_items:
                    label_elem = await item.query_selector(TaobaoSelectors.EMPHASIS_PARAM_SUBTITLE)
                    value_elem = await item.query_selector(TaobaoSelectors.EMPHASIS_PARAM_TITLE)

                    if label_elem and value_elem:
                        label = (await label_elem.text_content()).strip()
                        value = (await value_elem.text_content()).strip()
                        parameters.append({
                            'param_name': label,
                            'param_value': value,
                            'param_category': 'emphasis'
                        })

                # General parameters
                general_items = await self.page.query_selector_all(
                    TaobaoSelectors.GENERAL_PARAM_ITEM
                )

                for item in general_items:
                    label_elem = await item.query_selector(TaobaoSelectors.GENERAL_PARAM_TITLE)
                    value_elem = await item.query_selector(TaobaoSelectors.GENERAL_PARAM_SUBTITLE)

                    if label_elem and value_elem:
                        label = (await label_elem.text_content()).strip()
                        value = (await value_elem.text_content()).strip()
                        parameters.append({
                            'param_name': label,
                            'param_value': value,
                            'param_category': 'general'
                        })

        except Exception as e:
            logger.error(f"Error scraping parameters: {e}")

        return parameters

    async def _scrape_detail_images(self) -> List[Dict]:
        """Scrape detail images"""
        detail_images = []

        try:
            # Click details tab
            details_tab = await self.page.query_selector(
                TaobaoNavigationHelpers.get_tab_selector_by_name('details')
            )

            if not details_tab:
                logger.error("❌ Detail tab not found!")
                return detail_images

            await details_tab.click()
            await self.page.wait_for_timeout(2000)

            # Wait for desc-root
            try:
                await self.page.wait_for_selector(TaobaoSelectors.DESC_ROOT, timeout=10000)
            except Exception:
                logger.warning("⚠️  .desc-root not found, trying alternatives...")
                alternative_selectors = [
                    ".description",
                    ".detail-content",
                    ".desc-content",
                    "[class*='desc']",
                    "[class*='detail-wrap']"
                ]

                for selector in alternative_selectors:
                    elem = await self.page.query_selector(selector)
                    if elem:
                        logger.info(f"   ✅ Found alternative: {selector}")
                        imgs = await elem.query_selector_all("img")
                        if imgs:
                            for idx, img in enumerate(imgs):
                                src = await img.get_attribute('src')
                                data_src = await img.get_attribute('data-src')
                                url = data_src if data_src else src
                                if url and url.startswith('http'):
                                    detail_images.append({
                                        'url': url,
                                        'sequence': idx,
                                        'type': 'detail'
                                    })
                            return detail_images

                return detail_images

            # Scroll to load lazy images
            await self.page.evaluate("""
                () => {
                    const descRoot = document.querySelector('.desc-root');
                    if (descRoot) {
                        descRoot.scrollIntoView();
                        window.scrollBy(0, 500);
                    }
                }
            """)
            await self.page.wait_for_timeout(1000)

            # Additional scrolling
            for i in range(3):
                await self.page.evaluate("window.scrollBy(0, 800)")
                await self.page.wait_for_timeout(500)

            # Extract images
            detail_img_elems = await self.page.query_selector_all(
                f"{TaobaoSelectors.DESC_ROOT} img"
            )

            for idx, img in enumerate(detail_img_elems):
                src = await img.get_attribute('src')
                data_src = await img.get_attribute('data-src')

                url = data_src if data_src else src

                # Skip placeholder/tracking images
                if url and url.startswith('http'):
                    # Filter out common placeholders
                    if any(placeholder in url for placeholder in ['spaceball.gif', 'tps-2-2', 'pixel.gif', 'blank.gif']):
                        continue

                    detail_images.append({
                        'url': url,
                        'sequence': idx,
                        'type': 'detail'
                    })

        except Exception as e:
            logger.error(f"Error scraping detail images: {e}")

        return detail_images

    async def _scrape_reviews(self) -> List[Dict]:
        """Scrape reviews"""
        reviews = []

        try:
            # Click reviews tab
            reviews_tab = await self.page.query_selector(
                TaobaoNavigationHelpers.get_tab_selector_by_name('reviews')
            )
            if reviews_tab:
                await reviews_tab.click()
                await self.page.wait_for_timeout(2000)

                # Wait for reviews container
                await self.page.wait_for_selector(
                    TaobaoSelectors.COMMENTS_CONTAINER,
                    timeout=10000
                )

                # Scroll to load more reviews
                for i in range(5):
                    await self.page.evaluate("window.scrollBy(0, 600)")
                    await self.page.wait_for_timeout(800)

                # Extract reviews
                review_items = await self.page.query_selector_all(TaobaoSelectors.REVIEW_ITEM)

                for item in review_items:
                    review_data = {}

                    # Username
                    username_elem = await item.query_selector(TaobaoSelectors.REVIEW_USER_NAME)
                    if username_elem:
                        review_data['username'] = await username_elem.text_content()

                    # Content
                    content_elem = await item.query_selector(TaobaoSelectors.REVIEW_CONTENT)
                    if content_elem:
                        review_data['review_text'] = await content_elem.text_content()

                    # Meta
                    meta_elem = await item.query_selector(TaobaoSelectors.REVIEW_META)
                    if meta_elem:
                        meta_text = await meta_elem.text_content()
                        parts = meta_text.split('·')
                        if len(parts) >= 1:
                            review_data['review_date'] = parts[0].strip()
                        if len(parts) >= 2:
                            review_data['product_variant'] = parts[1].strip()

                    # Photos
                    photo_elems = await item.query_selector_all(
                        f"{TaobaoSelectors.REVIEW_PHOTO} img"
                    )
                    photos = []
                    for photo in photo_elems:
                        src = await photo.get_attribute('src')
                        if not src:
                            src = await photo.get_attribute('data-src')

                        if src and src.startswith('http'):
                            # Clean up to get full-size images
                            src = src.split('?')[0]
                            src = re.sub(r'\.jpg_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)
                            src = re.sub(r'_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)
                            src = re.sub(r'_\d+x\d+\.jpg$', '', src)
                            src = src.replace('_60x60', '').replace('_80x80', '').replace('_90x90', '').replace('_sum', '')

                            # Skip placeholders
                            if not any(placeholder in src for placeholder in ['spaceball.gif', 'tps-2-2', 'pixel.gif']):
                                photos.append(src)

                    review_data['photos'] = photos
                    reviews.append(review_data)

        except Exception as e:
            logger.error(f"Error scraping reviews: {e}")

        return reviews

    async def _scrape_qa(self) -> List[Dict]:
        """Scrape Q&A section"""
        qa_items = []

        try:
            # Scroll to Q&A
            await self.page.evaluate(f"""
                () => {{
                    const qaWrap = document.querySelector('{TaobaoSelectors.QA_WRAP}');
                    if (qaWrap) {{
                        qaWrap.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                    }}
                }}
            """)
            await self.page.wait_for_timeout(1000)

            await self.page.wait_for_selector(TaobaoSelectors.QA_WRAP, timeout=5000)

            qa_elems = await self.page.query_selector_all(TaobaoSelectors.QA_ITEM)

            for item in qa_elems:
                question_elem = await item.query_selector(TaobaoSelectors.QUESTION_TEXT)
                answer_elem = await item.query_selector(TaobaoSelectors.ANSWER)

                if question_elem and answer_elem:
                    question = await question_elem.text_content()
                    answer = await answer_elem.text_content()

                    qa_items.append({
                        'question': question.strip(),
                        'answer': answer.strip()
                    })

        except Exception:
            pass

        return qa_items

    def save_markdown(self, product_data: Dict) -> str:
        """Save product data as Markdown file"""
        logger.info("\n💾 Generating Markdown document...")

        # Create output directory
        output_dir = Path("product_info")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from title
        title = product_data.get('title', 'Unknown_Product')
        safe_title = sanitize_filename(title)
        filename = f"{safe_title}.md"
        filepath = output_dir / filename

        # Generate Markdown content
        markdown_content = generate_markdown(product_data)

        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        logger.info(f"✅ Markdown saved: {filepath}")

        return str(filepath)


async def main(user_input: str):
    """Main execution function"""
    import time
    start_time = time.time()
    scraper = TaobaoMarkdownScraper()

    try:
        # Initialize browser
        await scraper.initialize()

        # Scrape product
        product_data = await scraper.scrape_product(user_input)

        # Save as Markdown
        filepath = scraper.save_markdown(product_data)

        # Summary
        elapsed = time.time() - start_time
        logger.info("\n" + "="*60)
        logger.info("✅ Scraping complete!")
        logger.info(f"📁 Markdown file: {filepath}")
        logger.info(f"⏱️  Time elapsed: {elapsed:.1f} seconds")
        logger.info("="*60)

        # Display file contents
        logger.info("\n📄 Generated Markdown:\n")
        logger.info("="*60)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Show first 2000 chars
            if len(content) > 2000:
                logger.info(content[:2000] + "\n\n... (truncated, see full file at " + filepath + ")")
            else:
                logger.info(content)
        logger.info("="*60)

    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scrape_to_markdown.py <product_link_or_id>")
        print("")
        print("Examples:")
        print('  python3 scrape_to_markdown.py "【淘宝】假一赔四 https://e.tb.cn/h.StvCjJlWxkNatsx?tk=xxx"')
        print('  python3 scrape_to_markdown.py "752468272997"')
        print('  python3 scrape_to_markdown.py "https://detail.tmall.com/item.htm?id=752468272997"')
        sys.exit(1)

    user_input = sys.argv[1]
    asyncio.run(main(user_input))
