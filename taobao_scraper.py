#!/usr/bin/env python3
"""
Version: 2.5
Created: 2025-11-17
Updated: 2025-11-18

Taobao Product Scraper - Reusable module for MCP server
Provides scraping functionality for Taobao/Tmall products with browser automation.

Changes in v2.5:
- ✅ CRITICAL DEBUG: Added comprehensive logging throughout scraping pipeline
- ✅ Added detailed logs in extract_product_id to track URL parsing
- ✅ Added logs in short link resolution (browser & HTTP methods)
- ✅ Added logs in scrape_product to track each scraping step
- ✅ Helps diagnose where the process gets stuck (short link, page load, etc.)
- ✅ All log messages tagged with [Scraper], [LinkExtractor], [BrowserResolver], [HTTPResolver]
- ✅ TIMEOUT OPTIMIZATION: Reduced browser resolution timeout from 30s to 15s
- ✅ TIMEOUT OPTIMIZATION: Reduced HTTP resolution timeout from 10s to 8s
- ✅ Added specific TimeoutError handling for better error messages

Changes in v2.4:
- ✅ FIXED: Added pattern for .jpg_q50.jpg_.webp format (actual Taobao CDN format)
- ✅ FIXED: Comprehensive URL cleaning with proper regex ordering
- ✅ Added detailed comments for each URL pattern
- ✅ Now handles all variations: _q50, .jpg_q50.jpg_.webp, _100x100q50, etc.
- ✅ Tested against real Taobao product page URLs

Changes in v2.3:
- ✅ FIXED: URL cleaning logic now preserves file extensions (.jpg, .png)
- ✅ FIXED: .jpg_.webp suffix now correctly converted to .jpg instead of removed
- ✅ FIXED: .jpgq\d+ suffix pattern matching (was removing too much)
- ✅ Added PNG support in webp suffix handling
- ✅ Prevents broken image URLs from missing extensions

Changes in v2.2:
- ✅ FIXED: Login detection now uses multi-factor verification (DOM element + cookies)
- ✅ NEW: _check_login_status() method with reliable login detection
- ✅ Checks both .site-nav-login-info-nick element AND dnk/tb_token cookies
- ✅ Returns username when logged in for better user feedback
- ✅ More accurate login state detection prevents false positives/negatives

Changes in v2.1:
- ✅ FIXED: Browser session state detection - now properly detects when browser is closed externally
- ✅ Added browser liveness check in initialize() method
- ✅ Added browser liveness check in scrape_product() method
- ✅ Auto-reinitializes if browser was closed manually

Changes in v2.0 (MAJOR FEATURE EXPANSION):
- ✅ NEW: Shipping information (time, fee, from/to locations)
- ✅ NEW: Shop details (name, link, overall rating, detailed metrics)
- ✅ NEW: Guarantees & services (价保, 假一赔四, 极速退款, 7天退换, etc.)
- ✅ NEW: Product specifications (colors, sizes, stock status)
- ✅ FIXED: Main product gallery images now correctly extracted from #picGalleryEle
- ✅ Added 30+ new CSS selectors for comprehensive data extraction
- ✅ Now extracts 10 data categories (previously 6)

Changes in v1.3:
- Auto-click "Quick Entry" (快速进入) button when already logged in
- Handles Taobao's login confirmation page automatically
- Improved login detection logic to distinguish between new login vs confirmation

Changes in v1.2:
- Fixed short link extraction priority (now resolves short links before trying raw IDs)
- Added detailed logging for link resolution debugging
- Improved error handling with fallback from browser to HTTP resolution
- Increased timeouts for short link resolution

Changes in v1.1:
- initialize() now navigates to Taobao homepage instead of specific product
- More professional user experience when initializing login
"""

import asyncio
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import aiohttp
import ssl


# ==================== SELECTORS ====================

class TaobaoSelectors:
    """CSS selectors for Taobao/Tmall product pages"""
    # Basic product info
    PRODUCT_TITLE = ".mainTitle--R75fTcZL"
    STORE_NAME = "#J_SiteNavOpenShop"
    PRICE_NUMBER = ".text--LP7Wf49z"
    PRICE_UNIT = ".unit--zM7V7E0w"
    PRICE_NUMBER_ALT = ".text--Do8Zgb3q"

    # Main product gallery (left side demonstration images)
    PIC_GALLERY_ID = "#picGalleryEle"
    PIC_GALLERY_CLASS = ".picGallery--qY53_w0u"
    THUMBNAIL_PIC = ".thumbnailPic--QasTmWDm"
    MAIN_PIC = ".mainPic--zxTtQs0P"

    # Shop information
    SHOP_NAME = ".shopName--cSjM9uKk"
    SHOP_LINK = ".detailWrap--svoEjPUO"
    SHOP_RATING = ".StoreComprehensiveRating--If5wS20L"
    SHOP_LABEL_ITEM = ".storeLabelItem--IcqpWWIy"

    # Shipping information
    SHIPPING_TIME = ".shipping--Obxoxza7"
    SHIPPING_FEE = ".freight--oatKHK1s"
    SHIPPING_LOCATION = ".deliveryAddrWrap--KgrR00my span"
    SHIPPING_CONTAINER = ".DomesticDelivery--E69W_yfc"

    # Guarantees and services
    GUARANTEE_CONTAINER = ".GuaranteeInfo--OYtWvOEt"
    GUARANTEE_TEXT = ".guaranteeText--hqmmjLTB"

    # SKU (Specifications)
    SKU_ITEM = ".skuItem--Z2AJB9Ew"
    SKU_LABEL = ".ItemLabel--psS1SOyC"
    SKU_VALUE_ITEM = ".valueItem--smR4pNt4"
    SKU_VALUE_IMAGE_WRAP = ".valueItemImgWrap--ZvA2Cmim"
    SKU_HAS_IMAGE = ".hasImg--K82HLg1O"
    STOCK_STATUS = ".quantityTip--zL6BCu6j"

    # Tabs and navigation
    TAB_TITLE_ITEM = ".tabTitleItem--z4AoobEz"

    # Reviews
    COMMENTS_CONTAINER = ".comments--ChxC7GEN"
    REVIEW_ITEM = ".Comment--H5QmJwe9"
    REVIEW_USER_NAME = ".userName--KpyzGX2s"
    REVIEW_CONTENT = ".content--uonoOhaz"
    REVIEW_META = ".meta--PLijz6qf"
    REVIEW_PHOTO = ".photo--ZUITAPZq"

    # Parameters
    EMPHASIS_PARAM_ITEM = ".emphasisParamsInfoItem--H5Qt3iog"
    EMPHASIS_PARAM_TITLE = ".emphasisParamsInfoItemTitle--IGClES8z"
    EMPHASIS_PARAM_SUBTITLE = ".emphasisParamsInfoItemSubTitle--Lzwb8yjJ"
    GENERAL_PARAM_ITEM = ".generalParamsInfoItem--qLqLDVWp"
    GENERAL_PARAM_TITLE = ".generalParamsInfoItemTitle--Fo9kKj5Z"
    GENERAL_PARAM_SUBTITLE = ".generalParamsInfoItemSubTitle--S4pgp6b9"

    # Detail images
    DESC_ROOT = ".desc-root"

    # Q&A
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
        print(f"\n[LinkExtractor] Starting product ID extraction from: {user_input[:100]}...")

        if not user_input:
            print("[LinkExtractor] Empty input, returning None")
            return None

        user_input = user_input.strip()

        # Try direct link pattern first (highest priority)
        print("[LinkExtractor] Step 1: Trying direct link pattern...")
        direct_match = re.search(TaobaoLinkExtractor.DIRECT_LINK_PATTERN, user_input)
        if direct_match:
            product_id = direct_match.group(1)
            print(f"[LinkExtractor] ✅ Found product ID via direct link: {product_id}")
            return product_id

        # Try short link (resolve before trying raw ID to avoid false matches)
        print("[LinkExtractor] Step 2: Trying short link pattern...")
        short_link_match = re.search(TaobaoLinkExtractor.SHORT_LINK_PATTERN, user_input)
        if short_link_match:
            short_url = short_link_match.group(0)
            print(f"[LinkExtractor] 🔗 Detected short link: {short_url}")

            # Try browser resolution first (more reliable)
            if page:
                print("[LinkExtractor] Attempting browser resolution...")
                resolved_url = await TaobaoLinkExtractor.resolve_short_link_with_browser(short_url, page)
                if not resolved_url:
                    print("[LinkExtractor] ⚠️ Browser resolution failed, trying HTTP...")
                    resolved_url = await TaobaoLinkExtractor.resolve_short_link(short_url)
            else:
                print("[LinkExtractor] No browser available, using HTTP resolution...")
                resolved_url = await TaobaoLinkExtractor.resolve_short_link(short_url)

            if resolved_url:
                print(f"[LinkExtractor] ✅ Short link resolved to: {resolved_url}")
                # Recursively extract ID from resolved URL (without page to avoid re-resolving)
                product_id = await TaobaoLinkExtractor.extract_product_id(resolved_url, page=None)
                if product_id:
                    print(f"[LinkExtractor] ✅ Successfully extracted product ID: {product_id}")
                    return product_id
                else:
                    print(f"[LinkExtractor] ⚠️ WARNING: Resolved URL but could not extract ID from: {resolved_url}")
                    # Try one more time with the page context
                    return await TaobaoLinkExtractor.extract_product_id(resolved_url, page)
            else:
                print("[LinkExtractor] ❌ Failed to resolve short link - both methods failed")
                return None

        # Try raw product ID (last resort - only if no links found)
        print("[LinkExtractor] Step 3: Trying raw product ID pattern...")
        id_match = re.search(TaobaoLinkExtractor.PRODUCT_ID_PATTERN, user_input)
        if id_match:
            product_id = id_match.group(1)
            print(f"[LinkExtractor] ✅ Found raw product ID: {product_id}")
            return product_id

        print("[LinkExtractor] ❌ No product ID found in input")
        return None

    @staticmethod
    async def resolve_short_link_with_browser(short_url: str, page) -> Optional[str]:
        """Resolve short links using browser (15s timeout)"""
        try:
            print(f"[BrowserResolver] Navigating to short URL: {short_url}")
            # Reduced timeout from 30s to 15s to avoid long waits
            await page.goto(short_url, wait_until='domcontentloaded', timeout=15000)
            print("[BrowserResolver] Page loaded, waiting 2 seconds...")
            await asyncio.sleep(2)
            final_url = page.url
            print(f"[BrowserResolver] ✅ Resolved to: {final_url}")
            return final_url
        except asyncio.TimeoutError:
            print(f"[BrowserResolver] ⏱️ Timeout (15s) navigating to {short_url}")
            return None
        except Exception as e:
            # Log error but don't fail - will try HTTP method
            print(f"[BrowserResolver] ❌ Browser resolution failed for {short_url}: {e}")
            return None

    @staticmethod
    async def resolve_short_link(short_url: str, timeout: int = 8) -> Optional[str]:
        """Resolve short links using HTTP (8s timeout)"""
        try:
            print(f"[HTTPResolver] Resolving short URL: {short_url} (timeout={timeout}s)")
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Reduced timeout from 10s to 8s for faster failure detection
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
                    print(f"[HTTPResolver] ✅ Resolved to: {final_url}")
                    return final_url
        except asyncio.TimeoutError:
            print(f"[HTTPResolver] ⏱️ Timeout ({timeout}s) resolving {short_url}")
            return None
        except Exception as e:
            # Log error but don't fail
            print(f"[HTTPResolver] ❌ HTTP resolution failed for {short_url}: {e}")
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

    # Product Images - categorized by type
    thumbnail_images = product_data.get('thumbnail_images', [])
    if thumbnail_images:
        # Separate images by category - merge main_gallery into gallery
        gallery_images = [img for img in thumbnail_images if img.get('type') in ('main_gallery', 'gallery')]
        sku_images = [img for img in thumbnail_images if img.get('type') == 'sku_variant']

        # Gallery Images (includes main image)
        if gallery_images:
            md.append("## 画廊图片 (Gallery Images)\n")
            for idx, img in enumerate(gallery_images, 1):
                url = img.get('url', '')
                md.append(f"![画廊图{idx}]({url})")
            md.append("")

        # SKU Variant Images
        if sku_images:
            md.append("## SKU变体图片 (Color/Style Variants)\n")
            for idx, img in enumerate(sku_images, 1):
                url = img.get('url', '')
                md.append(f"![变体图{idx}]({url})")
            md.append("")

    # Detail Images
    detail_images = product_data.get('detail_images', [])
    if detail_images:
        md.append("## 详情图片 (Detail Images)\n")
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
        md.append("## 用户评价 (Customer Reviews)\n")
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
        md.append("## 问答 (Q&A)\n")
        for idx, qa in enumerate(qa_items, 1):
            md.append(f"### Q{idx}: {qa.get('question', '')}\n")
            md.append(f"**A**: {qa.get('answer', '')}\n")

    return '\n'.join(md)


# ==================== MAIN SCRAPER ====================

class TaobaoScraper:
    """
    Version: 1.0

    Reusable Taobao product scraper for MCP server.
    Manages browser lifecycle and provides product scraping functionality.
    """

    def __init__(self, profile_dir: str = "user_data/chrome_profile"):
        """
        Initialize scraper with browser profile directory.

        Args:
            profile_dir: Path to Chrome profile directory for persistent sessions
        """
        self.profile_dir = Path(profile_dir)
        self.browser: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self._is_initialized = False

    async def initialize(self) -> Dict[str, str]:
        """
        Initialize browser session with persistent profile.
        Handles login detection and waits for user authentication if needed.

        Returns:
            Dict with status and message
        """
        # Check if browser is actually alive (not just the flag)
        if self._is_initialized and self.page:
            try:
                # Test if page is still alive
                await self.page.evaluate("1 + 1")
                return {
                    "status": "already_initialized",
                    "message": "Browser session already active"
                }
            except Exception:
                # Browser was closed externally, reset state
                print("Browser was closed externally, reinitializing...")
                self._is_initialized = False
                self.browser = None
                self.page = None
                if self.playwright:
                    try:
                        await self.playwright.stop()
                    except Exception:
                        pass
                    self.playwright = None

        # Create browser profile directory
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=False,
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )

        self.page = await self.browser.new_page()
        self._is_initialized = True

        # Test if login is needed by navigating to Taobao homepage
        try:
            test_url = "https://www.taobao.com"
            await self.page.goto(test_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)

            current_url = self.page.url

            # Handle login page with quick entry button
            if 'login.taobao.com' in current_url or 'login.tmall.com' in current_url:
                # Try to click quick entry button if present
                quick_entry_clicked = await self._handle_quick_entry_button()

                # After clicking, wait and check login status
                if quick_entry_clicked:
                    await asyncio.sleep(2)
                    current_url = self.page.url

                    # If redirected away from login page, verify login with reliable detection
                    if 'login.taobao.com' not in current_url and 'login.tmall.com' not in current_url:
                        login_status = await self._check_login_status()
                        if login_status['isLoggedIn']:
                            username = login_status.get('username', 'Unknown')
                            return {
                                "status": "success",
                                "message": f"Browser initialized successfully. Auto-clicked 'Quick Entry' button. Logged in as: {username}"
                            }

                # Still on login page - need actual login
                return {
                    "status": "login_required",
                    "message": (
                        "LOGIN REQUIRED: Taobao requires login authentication.\n\n"
                        "Please complete the following steps:\n"
                        "1. In the opened browser window, scan the QR code to login (or use other login methods)\n"
                        "2. Wait for the browser to redirect to Taobao homepage\n"
                        "3. Once logged in successfully, the session will be saved for future use\n"
                        "4. Call this tool again or proceed to use taobao_fetch_product_info\n\n"
                        "Note: If you see a '快速进入' button, it will be clicked automatically."
                    )
                }

            # Not on login page - verify login status with reliable detection
            login_status = await self._check_login_status()

            if login_status['isLoggedIn']:
                username = login_status.get('username', 'Unknown')
                return {
                    "status": "success",
                    "message": f"Browser initialized successfully. Already logged in as: {username}"
                }
            else:
                # Not logged in but also not redirected to login page
                # This can happen if Taobao changes behavior
                return {
                    "status": "login_required",
                    "message": (
                        "LOGIN REQUIRED: Login detection shows you are not logged in.\n\n"
                        "Please try one of the following:\n"
                        "1. Manually navigate to https://login.taobao.com in the browser window\n"
                        "2. Scan QR code or use other login methods\n"
                        "3. Call this tool again after logging in"
                    )
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Initialization test failed: {str(e)}"
            }

    async def close(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
            self._is_initialized = False
        if self.playwright:
            await self.playwright.stop()

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
                        print(f"Found quick entry button with selector: {selector}")
                        await quick_entry_btn.click()
                        await asyncio.sleep(3)  # Wait for redirect
                        print("Successfully clicked quick entry button")
                        return True
            except Exception as e:
                print(f"Selector {selector} failed: {e}")
                continue

        return False

    async def _check_login_status(self) -> Dict[str, any]:
        """
        Check Taobao login status using reliable multi-factor verification.
        Uses both DOM elements and cookies to ensure accurate detection.

        Returns:
            Dict with keys:
                - isLoggedIn (bool): Whether user is logged in
                - username (str): User nickname if logged in
                - dnk (str): DNK cookie value if available
        """
        try:
            login_info = await self.page.evaluate("""() => {
                // Check for user nickname element
                const nickElement = document.querySelector('.site-nav-login-info-nick');

                // Helper function to get cookie value
                const getCookie = (name) => {
                    const value = `; ${document.cookie}`;
                    const parts = value.split(`; ${name}=`);
                    if (parts.length === 2) return parts.pop().split(';').shift();
                    return null;
                };

                // Check critical cookies
                const dnk = getCookie('dnk');  // Display nickname
                const tbToken = getCookie('_tb_token_');  // Taobao token

                // Multi-factor verification: element AND cookies must both confirm login
                const isLoggedIn = !!nickElement && !!dnk && !!tbToken;

                return {
                    isLoggedIn: isLoggedIn,
                    username: nickElement?.textContent?.trim() || null,
                    dnk: dnk ? decodeURIComponent(dnk) : null,
                    hasTbToken: !!tbToken,
                    hasNickElement: !!nickElement
                };
            }""")

            print(f"Login detection result: {login_info}")
            return login_info

        except Exception as e:
            print(f"Login status check failed: {e}")
            # Default to not logged in if check fails
            return {
                'isLoggedIn': False,
                'username': None,
                'dnk': None,
                'error': str(e)
            }

    async def scrape_product(self, user_input: str) -> Dict:
        """
        Scrape complete product information from Taobao/Tmall.

        Args:
            user_input: Product URL, short link, or product ID

        Returns:
            Dict containing all scraped product data

        Raises:
            ValueError: If product ID cannot be extracted
            RuntimeError: If browser is not initialized
        """
        print(f"\n{'='*60}")
        print(f"[Scraper] Starting product scrape")
        print(f"[Scraper] Input: {user_input[:100]}")
        print(f"{'='*60}\n")

        if not self._is_initialized or not self.page:
            raise RuntimeError("Browser not initialized. Call initialize() first.")

        # Verify browser is still alive
        print("[Scraper] Verifying browser is alive...")
        try:
            await self.page.evaluate("1 + 1")
            print("[Scraper] ✅ Browser is alive")
        except Exception as e:
            # Browser was closed externally
            self._is_initialized = False
            print(f"[Scraper] ❌ Browser session was closed: {e}")
            raise RuntimeError(
                f"Browser session was closed. Please call taobao_initialize_login again. "
                f"Error: {str(e)}"
            )

        # Extract product ID
        print("[Scraper] Extracting product ID...")
        extractor = TaobaoLinkExtractor()
        product_id = await extractor.extract_product_id(user_input, page=self.page)

        if not product_id:
            print(f"[Scraper] ❌ Failed to extract product ID from: {user_input}")
            raise ValueError(f"Could not extract product ID from: {user_input}")

        print(f"[Scraper] ✅ Product ID: {product_id}")

        # Navigate to product page
        product_url = extractor.build_product_url(product_id, platform='tmall')
        print(f"[Scraper] Navigating to product page: {product_url}")
        await self.page.goto(product_url, wait_until='domcontentloaded', timeout=60000)
        print("[Scraper] Page loaded, waiting 3 seconds...")
        await asyncio.sleep(3)

        # Check if redirected to login/confirmation page
        current_url = self.page.url
        print(f"[Scraper] Current URL: {current_url}")

        if 'login.taobao.com' in current_url or 'login.tmall.com' in current_url:
            print("[Scraper] ⚠️ Redirected to login page, trying quick entry...")
            # Try to click quick entry button if present (user already logged in, just needs confirmation)
            quick_entry_clicked = await self._handle_quick_entry_button()

            # Check if we successfully bypassed the confirmation
            current_url = self.page.url
            if not quick_entry_clicked or ('login.taobao.com' in current_url or 'login.tmall.com' in current_url):
                print("[Scraper] ❌ Login required!")
                raise RuntimeError(
                    "Login required! Please run taobao_initialize_login first and complete the login process."
                )

        print(f"[Scraper] Waiting for product title selector...")
        await self.page.wait_for_selector(TaobaoSelectors.PRODUCT_TITLE, state='attached', timeout=45000)
        print("[Scraper] ✅ Product title found")

        # Check for share link and clean if needed
        current_url = self.page.url
        if is_share_link(current_url):
            print("[Scraper] ⚠️ Share link detected, cleaning URL...")
            clean_url = clean_share_url(current_url, product_id)
            print(f"[Scraper] Navigating to clean URL: {clean_url}")
            await self.page.goto(clean_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(3)
            await self.page.wait_for_selector(TaobaoSelectors.PRODUCT_TITLE, state='attached', timeout=45000)
            print("[Scraper] ✅ Clean URL loaded")

        # Initialize data
        print("[Scraper] Initializing scraped data structure...")
        scraped_data = {
            'product_id': product_id,
            'product_url': product_url,
            'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Scrape all sections
        print("[Scraper] Scraping basic info...")
        basic_info = await self._scrape_basic_info()
        scraped_data.update(basic_info)
        print(f"[Scraper] ✅ Basic info: title={scraped_data.get('title', 'N/A')[:50]}")

        print("[Scraper] Scraping parameters...")
        scraped_data['parameters'] = await self._scrape_parameters()
        print(f"[Scraper] ✅ Parameters: {len(scraped_data['parameters'])} items")

        print("[Scraper] Scraping detail images...")
        scraped_data['detail_images'] = await self._scrape_detail_images()
        print(f"[Scraper] ✅ Detail images: {len(scraped_data['detail_images'])} images")

        print("[Scraper] Scraping reviews...")
        scraped_data['reviews'] = await self._scrape_reviews()
        print(f"[Scraper] ✅ Reviews: {len(scraped_data['reviews'])} reviews")

        print("[Scraper] Scraping Q&A...")
        try:
            scraped_data['qa'] = await self._scrape_qa()
            print(f"[Scraper] ✅ Q&A: {len(scraped_data['qa'])} items")
        except Exception as e:
            print(f"[Scraper] ⚠️ Q&A failed: {e}")
            scraped_data['qa'] = []

        # Scrape shipping information
        print("[Scraper] Scraping shipping info...")
        scraped_data['shipping'] = await self._scrape_shipping_info()
        print(f"[Scraper] ✅ Shipping info scraped")

        # Scrape shop details
        print("[Scraper] Scraping shop details...")
        scraped_data['shop'] = await self._scrape_shop_details()
        print(f"[Scraper] ✅ Shop details scraped")

        # Scrape guarantees
        print("[Scraper] Scraping guarantees...")
        scraped_data['guarantees'] = await self._scrape_guarantees()
        print(f"[Scraper] ✅ Guarantees: {len(scraped_data['guarantees'])} items")

        # Scrape specifications (colors, sizes, stock)
        print("[Scraper] Scraping specifications...")
        scraped_data['specifications'] = await self._scrape_specifications()
        print(f"[Scraper] ✅ Specifications scraped")

        print(f"\n{'='*60}")
        print("[Scraper] ✅ Product scraping completed successfully!")
        print(f"{'='*60}\n")

        return scraped_data

    async def _scrape_basic_info(self) -> Dict:
        """Scrape basic product information including title, price, and thumbnail images"""
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

            # Product images - capture ALL images (gallery + SKU variants)
            thumbnail_images = []

            # Strategy 1: Try to get main gallery images from #picGalleryEle
            gallery_found = False
            pic_gallery = await self.page.query_selector(TaobaoSelectors.PIC_GALLERY_ID)
            if not pic_gallery:
                pic_gallery = await self.page.query_selector(TaobaoSelectors.PIC_GALLERY_CLASS)

            if pic_gallery:
                gallery_images = await pic_gallery.query_selector_all('img')
                for idx, img in enumerate(gallery_images):
                    src = await img.get_attribute('src')
                    if not src or 'tps-2-2' in src:
                        src = await img.get_attribute('data-src')
                    if not src or 'tps-2-2' in src:
                        src = await img.get_attribute('data-ks-lazyload')

                    if src and src.startswith('http') and 'tps-2-2' not in src:
                        # Clean URL - remove Taobao's image processing suffixes
                        src = src.strip()  # Remove whitespace
                        src = src.split('?')[0]  # Remove query params

                        # Fix webp suffixes - preserve the image extension
                        # Pattern: .jpg_q50.jpg_.webp -> .jpg
                        src = re.sub(r'\.jpg_q\d+\.jpg_\.webp$', '.jpg', src)
                        # Pattern: _q50.jpg_.webp -> .jpg
                        src = re.sub(r'_q\d+\.jpg_\.webp$', '.jpg', src)
                        # Pattern: .jpg_.webp -> .jpg
                        src = re.sub(r'\.jpg_\.webp$', '.jpg', src)
                        # Pattern: .png_.webp -> .png
                        src = re.sub(r'\.png_\.webp$', '.png', src)
                        # Pattern: .jpg_100x100q50.jpg_.webp -> .jpg
                        src = re.sub(r'\.jpg_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)
                        # Pattern: _100x100q50.jpg_.webp -> .jpg
                        src = re.sub(r'_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)

                        # Fix other quality/size suffixes
                        src = re.sub(r'\.jpgq\d+$', '.jpg', src)  # .jpgq30 -> .jpg
                        src = re.sub(r'_\d+x\d+\.jpg$', '.jpg', src)  # _100x100.jpg -> .jpg

                        # Remove size markers
                        src = src.replace('_60x60', '').replace('_50x50', '').replace('_80x80', '').replace('_90x90', '').replace('_sum', '')

                        if not any(img['url'] == src for img in thumbnail_images):
                            thumbnail_images.append({
                                'url': src,
                                'sequence': len(thumbnail_images),
                                'type': 'gallery'
                            })
                            gallery_found = True

            # Strategy 2: ALSO capture SKU variant images (color selection thumbnails)
            sku_images = await self.page.query_selector_all(f"{TaobaoSelectors.SKU_VALUE_IMAGE_WRAP} img")
            for idx, img in enumerate(sku_images):
                src = await img.get_attribute('src')
                if not src:
                    src = await img.get_attribute('data-src')
                if not src:
                    src = await img.get_attribute('data-ks-lazyload')

                if src and src.startswith('http') and 'tps-2-2' not in src:
                    # Clean URL - remove Taobao's image processing suffixes
                    src = src.strip()  # Remove whitespace
                    src = src.split('?')[0]  # Remove query params

                    # Fix webp suffixes - preserve the image extension
                    # Pattern: .jpg_q50.jpg_.webp -> .jpg
                    src = re.sub(r'\.jpg_q\d+\.jpg_\.webp$', '.jpg', src)
                    # Pattern: _q50.jpg_.webp -> .jpg
                    src = re.sub(r'_q\d+\.jpg_\.webp$', '.jpg', src)
                    # Pattern: .jpg_.webp -> .jpg
                    src = re.sub(r'\.jpg_\.webp$', '.jpg', src)
                    # Pattern: .png_.webp -> .png
                    src = re.sub(r'\.png_\.webp$', '.png', src)
                    # Pattern: .jpg_100x100q50.jpg_.webp -> .jpg
                    src = re.sub(r'\.jpg_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)
                    # Pattern: _100x100q50.jpg_.webp -> .jpg
                    src = re.sub(r'_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)

                    # Fix other quality/size suffixes
                    src = re.sub(r'\.jpgq\d+$', '.jpg', src)  # .jpgq30 -> .jpg
                    src = re.sub(r'_90x90q30\.jpg$', '.jpg', src)  # _90x90q30.jpg -> .jpg
                    src = re.sub(r'_\d+x\d+\.jpg$', '.jpg', src)  # _100x100.jpg -> .jpg

                    # Remove size markers
                    src = src.replace('_60x60', '').replace('_50x50', '').replace('_80x80', '').replace('_90x90', '').replace('_sum', '')

                    if not any(img['url'] == src for img in thumbnail_images):
                        thumbnail_images.append({
                            'url': src,
                            'sequence': len(thumbnail_images),
                            'type': 'sku_variant'
                        })

            data['thumbnail_images'] = thumbnail_images

        except Exception as e:
            raise RuntimeError(f"Error scraping basic info: {e}")

        return data

    async def _scrape_parameters(self) -> List[Dict]:
        """Scrape product parameters from parameters tab"""
        parameters = []

        try:
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
            raise RuntimeError(f"Error scraping parameters: {e}")

        return parameters

    async def _scrape_detail_images(self) -> List[Dict]:
        """Scrape product detail images from details tab"""
        detail_images = []

        try:
            details_tab = await self.page.query_selector(
                TaobaoNavigationHelpers.get_tab_selector_by_name('details')
            )

            if not details_tab:
                return detail_images

            await details_tab.click()
            await self.page.wait_for_timeout(2000)

            try:
                await self.page.wait_for_selector(TaobaoSelectors.DESC_ROOT, timeout=10000)
            except Exception:
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

                if url and url.startswith('http'):
                    if any(placeholder in url for placeholder in ['spaceball.gif', 'tps-2-2', 'pixel.gif', 'blank.gif']):
                        continue

                    detail_images.append({
                        'url': url,
                        'sequence': idx,
                        'type': 'detail'
                    })

        except Exception as e:
            raise RuntimeError(f"Error scraping detail images: {e}")

        return detail_images

    async def _scrape_reviews(self) -> List[Dict]:
        """Scrape customer reviews from reviews tab"""
        reviews = []

        try:
            reviews_tab = await self.page.query_selector(
                TaobaoNavigationHelpers.get_tab_selector_by_name('reviews')
            )
            if reviews_tab:
                await reviews_tab.click()
                await self.page.wait_for_timeout(2000)

                await self.page.wait_for_selector(
                    TaobaoSelectors.COMMENTS_CONTAINER,
                    timeout=10000
                )

                # Scroll to load more reviews
                for i in range(5):
                    await self.page.evaluate("window.scrollBy(0, 600)")
                    await self.page.wait_for_timeout(800)

                review_items = await self.page.query_selector_all(TaobaoSelectors.REVIEW_ITEM)

                for item in review_items:
                    review_data = {}

                    username_elem = await item.query_selector(TaobaoSelectors.REVIEW_USER_NAME)
                    if username_elem:
                        review_data['username'] = await username_elem.text_content()

                    content_elem = await item.query_selector(TaobaoSelectors.REVIEW_CONTENT)
                    if content_elem:
                        review_data['review_text'] = await content_elem.text_content()

                    meta_elem = await item.query_selector(TaobaoSelectors.REVIEW_META)
                    if meta_elem:
                        meta_text = await meta_elem.text_content()
                        parts = meta_text.split('·')
                        if len(parts) >= 1:
                            review_data['review_date'] = parts[0].strip()
                        if len(parts) >= 2:
                            review_data['product_variant'] = parts[1].strip()

                    photo_elems = await item.query_selector_all(
                        f"{TaobaoSelectors.REVIEW_PHOTO} img"
                    )
                    photos = []
                    for photo in photo_elems:
                        src = await photo.get_attribute('src')
                        if not src:
                            src = await photo.get_attribute('data-src')

                        if src and src.startswith('http'):
                            src = src.split('?')[0]
                            src = re.sub(r'\.jpg_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)
                            src = re.sub(r'_\d+x\d+q?\d*\.jpg_\.webp$', '.jpg', src)
                            src = re.sub(r'_\d+x\d+\.jpg$', '', src)
                            src = src.replace('_60x60', '').replace('_80x80', '').replace('_90x90', '').replace('_sum', '')

                            if not any(placeholder in src for placeholder in ['spaceball.gif', 'tps-2-2', 'pixel.gif']):
                                photos.append(src)

                    review_data['photos'] = photos
                    reviews.append(review_data)

        except Exception as e:
            raise RuntimeError(f"Error scraping reviews: {e}")

        return reviews

    async def _scrape_qa(self) -> List[Dict]:
        """Scrape Q&A section"""
        qa_items = []

        try:
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

    async def _scrape_shipping_info(self) -> Dict:
        """Scrape shipping information"""
        shipping_info = {}

        try:
            # Shipping time
            shipping_time_elem = await self.page.query_selector(TaobaoSelectors.SHIPPING_TIME)
            if shipping_time_elem:
                shipping_info['time'] = await shipping_time_elem.text_content()

            # Shipping fee
            shipping_fee_elem = await self.page.query_selector(TaobaoSelectors.SHIPPING_FEE)
            if shipping_fee_elem:
                shipping_info['fee'] = await shipping_fee_elem.text_content()

            # Shipping locations (from and to)
            location_elem = await self.page.query_selector(TaobaoSelectors.SHIPPING_LOCATION)
            if location_elem:
                location_text = await location_elem.text_content()
                # Parse "浙江宁波 至 绵阳市 涪城区"
                if ' 至 ' in location_text:
                    parts = location_text.split(' 至 ')
                    shipping_info['from_location'] = parts[0].strip()
                    shipping_info['to_location'] = parts[1].strip() if len(parts) > 1 else ''
                else:
                    shipping_info['location_text'] = location_text.strip()

        except Exception:
            pass

        return shipping_info

    async def _scrape_shop_details(self) -> Dict:
        """Scrape shop details including ratings"""
        shop_details = {}

        try:
            # Shop name
            shop_name_elem = await self.page.query_selector(TaobaoSelectors.SHOP_NAME)
            if shop_name_elem:
                shop_details['name'] = await shop_name_elem.text_content()

            # Shop link
            shop_link_elem = await self.page.query_selector(TaobaoSelectors.SHOP_LINK)
            if shop_link_elem:
                href = await shop_link_elem.get_attribute('href')
                if href:
                    shop_details['link'] = href

            # Overall rating
            rating_elem = await self.page.query_selector(TaobaoSelectors.SHOP_RATING)
            if rating_elem:
                shop_details['overall_rating'] = await rating_elem.text_content()

            # Detailed ratings (good rate, shipping speed, service satisfaction)
            label_items = await self.page.query_selector_all(TaobaoSelectors.SHOP_LABEL_ITEM)
            if label_items:
                ratings = []
                for item in label_items:
                    text = await item.text_content()
                    if text:
                        ratings.append(text.strip())

                if len(ratings) >= 3:
                    shop_details['good_rate'] = ratings[0]
                    shop_details['shipping_speed'] = ratings[1]
                    shop_details['service_satisfaction'] = ratings[2]
                elif ratings:
                    shop_details['ratings'] = ratings

        except Exception:
            pass

        return shop_details

    async def _scrape_guarantees(self) -> List[str]:
        """Scrape guarantee tags"""
        guarantees = []

        try:
            guarantee_elems = await self.page.query_selector_all(TaobaoSelectors.GUARANTEE_TEXT)
            for elem in guarantee_elems:
                text = await elem.text_content()
                if text:
                    guarantees.append(text.strip())

            # Check for invoice availability
            page_content = await self.page.content()
            can_invoice = '可开发票' in page_content

            if can_invoice and '可开发票' not in guarantees:
                guarantees.insert(0, '可开发票')

        except Exception:
            pass

        return guarantees

    async def _scrape_specifications(self) -> Dict:
        """Scrape product specifications (colors, sizes, stock status) and SKU variant images"""
        specifications = {
            'colors': [],
            'sizes': [],
            'stock_status': '',
            'sku_images': []  # NEW: Images for color/variant selection
        }

        try:
            # Find all SKU items (颜色, 尺码, etc.)
            sku_items = await self.page.query_selector_all(TaobaoSelectors.SKU_ITEM)

            for sku_item in sku_items:
                # Get label (颜色, 尺码)
                label_elem = await sku_item.query_selector(TaobaoSelectors.SKU_LABEL)
                if not label_elem:
                    continue

                label_text = await label_elem.text_content()
                if not label_text:
                    continue

                label = label_text.strip()

                # Get all values for this SKU
                value_items = await sku_item.query_selector_all(TaobaoSelectors.SKU_VALUE_ITEM)

                values = []
                for value_item in value_items:
                    # Extract text from the value item
                    value_text = await value_item.text_content()
                    if value_text:
                        values.append(value_text.strip())

                # Categorize based on label
                if '颜色' in label or 'color' in label.lower():
                    specifications['colors'] = values
                elif '尺码' in label or 'size' in label.lower():
                    specifications['sizes'] = values
                else:
                    # Store other specifications
                    specifications[label] = values

            # Extract SKU variant images (color/style selection thumbnails)
            sku_image_items = await self.page.query_selector_all(f"{TaobaoSelectors.SKU_VALUE_IMAGE_WRAP} img")
            for idx, img_elem in enumerate(sku_image_items):
                src = await img_elem.get_attribute('src')
                if not src:
                    src = await img_elem.get_attribute('data-src')
                if not src:
                    src = await img_elem.get_attribute('data-ks-lazyload')

                if src and src.startswith('http'):
                    # Clean up image URL
                    src = src.split('?')[0]
                    src = re.sub(r'_q\d+\.jpg_\.webp$', '.jpg', src)
                    src = re.sub(r'\.jpg_\.webp$', '.jpg', src)
                    src = src.replace('_60x60', '').replace('_50x50', '').replace('_80x80', '')

                    # Avoid duplicates
                    if not any(img['url'] == src for img in specifications['sku_images']):
                        specifications['sku_images'].append({
                            'url': src,
                            'sequence': idx,
                            'type': 'sku_variant'
                        })

            # Stock status
            stock_elem = await self.page.query_selector(TaobaoSelectors.STOCK_STATUS)
            if stock_elem:
                specifications['stock_status'] = await stock_elem.text_content()

        except Exception:
            pass

        return specifications
