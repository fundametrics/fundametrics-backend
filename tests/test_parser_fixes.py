
import unittest
import sys
import os
sys.path.append(os.getcwd())
from scraper.sources.screener_parser import ScreenerParser

class TestScreenerIssue(unittest.TestCase):
    def test_off_by_one_alignment(self):
        # Simulation of the HTML that causes the issue
        # Note: the <thead> has 'Year 1', 'Year 2' but NO empty cell for the label column first (or it's just 'th's)
        # The parser extracts headers: ['Year 1', 'Year 2']
        # The row has: <td>Sales</td><td>100</td><td>200</td>
        
        html = """
        <html>
        <body>
            <section id="profit-loss">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Year 1</th>
                            <th>Year 2</th>
                            <th>Year 3</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Sales</td>
                            <td>100</td>
                            <td>200</td>
                            <td>300</td>
                        </tr>
                    </tbody>
                </table>
            </section>
        </body>
        </html>
        """
        
        parser = ScreenerParser(html, symbol="TEST")
        tables = parser.get_financial_tables()
        pl_table = tables['Profit & Loss']
        
        row = pl_table[0]
        print(f"Parsed Row: {row}")
        
        # CURRENT BUG EXPECTATION (What happens now):
        # 100 (Year 1 data) gets mapped to Year 2
        # We expect this to FAIL once we fix it.
        # But for reproduction, let's assert the BROKEN behavior to confirm it exists, 
        # or assert the CORRECT behavior and watch it fail.
        
        # Let's assert the CORRECT behavior, so this test fails now and passes later.
        self.assertEqual(row.get('Year 1'), 100.0, "Year 1 should be 100")
        self.assertEqual(row.get('Year 2'), 200.0, "Year 2 should be 200")
        self.assertEqual(row.get('Year 3'), 300.0, "Year 3 should be 300")

    def test_announcements_extraction(self):
        html = """
        <html>
        <body>
            <section id="documents">
                <h3>Announcements</h3>
                <ul class="list-links">
                    <li>
                        <div class="ink-600">Note: 05 Dec 2023</div>
                        <a href="/pdf/123">[Board Meeting] Financial Results</a>
                        <span class="ink-600">Dec 2023</span>
                    </li>
                    <li>
                        <a href="/pdf/456">Dividend Declaration</a>
                        <span class="date">Nov 2023</span>
                    </li>
                </ul>
            </section>
        </body>
        </html>
        """
        parser = ScreenerParser(html, symbol="TEST")
        announcements = parser.get_announcements()
        
        self.assertEqual(len(announcements), 2)
        self.assertEqual(announcements[0]['title'], "[Board Meeting] Financial Results")
        self.assertEqual(announcements[0]['link'], "/pdf/123")
        # Depending on which element it finds first or logic. The code splits span vs ink-600.
        # My mocked HTML has <div class="ink-600">Note...</div> and <span class="ink-600">Dec 2023</span>.
        # The parser: date_el = item.find('span', class_='ink-600') or item.find('span', class_='date')
        # So it should find the span.
        self.assertEqual(announcements[0]['date'], "Dec 2023")
        
        self.assertEqual(announcements[1]['title'], "Dividend Declaration")
        self.assertEqual(announcements[1]['date'], "Nov 2023")


if __name__ == '__main__':
    unittest.main()
