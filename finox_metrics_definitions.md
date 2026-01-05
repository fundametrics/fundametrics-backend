# Fundametrics Metrics Definitions

This document defines the proprietary formulas and naming conventions for all derived financial metrics in the Fundametrics platform.

## 1. Profitability Metrics

| Metric | Fundametrics ID | Formula |
| :--- | :--- | :--- |
| Operating Margin | `fundametrics_operating_margin` | `(Operating Profit / Revenue) * 100` |
| Return on Equity | `fundametrics_return_on_equity` | `(Net Income / Average Shareholder Equity) * 100` |

## 2. Valuation Metrics

| Metric | Fundametrics ID | Formula |
| :--- | :--- | :--- |
| Earnings Per Share | `fundametrics_eps` | `Net Income / Shares Outstanding` |
| Market Cap | `fundametrics_market_cap` | `Current Share Price * Total Shares Outstanding` |

## 3. Growth Metrics

| Metric | Fundametrics ID | Formula |
| :--- | :--- | :--- |
| Revenue Growth | `fundametrics_revenue_growth_annualized` | `((End Revenue / Start Revenue) ^ (1/n) - 1) * 100` |
| Internal Profit Growth | `fundametrics_growth_rate_internal` | `((End Net Income / Start Net Income) ^ (1/n) - 1) * 100` |

## 4. Operational Metrics

- **Trend Score**: Proprietary scoring based on directional persistence of raw line items over a 3-5 year horizon.

---
**Note**: All metrics are computed internally using raw numeric facts from public corporate disclosures. Fundametrics does not rely on third-party analytical datasets for these values.
