#!/usr/bin/env python3
"""
Version: 4.1
Created: 2025-11-17
Updated: 2025-11-17

Taobao MCP Server - Model Context Protocol server for Taobao product scraping.

Changes in v4.1:
- ✅ CRITICAL UX FIX: Updated tool description to force agent to auto-fetch all pages
- ✅ Added explicit instructions: "DO NOT ask user if they want more - fetch everything"
- ✅ Added workflow examples showing correct vs incorrect behavior
- ✅ User feedback: "User shouldn't be asked if they want page 2 - just fetch everything"

Changes in v4.0:
- ✅ SIMPLIFIED: Reduced from 6 tools to 2 tools for better UX
- ✅ NEW: Unified tool that fetches ALL product info and images at once
- ✅ IMPROVED: Images are labeled by type (gallery, detail, sku, review)
- ✅ KEPT: Pagination support (offset/limit) to avoid token limits
- ✅ REMOVED: Split image_fetchers approach (was confusing for users)

Tools:
1. taobao_initialize_login - Initialize browser session and handle login
2. taobao_fetch_product - Get ALL product info and images with pagination (auto-loops)

This server maintains a persistent browser session for efficient scraping.
All images are fetched together and labeled by type for clarity.
"""

import asyncio
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
)

# Local imports
from taobao_scraper import TaobaoScraper
from unified_fetcher import fetch_product_with_images


# ==================== CONFIGURATION ====================

# Product cache TTL (30 minutes)
PRODUCT_CACHE_TTL_MINUTES = 30


# ==================== PRODUCT CACHE ====================

class ProductCache:
    """Simple in-memory cache for scraped product data."""

    def __init__(self, ttl_minutes: int = PRODUCT_CACHE_TTL_MINUTES):
        self.cache = {}  # {product_id: {'data': dict, 'timestamp': datetime}}
        self.ttl = timedelta(minutes=ttl_minutes)

    def get(self, product_id: str) -> Optional[dict]:
        """Get cached product data if still valid."""
        if product_id in self.cache:
            entry = self.cache[product_id]
            if datetime.now() - entry['timestamp'] < self.ttl:
                print(f"[Cache] HIT for product {product_id}")
                return entry['data']
            else:
                print(f"[Cache] EXPIRED for product {product_id}")
                del self.cache[product_id]
        print(f"[Cache] MISS for product {product_id}")
        return None

    def set(self, product_id: str, data: dict):
        """Cache product data."""
        self.cache[product_id] = {
            'data': data,
            'timestamp': datetime.now()
        }
        print(f"[Cache] SET for product {product_id}")

    def clear(self):
        """Clear all cached data."""
        self.cache.clear()
        print("[Cache] CLEARED")


# ==================== PYDANTIC MODELS ====================

class ProductInputBase(BaseModel):
    """Base model for product input validation."""

    product_url_or_id: str = Field(
        ...,
        description=(
            "Product identifier in any of these formats:\n"
            "- Product ID (12-13 digits): '881280651752'\n"
            "- Direct URL: 'https://detail.tmall.com/item.htm?id=881280651752'\n"
            "- Short link: 'https://e.tb.cn/h.xxx'\n"
            "- Share text: '【淘宝】product https://e.tb.cn/h.xxx'"
        ),
        min_length=1,
        max_length=500
    )

    @field_validator('product_url_or_id')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure product_url_or_id is not empty or whitespace"""
        if not v or not v.strip():
            raise ValueError("product_url_or_id cannot be empty")
        return v.strip()


# ==================== MCP SERVER ====================

# Global instances
scraper: Optional[TaobaoScraper] = None
product_cache = ProductCache()

# Create MCP server
mcp_server = Server("taobao-mcp")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for the MCP server."""

    return [
        # Tool 1: Initialize Login
        Tool(
            name="taobao_initialize_login",
            description=(
                "**REQUIRED FIRST STEP** - Initialize Taobao/Tmall browser session and handle login.\n\n"
                "**When to use**: Before calling any other taobao_fetch_* tools.\n\n"
                "**What it does**:\n"
                "1. Launches persistent browser with saved credentials\n"
                "2. Tests authentication status\n"
                "3. Handles QR code login if needed\n"
                "4. Maintains session for all future scraping\n\n"
                "**Only needs to be called ONCE per session.**"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # Tool 2: Fetch Product (Unified)
        Tool(
            name="taobao_fetch_product",
            description=(
                "**🛍️ GET ALL PRODUCT INFO** - Fetch complete product information and ALL images with pagination.\n\n"
                "**⚠️ CRITICAL: AUTO-FETCH ALL PAGES**\n"
                "When user asks about a product, you MUST automatically fetch ALL images across ALL pages. "
                "Keep calling this tool with next_offset until has_more=False. "
                "DO NOT ask user \"do you want to see more images?\" - just fetch everything automatically in one conversation turn. "
                "The user expects to see the complete product information, not partial data.\n\n"
                "**Returns** (~10000-15000 tokens per page):\n"
                "- Product title, price, store name, product ID\n"
                "- Product parameters/specifications table\n"
                "- ALL images from ALL categories (labeled by type):\n"
                "  - 📸 Gallery: Main product photos from different angles\n"
                "  - 🔍 Detail: Specifications, features, advertising materials\n"
                "  - 🎨 SKU: Color/style variant thumbnails\n"
                "  - ⭐ Review: Customer-uploaded real-world photos\n"
                "- Pagination metadata (total_count, has_more, next_offset)\n\n"
                "**Pagination** (internal detail for you, transparent to user):\n"
                "- Default: 10 images per call (offset=0, limit=10)\n"
                "- Max: 20 images per call\n"
                "- First call returns basic info + first page of images\n"
                "- KEEP CALLING with next_offset until has_more=False\n"
                "- Response includes 'has_more' and 'next_offset' for navigation\n\n"
                "**Image Type Labels**:\n"
                "Each image is clearly labeled with its type (gallery/detail/sku/review) "
                "so you understand what category it belongs to.\n\n"
                "**Required Workflow**:\n"
                "1. Call with offset=0 → Get first 10 images\n"
                "2. If has_more=True, immediately call with offset=next_offset (NO user prompt needed)\n"
                "3. Repeat step 2 until has_more=False\n"
                "4. Only then provide your analysis to user with all images\n\n"
                "**Example of correct behavior**:\n"
                "User: \"Analyze this product: <url>\"\n"
                "You: [Call offset=0] → has_more=True, next_offset=10\n"
                "You: [Call offset=10] → has_more=True, next_offset=20\n"
                "You: [Call offset=20] → has_more=False\n"
                "You: \"Here's my analysis of the product with all 31 images...\"\n\n"
                "**WRONG behavior** (DO NOT DO THIS):\n"
                "User: \"Analyze this product\"\n"
                "You: [Call offset=0]\n"
                "You: \"I fetched 10/31 images. Would you like me to fetch more?\"\n"
                "❌ This is bad UX! Fetch everything automatically!"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "product_url_or_id": {
                        "type": "string",
                        "description": (
                            "Product URL, short link, share text, or product ID. "
                            "Examples: '881280651752', 'https://detail.tmall.com/item.htm?id=123', "
                            "'【淘宝】product https://e.tb.cn/h.xxx'"
                        )
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Starting index for pagination (default: 0)",
                        "default": 0,
                        "minimum": 0
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of images to return (default: 10, max: 20)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["product_url_or_id"]
            }
        ),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    """Handle tool execution requests."""
    global scraper

    # Route to appropriate handler
    if name == "taobao_initialize_login":
        return await handle_initialize_login()
    elif name == "taobao_fetch_product":
        return await handle_fetch_product(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


# ==================== TOOL HANDLERS ====================

async def handle_initialize_login() -> list[TextContent]:
    """Handle initialize_login tool execution."""
    global scraper

    try:
        # Create scraper if not exists
        if scraper is None:
            scraper = TaobaoScraper(profile_dir="user_data/chrome_profile")

        # Initialize browser
        result = await scraper.initialize()

        status = result.get('status', 'unknown')
        message = result.get('message', 'No message')

        if status == 'login_required':
            response_text = (
                f"**Status**: {status}\n\n"
                f"{message}\n\n"
                "Please complete the login in the browser window. "
                "The browser will remain open for 3 minutes.\n\n"
                "After logging in, you can proceed to use other tools."
            )
            return [TextContent(type="text", text=response_text)]

        elif status == 'success':
            response_text = (
                f"**Status**: ✅ {status}\n\n"
                f"{message}\n\n"
                "✅ **Ready to scrape!** You can now call:\n"
                "1. `taobao_fetch_product_basic` (recommended first)\n"
                "2. Then call image tools in parallel as needed"
            )
            return [TextContent(type="text", text=response_text)]

        elif status == 'already_initialized':
            response_text = (
                f"**Status**: ℹ️ {status}\n\n"
                f"{message}\n\n"
                "Browser session is active. You can continue using other tools."
            )
            return [TextContent(type="text", text=response_text)]

        else:
            response_text = (
                f"**Status**: ⚠️ {status}\n\n"
                f"{message}"
            )
            return [TextContent(type="text", text=response_text)]

    except Exception as e:
        error_text = (
            f"**Error during initialization**\n\n"
            f"Failed to initialize browser session.\n\n"
            f"**Error details**: {str(e)}\n\n"
            f"**Troubleshooting**:\n"
            f"- Ensure Playwright browsers are installed: `playwright install chromium`\n"
            f"- Check that the user_data directory is writable\n"
            f"- Verify no other browser instances are using the profile"
        )
        return [TextContent(type="text", text=error_text)]


async def _get_or_scrape_product(product_input: str) -> dict:
    """Get product data from cache or scrape if not cached."""
    global scraper

    # Check if browser is initialized
    if scraper is None or not scraper._is_initialized:
        raise RuntimeError(
            "Browser not initialized. Please call `taobao_initialize_login` first."
        )

    # Always scrape fresh data for now (cache disabled to ensure latest URL cleaning logic)
    # TODO: Re-enable cache after URL cleaning is stable
    print(f"[Scraper] Fetching fresh product data...")
    product_data = await scraper.scrape_product(product_input)

    product_id = product_data.get('product_id')
    if not product_id:
        raise ValueError("Failed to extract product ID from scraped data")

    # Update cache with fresh data
    product_cache.set(product_id, product_data)

    return product_data


async def handle_fetch_product(arguments: dict) -> list[TextContent | ImageContent]:
    """Handle fetch_product tool execution (unified fetcher with pagination)."""
    try:
        # Validate input
        input_data = ProductInputBase(**arguments)
        product_input = input_data.product_url_or_id

        # Extract pagination parameters
        offset = arguments.get('offset', 0)
        limit = arguments.get('limit', 10)

        # Get or scrape product
        product_data = await _get_or_scrape_product(product_input)

        # Fetch all product info and images with pagination
        return await fetch_product_with_images(
            product_data,
            offset=offset,
            limit=limit,
            include_preview=True
        )

    except ValueError as e:
        return [TextContent(type="text", text=f"**Error**: {str(e)}")]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"**Error**: {str(e)}")]
    except Exception as e:
        return [TextContent(type="text", text=f"**Unexpected error**: {str(e)}")]


# ==================== MAIN ====================

async def main():
    """Main entry point for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options()
        )


async def cleanup():
    """Clean up resources on server shutdown"""
    global scraper
    if scraper:
        await scraper.close()
    product_cache.clear()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        # Run cleanup
        if scraper:
            asyncio.run(cleanup())
