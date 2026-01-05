"""
Add sample data - ultra simple version
"""
import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('fundametrics_stock_data.db')
cursor = conn.cursor()

sample_companies = [
    ("RELIANCE", "Reliance Industries Limited", "Oil & Gas", "Diversified Energy Conglomerate"),
    ("TCS", "Tata Consultancy Services Limited", "IT Services", "Information Technology"),
    ("HDFCBANK", "HDFC Bank Limited", "Banking", "Private Sector Bank"),
    ("INFY", "Infosys Limited", "IT Services", "Information Technology"),
    ("HINDUNILVR", "Hindustan Unilever Limited", "FMCG", "Consumer Goods"),
]

now = datetime.now().isoformat()
today = datetime.now().date().isoformat()

for symbol, name, sector, industry in sample_companies:
    # Check if exists
    cursor.execute("SELECT id FROM companies WHERE symbol = ?", (symbol,))
    existing = cursor.fetchone()
    
    if existing:
        print(f"  ℹ️  {symbol} already exists, skipping...")
        continue
    
    # Insert company
    cursor.execute("""
        INSERT INTO companies (name, symbol, exchange, sector, industry, is_active, summary_generated, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, symbol, "NSE", sector, industry, 1, 0, now, now))
    
    company_id = cursor.lastrowid
    
    # Insert company facts
    cursor.execute("""
        INSERT INTO company_facts (id, company_id, face_value, book_value, shares_outstanding, snapshot_date, created_at)
        VALUES (NULL, ?, ?, ?, ?, ?, ?)
    """, (company_id, 10.00, 500.00, 1000000, today, now))
    
    # Insert shareholding
    for category, percentage in [("PROMOTER", 50.00), ("FII", 20.00), ("DII", 15.00), ("PUBLIC", 15.00)]:
        cursor.execute("""
            INSERT INTO shareholding (company_id, category, quarter_date, percentage, scraped_at)
            VALUES (?, ?, ?, ?, ?)
        """, (company_id, category, today, percentage, now))
    
    print(f"  ✅ Added {symbol}")

conn.commit()
print("\n✅ Sample data import completed!")

# Verify
cursor.execute("SELECT COUNT(*) FROM companies")
count = cursor.fetchone()[0]
print(f"📊 Total companies in database: {count}")

conn.close()
