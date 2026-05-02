"""
Moglix.com Web Scraper
Extracts categories, products, links, images, and text from moglix.com
Uses Playwright (headless browser) + BeautifulSoup (HTML parsing)
"""

import asyncio
import json
import csv
import os
import time
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.moglix.com"
OUTPUT_DIR = "output"
DELAY_BETWEEN_PAGES = 2  # seconds, be respectful


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


async def get_page_html(page, url, wait_selector=None):
    """Navigate to URL and return rendered HTML."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if wait_selector:
            await page.wait_for_selector(wait_selector, timeout=10000)
        else:
            await asyncio.sleep(2)  # let JS render
        return await page.content()
    except Exception as e:
        print(f"  Error loading {url}: {e}")
        return None


def extract_categories(soup):
    """Extract main categories from the homepage navigation."""
    categories = []
    # Category links in the nav follow pattern /category-name/id
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href.startswith("http"):
            href = urljoin(BASE_URL, href)
        # Category pages have numeric IDs at the end of the path
        parts = href.rstrip("/").split("/")
        if (
            href.startswith(BASE_URL)
            and len(parts) >= 4
            and parts[-1].isdigit()
            and "/mp/" not in href
        ):
            name = link.get_text(strip=True)
            if name and len(name) > 1:
                categories.append({"name": name, "url": href})
    # Deduplicate by URL
    seen = set()
    unique = []
    for c in categories:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)
    return unique


def extract_products(soup):
    """Extract product info from a listing/homepage."""
    products = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href.startswith("http"):
            href = urljoin(BASE_URL, href)
        if "/mp/" not in href:
            continue
        name = link.get_text(strip=True).replace("...", "").strip()
        if not name or len(name) < 5:
            continue
        products.append({"name": name, "url": href})
    # Deduplicate
    seen = set()
    unique = []
    for p in products:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)
    return unique


def extract_all_links(soup):
    """Extract every link on the page."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(BASE_URL, href)
        text = a.get_text(strip=True)
        links.append({"text": text, "url": href})
    return links


def extract_all_images(soup):
    """Extract every image on the page."""
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        if not src.startswith("http"):
            src = urljoin(BASE_URL, src)
        alt = img.get("alt", "")
        images.append({"alt": alt, "src": src})
    return images


def extract_text_content(soup):
    """Extract meaningful text blocks from the page."""
    texts = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "span", "li"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 3:
            texts.append(text)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def extract_product_detail(soup):
    """Extract detailed info from a single product page."""
    detail = {}
    # Title
    h1 = soup.find("h1")
    detail["title"] = h1.get_text(strip=True) if h1 else ""
    # Price
    for span in soup.find_all("span"):
        text = span.get_text(strip=True)
        if text.startswith("₹") and "OFF" not in text:
            detail.setdefault("price", text)
    # Description
    desc_div = soup.find("div", {"class": lambda c: c and "description" in c.lower()}) if soup else None
    detail["description"] = desc_div.get_text(strip=True) if desc_div else ""
    # Images
    detail["images"] = [
        img.get("src") or img.get("data-src")
        for img in soup.find_all("img")
        if (img.get("src") or img.get("data-src", "")).startswith("http")
        and "cdn.moglix.com" in (img.get("src") or img.get("data-src", ""))
    ]
    return detail


async def scrape_homepage(page):
    """Scrape the Moglix homepage for categories, products, links, images, text."""
    print("Scraping homepage...")
    html = await get_page_html(page, BASE_URL)
    if not html:
        return {}

    soup = BeautifulSoup(html, "lxml")
    data = {
        "categories": extract_categories(soup),
        "products": extract_products(soup),
        "links": extract_all_links(soup),
        "images": extract_all_images(soup),
        "text": extract_text_content(soup),
    }
    print(f"  Found {len(data['categories'])} categories, {len(data['products'])} products, "
          f"{len(data['links'])} links, {len(data['images'])} images")
    return data


async def scrape_category_page(page, category_url, category_name):
    """Scrape a single category page for its products."""
    print(f"Scraping category: {category_name}...")
    html = await get_page_html(page, category_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    products = extract_products(soup)
    images = extract_all_images(soup)
    print(f"  Found {len(products)} products, {len(images)} images")
    return {"products": products, "images": images, "category": category_name}


async def scrape_product_page(page, product_url):
    """Scrape a single product page for detailed info."""
    html = await get_page_html(page, product_url)
    if not html:
        return {}
    soup = BeautifulSoup(html, "lxml")
    return extract_product_detail(soup)


def save_json(data, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {path}")


def save_csv(data, filename, fieldnames):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"Saved {path}")


async def main():
    ensure_output_dir()

    # Configuration - adjust these to control scrape depth
    MAX_CATEGORIES = None    # scrape ALL category pages
    MAX_PRODUCTS = None      # scrape ALL product detail pages

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        # 1. Scrape homepage (skip if already done)
        cat_products_path = os.path.join(OUTPUT_DIR, "category_products.json")
        if os.path.exists(cat_products_path):
            print("Category data already exists, loading from disk...")
            with open(cat_products_path, "r", encoding="utf-8") as f:
                all_category_products = json.load(f)
            print(f"  Loaded {len(all_category_products)} products from categories")
        else:
            homepage_data = await scrape_homepage(page)
            save_json(homepage_data, "homepage.json")
            save_csv(homepage_data["categories"], "categories.csv", ["name", "url"])
            save_csv(homepage_data["products"], "products_homepage.csv", ["name", "url"])
            save_csv(homepage_data["images"], "images_homepage.csv", ["alt", "src"])

            # 2. Scrape category pages
            categories = homepage_data.get("categories", [])
            if MAX_CATEGORIES:
                categories = categories[:MAX_CATEGORIES]

            all_category_products = []
            for cat in categories:
                cat_data = await scrape_category_page(page, cat["url"], cat["name"])
                if cat_data:
                    for p_item in cat_data.get("products", []):
                        p_item["category"] = cat["name"]
                        all_category_products.append(p_item)
                await asyncio.sleep(DELAY_BETWEEN_PAGES)

            save_json(all_category_products, "category_products.json")
            save_csv(all_category_products, "category_products.csv", ["category", "name", "url"])

        # 3. Scrape individual product pages (incremental save every 50)
        product_urls = [p_item["url"] for p_item in all_category_products[:MAX_PRODUCTS]]
        details_path = os.path.join(OUTPUT_DIR, "product_details.json")

        # Resume from where we left off if file exists
        product_details = []
        done_urls = set()
        if os.path.exists(details_path):
            with open(details_path, "r", encoding="utf-8") as f:
                product_details = json.load(f)
            done_urls = {p["url"] for p in product_details}
            print(f"Resuming: {len(done_urls)} products already scraped")

        remaining = [u for u in product_urls if u not in done_urls]
        total = len(product_urls)
        for i, url in enumerate(remaining):
            done = len(done_urls) + i + 1
            print(f"Scraping product {done}/{total}...")
            detail = await scrape_product_page(page, url)
            detail["url"] = url
            product_details.append(detail)
            # Save every 50 products
            if len(product_details) % 50 == 0:
                save_json(product_details, "product_details.json")
            await asyncio.sleep(DELAY_BETWEEN_PAGES)

        save_json(product_details, "product_details.json")

        await browser.close()

    # Summary
    print("\n=== Scraping Complete ===")
    print(f"Output saved to ./{OUTPUT_DIR}/")
    for f in os.listdir(OUTPUT_DIR):
        size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
        print(f"  {f} ({size:,} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
