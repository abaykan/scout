# S.C.O.U.T 
Scope Change Observation & Unified Tracking

A modular Bug Bounty monitoring tool that tracks program changes, discovers new subdomains, and sends Telegram notifications.

## Features

- **Program Monitoring**: Monitor Bugcrowd, HackerOne, and YesWeHack (with more platforms coming) public programs and scope changes
- **Subdomain Discovery**: Monitor text files for new subdomains and alert on discoveries
- **Telegram Notifications**: Get instant alerts on new subdomains and program changes
- **Modular Architecture**: Easy to add new platforms
- **Automated Scanning**: Automated subdomain discovery with `subfinder`
- **Smart Filtering**: HackerOne targets filtered for both submission and bounty eligibility

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone git@github.com:abaykan/scout
cd scout

# Install dependencies
pip3 install -r requirements.txt
```

### 2. Database Setup

Create a MySQL database and user:

```sql
CREATE DATABASE scout_db;
CREATE USER 'scout_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON scout_db.* TO 'scout_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Configuration

Edit `config.json` with your settings:

```json
{
  "database": {
    "host": "localhost",
    "user": "scout_user",
    "password": "your_secure_password",
    "database": "scout_db",
    "port": 3306
  },
  "telegram": {
    "bot_token": "your_telegram_bot_token",
    "chat_id": "your_chat_id"
  },
  "notifications": {
    "type": "telegram",
    "enabled": true
  },
  "platforms": {
    "bugcrowd": {
      "enabled": true,
      "programs_to_monitor": [
        "https://bugcrowd.com/engagements/intercom",
        "https://bugcrowd.com/engagements/atlassian"
      ]
    },
    "hackerone": {
      "enabled": true,
      "programs_to_monitor": [
        "https://hackerone.com/hack_the_box"
      ]
    },
    "yeswehack": {
      "enabled": true,
      "programs_to_monitor": [
        "https://yeswehack.com/programs/zecible-public-bug-bounty-program"
      ]
    }
  }
}
```

### 4. Initialize Database

```bash
# Create database tables
python3 init_db.py
```

### 5. Run S.C.O.U.T

```bash
# Run monitoring once
python3 main.py
```

## Usage Examples

### Monitor Specific Programs

Add program URLs to `config.json`:

```json
"platforms": {
  "bugcrowd": {
    "enabled": true,
    "programs_to_monitor": [
      "https://bugcrowd.com/engagements/intercom",
      "https://bugcrowd.com/engagements/atlassian"
    ]
  },
  "hackerone": {
    "enabled": true,
    "programs_to_monitor": [
      "https://hackerone.com/hack_the_box",
      "https://hackerone.com/shopify"
    ]
  },
  "yeswehack": {
    "enabled": true,
    "programs_to_monitor": [
      "https://yeswehack.com/programs/zecible-public-bug-bounty-program",
      "https://yeswehack.com/programs/gojek-bug-bounty-program"
    ]
  }
}
```

### Subdomain Monitoring

S.C.O.U.T automatically:
- Scans wildcard domains using subfinder
- Saves results to `scans/{program-slug}.txt` files
- Monitors these files for new subdomains
- Sends Telegram notifications for new discoveries

```bash
# Example: Manual subdomain scanning
subfinder -d example.com -o manual-subdomains.txt
```

## Project Structure

```
scout/
├── main.py              # Main entry point
├── init_db.py           # Database initialization
├── config.json         # Configuration file
├── requirements.txt    # Python dependencies
├── scout.log          # Application logs
├── scans/             # Subdomain scan results
└── src/
    ├── __init__.py
    ├── db.py           # MySQL database operations
    ├── monitor.py      # Core monitoring system
    ├── notifier.py     # Telegram notifications
    ├── utils.py        # Utility functions
    └── platforms/
        ├── __init__.py
        ├── bugcrowd.py    # Bugcrowd platform implementation
        ├── hackerone.py   # HackerOne platform implementation
        └── yeswehack.py   # YesWeHack platform implementation
```

## Platform Support Details

### Bugcrowd
- Uses JSON API for accurate scope extraction
- Falls back to HTML parsing if API unavailable

### HackerOne
- Uses GraphQL API for structured scope data
- **Smart Filtering**: Only includes targets that are both `eligible_for_submission` AND `eligible_for_bounty`
- Handles program handles directly from URLs

### YesWeHack
- Uses HTML parsing with BeautifulSoup
- Extracts scope from tables and structured elements

## TODO
- [ ] More platform supports
- [ ] Optimize anything that can be optimized
- [ ] Handle private program


## License

MIT License - feel free to use and modify for your bug bounty activities.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
- Review logs in `scout.log`
- Open a GitHub issue
