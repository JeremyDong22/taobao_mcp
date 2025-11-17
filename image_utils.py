#!/usr/bin/env python3
"""
Version: 2.1
Created: 2025-11-17
Updated: 2025-11-17

Image Utilities - Common image processing functions for all fetchers.

Changes in v2.1:
- ✅ FIXED: AVIF to WebP conversion now properly validates output
- ✅ Conversion failure detection using magic bytes verification
- ✅ Failed conversions now skip the image instead of returning invalid data
- ✅ Added detailed debug logging for conversion process
- ✅ Prevents MIME type mismatch errors in MCP API

Changes in v2.0:
- ✅ Extracted from image_fetcher.py for modular architecture
- ✅ Supports all image fetchers (basic, gallery, detail, sku, review)
- ✅ AVIF to WebP conversion for MCP API compatibility
- ✅ Magic bytes detection for accurate MIME type identification

This module provides:
- Async image fetching from URLs
- Base64 encoding for MCP ImageContent
- Batch fetching with concurrency control
- MIME type detection and conversion (AVIF → WebP)
- Alibaba CDN anti-hotlinking bypass
"""

import asyncio
import aiohttp
import base64
from io import BytesIO
from typing import Optional, List, Tuple
from PIL import Image


# ==================== CONFIGURATION ====================

# Default maximum concurrent image downloads
DEFAULT_MAX_CONCURRENT = 10

# Default timeout per image fetch (seconds)
DEFAULT_TIMEOUT = 10


# ==================== IMAGE FETCHING ====================

async def fetch_image_as_base64(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[Tuple[str, str]]:
    """
    Fetch image from URL and convert to base64.

    Args:
        url: Image URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Tuple of (base64_data, mime_type) or None if fetch failed
    """
    try:
        timeout_config = aiohttp.ClientTimeout(total=timeout)

        # Headers to bypass Alibaba CDN anti-hotlinking protection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://detail.tmall.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
        }

        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    image_bytes = await response.read()

                    # Detect MIME type from actual file content (magic bytes)
                    content_type = response.headers.get('Content-Type', '')
                    mime_type = _detect_mime_type_from_bytes(image_bytes, url, content_type)

                    # Convert AVIF to WebP (MCP API doesn't support AVIF)
                    if mime_type == 'image/avif':
                        print(f"[Image] Converting AVIF to WebP: {url}")
                        converted_bytes = _convert_to_webp(image_bytes)

                        # Verify conversion succeeded by checking magic bytes
                        if len(converted_bytes) >= 12 and converted_bytes[0:4] == b'RIFF' and converted_bytes[8:12] == b'WEBP':
                            print(f"[Image] Successfully converted AVIF to WebP")
                            image_bytes = converted_bytes
                            mime_type = 'image/webp'
                        else:
                            # Conversion failed, skip this image
                            print(f"[Image] WARNING: AVIF conversion failed, skipping image: {url}")
                            return None

                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                    return (base64_data, mime_type)
                else:
                    print(f"Failed to fetch image {url}: HTTP {response.status}")
                    return None

    except asyncio.TimeoutError:
        print(f"Timeout fetching image: {url}")
        return None
    except Exception as e:
        print(f"Error fetching image {url}: {e}")
        return None


async def fetch_images_batch(
    image_urls: List[str],
    max_concurrent: int = DEFAULT_MAX_CONCURRENT
) -> List[Tuple[str, str, str]]:
    """
    Fetch multiple images concurrently.

    Args:
        image_urls: List of image URLs to fetch
        max_concurrent: Maximum concurrent requests

    Returns:
        List of tuples (url, base64_data, mime_type) for successfully fetched images
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_semaphore(url: str):
        async with semaphore:
            result = await fetch_image_as_base64(url)
            if result:
                base64_data, mime_type = result
                return (url, base64_data, mime_type)
            return None

    tasks = [fetch_with_semaphore(url) for url in image_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out None and exceptions
    return [r for r in results if r is not None and not isinstance(r, Exception)]


# ==================== MIME TYPE DETECTION ====================

def _detect_mime_type_from_bytes(image_bytes: bytes, url: str, content_type: str) -> str:
    """
    Detect MIME type from actual file content (magic bytes).

    This is more accurate than URL or header-based detection.

    Args:
        image_bytes: Raw image data
        url: Image URL (fallback)
        content_type: Content-Type header value (fallback)

    Returns:
        MIME type string (e.g., 'image/jpeg', 'image/avif')
    """
    # Check magic bytes (file signatures)
    if len(image_bytes) < 12:
        return _detect_mime_type(url, content_type)

    # JPEG: FF D8 FF
    if image_bytes[0:3] == b'\xff\xd8\xff':
        return 'image/jpeg'

    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if image_bytes[0:8] == b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a':
        return 'image/png'

    # GIF: GIF87a or GIF89a
    if image_bytes[0:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'

    # WebP: RIFF....WEBP
    if image_bytes[0:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return 'image/webp'

    # AVIF: check for 'ftyp' at offset 4 and 'avif' or 'avis' nearby
    # AVIF format: ....ftyp(avif|avis|...)
    if image_bytes[4:8] == b'ftyp':
        # Check next 8 bytes for AVIF signatures
        ftyp_content = image_bytes[8:20]
        if b'avif' in ftyp_content or b'avis' in ftyp_content:
            return 'image/avif'

    # Fallback to header/URL detection
    return _detect_mime_type(url, content_type)


def _detect_mime_type(url: str, content_type: str) -> str:
    """
    Detect MIME type from URL extension or Content-Type header.

    Fallback method when magic bytes detection fails.

    Args:
        url: Image URL
        content_type: Content-Type header value

    Returns:
        MIME type string (e.g., 'image/jpeg')
    """
    # Check Content-Type header first
    if 'avif' in content_type:
        return 'image/avif'
    elif 'jpeg' in content_type or 'jpg' in content_type:
        return 'image/jpeg'
    elif 'png' in content_type:
        return 'image/png'
    elif 'webp' in content_type:
        return 'image/webp'
    elif 'gif' in content_type:
        return 'image/gif'

    # Fallback to URL extension
    url_lower = url.lower()
    if url_lower.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    elif url_lower.endswith('.png'):
        return 'image/png'
    elif url_lower.endswith('.webp'):
        return 'image/webp'
    elif url_lower.endswith('.gif'):
        return 'image/gif'

    # Default fallback
    return 'image/jpeg'


# ==================== IMAGE CONVERSION ====================

def _convert_to_webp(image_bytes: bytes) -> bytes:
    """
    Convert image bytes to WebP format.

    Args:
        image_bytes: Original image data in any format

    Returns:
        Image data in WebP format, or empty bytes if conversion fails
    """
    try:
        # Open image from bytes
        img = Image.open(BytesIO(image_bytes))

        # Convert to RGB if necessary (WebP doesn't support all modes)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')

        # Save as WebP to BytesIO
        output = BytesIO()
        img.save(output, format='WEBP', quality=85)
        output.seek(0)

        converted_bytes = output.read()

        # Verify the output is valid WebP
        if len(converted_bytes) >= 12 and converted_bytes[0:4] == b'RIFF' and converted_bytes[8:12] == b'WEBP':
            print(f"[Image] WebP conversion successful, size: {len(converted_bytes)} bytes")
            return converted_bytes
        else:
            print(f"[Image] ERROR: WebP conversion produced invalid output")
            return b''  # Return empty bytes to signal failure

    except Exception as e:
        print(f"[Image] ERROR converting image to WebP: {e}")
        import traceback
        traceback.print_exc()
        # Return empty bytes to signal failure
        return b''
