#!/usr/bin/env python3
"""
Version: 1.0
Created: 2025-11-17

Taobao MCP Server - Model Context Protocol server for Taobao product scraping.

Provides two main tools:
1. initialize_login - Initialize browser session and handle Taobao login
2. fetch_product_info - Scrape product information and return as Markdown

This server maintains a persistent browser session for efficient scraping.
"""

import asyncio
from typing import Optional
from pydantic import BaseModel, Field, field_validator

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Local imports
from taobao_scraper import TaobaoScraper, generate_markdown


# ==================== PYDANTIC MODELS ====================

class FetchProductInfoInput(BaseModel):
    """
    Input schema for fetch_product_info tool.

    Accepts various formats:
    - Product ID: "881280651752"
    - Direct URL: "https://detail.tmall.com/item.htm?id=881280651752"
    - Short link: "https://e.tb.cn/h.xxx"
    - Share text: "【淘宝】product name https://e.tb.cn/h.xxx"
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "product_url_or_id": "881280651752"
                },
                {
                    "product_url_or_id": "https://detail.tmall.com/item.htm?id=881280651752"
                },
                {
                    "product_url_or_id": "【淘宝】product https://e.tb.cn/h.StvCjJlWxkNatsx?tk=xxx"
                }
            ]
        }
    }

    product_url_or_id: str = Field(
        ...,
        description=(
            "Product identifier in any of these formats:\n"
            "- Product ID (12-13 digits): '881280651752'\n"
            "- Direct URL: 'https://detail.tmall.com/item.htm?id=881280651752'\n"
            "- Short link: 'https://e.tb.cn/h.xxx'\n"
            "- Share text containing any of the above formats"
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

# Global scraper instance (persists across tool calls)
scraper: Optional[TaobaoScraper] = None

# Create MCP server
mcp_server = Server("taobao-mcp")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available tools for the MCP server.

    Returns:
        List of Tool objects describing available operations
    """
    return [
        Tool(
            name="taobao_initialize_login",
            description=(
                "**REQUIRED FIRST STEP** - Initialize Taobao/Tmall (淘宝/天猫) browser session and handle login authentication.\n\n"
                "**Keywords**: Taobao, 淘宝, Tmall, 天猫, login, initialize, setup, authentication, QR code, 登录, 初始化\n\n"
                "**When to use**:\n"
                "- User mentions Taobao (淘宝), Tmall (天猫), or Chinese e-commerce\n"
                "- User provides a Taobao/Tmall product link or share text\n"
                "- User wants to scrape, analyze, or research Taobao products\n"
                "- MUST be called BEFORE taobao_fetch_product_info\n\n"
                "**What this tool does**:\n"
                "1. Launches a persistent browser with saved login credentials\n"
                "2. Navigates to Taobao homepage to test authentication\n"
                "3. Detects if Taobao requires login (QR code scan 扫码登录)\n"
                "4. Waits for user to complete login if needed\n"
                "5. Saves the authenticated session for all future scraping\n\n"
                "**Important notes**:\n"
                "- Only needs to be called ONCE per session\n"
                "- Browser window remains open to maintain the session\n"
                "- If login required, user scans QR code in browser window\n"
                "- Session persists across multiple product fetches\n"
                "- NO parameters needed - just call it\n\n"
                "**Returns**:\n"
                "- status: 'success', 'login_required', 'already_initialized', or 'error'\n"
                "- message: Detailed status and next steps\n\n"
                "**Example workflow**:\n"
                "User: '帮我做一个research' + Taobao link\n"
                "Assistant: Calls taobao_initialize_login first → Then calls taobao_fetch_product_info"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="taobao_fetch_product_info",
            description=(
                "Fetch comprehensive product information from Taobao/Tmall (淘宝/天猫) and return as structured Markdown.\n\n"
                "**Keywords**: Taobao, 淘宝, Tmall, 天猫, product, 商品, scrape, research, analyze, compare, 分析, 对比, 评价, reviews\n\n"
                "**When to use**:\n"
                "- User provides Taobao/Tmall product link, share text, or product ID\n"
                "- User asks to research/analyze/compare Taobao products\n"
                "- User mentions keywords: product, 商品, reviews, 评价, price, 价格\n"
                "- User shares Chinese e-commerce links starting with e.tb.cn or detail.tmall.com\n\n"
                "**What this tool scrapes**:\n"
                "- Basic info: Title (标题), price (价格), store name (店铺), product ID\n"
                "- Images: Thumbnail images (缩略图) and detailed product images (详情图)\n"
                "- Parameters: Product specifications (参数) and attributes (属性)\n"
                "- Reviews: Customer reviews (用户评价) with ratings, text, and photos\n"
                "- Q&A: Customer questions and answers (问答)\n\n"
                "**Supported input formats** (in order of reliability):\n"
                "1. ✅ **Full share text** (RECOMMENDED): '【淘宝】假一赔四 https://e.tb.cn/h.xxx MF937 「商品名称」点击链接直接打开'\n"
                "2. ✅ **Product ID**: '881280651752'\n"
                "3. ✅ **Direct URL**: 'https://detail.tmall.com/item.htm?id=881280651752'\n"
                "4. ⚠️  **Short link alone**: 'https://e.tb.cn/h.xxx' (may fail due to anti-bot protection - use full share text instead)\n"
                "5. ✅ **Mixed text**: Any Chinese/English text containing above formats\n\n"
                "**IMPORTANT**: Short links (e.tb.cn) work best when included in full share text. Using them alone may fail due to Taobao's anti-bot protection.\n\n"
                "**Returns**:\n"
                "- Markdown-formatted product information (easy for AI to analyze)\n"
                "- Image URLs embedded as Markdown image links\n"
                "- Tables for product parameters\n"
                "- Structured reviews and Q&A sections\n"
                "- Metadata: scrape time, image counts, review counts\n\n"
                "**CRITICAL PREREQUISITE**:\n"
                "- ⚠️ MUST call taobao_initialize_login FIRST before using this tool!\n"
                "- Browser session must be initialized and logged in\n"
                "- If not initialized, returns error with clear instructions\n\n"
                "**Error handling**:\n"
                "- Not initialized → Returns error: 'Call taobao_initialize_login first'\n"
                "- Invalid link → Returns error: 'Could not extract product ID' + examples\n"
                "- Scraping failed → Returns error with detailed reason (timeout, page changed, etc.)\n\n"
                "**Example usage**:\n"
                "User: '【淘宝】product https://e.tb.cn/h.xxx'\n"
                "Assistant: Calls taobao_fetch_product_info(product_url_or_id='【淘宝】product https://e.tb.cn/h.xxx')"
            ),
            inputSchema=FetchProductInfoInput.model_json_schema()
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Handle tool execution requests.

    Args:
        name: Name of the tool to execute
        arguments: Tool-specific arguments

    Returns:
        List of TextContent objects containing the tool response

    Raises:
        ValueError: If tool name is unknown
    """
    global scraper

    if name == "taobao_initialize_login":
        return await handle_initialize_login()
    elif name == "taobao_fetch_product_info":
        return await handle_fetch_product_info(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_initialize_login() -> list[TextContent]:
    """
    Handle initialize_login tool execution.

    Initializes browser session and handles Taobao authentication.

    Returns:
        List containing TextContent with initialization status and instructions
    """
    global scraper

    try:
        # Create scraper if not exists
        if scraper is None:
            scraper = TaobaoScraper(profile_dir="../user_data/chrome_profile")

        # Initialize browser
        result = await scraper.initialize()

        status = result.get('status', 'unknown')
        message = result.get('message', 'No message')

        if status == 'login_required':
            # Wait for user to complete login (3 minutes timeout)
            response_text = (
                f"**Status**: {status}\n\n"
                f"{message}\n\n"
                "Please complete the login in the browser window. "
                "The browser will remain open for 3 minutes.\n\n"
                "After logging in, you can proceed to use fetch_product_info."
            )

            # Wait for login completion (non-blocking for MCP)
            return [TextContent(type="text", text=response_text)]

        elif status == 'success':
            response_text = (
                f"**Status**: ✅ {status}\n\n"
                f"{message}\n\n"
                "You can now use fetch_product_info to scrape products."
            )
            return [TextContent(type="text", text=response_text)]

        elif status == 'already_initialized':
            response_text = (
                f"**Status**: ℹ️ {status}\n\n"
                f"{message}\n\n"
                "Browser session is active. You can continue using fetch_product_info."
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


async def handle_fetch_product_info(arguments: dict) -> list[TextContent]:
    """
    Handle fetch_product_info tool execution.

    Scrapes product information and returns formatted Markdown.

    Args:
        arguments: Dict containing product_url_or_id

    Returns:
        List containing TextContent with Markdown-formatted product information
    """
    global scraper

    try:
        # Validate input
        input_data = FetchProductInfoInput(**arguments)
        product_input = input_data.product_url_or_id

        # Check if browser is initialized
        if scraper is None or not scraper._is_initialized:
            error_text = (
                "**Error: Browser not initialized**\n\n"
                "Please call `taobao_initialize_login` first to set up the browser session.\n\n"
                "**Steps**:\n"
                "1. Call taobao_initialize_login\n"
                "2. Complete login if required (scan QR code)\n"
                "3. Call taobao_fetch_product_info again"
            )
            return [TextContent(type="text", text=error_text)]

        # Scrape product
        product_data = await scraper.scrape_product(product_input)

        # Generate markdown
        markdown_output = generate_markdown(product_data)

        # Add metadata header
        metadata = (
            f"**Scraping completed successfully**\n\n"
            f"Product ID: {product_data.get('product_id', 'N/A')}\n"
            f"Scraped at: {product_data.get('scraped_at', 'N/A')}\n"
            f"Images found: {len(product_data.get('thumbnail_images', []))} thumbnails, "
            f"{len(product_data.get('detail_images', []))} details\n"
            f"Reviews: {len(product_data.get('reviews', []))}\n"
            f"Parameters: {len(product_data.get('parameters', []))}\n\n"
            f"---\n\n"
        )

        full_response = metadata + markdown_output

        return [TextContent(type="text", text=full_response)]

    except ValueError as e:
        # Input validation or product ID extraction error
        error_message = str(e)

        # Check if it's a short link that failed to resolve
        if "Could not extract product ID" in error_message and "e.tb.cn" in error_message:
            error_text = (
                f"**Error: Short link resolution failed**\n\n"
                f"{error_message}\n\n"
                f"**Possible causes**:\n"
                f"- Short link expired or invalid\n"
                f"- Network timeout during resolution\n"
                f"- Taobao blocked the resolution attempt\n\n"
                f"**Please try**:\n"
                f"1. Use the **full share text** (recommended): `【淘宝】product name https://e.tb.cn/h.xxx`\n"
                f"2. Get the direct product URL from browser address bar\n"
                f"3. Use just the product ID (12-13 digits)\n\n"
                f"**Accepted formats**:\n"
                f"- ✅ Full share text: '【淘宝】假一赔四 https://e.tb.cn/h.xxx MF287「产品名」'\n"
                f"- ✅ Product ID: '881280651752'\n"
                f"- ✅ Direct URL: 'https://detail.tmall.com/item.htm?id=881280651752'\n"
                f"- ⚠️  Short link alone: 'https://e.tb.cn/h.xxx' (may fail due to anti-bot protection)"
            )
        else:
            error_text = (
                f"**Error: Invalid input**\n\n"
                f"{error_message}\n\n"
                f"**Accepted formats**:\n"
                f"- Product ID: '881280651752'\n"
                f"- Direct URL: 'https://detail.tmall.com/item.htm?id=881280651752'\n"
                f"- Short link: 'https://e.tb.cn/h.xxx'\n"
                f"- Share text: '【淘宝】product https://e.tb.cn/h.xxx'"
            )
        return [TextContent(type="text", text=error_text)]

    except RuntimeError as e:
        # Scraping error (login required, timeout, etc.)
        error_text = (
            f"**Error during scraping**\n\n"
            f"{str(e)}\n\n"
            f"**Possible causes**:\n"
            f"- Login session expired - try calling taobao_initialize_login again\n"
            f"- Network timeout - check internet connection\n"
            f"- Page structure changed - scraper may need updates\n"
            f"- Product page unavailable or removed"
        )
        return [TextContent(type="text", text=error_text)]

    except Exception as e:
        # Unexpected error
        error_text = (
            f"**Unexpected error**\n\n"
            f"An unexpected error occurred while fetching product information.\n\n"
            f"**Error details**: {str(e)}\n\n"
            f"**Please try**:\n"
            f"- Restarting the MCP server\n"
            f"- Calling taobao_initialize_login again\n"
            f"- Verifying the product URL or ID is correct"
        )
        return [TextContent(type="text", text=error_text)]


async def main():
    """
    Main entry point for the MCP server.

    Starts the server and handles stdio communication.
    """
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options()
        )


# Cleanup on exit
async def cleanup():
    """Clean up resources on server shutdown"""
    global scraper
    if scraper:
        await scraper.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        # Run cleanup
        if scraper:
            asyncio.run(cleanup())
