
import pymongo
import os
from datetime import datetime

# Configuration
MONGO_URI = "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority"
BASE_URL = "https://fundametrics.in"
OUTPUT_FILE = "../finox-frontend/public/sitemap.xml" # Write directly to frontend public folder

def generate_sitemap():
    print("Connecting to MongoDB...")
    client = pymongo.MongoClient(MONGO_URI)
    db = client["fundametrics"]
    collection = db["companies_registry"]

    print("Fetching company list...")
    # Fetch all companies that are likely valid (e.g. have a symbol)
    companies = list(collection.find({}, {"symbol": 1}))
    
    # Static pages
    urls = [
        {"loc": f"{BASE_URL}/", "priority": "1.0", "changefreq": "daily"},
        {"loc": f"{BASE_URL}/stocks", "priority": "0.9", "changefreq": "daily"},
        {"loc": f"{BASE_URL}/about", "priority": "0.5", "changefreq": "monthly"},
    ]

    # Dynamic company pages
    print(f"Adding {len(companies)} company pages...")
    for company in companies:
        symbol = company.get("symbol")
        if symbol:
            urls.append({
                "loc": f"{BASE_URL}/company/{symbol}",
                "priority": "0.8",
                "changefreq": "daily"
            })

    # Generate XML
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for url in urls:
        xml_content += '  <url>\n'
        xml_content += f'    <loc>{url["loc"]}</loc>\n'
        xml_content += f'    <lastmod>{datetime.utcnow().strftime("%Y-%m-%d")}</lastmod>\n'
        xml_content += f'    <changefreq>{url["changefreq"]}</changefreq>\n'
        xml_content += f'    <priority>{url["priority"]}</priority>\n'
        xml_content += '  </url>\n'

    xml_content += '</urlset>'

    # Ensure directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"✅ Sitemap generated with {len(urls)} URLs at: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_sitemap()
