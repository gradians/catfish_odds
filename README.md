# Catfish Odds Logger

Fetches current river gauge and weather data given a USA ZIP code to compute a “catfish odds” score each hour, logging results to a JSON file.

## Features

- Hourly logging of catfish-odds score
- Automatic removal of entries older than 30 days
- Barometric stability calculation over past days
- Configurable via ZIP code for weather station lookup (default to Philadelphia gauge if mapping not implemented)

## Setup

1. **Clone the repository**  
   ```bash
   git clone https://github.com/yourusername/catfish_odds.git
   cd catfish_odds
   ```

2. **Create & edit `.env`**  
   ```bash
   cp .env.example .env
   ```
   - Set `ZIP_CODE` to your desired U.S. ZIP code.
   - Adjust `LOG_FILE_PATH` if needed.
   - Update `USER_AGENT` with your email.

3. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

4. **Run manually**  
   ```bash
   python log_odds.py
   ```

5. **Schedule hourly**  
   Add a cron job on Linux/macOS (Windows Task Scheduler for Windows):
   ```
   0 * * * * cd /path/to/catfish_odds && /usr/bin/env python3 log_odds.py
   ```

## License

MIT License © 2025 Ian Garrison