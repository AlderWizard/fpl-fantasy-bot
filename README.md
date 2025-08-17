# Premier League Fantasy Football Telegram Bot

A comprehensive Telegram bot for tracking Fantasy Premier League (FPL) league statistics, records, and speech reminders for gameweek winners.

## Features

- **League Tracking**: Add and monitor multiple FPL leagues
- **Live Standings**: View current league standings with scores and ranks
- **Records Tracking**: Track highest and lowest scores across all gameweeks
- **Speech Reminders**: Automatic reminders for gameweek winners to write speeches
- **Persistent Storage**: SQLite database for data persistence

## Commands

- `/start` - Welcome message and command overview
- `/addleague <league_id>` - Add a league to track
- `/leagues` - View all tracked leagues
- `/stats <league_id>` - Show league standings and stats
- `/records` - Show highest/lowest scores across all leagues
- `/speech` - Check pending speech reminders
- `/speechdone <league_id> <gameweek>` - Mark speech as completed
- `/help` - Show help message

## Setup

### 1. Prerequisites

- Python 3.8+
- Telegram Bot Token (from @BotFather)

### 2. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env file with your bot token
# FPL_TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. Getting Your League ID

1. Go to [Fantasy Premier League](https://fantasy.premierleague.com)
2. Navigate to your league
3. The league ID is in the URL: `fantasy.premierleague.com/leagues/LEAGUE_ID/standings/c`

### 4. Running the Bot

```bash
python run_fpl_bot.py
```

## How It Works

### League Statistics
- Fetches data from the official FPL API
- Shows current standings with total points and gameweek scores
- Displays top 10 players with ranks and scores

### Records Tracking
- Automatically tracks highest and lowest scores across all gameweeks
- Updates records in real-time as new gameweek data becomes available
- Shows records per league or across all tracked leagues

### Speech Reminder System
- Monitors completed gameweeks for winners
- Creates automatic reminders for gameweek winners to write speeches
- Tracks reminder status and completion
- Escalates reminders after 3+ days

## Database Schema

The bot uses SQLite with the following tables:
- `leagues` - Tracked leagues per chat
- `speech_reminders` - Pending speech reminders
- `records` - Highest/lowest score records
- `gameweek_tracking` - Processed gameweek status

## API Integration

Uses the official Fantasy Premier League API endpoints:
- `https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/`
- `https://fantasy.premierleague.com/api/entry/{manager_id}/history/`
- `https://fantasy.premierleague.com/api/bootstrap-static/`

## Deployment

### Raspberry Pi Deployment

```bash
# SSH to Raspberry Pi
ssh zacalderman@192.168.0.66

# Create directory for FPL bot
mkdir -p /home/zacalderman/fpl-fantasy-bot
cd /home/zacalderman/fpl-fantasy-bot

# Copy files and set up environment
# Install dependencies
pip install -r requirements.txt

# Run the bot
python run_fpl_bot.py
```

### Systemd Service

Create `/etc/systemd/system/fpl-bot.service`:

```ini
[Unit]
Description=FPL Fantasy Football Bot
After=network.target

[Service]
Type=simple
User=zacalderman
WorkingDirectory=/home/zacalderman/fpl-fantasy-bot
ExecStart=/usr/bin/python3 run_fpl_bot.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/home/zacalderman/fpl-fantasy-bot

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable fpl-bot
sudo systemctl start fpl-bot
sudo systemctl status fpl-bot
```

## Troubleshooting

### Common Issues

1. **Bot Token Error**: Ensure `FPL_TELEGRAM_BOT_TOKEN` is set in `.env`
2. **League Not Found**: Verify the league ID is correct and public
3. **API Rate Limits**: The bot includes automatic retry logic
4. **Database Errors**: Check file permissions for SQLite database

### Logs

Bot logs are written to `fpl_bot.log` and console output.

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is for educational and personal use only.
