from flask import Flask, render_template, jsonify
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sqlite3
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pytz
from dotenv import load_dotenv

# US Central timezone
CENTRAL_TZ = pytz.timezone('America/Chicago')

load_dotenv()

app = Flask(__name__)

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "spotify_history.db")

# Spotify API credentials
client_id = os.environ.get('client_id')
client_secret = os.environ.get('client_secret')
redirect_url = os.environ.get('redirect_url')
scope = os.environ.get('scope')

# Initialize Spotify client
try:
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_url,
        scope=scope
    ))
except Exception as e:
    sp = None
    print(f"Spotify authentication error: {e}")

def init_database():
    """Initialize SQLite database for storing listening history"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listening_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track TEXT NOT NULL,
            artist TEXT NOT NULL,
            album TEXT,
            release_date TEXT,
            popularity INTEGER,
            genres TEXT,
            played_at TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_played_at ON listening_history(played_at)')
    conn.commit()
    conn.close()

def fetch_artist_genres(artist_id):
    """Fetch genres for an artist"""
    try:
        if sp is None:
            return []
        artist = sp.artist(artist_id)
        return artist.get('genres', [])
    except Exception as e:
        print(f"Error fetching genres for artist {artist_id}: {e}")
        return []

def fetch_recently_played_paginated(limit=50, max_batches=20):
    """Fetch recently played tracks from Spotify API with pagination using 'before' parameter"""
    if sp is None:
        return []
    
    all_tracks = []
    before_timestamp = None

    for batch_num in range(max_batches):
        try:
            if before_timestamp:
                recently_played = sp.current_user_recently_played(limit=limit, before=before_timestamp)
            else:
                recently_played = sp.current_user_recently_played(limit=limit)

            if not recently_played['items']:
                break

            for item in recently_played['items']:
                track = item['track']
                track_name = track['name']
                artist_name = ", ".join(artist['name'] for artist in track['artists'])
                played_at = item['played_at']
                album_name = track['album']['name']
                release_date = track['album']['release_date']
                track_popularity = track['popularity']
                
                # Fetch genres for the first artist
                track_genres = []
                if track['artists']:
                    track_genres = fetch_artist_genres(track['artists'][0]['id'])

                all_tracks.append({
                    "Track": track_name,
                    "Artist": artist_name,
                    "Album": album_name,
                    "Release Date": release_date,
                    "Popularity": track_popularity,
                    "Genres": ", ".join(track_genres) if track_genres else "",
                    "Played At": played_at
                })

            # Use 'before' parameter with the oldest track's timestamp for next page
            if recently_played['items']:
                oldest_timestamp = int(pd.to_datetime(recently_played['items'][-1]['played_at']).timestamp() * 1000)
                # Stop if we're trying to fetch the same batch again (no more data)
                if before_timestamp == oldest_timestamp:
                    break
                before_timestamp = oldest_timestamp
            else:
                break
                
        except Exception as e:
            print(f"Error fetching recently played batch {batch_num + 1}: {e}")
            break

    return all_tracks

def sync_spotify_data():
    """Sync new tracks from Spotify API to database"""
    if sp is None:
        return
    
    print("Syncing Spotify data...")
    new_tracks = fetch_recently_played_paginated(limit=50, max_batches=20)
    
    if not new_tracks:
        print("No tracks fetched from Spotify API")
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    added_count = 0
    for track in new_tracks:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO listening_history 
                (track, artist, album, release_date, popularity, genres, played_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                track['Track'],
                track['Artist'],
                track['Album'],
                track['Release Date'],
                track['Popularity'],
                track['Genres'],
                track['Played At']
            ))
            if cursor.rowcount > 0:
                added_count += 1
        except Exception as e:
            print(f"Error inserting track: {e}")
    
    conn.commit()
    conn.close()
    print(f"Sync complete: {added_count} new tracks added to database")

def get_tracks_from_db(days=7):
    """Get tracks from database for the specified number of days"""
    conn = sqlite3.connect(DB_FILE)
    
    # Calculate cutoff date in Central time
    central_now = datetime.now(CENTRAL_TZ)
    cutoff_date = (central_now - timedelta(days=days)).isoformat()
    
    # Try new schema first, fall back to old schema for migration
    try:
        query = '''
            SELECT track_id, track_name, artist_ids, artist_names, album_id, album_name, 
                   release_date, duration_ms, popularity, genres, played_at
            FROM listening_history
            WHERE played_at >= ?
            ORDER BY played_at DESC
        '''
        df = pd.read_sql_query(query, conn, params=(cutoff_date,))
        
        if not df.empty:
            # Map to dashboard-friendly column names
            df.columns = ['Track ID', 'Track', 'Artist IDs', 'Artist', 'Album ID', 'Album', 
                         'Release Date', 'Duration (ms)', 'Popularity', 'Genres', 'Played At']
    except sqlite3.OperationalError:
        # Fall back to old schema
        query = '''
            SELECT track, artist, album, release_date, popularity, genres, played_at
            FROM listening_history
            WHERE played_at >= ?
            ORDER BY played_at DESC
        '''
        df = pd.read_sql_query(query, conn, params=(cutoff_date,))
        if not df.empty:
            df.columns = ['Track', 'Artist', 'Album', 'Release Date', 'Popularity', 'Genres', 'Played At']
    
    conn.close()
    
    if df.empty:
        return df
    
    # Parse timestamps (already in Central time from database)
    df['Played At'] = pd.to_datetime(df['Played At'])
    # Ensure timezone-aware (assume Central if not specified)
    if df['Played At'].dt.tz is None:
        df['Played At'] = df['Played At'].dt.tz_localize(CENTRAL_TZ)
    else:
        df['Played At'] = df['Played At'].dt.tz_convert(CENTRAL_TZ)
    
    return df

def get_last_7_days_data():
    """Get last 7 days of listening data from database"""
    # Sync new tracks from API first
    sync_spotify_data()
    
    # Get tracks from database
    df = get_tracks_from_db(days=7)
    
    return df

def clean_for_json(obj):
    """Recursively clean data for JSON serialization"""
    if pd.isna(obj):
        return None
    elif isinstance(obj, (pd.Timestamp, pd.Timedelta)):
        return obj.isoformat()
    elif isinstance(obj, (int, np.integer)):
        return int(obj)
    elif isinstance(obj, (float, np.floating)):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    else:
        return obj

@app.route('/')
def dashboard():
    """Render the main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/data')
def get_data():
    """API endpoint to get last 7 days of listening data"""
    if sp is None:
        return jsonify({
            'error': 'Spotify authentication failed. Please check your credentials in .env file.'
        }), 500
    
    df_last_7 = get_last_7_days_data()
    
    if df_last_7.empty:
        return jsonify({
            'error': 'No data available for the last 7 days.'
        }), 404
    
    # Replace NaN with empty string for string columns, None for others
    df_last_7 = df_last_7.copy()
    for col in df_last_7.columns:
        if df_last_7[col].dtype == 'object':
            df_last_7[col] = df_last_7[col].fillna('')
        else:
            df_last_7[col] = df_last_7[col].fillna(0)
    
    # Convert to JSON-friendly format
    data = df_last_7.to_dict('records')
    
    # Clean all values for JSON serialization
    cleaned_data = [clean_for_json(record) for record in data]
    
    return jsonify({
        'data': cleaned_data,
        'total_tracks': len(df_last_7),
        'date_range': {
            'start': (datetime.now() - timedelta(days=7)).isoformat(),
            'end': datetime.now().isoformat()
        }
    })

@app.route('/api/stats')
def get_stats():
    """API endpoint to get aggregated statistics"""
    if sp is None:
        return jsonify({
            'error': 'Spotify authentication failed. Please check your credentials in .env file.'
        }), 500
    
    df_last_7 = get_last_7_days_data()
    
    if df_last_7.empty:
        return jsonify({'error': 'No data available for the last 7 days.'}), 404
    
    # Most played tracks
    top_tracks = df_last_7.groupby(['Track', 'Artist']).size().reset_index(name='Play Count')
    top_tracks = top_tracks.sort_values('Play Count', ascending=False).head(10)
    
    # Most played artists
    # Split artists and count individual artist plays
    all_artists = []
    for artists in df_last_7['Artist'].str.split(', '):
        all_artists.extend(artists)
    top_artists = pd.Series(all_artists).value_counts().head(10).reset_index()
    top_artists.columns = ['Artist', 'Play Count']
    
    # Genre distribution - handle NaN values
    all_genres = []
    for genres in df_last_7['Genres'].astype(str).str.split(', '):
        if isinstance(genres, list):
            all_genres.extend([g.strip() for g in genres if g.strip() and g.strip() != 'nan'])
    if all_genres:
        genre_counts = pd.Series(all_genres).value_counts().head(10).reset_index()
        genre_counts.columns = ['Genre', 'Count']
    else:
        genre_counts = pd.DataFrame(columns=['Genre', 'Count'])
    
    # Listening activity by day
    df_last_7['Date'] = df_last_7['Played At'].dt.date
    daily_counts = df_last_7.groupby('Date').size().reset_index(name='Count')
    daily_counts['Date'] = daily_counts['Date'].astype(str)
    
    # Popularity statistics - handle NaN
    avg_popularity = df_last_7['Popularity'].mean()
    if pd.isna(avg_popularity):
        avg_popularity = 0
    
    # Convert DataFrames to dict, handling any NaN values
    def clean_dict_for_json(data):
        """Convert DataFrame records and clean all values for JSON"""
        if data.empty:
            return []
        # Fill NaN values before converting
        data = data.fillna('').copy()
        records = data.to_dict('records')
        # Clean each record recursively
        return [clean_for_json(record) for record in records]
    
    return jsonify({
        'top_tracks': clean_dict_for_json(top_tracks),
        'top_artists': clean_dict_for_json(top_artists),
        'genres': clean_dict_for_json(genre_counts),
        'daily_activity': clean_dict_for_json(daily_counts),
        'avg_popularity': round(float(avg_popularity), 2) if not pd.isna(avg_popularity) else 0.0,
        'unique_tracks': int(df_last_7['Track'].nunique()),
        'unique_artists': int(df_last_7['Artist'].nunique())
    })

# Initialize database on startup
init_database()

if __name__ == '__main__':
    app.run(debug=True, port=5000)