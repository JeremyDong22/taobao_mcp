# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Taobao MCP Server - an MCP (Model Context Protocol) server that exposes Taobao/Tmall product information scraping functionality to Claude Code and other AI assistants.

## Project Structure

```
taobao_mcp/
├── server.py               # MCP server implementation
├── taobao_scraper.py       # Core scraper logic with Playwright automation
├── image_utils.py          # Image download and processing utilities
├── unified_fetcher.py      # Unified product fetching interface
├── pyproject.toml          # Python package configuration
├── README.md               # Detailed usage instructions
├── USAGE.txt               # Quick reference guide
└── __init__.py             # Package initialization
```

## Core Components

### server.py
MCP server implementation that exposes tools for:
- Browser session initialization and login management
- Product information scraping from Taobao/Tmall URLs
- Returns structured product data to AI assistants

### taobao_scraper.py
Core scraping logic using Playwright for browser automation:
- Handles Taobao/Tmall product page scraping
- Manages persistent browser sessions with login state
- Extracts product details, pricing, images, and reviews

### image_utils.py
Image handling utilities for:
- Downloading product images
- Converting images to base64 encoding
- Image processing and optimization

### unified_fetcher.py
Unified interface for fetching product information from various sources

## Usage

Configure in Claude Code MCP settings (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "taobao": {
      "command": "uv",
      "args": ["--directory", "/path/to/taobao_mcp", "run", "taobao-mcp"]
    }
  }
}
```

Available MCP tools:
- `taobao_initialize_login`: Set up browser session and handle authentication
- `taobao_fetch_product_info`: Scrape product data from Taobao/Tmall URLs

## Development Guidelines

- Uses Playwright for reliable browser automation
- Persistent browser sessions to maintain login state
- Returns structured JSON data for AI consumption
- See README.md for detailed setup and usage instructions
