# Fundametrics: System Architecture & Operational Manual

**Version:** 2.0 (Institutional)
**Last Updated:** December 30, 2025

---

## 1. Executive Summary
**Fundametrics** (formerly Fundametrics) is a high-precision financial intelligence platform designed for the "sovereign investor." Unlike traditional portals that rely on generalized consensus or black-box ratings, Fundametrics operates on a **"Zero Speculation, Audit-Extract"** philosophy. It mechanically parses raw financial filings (PDFs, HTML disclosures) to construct a localized, audit-verified database of Indian equities.

The system is built as a **Modern Monorepo** separated into a high-performance Python scraping/analytics engine (`fundametrics-scraper`) and a reactive, institutional-grade React frontend (`fundametrics-frontend`).

---

## 2. High-Level Architecture

```mermaid
graph TD
    User[Institutional User] -->|Browses| Frontend[React SPA (Vite)]
    Frontend -->|REST API Requests| API[FastAPI Gateway]
    
    subgraph "Backend Intelligence Node (fundametrics-scraper)"
        API --> Pipeline[Data Pipeline Orchestrator]
        Pipeline --> Sources[Source Adapters (Trendlyne, Screener, NSE)]
        Sources -->|Raw HTML/PDF| Ingestion[Ingestion Engine]
        Ingestion -->|Unstructured Data| Mapper[Financial Mapper & Normalizer]
        Mapper -->|Structured Facts| Repository[Local JSON Data Repository]
        
        Repository --> Metrics[Metrics Engine (Ratios, Growth, safe_div)]
        Metrics --> Audit[Audit Trail Generator]
        Audit --> API
    end

    subgraph "Frontend Experience (fundametrics-frontend)"
        Router[React Router] --> Landing[Landing Page]
        Router --> Stocks[Stock Catalogue]
        Router --> Terminal[Company Terminal (Full-Width)]
        Router --> Indices[Market Indices]
        
        Terminal --> Snapshot[Executive Snapshot]
        Terminal --> Viz[Visual Charts]
        Terminal --> News[News & Media Disclosures]
    end
```

---

## 3. The Backend Engine (`fundametrics-scraper`)

The "Brain" of Fundametrics. It handles data acquisition, cleaning, calculation, and serving.

### 3.1 Core Modules (`scraper/core`)
*   **`ingestion.py`**: The entry point for data fetching. It orchestrates calls to various source parsers.
*   **`financial_mapper.py`**: A critical translation layer that maps chaotic, non-standardized line items from raw filings (e.g., "Emp. Benefit Exp.") into standardized Fundametrics canonical keys (e.g., `employee_costs`).
*   **`metrics_engine.py`**: Calculates high-order financial ratios (ROE, ROCE, Altman Z-Score) from the raw atomic facts. *Note: We calculate our own ratios; we do not trust third-party pre-calculated values.*
*   **`shareholding_engine.py`**: Analyzes quarterly shareholding patterns to detect "Smart Money" movements (FII/DII accumulation).
*   **`api_response_builder.py`**: Assembles the massive, highly nested JSON response required by the frontend, ensuring fields like `trust_score` and `audit_trail` are populated.
*   **`repository.py`**: Manages the persistence of stock data in a flat-file JSON structure, acting as a lightweight, portable database.
*   **`indices.py`**: Manages the constituents of major market indices (NIFTY 50, SENSEX, BANK NIFTY).

### 3.2 Key Data Flows
1.  **Ingestion**: `GET /api/stocks/{symbol}` triggers a check in `DataRepository`.
2.  **Staleness Check**: If data is older than 24 hours (configurable), a live scrape is triggered.
3.  **Normalization**: Raw numbers are normalized (Crores conversion, sign correction).
4.  **Audit**: Every data point is tagged with its source origin (e.g., "From Table 4, Row 2 of FY24 Annual Report").

---

## 4. The Frontend Application (`fundametrics-frontend`)

The "Face" of Fundametrics. A single-page application built for speed, density, and visual clarity.

### 4.1 Technology Stack
*   **Framework**: React 18 with TypeScript.
*   **Build Tool**: Vite (for sub-millisecond HMR).
*   **Styling**: Tailwind CSS (Utility-first, custom "Sovereign" design system).
*   **Routing**: React Router v6.
*   **State Management**: React Hooks (local state) + SWR pattern (via custom `api` util).

### 4.2 Key Pages
*   **Landing Page (`LandingPage.tsx`)**: High-impact introduction. Features "Active Stream" of processed stocks and "Core Indices" cards.
*   **Company Terminal (`CompanyPage.tsx`)**: The core product. A full-width, immersive dashboard displaying:
    *   **Executive Snapshot**: Critical stats at a glance.
    *   **Visual Trends**: Interactive charts for Topline/Bottomline.
    *   **Financial Statements**: Detail-rich Profit & Loss, Balance Sheet, Cash Flow tables.
    *   **Intelligence Narratives**: AI-generated thesis summaries (if available).
    *   **Live News**: Sentiment-analysed news feed.
*   **Catalogue (`StocksPage.tsx`)**: Searchable database with sector filtering.
*   **Indices (`IndexPage.tsx`)**: Dedicated view for index constituents.

### 4.3 Design Philosophy
*   **"Institutional" Aesthetic**: Dark text on off-white backgrounds (#F8FAFC), rigid grid layouts, high-contrast typography (Inter/Manrope fonts).
*   **Full-Width Utilization**: The UI expands to fill 100% of the viewport (recently updated) to maximize data density without scrolling.
*   **Micro-Interactions**: Hover effects on cards, smooth transitions between tabs.

---

## 5. Directory Structure Map

### Backend (`fundametrics-scraper`)
```text
scraper/
├── api/
│   ├── app.py             # FastAPI entry point
│   └── routes.py          # /stocks, /search, /indices endpoints
├── core/
│   ├── ingestion.py       # Data fetch orchestration
│   ├── financial_mapper.py# Logic to Normalize messy data
│   ├── metrics_engine.py  # Fin calculations
│   └── repository.py      # JSON file handling
├── sources/               # External site scrapers (Trendlyne, etc.)
└── models/                # Pydantic data schemas
```

### Frontend (`fundametrics-frontend`)
```text
src/
├── components/            # Reusable UI building blocks
│   ├── Navbar.tsx         # Global Navigation
│   ├── Footer.tsx         # Legal & Branding
│   ├── FinancialTable.tsx # Complex data grids
│   └── ExecutiveSnapshot.tsx # Key metrics cards
├── pages/                 # Route Views
│   ├── CompanyPage.tsx    # The main terminal view
│   └── IndexPage.tsx      # Index constituent view
├── utils/
│   └── api.ts             # Centralized fetch wrapper
└── App.tsx                # Route definitions
```

---

## 6. How to Run

### Prerequisite
Ensure Python 3.9+ and Node.js 18+ are installed.

### 1. Start the Backend Intelligence Node
```bash
cd fundametrics-scraper
# Install dependencies (first time only)
# pip install -r requirements.txt
python -m uvicorn scraper.api.app:app --port 8001 --reload
```
*Server runs at `http://localhost:8001`*

### 2. Start the Reporting Frontend
```bash
cd fundametrics-frontend
# Install dependencies (first time only)
# npm install
npm run dev
```
*UI runs at `http://localhost:5173`*

---

**Fundametrics** is a living system. The architecture prioritizes data integrity ("Audit") over breadth, ensuring that when an institutional user sees a number, they can trust its origin.
