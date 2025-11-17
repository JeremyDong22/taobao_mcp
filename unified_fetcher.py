#!/usr/bin/env python3
"""
Version: 1.1
Created: 2025-11-17
Updated: 2025-11-18

Unified Product Fetcher - Returns all product information and images with pagination.

This replaces the split fetcher approach (basic, gallery, detail, sku, review) with
a single unified tool that:
- Fetches ALL product information and images at once
- Labels each image with its type (gallery, detail, sku, review)
- Applies pagination to the combined image list
- Returns pagination metadata for easy navigation

Changes in v1.1:
- ✅ CRITICAL FIX: Review photos bug - photos are strings, not dicts
- ✅ Added type checking to handle both string URLs and dict formats
- ✅ Prevents TypeError when processing review photos
- ✅ This was causing the MCP tool to hang/crash with certain inputs

Changes in v1.0:
- ✅ Initial implementation combining all image types
- ✅ Pagination support with offset and limit parameters
- ✅ Image type labels for clarity
- ✅ Simplified UX - only 2 tools needed (initialize + fetch)

Token usage: ~8000-15000 per call (well below 25000 limit)
Default: 10 images per call
Max: 20 images per call

Use case: Single tool to fetch complete product information with images.
"""

from typing import List, Tuple, Dict, Optional
from mcp.types import TextContent, ImageContent

import sys
import os
sys.path.append(os.path.dirname(__file__))

from image_utils import fetch_images_batch


# ==================== CONFIGURATION ====================

# Default number of images per page
DEFAULT_LIMIT = 10

# Maximum images that can be fetched in a single call
MAX_LIMIT = 20

# Preview image count for basic info
PREVIEW_IMAGE_COUNT = 6


# ==================== IMAGE TYPE LABELS ====================

IMAGE_TYPE_INFO = {
    'gallery': {
        'label': '📸 Gallery',
        'description': 'Main product photos from different angles (left-side thumbnails)',
        'emoji': '📸'
    },
    'detail': {
        'label': '🔍 Detail',
        'description': 'Product specifications, features, and advertising materials',
        'emoji': '🔍'
    },
    'sku': {
        'label': '🎨 SKU Variant',
        'description': 'Color/style selection thumbnails',
        'emoji': '🎨'
    },
    'review': {
        'label': '⭐ Review Photo',
        'description': 'User-uploaded real-world product photos',
        'emoji': '⭐'
    }
}


# ==================== MAIN FETCHER ====================

async def fetch_product_with_images(
    product_data: dict,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
    include_preview: bool = True
) -> List[TextContent | ImageContent]:
    """
    Fetch complete product information with all images (paginated).

    This is the unified fetcher that replaces all specialized fetchers.
    It collects ALL images from all categories, labels them by type,
    and returns them with pagination.

    Args:
        product_data: Product data dict from TaobaoScraper
        offset: Starting index for pagination (default 0)
        limit: Maximum number of images to fetch (default 10, max 20)
        include_preview: Whether to include basic info and preview images (default True)

    Returns:
        List of TextContent and ImageContent for MCP response
    """
    # Validate and clamp limit
    limit = min(limit, MAX_LIMIT)

    # Step 1: Collect all images with type labels
    all_images = _collect_all_images(product_data)
    total_count = len(all_images)

    # Step 2: Generate basic product information
    basic_info_md = _generate_basic_info(product_data, all_images)

    # Step 3: Apply pagination to image list
    paginated_images = all_images[offset:offset + limit]

    # Step 4: Calculate pagination metadata
    has_more = (offset + limit) < total_count
    next_offset = offset + limit if has_more else None

    # Step 5: Build pagination info markdown
    pagination_md = _generate_pagination_info(
        offset=offset,
        limit=limit,
        total_count=total_count,
        has_more=has_more,
        next_offset=next_offset,
        current_page_count=len(paginated_images)
    )

    # Step 6: Fetch images for current page
    print(f"[Unified] Fetching {len(paginated_images)} images (offset={offset}, limit={limit}, total={total_count})...")
    image_urls = [img['url'] for img in paginated_images]
    fetched_images = await fetch_images_batch(image_urls, max_concurrent=15)
    print(f"[Unified] Successfully fetched {len(fetched_images)} images")

    # Step 7: Build response content
    content_list: List[TextContent | ImageContent] = []

    # Add basic info (if first page or include_preview=True)
    if offset == 0 or include_preview:
        content_list.append(TextContent(type="text", text=basic_info_md))

    # Add pagination info
    content_list.append(TextContent(type="text", text=pagination_md))

    # Add images with type labels
    for idx, ((url, base64_data, mime_type), img_info) in enumerate(zip(fetched_images, paginated_images), 1):
        image_type = img_info['type']
        type_info = IMAGE_TYPE_INFO.get(image_type, {})
        emoji = type_info.get('emoji', '🖼️')
        label = type_info.get('label', image_type.title())

        # Add text label before each image
        global_idx = offset + idx
        content_list.append(
            TextContent(
                type="text",
                text=f"\n### {emoji} Image {global_idx}/{total_count}: {label}\n"
            )
        )

        # Add image
        content_list.append(
            ImageContent(type="image", data=base64_data, mimeType=mime_type)
        )

    return content_list


# ==================== HELPER FUNCTIONS ====================

def _collect_all_images(product_data: dict) -> List[Dict]:
    """
    Collect all images from product_data and label them by type.

    Returns:
        List of dicts with keys: 'url', 'type'
    """
    all_images = []

    # 1. Gallery images (thumbnail_images)
    gallery_images = product_data.get('thumbnail_images', [])
    for img in gallery_images:
        all_images.append({
            'url': img['url'],
            'type': 'gallery'
        })

    # 2. Detail images
    detail_images = product_data.get('detail_images', [])
    for img in detail_images:
        all_images.append({
            'url': img['url'],
            'type': 'detail'
        })

    # 3. SKU images
    specifications = product_data.get('specifications', {})
    if isinstance(specifications, dict):
        sku_images = specifications.get('sku_images', [])
        for img in sku_images:
            all_images.append({
                'url': img['url'],
                'type': 'sku'
            })

    # 4. Review images
    reviews = product_data.get('reviews', [])
    for review in reviews:
        photos = review.get('photos', [])
        for photo in photos:
            # photos is a list of URL strings, not dictionaries
            if isinstance(photo, str):
                all_images.append({
                    'url': photo,
                    'type': 'review'
                })
            elif isinstance(photo, dict) and 'url' in photo:
                all_images.append({
                    'url': photo['url'],
                    'type': 'review'
                })

    return all_images


def _generate_basic_info(product_data: dict, all_images: List[Dict]) -> str:
    """Generate basic product information markdown."""

    # Basic info
    title = product_data.get('title', 'N/A')
    current_price = product_data.get('current_price', 'N/A')
    original_price = product_data.get('original_price')

    if original_price:
        price = f"¥{current_price} (原价: ¥{original_price})"
    else:
        price = f"¥{current_price}" if current_price != 'N/A' else 'N/A'

    store_name = product_data.get('store_name', 'N/A')
    product_id = product_data.get('product_id', 'N/A')
    scraped_at = product_data.get('scraped_at', 'N/A')

    # Count images by type
    image_counts = {
        'gallery': sum(1 for img in all_images if img['type'] == 'gallery'),
        'detail': sum(1 for img in all_images if img['type'] == 'detail'),
        'sku': sum(1 for img in all_images if img['type'] == 'sku'),
        'review': sum(1 for img in all_images if img['type'] == 'review')
    }

    # Parameters
    parameters = product_data.get('parameters', [])

    # Build markdown
    md = f"# 🛍️ Product Information\n\n"
    md += f"**Product ID**: {product_id}\n"
    md += f"**Scraped at**: {scraped_at}\n\n"

    md += f"## 📋 Basic Details\n\n"
    md += f"**Title**: {title}\n\n"
    md += f"**Price**: {price}\n\n"
    md += f"**Store**: {store_name}\n\n"

    # Parameters table
    if parameters:
        md += f"## 🔧 Product Parameters ({len(parameters)} items)\n\n"
        md += "| Parameter | Value |\n"
        md += "|-----------|-------|\n"
        for param in parameters:
            param_name = param.get('param_name', 'N/A')
            param_value = param.get('param_value', 'N/A')
            md += f"| {param_name} | {param_value} |\n"
        md += "\n"

    # Image statistics by type
    md += f"## 📊 Total Images: {len(all_images)}\n\n"

    for img_type, count in image_counts.items():
        if count > 0:
            type_info = IMAGE_TYPE_INFO.get(img_type, {})
            emoji = type_info.get('emoji', '🖼️')
            description = type_info.get('description', '')
            md += f"- {emoji} **{img_type.title()}**: {count} images - {description}\n"

    md += "\n---\n\n"

    return md


def _generate_pagination_info(
    offset: int,
    limit: int,
    total_count: int,
    has_more: bool,
    next_offset: Optional[int],
    current_page_count: int
) -> str:
    """Generate pagination information markdown."""

    md = f"## 📄 Pagination\n\n"
    md += f"- **Current page**: {current_page_count} images (offset={offset}, limit={limit})\n"
    md += f"- **Total images**: {total_count}\n"
    md += f"- **Has more**: {'Yes' if has_more else 'No'}\n"

    if has_more:
        md += f"- **Next page**: Use `offset={next_offset}` to fetch more images\n"

    md += "\n"

    if current_page_count == 0:
        if total_count == 0:
            md += "⚠️ No images found for this product.\n\n"
        elif offset >= total_count:
            md += f"⚠️ Offset {offset} exceeds total images ({total_count}).\n"
            md += f"Please use offset < {total_count}.\n\n"
        else:
            md += "ℹ️ No images in this page range.\n\n"

    md += "---\n\n"

    return md
