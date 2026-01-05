# Fundametrics Stock Scraper

Production-grade web scraping system for Indian stock fundamental data from Screener.in and Moneycontrol.

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- MySQL 8.0+
- Git

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd fundametrics-scraper
```

2. **Create virtual environment**
```bash
# Windows
py -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your database credentials
# nano .env  # or use your preferred editor
```

5. **Initialize database**
```bash
python scripts/init_db.py
```

6. **Run the scraper**
```bash
python main.py
```

## 📁 Project Structure

```
fundametrics-scraper/
│
├── scraper/                    # Core scraping modules
│   ├── sources/                # Source-specific scrapers
│   │   ├── screener.py         # Screener.in scraper
│   │   └── moneycontrol.py     # Moneycontrol scraper
│   │
│   ├── core/                   # Core processing modules
│   │   ├── fetcher.py          # HTTP fetching logic
│   │   ├── parser.py           # HTML parsing
│   │   ├── cleaner.py          # Data cleaning
│   │   └── validator.py        # Data validation
│   │
│   └── utils/                  # Utility modules
│       ├── headers.py          # HTTP headers management
│       ├── proxies.py          # Proxy rotation
│       ├── rate_limiter.py     # Rate limiting
│       └── logger.py           # Logging utility
│
├── db/                         # Database modules
│   ├── models.py               # SQLAlchemy models
│   └── migrate.py              # Migration scripts
│
├── config/                     # Configuration
│   └── settings.yaml           # Main configuration file
│
├── scheduler/                  # Job scheduling
│   └── cron.py                 # Scheduled jobs
│
├── logs/                       # Log files (auto-created)
├── data/                       # Data storage (auto-created)
│   ├── raw/                    # Raw HTML cache
│   ├── processed/              # Processed data
│   └── backups/                # Database backups
│
├── .env                        # Environment variables (create from .env.example)
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
└── main.py                     # Application entry point
```

## ⚙️ Configuration

All configuration is managed through `config/settings.yaml`. Key settings:

- **Scrapers**: Rate limits, timeouts, endpoints
- **Database**: Connection settings, pool configuration
- **Scheduler**: Scraping schedule (default: 6 PM IST daily)
- **Logging**: Log levels, rotation, retention
- **Monitoring**: Prometheus metrics, alerts

Environment-specific values (passwords, secrets) should be set in `.env` file.

## 🔧 Usage

### Manual Scraping
```bash
# Scrape specific stock
python scripts/manual_scrape.py --symbol RELIANCE

# Scrape multiple stocks
python scripts/manual_scrape.py --symbols RELIANCE,TCS,INFY

# Scrape all stocks
python scripts/manual_scrape.py --all
```

### Scheduled Scraping
```bash
# Start scheduler (runs daily at 6 PM IST)
python main.py --mode scheduler
```

### API Server
```bash
# Start API server
python main.py --mode api

# API will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## 📊 API Endpoints

- `GET /api/v1/stocks/{symbol}/fundamentals` - Get fundamental data
- `GET /api/v1/stocks/{symbol}/financials` - Get financial statements
- `GET /api/v1/stocks/search` - Search stocks
- `GET /api/v1/scraper/status` - Get scraper status
- `POST /api/v1/scraper/trigger` - Trigger manual scrape (admin)

## 🛡️ Anti-Ban Measures

- **Rate limiting**: 10 req/min for Screener.in, 15 req/min for Moneycontrol
- **User-agent rotation**: Rotates through realistic browser user-agents
- **Random delays**: 6±2 seconds between requests
- **Retry logic**: Exponential backoff on failures
- **Session management**: Persistent sessions with cookie handling
- **Respectful scraping**: Off-peak hours, minimal server load

## 🔄 Failure Recovery

- **Checkpoints**: Resume from last successful point
- **Retry queue**: Failed requests automatically retried
- **Data versioning**: Keep last 7 versions, rollback capability
- **Circuit breaker**: Auto-stop if error rate > 20%
- **Graceful degradation**: Use cached data if scraping fails

## 📈 Monitoring

- **Prometheus metrics** on port 9090
- **Health checks** every 60 seconds
- **Email/Slack alerts** for failures
- **Success rate tracking** (target: >95%)

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=scraper

# Run specific test
pytest tests/unit/test_scrapers.py
```

## 📝 Logging

Logs are stored in `logs/` directory:
- `fundametrics-scraper.log` - All logs (rotated at 500MB)
- `errors.log` - Error logs only (rotated at 100MB)

Log retention: 30 days for general logs, 90 days for errors.

## 🚢 Deployment

### Docker
```bash
# Build image
docker build -t fundametrics-scraper .

# Run with docker-compose
docker-compose up -d
```

### Production Checklist
- [ ] Set `APP_ENV=production` in `.env`
- [ ] Set `DEBUG=false` in `.env`
- [ ] Configure strong database password
- [ ] Enable HTTPS for API
- [ ] Set up database backups
- [ ] Configure monitoring alerts
- [ ] Review rate limits
- [ ] Test failure recovery

## 📄 License

Proprietary - Fundametrics

## 🤝 Contributing

Internal project - contact the development team for contribution guidelines.

## ⚠️ Legal Notice

This scraper is designed to:
- Scrape only publicly available data
- Respect robots.txt
- Minimize server load
- Comply with website terms of service
- Follow India's IT Act, 2000

**Use responsibly and ethically.**

## 📞 Support

For issues or questions, contact: dev@fundametrics.com
