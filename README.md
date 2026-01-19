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
5. Add a redirect URI (e.g., `http://localhost:8080`)

### 3. Collect Listening Data

First, run the `spotify.py` script to collect your listening data:

```bash
python spotify.py
```

This will:
- Authenticate with Spotify
- Fetch your recently played tracks
- Save the data to `data/spotify_recently_played.xlsx`

**Note**: You may need to run this script periodically to keep your data up to date. The dashboard will show data for the last 7 days from your collected data.

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
├── spotify.py                  # Script to fetch and save Spotify data
├── requirements.txt            # Python dependencies
├── templates/
│   └── dashboard.html         # Dashboard HTML template
├── data/
│   └── spotify_recently_played.xlsx  # Listening data storage
└── README.md                   # This file
```

## Usage

1. **Collect Data**: Run `spotify.py` to fetch your recently played tracks from Spotify
2. **View Dashboard**: Start the Flask app with `python app.py` and open `http://localhost:5000` in your browser
3. **Update Data**: Periodically run `spotify.py` to update your listening history

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
- Make sure you've run `spotify.py` at least once to collect data
- Check that the Excel file exists in `data/spotify_recently_played.xlsx`

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