# Taobao MCP Server

**Model Context Protocol (MCP) server for scraping Taobao/Tmall (淘宝/天猫) product information.**

This MCP server enables AI assistants to fetch comprehensive product data from Taobao and Tmall, including product details, images, specifications, customer reviews, and Q&A sections. Perfect for product research, comparison, and analysis.

---

## 🌟 Features

- **Automatic Link Detection**: Recognizes Taobao/Tmall links in Chinese share text
- **Multiple Input Formats**: Supports product IDs, direct URLs, short links, and share text
- **Comprehensive Data**: Scrapes titles, prices, images, specs, reviews, and Q&A
- **Persistent Sessions**: Browser session remains logged in across multiple requests
- **Bilingual Support**: Handles both English and Chinese (中文) input/output
- **Markdown Output**: Returns structured, AI-friendly Markdown format

---

## 📦 What Gets Scraped

For each product, this MCP server extracts:

| Data Type | Details |
|-----------|---------|
| **Basic Info** | Title (标题), Price (价格), Store Name (店铺), Product ID |
| **Images** | Thumbnail images (缩略图) + Detailed product images (详情图) |
| **Parameters** | Product specifications (参数) and attributes (属性) |
| **Reviews** | Customer reviews (用户评价) with text, ratings, and photos |
| **Q&A** | Customer questions and seller answers (问答) |

---

## 🚀 Installation

### Prerequisites

- Python 3.10 or higher
- `uv` package manager (or regular `pip`)
- Chromium browser (installed automatically by Playwright)

### Step 1: Install Dependencies

```bash
cd taobao_mcp
uv pip install -e .
# OR
pip install -e .
```

### Step 2: Install Playwright Browser

```bash
playwright install chromium
```

### Step 3: Configure MCP Server

Create or edit the MCP configuration file:

#### For Claude Code CLI

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "taobao-scraper": {
      "command": "python3",
      "args": [
        "/absolute/path/to/taobao_mcp/server.py"
      ],
      "env": {}
    }
  }
}
```

**Replace `/absolute/path/to/` with the actual path to this directory!**

#### For Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "taobao-scraper": {
      "command": "python3",
      "args": [
        "/absolute/path/to/taobao_mcp/server.py"
      ]
    }
  }
}
```

### Step 4: Restart Your AI Assistant

- **Claude Code CLI**: Start a new conversation or reload
- **Claude Desktop**: Restart the application

---

## 🎯 Usage Workflow

### Step 1: Initialize Login (REQUIRED FIRST)

Before scraping any products, you **MUST** initialize the browser session:

```
User: "Initialize Taobao login"
AI: [Calls taobao_initialize_login]
```

The AI will:
1. Launch a Chrome browser window
2. Navigate to Taobao homepage
3. Check if login is required
4. If login needed: Wait for you to scan the QR code (扫码登录)
5. Save the session for future use

**This only needs to be done ONCE per session!**

### Step 2: Fetch Product Information

After initialization, you can fetch products using any of these formats:

```
User: "【淘宝】假一赔四 https://e.tb.cn/h.StvCjJlWxkNatsx?tk=xxx MF937 「UBV美式休闲空气层棉...」"
AI: [Calls taobao_fetch_product_info with the full text]
```

```
User: "Analyze this product: https://detail.tmall.com/item.htm?id=881280651752"
AI: [Calls taobao_fetch_product_info with the URL]
```

```
User: "Research product 881280651752"
AI: [Calls taobao_fetch_product_info with the ID]
```

The AI will automatically:
- Extract the product ID/URL from your message
- Navigate to the product page
- Scrape all available information
- Return structured Markdown

---

## 🔧 Available Tools

### 1. `taobao_initialize_login`

**Purpose**: Initialize browser session and handle Taobao authentication

**Parameters**: None

**When to call**:
- User mentions Taobao (淘宝), Tmall (天猫), or provides a product link
- MUST be called BEFORE `taobao_fetch_product_info`
- Only needs to be called ONCE per session

**Returns**:
- Status: `success`, `login_required`, `already_initialized`, or `error`
- Message with next steps

**Example**:
```
User: "帮我做一个research" + Taobao link
AI: → Calls taobao_initialize_login first
```

### 2. `taobao_fetch_product_info`

**Purpose**: Scrape comprehensive product information and return as Markdown

**Parameters**:
- `product_url_or_id` (string): Product ID, URL, short link, or share text

**Supported formats**:
- Product ID: `"881280651752"`
- Direct URL: `"https://detail.tmall.com/item.htm?id=881280651752"`
- Short link: `"https://e.tb.cn/h.StvCjJlWxkNatsx?tk=xxx"`
- Share text: `"【淘宝】假一赔四 https://e.tb.cn/h.xxx MF937 「商品名称」"`

**Returns**:
- Markdown-formatted product information
- Includes metadata (scrape time, image counts, review counts)
- Image URLs as Markdown image links
- Parameter tables
- Structured reviews and Q&A

**Example**:
```
User: "【淘宝】product https://e.tb.cn/h.xxx"
AI: → Calls taobao_fetch_product_info(product_url_or_id='【淘宝】product https://e.tb.cn/h.xxx')
```

---

## 🤖 How AI Assistants Will Use This

### Automatic Detection

When you mention Taobao-related keywords or provide links, the AI will automatically:

**Trigger Keywords** (English):
- Taobao, Tmall, product, scrape, research, analyze, compare, reviews

**Trigger Keywords** (Chinese):
- 淘宝, 天猫, 商品, 分析, 对比, 评价, 价格

**Trigger Patterns**:
- URLs starting with `https://e.tb.cn/`
- URLs containing `detail.tmall.com` or `item.taobao.com`
- Share text like `【淘宝】...`

### Example Conversations

**Scenario 1: Research Request**
```
User: "帮我做一个research" + [Taobao link]

AI思考:
1. User wants to research a Taobao product
2. Need to initialize first (if not already done)
3. Then fetch the product info

AI执行:
→ taobao_initialize_login()
→ taobao_fetch_product_info(product_url_or_id='[link]')
→ Analyzes the returned Markdown and presents insights
```

**Scenario 2: Product Comparison**
```
User: "Compare these two products: [link1] and [link2]"

AI执行:
→ taobao_initialize_login() (if needed)
→ taobao_fetch_product_info([link1])
→ taobao_fetch_product_info([link2])
→ Compares prices, specs, reviews, etc.
```

**Scenario 3: User Doesn't Know About MCP**
```
User: "Can you help me browse Taobao?"

AI:
"I can help you research Taobao products! I have access to a Taobao scraping tool.

First, I need to initialize the browser session. This will open a browser window where you may need to scan a QR code if login is required.

Let me start the initialization..."

→ taobao_initialize_login()
```

---

## ⚠️ Important Notes

### Prerequisites

1. **ALWAYS call `taobao_initialize_login` first**
   - This is mandatory before any product scraping
   - The AI should do this automatically when detecting Taobao content

2. **Browser must remain open**
   - The browser window will stay open to maintain the session
   - Don't close it manually during scraping

3. **QR Code Login**
   - If Taobao requires login, scan the QR code in the browser window
   - Use the Taobao mobile app to scan
   - Session will be saved for future use

### Data Freshness

- Scrapes live data from Taobao/Tmall
- Reviews and prices are current as of scrape time
- Scraped data is returned immediately (not cached)

### Limitations

- Only works with public product pages
- Some products may require login to view full details
- Rate limiting may apply for too many requests in short time
- Page structure changes may require updates to selectors

---

## 🐛 Troubleshooting

### Error: "Browser not initialized"

**Cause**: Trying to fetch product before initializing

**Solution**:
```
AI should call: taobao_initialize_login()
```

### Error: "Could not extract product ID"

**Cause**: Invalid product link or ID format

**Solution**: Verify the input format matches one of:
- Product ID (12-13 digits): `881280651752`
- Direct URL: `https://detail.tmall.com/item.htm?id=881280651752`
- Short link: `https://e.tb.cn/h.xxx`
- Share text containing the above

### Error: "Login required"

**Cause**: Session expired or not logged in

**Solution**:
1. Call `taobao_initialize_login` again
2. Scan QR code in browser if prompted
3. Retry fetching the product

### Browser Doesn't Open

**Cause**: Playwright browser not installed or permission issues

**Solution**:
```bash
playwright install chromium
# Verify installation
python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); browser = p.chromium.launch(); print('✓ OK'); browser.close(); p.stop()"
```

### Short Link Resolution Fails

**Cause**: Network issues or invalid short link

**Solution**: Try using the direct product URL or ID instead

### MCP Server Connection Failed (Claude Code)

**Symptoms**:
- MCP server shows as "failed" in `/mcp` management panel
- Error in logs: `"No such file or directory (os error 2)"`
- Logs location: `/Users/yourusername/Library/Caches/claude-cli-nodejs/-Users-yourusername-Desktop-test/mcp-logs-taobao-scraper/`

**Common Causes**:
1. **Incorrect path in `.mcp.json`**: The configuration file may have wrong directory paths
2. **Using wrong Python interpreter**: Not using the virtual environment's Python
3. **Double-nested directories**: Path like `/path/to/taobao_mcp/taobao_mcp` (incorrect)

**Solution**:

1. **Check your `.mcp.json` configuration** (located in your project root):
   ```json
   {
     "mcpServers": {
       "taobao-scraper": {
         "command": "/absolute/path/to/taobao_mcp/.venv/bin/python",
         "args": [
           "/absolute/path/to/taobao_mcp/server.py"
         ],
         "env": {}
       }
     }
   }
   ```

2. **Verify paths are correct**:
   ```bash
   # Check Python exists
   ls -la /path/to/taobao_mcp/.venv/bin/python

   # Check server.py exists
   ls -la /path/to/taobao_mcp/server.py

   # Test server can start
   /path/to/taobao_mcp/.venv/bin/python /path/to/taobao_mcp/server.py <<< '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
   ```

3. **Common mistakes to avoid**:
   - ❌ Using `python3` instead of full path to venv Python
   - ❌ Path like `/path/to/taobao_mcp/taobao_mcp/server.py` (double directory)
   - ❌ Relative paths like `./server.py` (use absolute paths)
   - ✅ Correct: Full absolute paths to both Python and server.py

4. **After fixing, restart Claude Code** to reload the MCP server

**Debug Tips**:
- Run `claude --debug` to see detailed logs
- Check log files in `~/Library/Caches/claude-cli-nodejs/`
- Look for the most recent log file in the `mcp-logs-taobao-scraper/` directory

---

## 📂 File Structure

```
taobao_mcp/
├── README.md              # This file (comprehensive documentation)
├── server.py              # Main MCP server with tool registration
├── taobao_scraper.py      # Core scraping logic and browser automation
├── pyproject.toml         # Python dependencies
├── USAGE.txt              # Quick reference guide
└── .venv/                 # Virtual environment (created during install)
```

---

## 🔄 Update & Maintenance

### Updating the MCP Server

```bash
cd taobao_mcp
git pull  # If using git
uv pip install -e . --force-reinstall
```

### Clearing Browser Cache

If experiencing issues, clear the browser profile:

```bash
rm -rf ../user_data/chrome_profile
```

Then re-initialize and login again.

### Version Information

- **Current Version**: 1.2
- **Last Updated**: 2025-11-17
- **MCP Protocol Version**: 1.0
- **Python SDK Version**: Compatible with mcp>=0.9.0

---

## 💡 Tips for Best Results

1. **Use Chinese share text directly** - No need to extract the link manually
2. **Initialize once per session** - Don't re-initialize unless login expires
3. **Wait for initialization to complete** - Scan QR code if prompted
4. **Keep browser window open** - Don't close it during scraping
5. **Use direct URLs when possible** - Faster than resolving short links

---

## 🌐 Language Support

This MCP server fully supports:
- **English**: All tool descriptions and error messages
- **Chinese (中文)**: Recognizes Chinese product names, descriptions, and share text
- **Mixed Input**: Handles bilingual text seamlessly

---

## 📝 License & Credits

Created for research and product analysis purposes.

**Dependencies**:
- MCP Python SDK - Model Context Protocol implementation
- Playwright - Browser automation
- Pydantic - Input validation
- aiohttp - HTTP client

---

## 🆘 Support

If you encounter issues:

1. Check this README thoroughly
2. Verify installation steps were followed correctly
3. Check browser profile permissions
4. Try clearing browser cache and re-initializing
5. Ensure Taobao website is accessible from your network

---

**Happy Scraping! 🎉**

*This MCP server helps AI assistants research Taobao products efficiently.*
