import yfinance as yf

aapl = yf.Ticker("Reliance.Ns")
data = aapl.history(period="1mo")
# Get income statement
income = aapl.income_stmt
print(aapl.financials)

