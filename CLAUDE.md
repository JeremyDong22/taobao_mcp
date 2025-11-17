# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Taobao Agent project - a comprehensive Taobao/Tmall product information scraper with both standalone and MCP server implementations.

## Project Structure

```
taobao-agent/
├── taobao_scraper/             # Standalone scraper module
│   ├── scrape_to_markdown.py   # Main scraper script (900+ lines)
│   ├── user_data/              # Browser profile and authentication state
│   ├── product_info/           # Output: generated Markdown product files
│   ├── knowledge/              # Technical documentation
│   └── CLAUDE.md               # Detailed scraper documentation
│
└── taobao_mcp/                 # MCP (Model Context Protocol) server
    ├── server.py               # MCP server implementation
    ├── taobao_scraper.py       # Core scraper logic for MCP
    ├── image_fetcher.py        # Image handling utilities
    ├── pyproject.toml          # Python package configuration
    └── README.md               # MCP server usage instructions
```

## Components

### taobao_scraper
Standalone Python script for scraping Taobao/Tmall product information to Markdown files. Uses Playwright for browser automation with persistent login sessions. See `taobao_scraper/CLAUDE.md` for detailed documentation.

**Usage:**
```bash
cd taobao_scraper
python3 scrape_to_markdown.py "【淘宝】product link"
```

### taobao_mcp
MCP server that exposes Taobao scraping functionality to Claude Code and other AI assistants. Allows Claude to fetch and analyze Taobao product information on demand.

**Usage:**
Configure in Claude Code MCP settings, then use tools:
- `taobao_initialize_login`: Set up browser session
- `taobao_fetch_product_info`: Scrape product data

## Development Guidelines

- Both modules share similar scraping logic but serve different use cases
- Standalone scraper outputs to files, MCP server returns structured data
- Browser session management is handled independently in each module
- See individual CLAUDE.md files in each folder for module-specific guidance
