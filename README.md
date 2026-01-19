# Spotify Listening Dashboard

A web application that displays a beautiful dashboard of your most recent songs listened to in the last 7 days using the Spotify Web API.

## Features

- 📊 **Interactive Dashboard**: Visual charts showing your listening habits
- 🎵 **Top Tracks**: See your most played tracks in the last 7 days
- 🎤 **Top Artists**: Discover which artists you've been listening to most
- 🎸 **Genre Distribution**: Visualize your music taste by genre
- 📈 **Listening Activity**: Track your listening activity over time
- 📋 **Recent Plays Table**: Detailed list of all recent plays

## Prerequisites

- Python 3.7 or higher
- Spotify account with access to Spotify Web API
- Spotify app credentials (Client ID, Client Secret, Redirect URI)

## Setup Instructions

### 1. Install Dependencies

Make sure you have a virtual environment activated, then install the required packages:

```bash
pip install -r requirements.txt
```

### 2. Configure Spotify API Credentials

Create a `.env` file in the root directory with your Spotify API credentials:

```
client_id=your_client_id_here
client_secret=your_client_secret_here
redirect_url=your_redirect_url_here
scope=user-read-recently-played
```

To get your Spotify API credentials:
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Create a new app
4. Copy your Client ID and Client Secret
5. Add a redirect URI (e.g., `http://localhost:3000`)

### 3. Initialize Database

The app uses SQLite database to store your listening history. The database will be created automatically when you first run the app.

**Note**: The dashboard automatically syncs new tracks from Spotify API when you visit it. You can also manually sync by running:

```bash
python sync_spotify.py
```

### 4. Run the Web Application

Start the Flask web server:

```bash
python app.py
```

The dashboard will be available at: `http://localhost:5000`

## Project Structure

```
spotify/
├── app.py                      # Flask web application
├── sync_spotify.py             # Standalone script to sync Spotify data
├── sync_spotify.bat            # Windows batch file for automation
├── setup_windows_scheduler.ps1  # PowerShell script for Task Scheduler
├── requirements.txt            # Python dependencies
├── templates/
│   └── dashboard.html         # Dashboard HTML template
├── .github/
│   └── workflows/
│       └── sync_spotify.yml   # GitHub Actions workflow
├── spotify_history.db          # SQLite database (created automatically)
└── README.md                   # This file
```

## Usage

1. **View Dashboard**: Start the Flask app with `python app.py` and open `http://localhost:5000` in your browser
   - The dashboard automatically syncs new tracks from Spotify when you visit it
2. **Manual Sync** (Optional): Run `python sync_spotify.py` to manually sync tracks
3. **Automated Sync**: Set up automated syncing using GitHub Actions or Windows Task Scheduler (see `SETUP_AUTOMATION.md`)

All data is stored in the SQLite database (`spotify_history.db`), which grows over time as you listen to music.

## Dashboard Features

### Statistics Cards
- **Total Plays**: Number of times you've played tracks in the last 7 days
- **Unique Tracks**: Number of unique songs you've listened to
- **Unique Artists**: Number of different artists in your recent plays
- **Average Popularity**: Average popularity score of your listened tracks

### Charts

1. **Top Tracks Bar Chart**: Shows your 10 most played tracks with play counts
2. **Top Artists Doughnut Chart**: Visual distribution of your top 10 artists
3. **Genre Distribution Pie Chart**: Breakdown of genres in your listening history
4. **Listening Activity Line Chart**: Daily listening activity over the last 7 days

### Recent Plays Table
A detailed table showing all your recent plays with:
- Track name
- Artist
- Album
- Genres
- Popularity score
- Date and time played

## API Endpoints

- `GET /` - Main dashboard page
- `GET /api/data` - JSON endpoint returning last 7 days of listening data
- `GET /api/stats` - JSON endpoint returning aggregated statistics

## Troubleshooting

### No Data Available
If you see "No data available" error:
- Make sure you've visited the dashboard at least once (it auto-syncs on first visit)
- Or manually run `python sync_spotify.py` to fetch data from Spotify
- Check that the database file `spotify_history.db` exists in your project directory
- Verify your Spotify credentials in `.env` are correct

### Authentication Issues
If you encounter authentication errors:
- Verify your `.env` file has correct credentials
- Make sure your redirect URI matches exactly in the Spotify app settings
- Check that you've granted the necessary scopes (`user-read-recently-played`)

## License

This project is for personal use. Make sure to comply with Spotify's [Developer Terms of Service](https://developer.spotify.com/terms).

## Resources

- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api)
- [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)