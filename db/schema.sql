-- Finox Scraper Database Schema
-- Focus: Indian Stock Fundamentals, Historical Snapshots, No Overwrites

CREATE DATABASE IF NOT EXISTS finox_db;
USE finox_db;

-- 1. Companies Table
CREATE TABLE IF NOT EXISTS companies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    exchange ENUM('NSE', 'BSE', 'BOTH') DEFAULT 'NSE',
    sector VARCHAR(100),
    industry VARCHAR(100),
    website_url VARCHAR(255),
    about TEXT,
    summary_generated BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_symbol_exchange (symbol, exchange)
);

-- 2. Company Facts (Raw corporate constants)
CREATE TABLE IF NOT EXISTS company_facts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    face_value DECIMAL(10, 2),
    book_value DECIMAL(10, 2),
    shares_outstanding DECIMAL(20, 2),
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    INDEX idx_company_snapshot (company_id, snapshot_date DESC)
);

-- 3. Computed Metrics (Internal Finox Analytics)
CREATE TABLE IF NOT EXISTS computed_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    metric_name VARCHAR(150) NOT NULL,
    period DATE NOT NULL,
    value DECIMAL(20, 2),
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    INDEX idx_company_period (company_id, period DESC),
    INDEX idx_metric_name (metric_name)
);

-- 3. Financials Yearly (P&L, Balance Sheet, Cash Flow metrics)
CREATE TABLE IF NOT EXISTS financials_yearly (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    statement_type ENUM('P&L', 'BALANCE_SHEET', 'CASH_FLOW', 'QUARTERS') NOT NULL,
    metric_name VARCHAR(150) NOT NULL,
    fiscal_year DATE NOT NULL,
    value DECIMAL(20, 2),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    INDEX idx_company_fiscal (company_id, fiscal_year DESC),
    INDEX idx_metric (metric_name)
);

-- 4. Shareholding Pattern
CREATE TABLE IF NOT EXISTS shareholding (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    category ENUM('PROMOTER', 'FII', 'DII', 'PUBLIC', 'OTHERS') NOT NULL,
    quarter_date DATE NOT NULL,
    percentage DECIMAL(5, 2),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    INDEX idx_company_quarter (company_id, quarter_date DESC)
);

-- 5. Management Table
CREATE TABLE IF NOT EXISTS management (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    designation VARCHAR(255),
    type ENUM('BOARD', 'EXECUTIVE') DEFAULT 'BOARD',
    experience TEXT,
    qualification TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    INDEX idx_company_mgmt (company_id)
);

-- 7. Scrape Logs (Internal debugging only)
CREATE TABLE IF NOT EXISTS scrape_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id INT,
    status ENUM('SUCCESS', 'FAILED', 'PARTIAL') NOT NULL,
    message TEXT,
    duration_ms INT,
    items_scraped INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
);

-- Optimization: View for Latest Company Facts
CREATE OR REPLACE VIEW view_latest_company_facts AS
SELECT f1.*
FROM company_facts f1
INNER JOIN (
    SELECT company_id, MAX(snapshot_date) as latest_date
    FROM company_facts
    GROUP BY company_id
) f2 ON f1.company_id = f2.company_id AND f1.snapshot_date = f2.latest_date;
