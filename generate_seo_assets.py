import asyncio
import os
from datetime import datetime
from scraper.core.db import get_db

async def generate_assets():
    print("Generating SEO assets...")
    db = get_db()
    registry_col = db["companies_registry"]
    
    # Get all symbols
    cursor = registry_col.find({}, {"symbol": 1})
    symbols = []
    async for doc in cursor:
        symbols.append(doc["symbol"])
    
    print(f"Found {len(symbols)} symbols in registry.")
    
    # 1. Generate Sitemap
    base_url = "https://fundametrics.in"
    sitemap_content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    
    # Static pages
    static_pages = [
        ("/", 1.0),
        ("/stocks", 0.9),
        ("/about", 0.8),
        ("/about-data", 0.8),
        ("/disclaimer", 0.5)
    ]
    
    for page, priority in static_pages:
        sitemap_content.append(f"  <url>")
        sitemap_content.append(f"    <loc>{base_url}{page}</loc>")
        sitemap_content.append(f"    <changefreq>weekly</changefreq>")
        sitemap_content.append(f"    <priority>{priority}</priority>")
        sitemap_content.append(f"  </url>")
    
    # Company pages
    for symbol in symbols:
        sitemap_content.append(f"  <url>")
        sitemap_content.append(f"    <loc>{base_url}/stocks/{symbol}</loc>")
        sitemap_content.append(f"    <changefreq>weekly</changefreq>")
        sitemap_content.append(f"    <priority>0.7</priority>")
        sitemap_content.append(f"  </url>")
        
    sitemap_content.append("</urlset>")
    
    # Write Sitemap
    frontend_public = os.path.abspath("../finox-frontend/public")
    if not os.path.exists(frontend_public):
        # Fallback if structure is different
        frontend_public = os.path.abspath("c:/Users/Laser cote/.gemini/antigravity/scratch/finox-frontend/public")

    sitemap_path = os.path.join(frontend_public, "sitemap.xml")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sitemap_content))
    print(f"✓ Sitemap generated at {sitemap_path}")
    
    # 2. Generate Robots.txt
    robots_content = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /admin/",
        "",
        f"Sitemap: {base_url}/sitemap.xml"
    ]
    
    robots_path = os.path.join(frontend_public, "robots.txt")
    with open(robots_path, "w", encoding="utf-8") as f:
        f.write("\n".join(robots_content))
    print(f"✓ Robots.txt generated at {robots_path}")

if __name__ == "__main__":
    asyncio.run(generate_assets())
