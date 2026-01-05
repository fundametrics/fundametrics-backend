import asyncio
import json
from scraper.core.fetcher import Fetcher
from scraper.sources.screener import ScreenerScraper
from scraper.sources.trendlyne import TrendlyneScraper
from scraper.core.api_response_builder import FundametricsResponseBuilder

async def test_mrf():
    print('🚀 Starting MRF data pipeline test...')
    fetcher = Fetcher()
    screener = ScreenerScraper(fetcher)
    
    try:
        # Fetch financial data
        print('\n📊 Fetching financial data...')
        financial_data = await screener.scrape_stock('MRF')
        
        # Fetch company profile
        print('🏢 Fetching company profile...')
        trendlyne = TrendlyneScraper(fetcher)
        profile_data = await trendlyne.scrape_stock('MRF')
        
        # Build API response
        print('\n🔧 Building API response...')
        builder = FundametricsResponseBuilder(
            symbol='MRF',
            company_name=profile_data.get('company_name', 'MRF Limited'),
            sector=profile_data.get('sector', 'Automobile Tyres & Rubber')
        )
        
        # Add financial data
        if 'financials' in financial_data:
            income_statement = financial_data['financials'].get('income_statement', {})
            if 'income_statement' in financial_data['financials']:
                builder.add_income_statement(income_statement)
            if 'balance_sheet' in financial_data['financials']:
                builder.add_balance_sheet(financial_data['financials']['balance_sheet'])
            if 'shareholding' in financial_data:
                builder.add_shareholding(financial_data['shareholding'])

        if 'income_statement' in financial_data.get('financials', {}):
            income_statement = financial_data['financials']['income_statement']
            if income_statement:
                latest_period = sorted(income_statement.keys())[-1]
                latest_row = income_statement[latest_period]
                print('\n🔍 Raw income statement snapshot:')
                print(f'Period: {latest_period}')
                for label, value in latest_row.items():
                    print(f'  {label}: {value}')

        response = builder.build()
        
        # Print formatted output
        print('\n' + '='*50)
        print('📋 MRF DATA REPORT'.center(50))
        print('='*50)
        
        print('\n🏢 COMPANY INFO:')
        print('-'*50)
        print(f"Name: {response['company']['name']}")
        print(f"Sector: {response['company']['sector']}")
        
        print('\n💵 FINANCIAL DATA:')
        print('-'*50)
        latest = response['financials']['latest']
        for key, value in latest.items():
            if key != 'period':  # Skip period, we'll show it separately
                print(f"{key.replace('_', ' ').title()}: {value:,.2f}" if isinstance(value, (int, float)) else f"{key.replace('_', ' ').title()}: {value}")
        
        print('\n📊 COMPUTED METRICS:')
        print('-'*50)
        for metric, value in response['financials']['metrics'].items():
            print(f"{metric.replace('_', ' ').title()}: {value:,.2f}")
        
        print('\n📅 METADATA:')
        print('-'*50)
        print(f"Latest Period: {latest.get('period', 'N/A')}")
        print(f"Data Sources: {', '.join(response['metadata']['data_sources'])}")
        print(f"Generated At: {response['metadata'].get('as_of_date', 'N/A')}")
        
        # Save full response to file
        with open('mrf_full_response.json', 'w') as f:
            json.dump(response, f, indent=2)
        print('\n💾 Full response saved to: mrf_full_response.json')
        
    except Exception as e:
        print(f'\n❌ Error: {str(e)}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_mrf())