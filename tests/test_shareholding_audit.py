"""
Tests for the Fundametrics Shareholding Audit module.
"""

import unittest
from scraper.core.shareholding_audit import ShareholdingAudit, ShareholdingData

class TestShareholdingAudit(unittest.TestCase):
    def setUp(self):
        self.audit = ShareholdingAudit()
    
    def test_normalize_basic_data(self):
        """Test basic normalization of shareholding data"""
        raw_data = {
            "2024-Q1": {
                "Promoter": 65.2,
                "Institutional Investors": 18.5,
                "Public Shareholding": 15.8,
                "Government": 0.5
            }
        }
        
        expected = {
            'promoter': 65.2,
            'institutional': 18.5,
            'public': 15.8,
            'government': 0.5,
            'other': None
        }
        
        result = self.audit.normalize_shareholding_data(raw_data)
        self.assertEqual(len(self.audit.anomalies), 0)
        self.assertIn("2024-Q1", result)
        self.assertDictEqual(result["2024-Q1"], expected)
    
    def test_invalid_period(self):
        """Test handling of invalid period formats"""
        raw_data = {
            "Invalid-Period": {
                "Promoter": 60.0,
                "Institutions": 20.0,
                "Public": 20.0
            }
        }
        
        result = self.audit.normalize_shareholding_data(raw_data)
        self.assertEqual(len(self.audit.anomalies), 1)
        self.assertEqual(self.audit.anomalies[0].issue, "Invalid period format")
        self.assertEqual(len(result), 0)
    
    def test_invalid_category(self):
        """Test handling of invalid shareholding categories"""
        raw_data = {
            "2024-Q1": {
                "Promoter": 60.0,
                "Invalid Category": 10.0,
                "Public": 30.0
            }
        }
        
        result = self.audit.normalize_shareholding_data(raw_data)
        # We expect 2 anomalies: one for invalid category and one for total validation
        self.assertEqual(len(self.audit.anomalies), 2)
        self.assertEqual(self.audit.anomalies[0].issue, "Invalid shareholding category")
        self.assertIsNone(result["2024-Q1"]["other"])
    
    def test_total_validation(self):
        """Test validation of shareholding totals"""
        # Total > 100.5%
        raw_data = {
            "2024-Q1": {
                "Promoter": 90.0,
                "Institutions": 20.0,
                "Public": 10.0
            }
        }
        
        result = self.audit.normalize_shareholding_data(raw_data)
        self.assertEqual(len(self.audit.anomalies), 1)
        self.assertIn("expected ~100%", self.audit.anomalies[0].details)
        self.assertTrue(self.audit.has_errors())
    
    def test_summary_generation(self):
        """Test generation of shareholding summary"""
        raw_data = {
            "2023-Q4": {
                "Promoter": 60.0,
                "Institutions": 20.0,
                "Public": 20.0
            },
            "2024-Q1": {
                "Promoter": 65.0,
                "Institutions": 18.0,
                "Public": 17.0
            }
        }
        
        normalized = self.audit.normalize_shareholding_data(raw_data)
        summary = self.audit.get_shareholding_summary(normalized)
        
        self.assertEqual(summary['period'], "2024-Q1")
        self.assertEqual(summary['total_percentage'], 100.0)
        self.assertTrue(summary['is_valid'])
        self.assertEqual(summary['anomaly_count'], 0)

if __name__ == "__main__":
    unittest.main()
