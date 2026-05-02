"""Parallel product scraper — splits remaining URLs across N workers."""
import asyncio
import json
import os
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

OUTPUT_DIR = "output"
MAIN_FILE = os.path.join(OUTPUT_DIR, "product_details.json")
NUM_WORKERS = 4
DELAY = 1.5

JUNK = ('logo', 'translate.gif', 'cms/utility', 'placeholder', 'loader', 'sprite', 'icon')


def extract_product_detail(soup):
    detail = {}
    h1 = soup.find("h1")
    detail["title"] = h1.get_text(strip=True) if h1 else ""
    for span in soup.find_all("span"):
        text = span.get_text(strip=True)
        if text.startswith("₹") and "OFF" not in text:
            detail.setdefault("price", text)
    desc_div = soup.find("div", {"class": lambda c: c and "description" in c.lower()}) if soup else None
    detail["description"] = desc_div.get_text(strip=True) if desc_div else ""
    detail["images"] = [
        img.get("src") or img.get("data-src")
        for img in soup.find_all("img")
        if (img.get("src") or img.get("data-src", "")).startswith("http")
        and "cdn.moglix.com" in (img.get("src") or img.get("data-src", ""))
        and not any(j in (img.get("src") or img.get("data-src", "")).lower() for j in JUNK)
    ]
    return detail


async def scrape_worker(worker_id, urls, results, lock):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
        page = await ctx.new_page()
        for i, url in enumerate(urls):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_selector('img[src*="/p/"]', timeout=6000)
                except Exception:
                    pass
                html = await page.content()
                soup = BeautifulSoup(html, "lxml")
                detail = extract_product_detail(soup)
                detail["url"] = url
                async with lock:
                    results.append(detail)
                    if len(results) % 50 == 0:
                        save(results)
            except Exception as e:
                print(f"  W{worker_id} error {url[:60]}: {e}")
                async with lock:
                    results.append({"url": url, "title": "", "images": []})
            if (i + 1) % 25 == 0:
                print(f"  W{worker_id}: {i+1}/{len(urls)}")
            await asyncio.sleep(DELAY)
        await browser.close()
    print(f"  W{worker_id}: done ({len(urls)} products)")


def save(results):
    # Merge with existing main file
    existing = []
    if os.path.exists(MAIN_FILE):
        with open(MAIN_FILE) as f:
            existing = json.load(f)
    done_urls = {p["url"] for p in existing}
    new = [r for r in results if r["url"] not in done_urls]
    merged = existing + new
    with open(MAIN_FILE, "w") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {len(merged)} total ({len(new)} new)")


async def main():
    with open(os.path.join(OUTPUT_DIR, "category_products.json")) as f:
        all_products = json.load(f)

    done_urls = set()
    if os.path.exists(MAIN_FILE):
        with open(MAIN_FILE) as f:
            done_urls = {p["url"] for p in json.load(f)}

    remaining = [p["url"] for p in all_products if p["url"] not in done_urls]
    print(f"Already done: {len(done_urls)}, Remaining: {len(remaining)}, Workers: {NUM_WORKERS}")

    if not remaining:
        print("Nothing to scrape!")
        return

    # Split URLs across workers
    chunks = [[] for _ in range(NUM_WORKERS)]
    for i, url in enumerate(remaining):
        chunks[i % NUM_WORKERS].append(url)

    results = []
    lock = asyncio.Lock()
    tasks = [scrape_worker(i, chunk, results, lock) for i, chunk in enumerate(chunks)]
    await asyncio.gather(*tasks)

    save(results)
    print(f"\nDone! Total products: {len(done_urls) + len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
