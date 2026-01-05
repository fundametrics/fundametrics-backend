# Fundametrics Data Principles

These principles govern the collection, storage, and presentation of financial data within the Fundametrics platform to ensure legal compliance and technical excellence.

## 1. Scraper Boundaries
- **Facts Only**: Scrapers are data photocopiers of public corporate disclosures. They collect raw numeric facts without interpretation.
- **No Ratios/CAGRs**: Percentage-based metrics (ROE, ROCE, OPM), scores, and growth indicators are never scraped.
- **No Source Metadata**: Third-party site names are never stored in code, databases, or API responses.

## 2. Metric Ownership
- **Internal Computation**: All analytics, ratios, margins, and growth rates are computed internally by the Fundametrics Metrics Engine.
- **Internal IP**: Fundametrics owns the formulas, naming conventions, and presentation logic for all derived metrics.
- **Neutral Identifiers**: Scraped fields use neutral, database-style identifiers (e.g., `revenue`, `net_income`) rather than UI-friendly labels.

## 3. Data Structure & Safety
- **Unique Architecture**: Fundametrics uses a proprietary year-keyed data structure, not mirroring any third-party table layouts.
- **Fact/Metric Separation**: Raw accounting facts are stored separately from computed metrics.
- **Rewritten Descriptions**: Company profiles are summarized or extracted only from annual report disclosures, never stored verbatim.

## 4. Legal Compliance
- All numeric data is treated as originating from public corporate disclosures.
- "Same number ≠ same IP": Numeric facts are public; their curated presentation is proprietary. Fundametrics ensures its presentation is unique.
- Marking generated summaries with `summary_generated: true`.
