"""
Fundametrics API Response Builder
=========================

This module constructs legally-safe API responses by combining data from
various sources (metrics, shareholding, etc.) into a standardized format.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass
from scraper.utils.logger import get_logger
from scraper.core.metrics import MetricValue
from scraper.core.confidence import compute_confidence
from scraper.core.shareholding import (
    ShareholdingSnapshot,
    compute_holder_delta,
    infer_snapshot_date,
)
from .metrics_engine import FundametricsMetricsEngine
from .ratios_engine import FundametricsRatiosEngine
from .shareholding_audit import ShareholdingAudit, ShareholdingData
from .shareholding_engine import ShareholdingInsightEngine

log = get_logger(__name__)

_EMPTY_MARKERS = {"", "-", "--", "na", "n/a", "null", "none"}

@dataclass
class DataFreshness:
    """Tracks when data was last updated"""
    as_of_date: str
    days_since_update: int
    freshness_status: str  # 'fresh', 'stale', or 'outdated'

class FundametricsResponseBuilder:
    """
    Builds standardized API responses that comply with legal requirements.
    Combines data from metrics engine and shareholding audit.
    """

    _SHAREHOLDING_TTL_HOURS = 24 * 90  # 90 days default freshness window
    
    FUNDAMETRICS_DISCLAIMER = {
        "data_nature": "Raw financial statement figures sourced from publicly available disclosures",
        "metrics_notice": "All ratios and metrics are computed internally by Fundametrics",
        "investment_notice": "This information is for educational purposes only and is not investment advice",
        "liability": "Fundametrics does not guarantee accuracy or completeness",
    }

    def __init__(self, symbol: str, company_name: str, sector: str):
        """
        Initialize with basic company information.
        
        Args:
            symbol: Stock symbol (e.g., 'COALINDIA')
            company_name: Full company name
            sector: Industry sector
        """
        self.symbol = symbol.upper()
        self.company_name = company_name
        self.sector = sector
        self.about = None
        self.management = []
        self.news = []
        self.metrics_engine = FundametricsMetricsEngine()
        self.ratios_engine = FundametricsRatiosEngine()
        self.shareholding_audit = ShareholdingAudit()
        self.shareholding_engine = ShareholdingInsightEngine()
        self.shareholding_summary: Dict[str, Any] = {
            "status": "unavailable",
            "period": None,
            "summary": {},
            "is_valid": None,
            "insights": [],
        }
        self.canonical_financials: Optional[Dict[str, Any]] = None
        self.data_sources: List[str] = []
        self.warnings: List[str] = []
        self._quarterly_periods: List[str] = []
        self.company_metadata: Dict[str, Any] = {}

    @staticmethod
    def _emit_metric(metric: Optional[MetricValue], default_unit: str = "", fallback_reason: str = "Unavailable") -> Dict[str, Any]:
        if metric is None:
            return {
                "value": None,
                "unit": default_unit,
                "computed": False,
                "reason": fallback_reason,
            }

        payload: Dict[str, Any] = {
            "value": metric.value,
            "unit": metric.unit or default_unit,
            "computed": metric.computed,
        }
        if metric.value is not None:
            confidence = metric.confidence.to_dict() if getattr(metric, "confidence", None) else {"score": 0, "grade": "none"}
            payload["confidence"] = confidence
        if metric.statement_id:
            payload["statement_id"] = metric.statement_id
        if metric.value is None:
            payload["reason"] = metric.reason or fallback_reason
        elif metric.reason:
            payload["reason"] = metric.reason
        return payload

    def set_canonical_financials(self, canonical: Optional[Dict[str, Any]]) -> "FundametricsResponseBuilder":
        if canonical is not None:
            self.canonical_financials = canonical
        return self

    def set_company_metadata(self, metadata: Optional[Dict[str, Any]]) -> "FundametricsResponseBuilder":
        """Attach sanitized company metadata for ratios and provenance."""
        if isinstance(metadata, dict):
            sanitized = {
                key: value
                for key, value in metadata.items()
                if key not in {"source", "source_url", "raw_html", "fetcher_metadata"}
            }
            self.company_metadata = sanitized
            # Also extract about text if present
            if "about" in metadata and not self.about:
                self.about = metadata["about"]
        else:
            self.company_metadata = {}
        return self

    @staticmethod
    def _to_float(val: Any) -> Optional[float]:
        """Safely convert various metric formats to float."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, MetricValue):
            return val.value
        if isinstance(val, dict):
            # Could be a serialized MetricValue or a Trendlyne-style dict
            if "value" in val:
                return FundametricsResponseBuilder._to_float(val["value"])
            return None
        if isinstance(val, str):
            try:
                return float(val.replace(",", "").replace("%", ""))
            except (ValueError, TypeError):
                return None
        return None

    def set_about(self, about: Optional[str]) -> "FundametricsResponseBuilder":
        if about:
            self.about = about
        return self

    def set_management(self, management: Optional[List[Dict[str, Any]]]) -> "FundametricsResponseBuilder":
        if management:
            self.management = management
        return self

    def set_market_facts(self, market: Optional[Dict[str, Any]]) -> "FundametricsResponseBuilder":
        """Attach market facts to the builder."""
        if isinstance(market, dict):
            self.company_metadata["price"] = market.get("price")
            self.company_metadata["market_cap"] = market.get("market_cap")
        return self

    def set_news(self, news: Optional[List[Dict[str, Any]]]) -> "FundametricsResponseBuilder":
        if news:
            self.news = news
        return self

    def set_quarterly_financials(self, quarters: Optional[Dict[str, Dict[str, float]]]) -> "FundametricsResponseBuilder":
        """Track quarterly availability for downstream metadata."""
        self._quarterly_periods = []
        if isinstance(quarters, dict) and quarters:
            periods = [period for period in quarters.keys() if isinstance(period, str)]
            periods.sort(key=self.metrics_engine._period_sort_key)
            self._quarterly_periods = periods
            if "quarters" not in self.data_sources:
                self.data_sources.append("quarters")
        return self

    def add_shareholding(self, shareholding_data: Dict[str, Dict[str, float]]) -> 'FundametricsResponseBuilder':
        """Add raw shareholding data (will be normalized and audited)"""
        self.raw_shareholding = shareholding_data
        if 'shareholding' not in self.data_sources:
            self.data_sources.append('shareholding')
        return self
    
    def _calculate_data_freshness(self) -> DataFreshness:
        """Determine how fresh the data is"""
        # This would be implemented to check when the data was last updated
        # For now, using current time as a placeholder
        now = datetime.now(timezone.utc)
        as_of_date = now.strftime('%Y-%m-%d')
        
        # Placeholder logic - would be based on actual data timestamps
        days_since_update = 1
        
        if days_since_update <= 1:
            status = 'fresh'
        elif days_since_update <= 5:
            status = 'stale'
        else:
            status = 'outdated'
        
        return DataFreshness(
            as_of_date=as_of_date,
            days_since_update=days_since_update,
            freshness_status=status
        )
    
    def _detect_periodicity(self, period: Optional[str]) -> Optional[str]:
        if not period:
            return None
        if period in set(self._quarterly_periods):
            return "quarterly"
        return "annual"

    def _compute_metrics(self) -> Dict[str, Any]:
        """Compute metrics and ratios using canonical financial data."""
        canonical = self.canonical_financials or {}
        log.debug(f"canonical keys: {list(canonical.keys()) if canonical else 'EMPTY'}")
        
        income_statement = canonical.get("income_statement") or getattr(self, "income_statement", {}) or {}
        balance_sheet = canonical.get("balance_sheet") or getattr(self, "balance_sheet", {}) or {}

        if income_statement and 'income_statement' not in self.data_sources:
            self.data_sources.append('income_statement')
        if balance_sheet and 'balance_sheet' not in self.data_sources:
            self.data_sources.append('balance_sheet')

        if not income_statement:
            return {
                "metrics": {},
                "ratios": {},
                "period": None,
                "periodicity": None,
                "latest_row": {},
            }

        ordered_periods = sorted(
            (p for p in income_statement.keys() if isinstance(p, str)),
            key=self.metrics_engine._period_sort_key,
        )
        if not ordered_periods:
            return {
                "metrics": {},
                "ratios": {},
                "period": None,
                "periodicity": None,
                "latest_row": {},
            }

        latest_period = ordered_periods[-1]
        latest_row = income_statement.get(latest_period, {}) or {}

        # Promote Face Value from canonical financials if missing in metadata
        if not self._to_float(self.company_metadata.get("constants", {}).get("face_value")):
             ratios_table = (self.canonical_financials or {}).get("ratios_table", {})
             # Search reversed periods for latest non-null face_value
             for p in reversed(ordered_periods):
                  val = self._to_float(ratios_table.get(p, {}).get("face_value"))
                  if val is not None:
                      self.company_metadata.setdefault("constants", {})["face_value"] = val
                      break
        
        constants = self.company_metadata.get("constants") or {}
        shares_outstanding = self._to_float(constants.get("shares_outstanding"))
        
        # Fallback for shares outstanding using Equity Capital / Face Value
        if shares_outstanding is None:
            face_value = self._to_float(constants.get("face_value"))
            # Look for equity_capital in balance sheet
            bs = (self.canonical_financials or {}).get("balance_sheet", {})
            bs_periods = sorted(bs.keys(), key=self.metrics_engine._period_sort_key)
            if bs_periods and face_value:
                last_bs = bs.get(bs_periods[-1], {})
                equity_val = self._to_float(last_bs.get("equity_capital"))
                if equity_val and face_value:
                    try:
                        # Equity Capital in Cr, Face Value in INR. Count in Cr.
                        shares_outstanding = float(equity_val) / float(face_value)
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass

        share_price_block = self.company_metadata.get("price") or {}
        share_price = self._to_float(share_price_block.get("value"))
        if share_price is None:
            share_price = self._to_float(constants.get("share_price"))

        metrics_values = {}
        try:
            metrics_values = self.metrics_engine.compute_metric_values(
                income_statement=income_statement,
                balance_sheet=balance_sheet,
                shares_outstanding=shares_outstanding,
                share_price=share_price,
                metadata=self.company_metadata,
            )
        except Exception as exc:
            self.warnings.append(f"Internal metrics engine error: {exc}")
            log.exception("Error in compute_metric_values")
            # Continue with empty metrics_values to allow backfill

        try:
            # Backfill Market Cap if missing and computable
            existing_mcap = self._to_float(self.company_metadata.get("market_cap"))
            if existing_mcap is None and share_price and shares_outstanding:
                try:
                    mcap_val = float(share_price) * float(shares_outstanding)
                    self.company_metadata["market_cap"] = round(mcap_val, 2)
                    metrics_values["market_cap"] = MetricValue(
                        value=round(mcap_val, 2),
                        unit="Cr",
                        statement_id=None,
                        computed=True,
                        reason="Derived from Price * Shares (in Cr)"
                    )
                except (ValueError, TypeError):
                    pass
            elif existing_mcap is not None:
                 metrics_values["market_cap"] = MetricValue(
                    value=float(existing_mcap),
                    unit="Cr",
                    statement_id=None,
                    computed=False
                 )
            
            # --- STRATEGIC BACKFILL: Use Scraped Ratios if Computed are Missing ---
            # This ensures we display PE, ROE, ROCE even if 'Price' or 'Equity' derivation failed.
            ratios_table = (self.canonical_financials or {}).get("ratios_table", {})
            if ratios_table:
                # Get latest period with data
                latest_scraped_p = sorted(ratios_table.keys(), key=self.metrics_engine._period_sort_key)[-1]
                scraped_row = ratios_table.get(latest_scraped_p, {})

                # Map Fundametrics Metric Key -> Scraped Ratio Key (from FundametricsRatiosEngine)
                backfill_map = {
                    "fundametrics_pe_ratio": "price_to_earnings",
                    "fundametrics_return_on_equity": "return_on_equity",
                    "fundametrics_return_on_capital_employed": "return_on_capital_employed",
                    "fundametrics_dividend_yield": "dividend_yield",
                    "fundametrics_book_value_per_share": "book_value_per_share",
                    "fundametrics_debt_to_equity": "debt_to_equity"
                }

                for metric_key, scraped_key in backfill_map.items():
                    current_metric = metrics_values.get(metric_key)
                    # If current is missing or explicitly None value
                    if not current_metric or current_metric.value is None:
                        scraped_val = scraped_row.get(scraped_key)
                        final_val = self._to_float(scraped_val)
                              
                        if final_val is not None:
                             metrics_values[metric_key] = MetricValue(
                                 value=float(final_val),
                                 unit="x" if any(x in metric_key for x in ["ratio", "pe", "debt"]) else "%",
                                 statement_id=None,
                                 computed=False,
                                 reason=f"Backfilled from {latest_scraped_p} scraped table"
                             )
                
            # --- SECONDARY BACKFILL: Global Constants (High Priority Snapshot) ---
            constants_backfill_map = {
                "fundametrics_pe_ratio": "pe_ratio",
                "fundametrics_return_on_equity": "roe",
                "fundametrics_return_on_capital_employed": "roce",
                "fundametrics_dividend_yield": "dividend_yield",
                "fundametrics_book_value_per_share": "book_value",
                "fundametrics_market_cap": "market_cap",
                "fundametrics_debt_to_equity": "debt_to_equity"
            }
            
            const_data = self.company_metadata.get("constants", {}) or self.company_metadata
            for metric_key, const_key in constants_backfill_map.items():
                current_metric = metrics_values.get(metric_key)
                is_missing = not current_metric or current_metric.value is None
                
                if is_missing:
                    val = self._to_float(const_data.get(const_key))
                    if val is not None:
                        metrics_values[metric_key] = MetricValue(
                            value=float(val),
                            unit="Cr" if "market_cap" in metric_key else ("x" if any(x in metric_key for x in ["pe", "debt"]) else ("INR" if "book" in metric_key else "%")),
                            statement_id=None,
                            computed=False,
                            reason="Backfilled from source snapshot constants"
                        )
        except Exception as exc:
            self.warnings.append(f"Error in backfill logic: {exc}")
            log.exception("Error in strategic backfill")

        try:
            ratios_values = self.ratios_engine.compute(
                income_statement=income_statement,
                balance_sheet=balance_sheet,
                metadata=self.company_metadata,
            )
        except Exception as exc:
            self.warnings.append(f"Error computing ratios: {exc}")
            log.exception("Error in ratios_engine.compute")
            ratios_values = {}

        periodicity = self._detect_periodicity(latest_period)

        return {
            "metrics": metrics_values,
            "ratios": ratios_values,
            "period": latest_period,
            "periodicity": periodicity,
            "latest_row": latest_row,
        }
    
    def build(self) -> Dict[str, Any]:
        """
        Construct the final API response.
        
        Returns:
            Dict containing the complete API response
        """
        # Calculate data freshness
        freshness = self._calculate_data_freshness()
        
        metrics_bundle = self._compute_metrics()
        metrics_values = metrics_bundle.get("metrics", {})
        ratios_values = metrics_bundle.get("ratios", {})
        latest_row = metrics_bundle.get("latest_row", {})

        metrics_output = {
            key: self._emit_metric(metric)
            for key, metric in metrics_values.items()
        }
        ratios_output = {
            key: self._emit_metric(metric)
            for key, metric in ratios_values.items()
        }

        integrity = self._resolve_integrity(metrics_output, ratios_output)

        latest_financials = {
            key: self._emit_metric(metric)
            for key, metric in latest_row.items()
            if isinstance(metric, MetricValue)
        }
        if metrics_bundle.get("period"):
            latest_financials["period"] = metrics_bundle["period"]
            latest_financials["periodicity"] = metrics_bundle.get("periodicity")

        metadata_block = {
            'data_freshness': freshness.freshness_status,
            'as_of_date': freshness.as_of_date,
            'data_sources': self._unique_sources(),
            'computed_by': 'fundametrics-metrics-engine',
            'metrics_origin': 'fundametrics_internal',
            'version': '1.0.0',
            'fundametrics_disclaimer': self.FUNDAMETRICS_DISCLAIMER.copy(),
            **(self.company_metadata or {})
        }

        response = {
            'symbol': self.symbol,
            'company': {
                'name': self.company_name,
                'sector': self.sector,
                'about': self.about,
            },
            'management': self.management,
            'news': self.news,
            'financials': {
                'latest': latest_financials,
                'metrics': metrics_output,
                'ratios': ratios_output,
                'income_statement': {
                    p: {m: self._emit_metric(v) for m, v in row.items()}
                    for p, row in (self.canonical_financials.get('income_statement', {}) if self.canonical_financials else {}).items()
                },
                'balance_sheet': {
                    p: {m: self._emit_metric(v) for m, v in row.items()}
                    for p, row in (self.canonical_financials.get('balance_sheet', {}) if self.canonical_financials else {}).items()
                },
                'cash_flow': {
                    p: {m: self._emit_metric(v) for m, v in row.items()}
                    for p, row in (self.canonical_financials.get('cash_flow', {}) if self.canonical_financials else {}).items()
                },
                'ratios_table': {
                    p: {m: self._emit_metric(v) for m, v in row.items()}
                    for p, row in (self.canonical_financials.get('ratios', {}) if self.canonical_financials else {}).items()
                },
            },
            'ai_summary': self._generate_basic_summary(metrics_values, ratios_values),
            'signals': self._generate_basic_signals(metrics_values, ratios_values),
            'shareholding': {
                'status': 'unavailable',
                'summary': {},
                'insights': [],
                'history': [],
            },
            'metadata': metadata_block,
            'metrics': {
                'integrity': integrity,
                'values': metrics_output,
                'ratios': ratios_output,
            },
        }

        # --- AUGMENT HISTORICAL RATIOS ---
        if self.canonical_financials:
            income = self.canonical_financials.get('income_statement', {})
            balance = self.canonical_financials.get('balance_sheet', {})
            ratios_table = response['financials']['ratios_table']
            
            for period in income.keys():
                if period not in ratios_table:
                    ratios_table[period] = {}
                
                row_inc = income.get(period, {})
                row_bal = balance.get(period, {})
                
                rev = row_inc.get('revenue')
                op = row_inc.get('operating_profit')
                ni = row_inc.get('net_income')
                
                # OPM & NPM
                if 'operating_profit_margin' not in ratios_table[period] and rev and op:
                    r_opm = self.metrics_engine.calc_operating_margin(rev, op)
                    if r_opm.value is not None:
                        ratios_table[period]['operating_profit_margin'] = self._emit_metric(r_opm)
                
                if 'net_profit_margin' not in ratios_table[period] and rev and ni:
                    r_npm = self.metrics_engine.calc_net_margin(rev, ni)
                    if r_npm.value is not None:
                        ratios_table[period]['net_profit_margin'] = self._emit_metric(r_npm)

                # ROE Estimation
                if 'roe' not in ratios_table[period] and ni:
                    # Try to get equity (Cap + Reserves)
                    cap = row_bal.get('equity_capital')
                    res = row_bal.get('reserves')
                    if cap and res and cap.value is not None and res.value is not None:
                        equity = cap.value + res.value
                        if equity > 0:
                            roe_val = round((ni.value / equity) * 100, 2)
                            ratios_table[period]['roe'] = self._emit_metric(MetricValue(roe_val, "%", None, True))
                
                # ROCE Estimation
                if 'roce' not in ratios_table[period] and op:
                    # Use Operating Profit as proxy for EBIT if EBIT missing
                    cap = row_bal.get('equity_capital')
                    res = row_bal.get('reserves')
                    bor = row_bal.get('borrowings')
                    if cap and res and bor and cap.value is not None and res.value is not None and bor.value is not None:
                        cap_employed = cap.value + res.value + bor.value
                        if cap_employed > 0:
                            roce_val = round((op.value / cap_employed) * 100, 2)
                            ratios_table[period]['roce'] = self._emit_metric(MetricValue(roce_val, "%", None, True))

                # Face Value Injection
                if 'face_value' not in ratios_table[period]:
                    fv = self.company_metadata.get('constants', {}).get('face_value')
                    if fv:
                        try:
                            ratios_table[period]['face_value'] = self._emit_metric(MetricValue(float(fv), "INR", None, True))
                        except (ValueError, TypeError): pass

                # Book Value Estimation
                if 'book_value' not in ratios_table[period]:
                    cap = row_bal.get('equity_capital')
                    res = row_bal.get('reserves')
                    fv = self.company_metadata.get('constants', {}).get('face_value')
                    
                    if cap and res and fv and cap.value is not None and res.value is not None:
                        try:
                            fv_val = float(fv)
                            if fv_val > 0 and cap.value > 0:
                                # Book Value = ((Equity + Reserves) / (Equity / Face Value))
                                # Simplified: (Equity + Reserves) * Face Value / Equity
                                total_equity = cap.value + res.value
                                bv_val = round((total_equity * fv_val) / cap.value, 2)
                                ratios_table[period]['book_value'] = self._emit_metric(MetricValue(bv_val, "INR", None, True))
                        except (ValueError, ZeroDivisionError, TypeError):
                            pass

                # PE Ratio Estimation (Historical)
                # Using CURRENT price vs Historical EPS (Static Price PE)
                price_block = self.company_metadata.get('price') or {}
                curr_price = price_block.get('value')
                if curr_price is None:
                    constants = self.company_metadata.get('constants', {})
                    curr_price = constants.get('share_price') or constants.get('current_price')
                eps_metric = row_inc.get('eps')
                if curr_price and eps_metric and eps_metric.value and eps_metric.value > 0:
                    pe_val = round(float(curr_price) / float(eps_metric.value), 2)
                    ratios_table[period]['price_to_earnings'] = self._emit_metric(MetricValue(pe_val, "x", None, True))

                # Dividend Yield Estimation
                div_payout = row_inc.get('dividend_payout_pct')
                if curr_price and eps_metric and div_payout and eps_metric.value and div_payout.value:
                    try:
                        dps = (float(eps_metric.value) * float(div_payout.value)) / 100.0
                        yield_val = round((dps / float(curr_price)) * 100, 2)
                        ratios_table[period]['dividend_yield'] = self._emit_metric(MetricValue(yield_val, "%", None, True))
                    except (ValueError, ZeroDivisionError, TypeError):
                        pass
        # --- END AUGMENT ---

        metrics_context = {
            'period': metrics_bundle.get('period'),
            'periodicity': metrics_bundle.get('periodicity') or ('quarterly' if self._quarterly_periods else 'annual'),
            'engine': 'FundametricsMetricsEngine'
        }
        response['metadata']['metrics_context'] = metrics_context

        response['metadata']['quarterly_data'] = {
            'available': bool(self._quarterly_periods),
            'latest_period': self._quarterly_periods[-1] if self._quarterly_periods else None,
            'periods_available': len(self._quarterly_periods),
        }

        summary = self._build_shareholding_payload()
        response['shareholding'] = summary
        response['metadata']['shareholding_status'] = summary.get('status', 'unavailable')

        if self.warnings:
            response['metadata']['warnings'] = self.warnings

        return response

    def _resolve_integrity(self, metrics_output: Dict[str, Dict[str, Any]], ratios_output: Dict[str, Dict[str, Any]]) -> str:
        entries = [
            entry
            for entry in list(metrics_output.values()) + list(ratios_output.values())
            if isinstance(entry, dict)
        ]

        if not entries:
            return "partial"

        for entry in entries:
            value = entry.get("value")
            if value is None:
                return "partial"

            confidence = entry.get("confidence")
            if not isinstance(confidence, dict):
                return "partial"
            score = confidence.get("score")
            if not isinstance(score, int):
                try:
                    score = int(score)
                except (TypeError, ValueError):
                    return "partial"
            if score < 60:
                return "partial"

        return "verified"

    def _build_shareholding_payload(self) -> Dict[str, Any]:
        canonical = self.canonical_financials or {}
        exchange = canonical.get("meta", {}).get("exchange", "unknown")

        if not hasattr(self, 'raw_shareholding') or not self.raw_shareholding:
            return {
                "status": "unavailable",
                "summary": {},
                "insights": [],
            }

        try:
            normalized = self.shareholding_audit.normalize_shareholding_data(self.raw_shareholding)
        except Exception as exc:
            self.warnings.append(f"Shareholding normalization failed: {exc}")
            log.exception("Shareholding normalization error")
            return {
                "status": "unavailable",
                "summary": {},
                "insights": [],
            }

        anomalies = self.shareholding_audit.get_anomalies()
        for anomaly in anomalies:
            self.warnings.append(
                f"Shareholding {anomaly.severity}: {anomaly.issue} ({anomaly.period})"
            )

        summary_raw = self.shareholding_audit.get_shareholding_summary(normalized)
        summary_payload = summary_raw if isinstance(summary_raw, dict) else {}

        insights_raw = self.shareholding_engine.generate_insights(normalized)
        insights = self._normalise_insights(insights_raw)

        snapshots: List[ShareholdingSnapshot] = []
        for period, holders in normalized.items():
            cleaned_holders = {
                key: float(value)
                for key, value in holders.items()
                if value is not None
            }
            snapshots.append(
                ShareholdingSnapshot(
                    exchange=exchange,
                    period_label=period,
                    as_of=infer_snapshot_date(period),
                    holders=cleaned_holders,
                )
            )

        if not snapshots:
            return {
                "status": "unavailable",
                "summary": {},
                "insights": insights,
            }

        snapshots.sort(key=lambda snap: snap.as_of)
        latest = snapshots[-1]
        previous = snapshots[-2] if len(snapshots) > 1 else None
        delta_values, delta_reason = compute_holder_delta(latest, previous)

        latest_normalised = normalized.get(latest.period_label, {})
        coverage_total = len(latest_normalised) if latest_normalised else 0
        coverage_present = sum(1 for value in (latest_normalised or {}).values() if value is not None)
        coverage_ratio = (coverage_present / coverage_total) if coverage_total else 0.0

        def _as_datetime(value: Any) -> datetime:
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    return value.replace(tzinfo=timezone.utc)
                return value
            # Handle date objects
            return datetime.combine(value, datetime.min.time()).replace(tzinfo=timezone.utc)

        generated_at = _as_datetime(latest.as_of)
        now = datetime.now(timezone.utc)

        holders_payload = {}
        for holder, value in latest.holders.items():
            payload = {
                "value": value,
                "unit": "%",
            }
            payload["confidence"] = self._shareholding_confidence(
                value=value,
                generated_at=generated_at,
                coverage_ratio=coverage_ratio,
                now=now,
            )
            holders_payload[holder] = payload

        def _delta_confidence() -> Optional[Dict[str, Any]]:
            if delta_values is None:
                return None
            if previous is None:
                return self._shareholding_confidence(
                    value=0.0,
                    generated_at=generated_at,
                    coverage_ratio=coverage_ratio,
                    now=now,
                )
            previous_normalised = normalized.get(previous.period_label, {})
            prev_total = len(previous_normalised) if previous_normalised else 0
            prev_present = sum(1 for value in (previous_normalised or {}).values() if value is not None)
            combined_ratio = min(
                coverage_ratio,
                (prev_present / prev_total) if prev_total else 0.0,
            )
            return self._shareholding_confidence(
                value=0.0,
                generated_at=generated_at,
                coverage_ratio=combined_ratio,
                now=now,
            )

        delta_payload: Optional[Dict[str, Any]]
        if delta_values is None:
            delta_payload = {
                "values": None,
                "reason": delta_reason or "Incompatible shareholding snapshots",
                "confidence": None,
            }
        else:
            delta_confidence = _delta_confidence()
            delta_values_payload: Dict[str, Any] = {}
            for holder, value in delta_values.items():
                delta_values_payload[holder] = {
                    "value": value,
                    "unit": "%",
                    "confidence": self._shareholding_confidence(
                        value=value,
                        generated_at=generated_at,
                        coverage_ratio=coverage_ratio,
                        now=now,
                    ),
                }
            delta_payload = {
                "values": delta_values_payload,
                "reason": None,
                "confidence": delta_confidence,
            }

        history_payload = []
        for snap in sorted(snapshots, key=lambda s: s.as_of, reverse=True):
            history_payload.append({
                "period": snap.period_label,
                "as_of": snap.as_of.isoformat(),
                **snap.holders
            })

        return {
            "status": "available",
            "period": latest.period_label,
            "as_of": latest.as_of.isoformat(),
            "exchange": latest.exchange,
            "holders": holders_payload,
            "delta": delta_payload,
            "summary": summary_payload,
            "insights": insights,
            "history": history_payload,
        }

    def _shareholding_confidence(
        self,
        *,
        value: float,
        generated_at: datetime,
        coverage_ratio: float,
        now: datetime,
    ) -> Dict[str, Any]:
        metric = MetricValue(
            value=value,
            unit="%",
            statement_id=None,
            computed=True,
        )
        metric.confidence_inputs = {
            "source_type": "exchange",
            "generated_at": generated_at.isoformat(),
            "ttl_hours": self._SHAREHOLDING_TTL_HOURS,
            "statement_status": "single",
            "completeness_ratio": coverage_ratio,
        }
        metric.confidence = compute_confidence(metric, None, now)
        return metric.confidence.to_dict()

    @staticmethod
    def _normalise_insights(insights: Any) -> List[Dict[str, Any]]:
        """Return insights as a list of {title, description} for the frontend."""
        if not isinstance(insights, dict):
            return []

        normalised = []
        
        # 1. Promoter Trend
        p_trend = insights.get("promoter_trend", "unknown")
        if p_trend != "unknown":
            titles = {"increasing": "Promoter Accrual", "decreasing": "Promoter Dilution", "flat": "Promoter Stability"}
            descs = {
                "increasing": "Promoters are actively increasing their stake, signaling high internal confidence.",
                "decreasing": "Recent filings reveal a reduction in promoter holding, warranting observation.",
                "flat": "Promoter holding has remained consistent over the analysis horizon."
            }
            normalised.append({"title": titles.get(p_trend, "Promoter Trend"), "description": descs.get(p_trend, "Stable ownership profile detected.")})

        # 2. Institutional Bias
        i_bias = insights.get("institutional_bias", "unknown")
        if i_bias != "unknown":
            titles = {"bullish": "Institutional Inflow", "bearish": "Institutional Outflow", "neutral": "Institutional Neutral"}
            descs = {
                "bullish": "Institutional investors (FII/DII) are accumulating shares in recent cycles.",
                "bearish": "Smart money is currently reducing its exposure to this symbol.",
                "neutral": "Institutional positions are holding steady with no significant bias."
            }
            normalised.append({"title": titles.get(i_bias, "Institutional Flow"), "description": descs.get(i_bias, "Market-making institutions are maintaining balanced portfolios.")})

        # 3. Retail Risk
        r_risk = insights.get("retail_risk", "unknown")
        if r_risk != "unknown":
            titles = {"high": "Retail Saturation", "medium": "Elevated Retail Interest", "low": "Low Retail Risk"}
            descs = {
                "high": "High retail participation without institutional support may increase price volatility.",
                "medium": "Growing retail interest observed alongside institutional redistribution.",
                "low": "Retail participation is well-balanced by strategic and institutional holdings."
            }
            normalised.append({"title": titles.get(r_risk, "Retail Distribution"), "description": descs.get(r_risk, "Public holding levels are consistent with sector benchmarks.")})

        # 4. Stability Score
        score = insights.get("ownership_stability_score")
        if score is not None:
            status = "Excellent" if score > 85 else "High" if score > 70 else "Moderate" if score > 50 else "Watchlist"
            normalised.append({
                "title": f"Stability: {status}",
                "description": f"Overall ownership ledger integrity is scored at {score}/100 based on recent volatility."
            })

        return normalised

    def _unique_sources(self) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for item in self.data_sources:
            if item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered

    def _generate_basic_signals(self, metrics: Dict[str, MetricValue], ratios: Dict[str, MetricValue]) -> List[Dict[str, Any]]:
        """Generate rule-based signals for the company."""
        signals = []
        
        # 1. P/E Signal
        pe = ratios.get("price_to_earnings") or metrics.get("fundametrics_pe_ratio")
        if pe and pe.value:
            if pe.value > 50:
                signals.append({"label": "High Valuation", "severity": "warning", "description": f"Stock is trading at a high P/E ratio of {pe.value:.1f}x."})
            elif pe.value < 15:
                signals.append({"label": "Attractive Valuation", "severity": "success", "description": f"Stock is trading at a low P/E ratio of {pe.value:.1f}x."})

        # 2. Debt Signal
        de = ratios.get("debt_to_equity") or metrics.get("fundametrics_debt_to_equity")
        if de and de.value:
            if de.value > 1.5:
                signals.append({"label": "High Leverage", "severity": "danger", "description": f"Debt-to-Equity ratio of {de.value:.1f} is above healthy levels."})
            elif de.value < 0.5:
                signals.append({"label": "Low Debt", "severity": "success", "description": f"Company maintains a conservative debt profile ({de.value:.1f}x)."})

        # 3. ROE Signal
        roe = ratios.get("return_on_equity") or metrics.get("fundametrics_return_on_equity")
        if roe and roe.value:
            if roe.value > 20:
                signals.append({"label": "Strong ROE", "severity": "success", "description": f"Efficient capital usage with {roe.value:.1f}% Return on Equity."})
            elif roe.value < 8:
                signals.append({"label": "Weak ROE", "severity": "warning", "description": f"Sub-par capital efficiency with {roe.value:.1f}% Return on Equity."})

        return signals

    def _generate_basic_summary(self, metrics: Dict[str, MetricValue], ratios: Dict[str, MetricValue]) -> Dict[str, Any]:
        """Generate a basic text summary of the company's financial health."""
        paragraphs = []
        
        # Valuation Para
        pe = ratios.get("price_to_earnings") or metrics.get("fundametrics_pe_ratio")
        p0 = f"{self.company_name} is currently analyzed with a focus on its financial metrics. "
        if pe and pe.value:
            p0 += f"The stock is trading at a price-to-earnings multiple of {pe.value:.1f}x. "
        else:
            p0 += "Valuation multiples are currently being computed based on latest price data. "
        paragraphs.append(p0)

        # Efficiency Para
        roe = ratios.get("return_on_equity") or metrics.get("fundametrics_return_on_equity")
        margin = ratios.get("operating_margin") or metrics.get("fundametrics_operating_margin")
        p1 = ""
        if roe and roe.value:
            status = "efficient" if roe.value > 15 else "stable" if roe.value > 8 else "improving"
            p1 += f"Return on Equity stands at {roe.value:.1f}%, reflecting a {status} capital allocation strategy. "
        if margin and margin.value:
            p1 += f"The operating margin of {margin.value:.1f}% indicates the core profitability of the business."
        if p1:
            paragraphs.append(p1)

        # Conclusion Para
        paragraphs.append("Investors should monitor historical growth trends and sector benchmarks for a full context.")

        return {
            "paragraphs": paragraphs,
            "generated": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "historical-only"
        }
