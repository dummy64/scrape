# Moglix Scraper

Scrapes [moglix.com](https://www.moglix.com) for categories, products, and product details using Playwright + BeautifulSoup.

## Scraped Data

| File | Description |
|------|-------------|
| `output/homepage.json` | Homepage categories, products, links, images, text |
| `output/category_products.json` | All products grouped by category (9500+) |
| `output/product_details.json` | Detailed info per product (title, price, description, images) |
| `output/categories.csv` | Category names and URLs |
| `output/category_products.csv` | Products with category mapping |

## Run the Scraper

```bash
./run.sh
```

This creates a virtual environment, installs dependencies, and runs the scraper. Output goes to `output/`.

## Browse UI

A static HTML dashboard to browse scraped categories and products.

**Live:** Enable GitHub Pages (Settings → Pages → Deploy from `main`, folder `/docs`) and visit `https://<username>.github.io/scrape/`

**Local:**
```bash
cd docs && python3 -m http.server 8899
# Open http://localhost:8899
```
