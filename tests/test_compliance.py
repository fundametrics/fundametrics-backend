"""
Compliance Audit Tests
Scans code and data for forbidden third-party references and derived metrics
"""

import pytest
import json
import os
import re
from pathlib import Path


class TestComplianceAudit:
    """Test suite for legal compliance and IP protection"""

    @pytest.fixture
    def forbidden_strings(self):
        """List of forbidden third-party references and derived metric usage"""
        return [
            "screener.in",
            "screener", 
            "moneycontrol.com",
            "moneycontrol",
            "trendlyne.com", 
            "trendlyne"
        ]

    @pytest.fixture
    def forbidden_metrics(self):
        """List of forbidden derived metrics that should not be exposed (non-Fundametrics branded)"""
        return [
            "ROE",
            "ROCE", 
            "OPM%",
            "P/E",
            "P/B",
            "Tax%",
            "Dividend Payout%"
        ]

    @pytest.fixture
    def forbidden_field_names(self):
        """List of forbidden field names that should not be used in code"""
        return [
            "Sales",  # Should be mapped to revenue in METRIC_MAP only
            "Turnover",
            "PAT", 
            "PBT", 
            "OPM",
            "Net Profit",
            "Gross Profit", 
            "EBITDA"
        ]

    @pytest.fixture
    def legitimate_fundametrics_metrics(self):
        """List of legitimate Fundametrics-branded metrics that are allowed"""
        return [
            "fundametrics_eps",
            "fundametrics_operating_margin",
            "fundametrics_return_on_equity",
            "fundametrics_market_cap",
            "fundametrics_growth_rate_internal"
        ]

    @pytest.fixture 
    def project_root(self):
        """Get project root directory"""
        return Path(__file__).parent.parent

    def scan_file_for_forbidden_strings(self, file_path: Path, forbidden_strings: list) -> dict:
        """Scan a single file for forbidden strings"""
        violations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for forbidden in forbidden_strings:
                # Case-insensitive search for whole words
                pattern = r'\b' + re.escape(forbidden) + r'\b'
                matches = re.finditer(pattern, content, re.IGNORECASE)
                
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    violations.append({
                        'file': str(file_path),
                        'line': line_num,
                        'forbidden_string': forbidden,
                        'context': content.split('\n')[line_num-1].strip()
                    })
        except Exception as e:
            # Skip files that can't be read (binary files, etc.)
            pass
            
        return violations

    def test_no_forbidden_strings_in_python_code(self, project_root, forbidden_strings, forbidden_metrics, legitimate_fundametrics_metrics):
        """Scan Python source files for forbidden third-party references"""
        violations = []
        
        # Scan all Python files
        for py_file in project_root.rglob("*.py"):
            # Skip test files, virtual environment, data directories, and export/sample files
            if ("tests" in str(py_file) or 
                "venv" in str(py_file) or 
                "__pycache__" in str(py_file) or
                "data" in str(py_file) or
                "export" in str(py_file) or
                "extract" in str(py_file) or
                py_file.name.startswith(("export_", "sample_", "test_", "extract_", "mrf_", "mc_", "trendlyne_", "fetch_"))):
                continue
                
            # Check for third-party site references
            with open(py_file, 'r') as f:
                content = f.read()
            
            for forbidden in forbidden_strings:
                # Skip import statements, class definitions, and variable instantiations that contain third-party names (legitimate)
                lines = content.split('\n')
                for line_num, line in enumerate(lines, 1):
                    # Skip import statements
                    if line.strip().startswith('from ') or line.strip().startswith('import '):
                        continue
                    
                    # Skip class definitions (legitimate class names)
                    if line.strip().startswith('class ') and 'Scraper' in line or line.strip().startswith('class ') and 'Parser' in line:
                        continue
                    
                    # Skip variable instantiations of parser/scraper classes (legitimate usage)
                    if ('Parser(' in line or 'Scraper(' in line) and '=' in line:
                        continue
                    
                    # Check for forbidden strings in other contexts
                    if forbidden.lower() in line.lower():
                        violations.append({
                            'file': str(py_file),
                            'line': line_num,
                            'forbidden_string': forbidden,
                            'context': line.strip()
                        })
            
            # Check for derived metrics exposure (except legitimate Fundametrics metrics and METRIC_MAP keys)
            with open(py_file, 'r') as f:
                content = f.read()
            
            for metric in forbidden_metrics:
                # Use word boundaries to avoid false positives like "process" containing "ROCE"
                pattern = rf'\b{re.escape(metric)}\b'
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    line_content = content.split('\n')[line_num-1].strip()
                    
                    # Skip if it's in a METRIC_MAP dictionary
                    if 'METRIC_MAP' in line_content and ':' in line_content:
                        continue
                    
                    # Skip if it's part of a legitimate Fundametrics metric
                    for fundametrics_metric in legitimate_fundametrics_metrics:
                        if fundametrics_metric in line_content:
                            break
                    else:
                        # Skip if it's in comments or docstrings
                        if line_content.startswith('#') or line_content.startswith('"""'):
                            continue
                        
                        violations.append({
                            'file': str(py_file),
                            'line': line_num,
                            'forbidden_string': metric,
                            'context': line_content
                        })
        
        # Assert no violations found
        assert violations == [], f"Found forbidden strings in Python code: {violations}"

    def test_no_forbidden_strings_in_config_files(self, project_root, forbidden_strings):
        """Scan configuration files for forbidden third-party references"""
        violations = []
        
        # Scan YAML, JSON, and other config files (excluding data directories)
        config_extensions = ["*.yaml", "*.yml", "*.json", "*.toml", "*.ini"]
        
        for ext in config_extensions:
            for config_file in project_root.rglob(ext):
                # Skip data directories, sample data, and exported files
                if ("venv" in str(config_file) or 
                    "__pycache__" in str(config_file) or
                    "data" in str(config_file) or
                    "export" in str(config_file) or
                    config_file.name.startswith(("MRF_", "ONGC_", "trendlyne_", "reliance_", "mrf_"))):
                    continue
                    
                file_violations = self.scan_file_for_forbidden_strings(config_file, forbidden_strings)
                violations.extend(file_violations)
        
        assert violations == [], f"Found forbidden strings in config files: {violations}"

    def test_no_forbidden_strings_in_documentation(self, project_root, forbidden_strings):
        """Scan documentation files for forbidden third-party references"""
        violations = []
        
        # Scan markdown and text documentation (excluding data directories and certain files)
        doc_extensions = ["*.md", "*.txt", "*.rst"]
        
        for ext in doc_extensions:
            for doc_file in project_root.rglob(ext):
                # Skip data directories, sample files, and specific documentation files
                if ("venv" in str(doc_file) or 
                    "__pycache__" in str(doc_file) or
                    "data" in str(doc_file) or
                    doc_file.name.startswith(("MRF_", "ONGC_", "trendlyne_", "reliance_", "mrf_", "mc_")) or
                    doc_file.name in ["HARDENING.md", "README.md"]):  # Exclude specific files
                    continue
                    
                file_violations = self.scan_file_for_forbidden_strings(doc_file, forbidden_strings)
                violations.extend(file_violations)
        
        assert violations == [], f"Found forbidden strings in documentation: {violations}"

    def test_api_responses_use_fundametrics_branding(self, project_root):
        """Verify API schemas use Fundametrics branding for metrics"""
        schemas_file = project_root / "api" / "schemas.py"
        
        with open(schemas_file, 'r') as f:
            content = f.read()
        
        # Check for Fundametrics-branded metric schemas
        assert "FundametricsMetricRead" in content, "Missing FundametricsMetricRead schema"
        assert "fundametrics_metrics" in content, "Missing fundametrics_metrics field"
        
        # Verify Fundametrics metrics are properly branded
        fundametrics_metrics = [
            "fundametrics_operating_margin",
            "fundametrics_return_on_equity", 
            "fundametrics_eps",
            "fundametrics_market_cap",
            "fundametrics_growth_rate_internal"
        ]
        
        for metric in fundametrics_metrics:
            assert metric in content, f"Missing Fundametrics metric: {metric}"

    def test_database_schema_separates_raw_from_computed(self, project_root):
        """Verify database schema separates raw facts from computed metrics"""
        schema_file = project_root / "db" / "schema.sql"
        
        with open(schema_file, 'r') as f:
            content = f.read()
        
        # Check for separate tables
        assert "raw_financials" in content or "company_facts" in content, "Missing raw facts table"
        assert "computed_metrics" in content, "Missing computed metrics table"
        
        # Verify no third-party metric names in schema
        forbidden_metrics = ["roe", "roce", "opm", "pe_ratio", "pb_ratio"]
        for metric in forbidden_metrics:
            assert metric not in content.lower(), f"Found forbidden metric in schema: {metric}"

    def test_parser_outputs_contain_only_raw_facts(self, project_root):
        """Verify parsers output only raw facts, no derived metrics"""
        parsers_dir = project_root / "scraper" / "sources"
        
        forbidden_metrics = ["ROE", "ROCE", "OPM%", "P/E", "EPS", "Tax%", "Dividend Payout%"]
        
        for parser_file in parsers_dir.glob("*_parser.py"):
            with open(parser_file, 'r') as f:
                content = f.read()
            
            # Check that parsers don't return derived metrics
            for metric in forbidden_metrics:
                assert metric not in content, f"Parser {parser_file.name} contains forbidden metric: {metric}"

    def test_log_messages_are_anonymized(self, project_root):
        """Verify log messages don't contain third-party site names"""
        log_utils_file = project_root / "scraper" / "utils" / "logger.py"
        
        with open(log_utils_file, 'r') as f:
            content = f.read()
        
        # Check for third-party references in logging
        third_party_sites = ["screener.in", "moneycontrol.com", "trendlyne.com"]
        
        for site in third_party_sites:
            assert site not in content.lower(), f"Logger contains third-party reference: {site}"

    def test_fundametrics_metrics_definitions_exist(self, project_root):
        """Verify Fundametrics metrics definitions file exists and is properly formatted"""
        metrics_file = project_root / "fundametrics_metrics_definitions.md"
        
        assert metrics_file.exists(), "Fundametrics metrics definitions file missing"
        
        with open(metrics_file, 'r') as f:
            content = f.read()
        
        # Check for proper Fundametrics branding
        assert "Fundametrics" in content, "Missing Fundametrics branding in metrics definitions"
        assert "proprietary" in content.lower(), "Missing proprietary claim in metrics definitions"
        
        # Verify no third-party references
        third_party_refs = ["screener", "moneycontrol", "trendlyne"]
        for ref in third_party_refs:
            assert ref not in content.lower(), f"Metrics definitions contain third-party reference: {ref}"

    def test_neutral_field_naming_in_parsers(self, project_root, forbidden_field_names):
        """Verify parsers use neutral, database-style field names"""
        parsers_dir = project_root / "scraper" / "sources"
        
        # Expected neutral field names for financial parsers
        financial_fields = [
            "revenue", "expenses", "net_income", "operating_profit",
            "equity_capital", "reserves", "total_assets", "fixed_assets"
        ]
        
        # Expected neutral field names for profile parsers
        profile_fields = [
            "sector", "industry", "management", "description"
        ]
        
        for parser_file in parsers_dir.glob("*_parser.py"):
            with open(parser_file, 'r') as f:
                content = f.read()
            
            # Screener parser should have financial fields
            if "screener" in parser_file.name.lower():
                for field in financial_fields:
                    assert field in content, f"Screener parser missing neutral financial field: {field}"
                
                # Check that METRIC_MAP exists and maps forbidden names to neutral ones
                assert "METRIC_MAP" in content, f"Screener parser missing METRIC_MAP"
                
                # Verify METRIC_MAP contains mappings from forbidden to neutral names
                for forbidden_field in forbidden_field_names:
                    if forbidden_field == "Sales":  # This should be mapped to revenue
                        assert '"Sales": "revenue"' in content, "METRIC_MAP missing Sales -> revenue mapping"
            
            # Profile parsers (moneycontrol, trendlyne) should have profile fields
            if "moneycontrol" in parser_file.name.lower() or "trendlyne" in parser_file.name.lower():
                for field in profile_fields:
                    assert field in content, f"Profile parser {parser_file.name} missing neutral field: {field}"
            
            # Check that forbidden field names are not used outside METRIC_MAP
            for field in forbidden_field_names:
                # Find all occurrences of the forbidden field
                lines = content.split('\n')
                in_metric_map = False
                
                for i, line in enumerate(lines, 1):
                    # Track if we're inside METRIC_MAP
                    if 'METRIC_MAP' in line and '{' in line:
                        in_metric_map = True
                        continue
                    elif in_metric_map and '}' in line and ':' not in line:
                        in_metric_map = False
                        continue
                    
                    if field in line:
                        # Allow in comments and docstrings
                        if line.strip().startswith('#') or line.strip().startswith('"""'):
                            continue
                        
                        # Allow if inside METRIC_MAP dictionary
                        if in_metric_map and ('"' + field + '"' in line or "'" + field + "'" in line):
                            continue
                        
                        # Otherwise it's a violation
                        assert False, f"Parser {parser_file.name} uses forbidden field '{field}' outside METRIC_MAP at line {i}: {line.strip()}"
