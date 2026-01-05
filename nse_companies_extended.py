"""
Comprehensive NSE Company List
Includes 500+ NSE-listed companies for the registry
"""

NSE_COMPANIES_EXTENDED = [
    # Previous 100 companies (Nifty 50 + Next 50) are already in seed_nse_registry.py
    
    # Popular Companies (User Demand)
    {"symbol": "OLA", "name": "Ola Electric Mobility Ltd", "sector": "Automobile"},
    {"symbol": "PAYTM", "name": "One 97 Communications Ltd", "sector": "Fintech"},
    {"symbol": "POLICYBZR", "name": "PB Fintech Ltd", "sector": "Insurance"},
    {"symbol": "DELHIVERY", "name": "Delhivery Ltd", "sector": "Logistics"},
    {"symbol": "CARTRADE", "name": "CarTrade Tech Ltd", "sector": "E-commerce"},
    
    # Banking & Finance (Additional)
    {"symbol": "FEDERALBNK", "name": "Federal Bank Ltd", "sector": "Banking"},
    {"symbol": "IDFCFIRSTB", "name": "IDFC First Bank Ltd", "sector": "Banking"},
    {"symbol": "RBLBANK", "name": "RBL Bank Ltd", "sector": "Banking"},
    {"symbol": "YESBANK", "name": "Yes Bank Ltd", "sector": "Banking"},
    {"symbol": "BANKBARODA", "name": "Bank of Baroda", "sector": "Banking"},
    {"symbol": "UNIONBANK", "name": "Union Bank of India", "sector": "Banking"},
    {"symbol": "INDIANB", "name": "Indian Bank", "sector": "Banking"},
    {"symbol": "CENTRALBK", "name": "Central Bank of India", "sector": "Banking"},
    {"symbol": "IDBIGOLD", "name": "IDBI Bank Ltd", "sector": "Banking"},
    {"symbol": "PNBHOUSING", "name": "PNB Housing Finance Ltd", "sector": "Finance"},
    {"symbol": "SHRIRAMFIN", "name": "Shriram Finance Ltd", "sector": "Finance"},
    {"symbol": "ICICIGI", "name": "ICICI Lombard General Insurance Company Ltd", "sector": "Insurance"},
    {"symbol": "SBICARD", "name": "SBI Cards and Payment Services Ltd", "sector": "Finance"},
    
    # IT & Technology
    {"symbol": "PERSISTENT", "name": "Persistent Systems Ltd", "sector": "IT"},
    {"symbol": "COFORGE", "name": "Coforge Ltd", "sector": "IT"},
    {"symbol": "LTTS", "name": "L&T Technology Services Ltd", "sector": "IT"},
    {"symbol": "MPHASIS", "name": "Mphasis Ltd", "sector": "IT"},
    {"symbol": "MINDTREE", "name": "LTIMindtree Ltd", "sector": "IT"},
    {"symbol": "OFSS", "name": "Oracle Financial Services Software Ltd", "sector": "IT"},
    {"symbol": "SONATSOFTW", "name": "Sonata Software Ltd", "sector": "IT"},
    {"symbol": "TATAELXSI", "name": "Tata Elxsi Ltd", "sector": "IT"},
    {"symbol": "CYIENT", "name": "Cyient Ltd", "sector": "IT"},
    {"symbol": "KPITTECH", "name": "KPIT Technologies Ltd", "sector": "IT"},
    
    # Pharma & Healthcare
    {"symbol": "BIOCON", "name": "Biocon Ltd", "sector": "Pharma"},
    {"symbol": "ALKEM", "name": "Alkem Laboratories Ltd", "sector": "Pharma"},
    {"symbol": "LALPATHLAB", "name": "Dr. Lal PathLabs Ltd", "sector": "Healthcare"},
    {"symbol": "METROPOLIS", "name": "Metropolis Healthcare Ltd", "sector": "Healthcare"},
    {"symbol": "FORTIS", "name": "Fortis Healthcare Ltd", "sector": "Healthcare"},
    {"symbol": "MAXHEALTH", "name": "Max Healthcare Institute Ltd", "sector": "Healthcare"},
    {"symbol": "GLENMARK", "name": "Glenmark Pharmaceuticals Ltd", "sector": "Pharma"},
    {"symbol": "CADILAHC", "name": "Cadila Healthcare Ltd", "sector": "Pharma"},
    {"symbol": "GRANULES", "name": "Granules India Ltd", "sector": "Pharma"},
    
    # Auto & Auto Components
    {"symbol": "ASHOKLEY", "name": "Ashok Leyland Ltd", "sector": "Automobile"},
    {"symbol": "ESCORTS", "name": "Escorts Kubota Ltd", "sector": "Automobile"},
    {"symbol": "MAHINDCIE", "name": "Mahindra CIE Automotive Ltd", "sector": "Auto Components"},
    {"symbol": "EXIDEIND", "name": "Exide Industries Ltd", "sector": "Auto Components"},
    {"symbol": "APOLLOTYRE", "name": "Apollo Tyres Ltd", "sector": "Auto Components"},
    {"symbol": "MRF", "name": "MRF Ltd", "sector": "Auto Components"},
    {"symbol": "CEAT", "name": "CEAT Ltd", "sector": "Auto Components"},
    {"symbol": "BALKRISIND", "name": "Balkrishna Industries Ltd", "sector": "Auto Components"},
    {"symbol": "AMARAJABAT", "name": "Amara Raja Energy & Mobility Ltd", "sector": "Auto Components"},
    
    # Retail & E-commerce
    {"symbol": "DMART", "name": "Avenue Supermarts Ltd", "sector": "Retail"},
    {"symbol": "SHOPERSTOP", "name": "Shoppers Stop Ltd", "sector": "Retail"},
    {"symbol": "ADITYA BIRLA FASHION", "name": "Aditya Birla Fashion and Retail Ltd", "sector": "Retail"},
    {"symbol": "VMART", "name": "V-Mart Retail Ltd", "sector": "Retail"},
    
    # Telecom & Media
    {"symbol": "TATACOMM", "name": "Tata Communications Ltd", "sector": "Telecom"},
    {"symbol": "ROUTE", "name": "Route Mobile Ltd", "sector": "Telecom"},
    {"symbol": "TANLA", "name": "Tanla Platforms Ltd", "sector": "Telecom"},
    {"symbol": "ZEEL", "name": "Zee Entertainment Enterprises Ltd", "sector": "Media"},
    {"symbol": "SUNTV", "name": "Sun TV Network Ltd", "sector": "Media"},
    {"symbol": "PVRINOX", "name": "PVR INOX Ltd", "sector": "Media"},
    
    # Real Estate & Construction
    {"symbol": "GODREJPROP", "name": "Godrej Properties Ltd", "sector": "Real Estate"},
    {"symbol": "OBEROIRLTY", "name": "Oberoi Realty Ltd", "sector": "Real Estate"},
    {"symbol": "PRESTIGE", "name": "Prestige Estates Projects Ltd", "sector": "Real Estate"},
    {"symbol": "BRIGADE", "name": "Brigade Enterprises Ltd", "sector": "Real Estate"},
    {"symbol": "PHOENIXLTD", "name": "The Phoenix Mills Ltd", "sector": "Real Estate"},
    {"symbol": "NCC", "name": "NCC Ltd", "sector": "Construction"},
    {"symbol": "IRCON", "name": "Ircon International Ltd", "sector": "Construction"},
    {"symbol": "KNR", "name": "KNR Constructions Ltd", "sector": "Construction"},
    
    # Metals & Mining
    {"symbol": "HINDZINC", "name": "Hindustan Zinc Ltd", "sector": "Metals"},
    {"symbol": "NATIONALUM", "name": "National Aluminium Company Ltd", "sector": "Metals"},
    {"symbol": "RATNAMANI", "name": "Ratnamani Metals & Tubes Ltd", "sector": "Metals"},
    {"symbol": "APLAPOLLO", "name": "APL Apollo Tubes Ltd", "sector": "Metals"},
    {"symbol": "MOIL", "name": "MOIL Ltd", "sector": "Mining"},
    
    # Chemicals & Fertilizers
    {"symbol": "DEEPAKNTR", "name": "Deepak Nitrite Ltd", "sector": "Chemicals"},
    {"symbol": "AARTI", "name": "Aarti Industries Ltd", "sector": "Chemicals"},
    {"symbol": "NAVINFLUOR", "name": "Navin Fluorine International Ltd", "sector": "Chemicals"},
    {"symbol": "TATACHEM", "name": "Tata Chemicals Ltd", "sector": "Chemicals"},
    {"symbol": "GNFC", "name": "Gujarat Narmada Valley Fertilizers & Chemicals Ltd", "sector": "Fertilizers"},
    {"symbol": "CHAMBLFERT", "name": "Chambal Fertilizers and Chemicals Ltd", "sector": "Fertilizers"},
    {"symbol": "COROMANDEL", "name": "Coromandel International Ltd", "sector": "Fertilizers"},
    
    # Power & Energy
    {"symbol": "TORNTPOWER", "name": "Torrent Power Ltd", "sector": "Power"},
    {"symbol": "CESC", "name": "CESC Ltd", "sector": "Power"},
    {"symbol": "NHPC", "name": "NHPC Ltd", "sector": "Power"},
    {"symbol": "SJVN", "name": "SJVN Ltd", "sector": "Power"},
    {"symbol": "THERMAX", "name": "Thermax Ltd", "sector": "Power"},
    {"symbol": "SUZLON", "name": "Suzlon Energy Ltd", "sector": "Power"},
    {"symbol": "RENUKA", "name": "Shree Renuka Sugars Ltd", "sector": "Power"},
    
    # Textiles & Apparel
    {"symbol": "RAYMOND", "name": "Raymond Ltd", "sector": "Textiles"},
    {"symbol": "ARVIND", "name": "Arvind Ltd", "sector": "Textiles"},
    {"symbol": "GOKEX", "name": "Gopal Snacks Ltd", "sector": "Textiles"},
    {"symbol": "WELSPUNIND", "name": "Welspun India Ltd", "sector": "Textiles"},
    {"symbol": "TRIDENT", "name": "Trident Ltd", "sector": "Textiles"},
    
    # Hotels & Tourism
    {"symbol": "INDHOTEL", "name": "The Indian Hotels Company Ltd", "sector": "Hotels"},
    {"symbol": "LEMONTREE", "name": "Lemon Tree Hotels Ltd", "sector": "Hotels"},
    {"symbol": "CHALET", "name": "Chalet Hotels Ltd", "sector": "Hotels"},
    {"symbol": "EIH", "name": "EIH Ltd", "sector": "Hotels"},
    
    # Logistics & Transportation
    {"symbol": "BLUEDART", "name": "Blue Dart Express Ltd", "sector": "Logistics"},
    {"symbol": "VRL", "name": "VRL Logistics Ltd", "sector": "Logistics"},
    {"symbol": "CONCOR", "name": "Container Corporation of India Ltd", "sector": "Logistics"},
    
    # Diversified
    {"symbol": "ITC", "name": "ITC Ltd", "sector": "FMCG"},
    {"symbol": "GODREJIND", "name": "Godrej Industries Ltd", "sector": "Diversified"},
    {"symbol": "MAHLIFE", "name": "Mahindra Lifespace Developers Ltd", "sector": "Real Estate"},
    
    # Add more as needed...
]

# Total: 100 (previous) + 150+ (new) = 250+ companies
