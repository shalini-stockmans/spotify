from flask import Flask, render_template, jsonify, request
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
    
    # Create table with new schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listening_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id TEXT,
            track_name TEXT NOT NULL,
            artist_ids TEXT,
            artist_names TEXT NOT NULL,
            album_id TEXT,
            album_name TEXT,
            release_date TEXT,
            duration_ms INTEGER,
            popularity INTEGER,
            genres TEXT,
            played_at TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check existing columns to determine schema version
    cursor.execute("PRAGMA table_info(listening_history)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    # Migrate old schema if needed
    if 'track' in existing_columns and 'track_name' not in existing_columns:
        try:
            cursor.execute('ALTER TABLE listening_history RENAME COLUMN track TO track_name')
        except sqlite3.OperationalError:
            pass
    
    if 'artist' in existing_columns and 'artist_names' not in existing_columns:
        try:
            cursor.execute('ALTER TABLE listening_history RENAME COLUMN artist TO artist_names')
        except sqlite3.OperationalError:
            pass
    
    if 'album_name' not in existing_columns:
        if 'album' in existing_columns:
            try:
                cursor.execute('ALTER TABLE listening_history RENAME COLUMN album TO album_name')
            except sqlite3.OperationalError:
                try:
                    cursor.execute('ALTER TABLE listening_history ADD COLUMN album_name TEXT')
                    cursor.execute('UPDATE listening_history SET album_name = album WHERE album_name IS NULL')
                except sqlite3.OperationalError:
                    pass
        else:
            try:
                cursor.execute('ALTER TABLE listening_history ADD COLUMN album_name TEXT')
            except sqlite3.OperationalError:
                pass
    
    # Add new columns if they don't exist
    new_columns = {
        'track_id': 'TEXT',
        'artist_ids': 'TEXT',
        'album_id': 'TEXT',
        'duration_ms': 'INTEGER'
    }
    
    cursor.execute("PRAGMA table_info(listening_history)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(f'ALTER TABLE listening_history ADD COLUMN {col_name} {col_type}')
            except sqlite3.OperationalError:
                pass
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_played_at ON listening_history(played_at)')
    conn.commit()
    conn.close()

def fetch_artist_genres(artist_id, artist_name=""):
    """Fetch genres for an artist, using local cache to avoid redundant API calls"""
    if sp is None:
        return []
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Ensure cache table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS genre_cache (
            artist_id TEXT PRIMARY KEY,
            artist_name TEXT,
            genres TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check cache first
    cursor.execute("SELECT genres FROM genre_cache WHERE artist_id = ?", (artist_id,))
    row = cursor.fetchone()
    if row is not None:
        conn.close()
        return row[0].split(", ") if row[0] else []
    
    # Not cached — call Spotify API
    try:
        artist = sp.artist(artist_id)
        genres = artist.get('genres', [])
        genre_str = ", ".join(genres) if genres else ""
        cursor.execute(
            "INSERT OR REPLACE INTO genre_cache (artist_id, artist_name, genres) VALUES (?, ?, ?)",
            (artist_id, artist_name or artist.get('name', ''), genre_str)
        )
        conn.commit()
        conn.close()
        return genres
    except Exception as e:
        print(f"Error fetching genres for artist {artist_id}: {e}")
        conn.close()
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
                
                # Fetch genres for the first artist (cached per artist)
                track_genres = []
                if track['artists']:
                    track_genres = fetch_artist_genres(track['artists'][0]['id'], track['artists'][0]['name'])

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
    
    # Check schema once before the loop
    cursor.execute("PRAGMA table_info(listening_history)")
    columns = [col[1] for col in cursor.fetchall()]
    has_new_schema = 'track_name' in columns
    has_album_name = 'album_name' in columns
    
    added_count = 0
    for track in new_tracks:
        try:
            if has_new_schema:
                # New schema - use all columns
                cursor.execute('''
                    INSERT OR IGNORE INTO listening_history 
                    (track_name, artist_names, album_name, release_date, popularity, genres, played_at)
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
            elif has_album_name:
                # Partially migrated - has album_name but not track_name
                cursor.execute('''
                    INSERT OR IGNORE INTO listening_history 
                    (track, artist, album_name, release_date, popularity, genres, played_at)
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
            else:
                # Old schema - use old column names
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
    
    # Parse timestamps - handle mixed timezones (UTC and Central)
    def parse_timestamp(ts):
        try:
            dt = pd.to_datetime(ts)
            # If it ends with 'Z', it's UTC (old format)
            if isinstance(ts, str) and ts.endswith('Z'):
                if dt.tzinfo is None:
                    dt = pytz.UTC.localize(dt)
                else:
                    dt = dt.astimezone(pytz.UTC)
                # Convert to Central
                return dt.astimezone(CENTRAL_TZ)
            else:
                # Assume Central time (new format)
                if dt.tzinfo is None:
                    return CENTRAL_TZ.localize(dt)
                else:
                    return dt.astimezone(CENTRAL_TZ)
        except:
            return pd.NaT
    
    # Apply parsing to handle mixed timezones
    df['Played At'] = df['Played At'].apply(parse_timestamp)
    
    return df

def get_last_7_days_data():
    """Get last 7 days of listening data from database only (no API sync)"""
    # Only read from database - syncing is handled by sync_spotify.py
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
    """API endpoint to get listening data from database. Accepts ?days=7 or ?days=30"""
    days = request.args.get('days', 7, type=int)
    days = max(1, min(days, 365))

    df = get_tracks_from_db(days=days)
    
    if df.empty:
        return jsonify({
            'error': f'No data available for the last {days} days.'
        }), 404
    
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('')
        else:
            df[col] = df[col].fillna(0)
    
    data = df.to_dict('records')
    cleaned_data = [clean_for_json(record) for record in data]
    
    recent_count = 15 if days <= 7 else 25
    recent = cleaned_data[:recent_count] if len(cleaned_data) > recent_count else cleaned_data
    
    return jsonify({
        'data': cleaned_data,
        'recent_plays': recent,
        'total_tracks': len(df),
        'date_range': {
            'start': (datetime.now() - timedelta(days=days)).isoformat(),
            'end': datetime.now().isoformat()
        }
    })

@app.route('/api/stats')
def get_stats():
    """API endpoint to get aggregated statistics. Accepts ?days=7 or ?days=30"""
    days = request.args.get('days', 7, type=int)
    days = max(1, min(days, 365))

    df = get_tracks_from_db(days=days)
    
    if df.empty:
        return jsonify({'error': f'No data available for the last {days} days.'}), 404
    
    top_tracks = df.groupby(['Track', 'Artist']).size().reset_index(name='Play Count')
    top_tracks = top_tracks.sort_values('Play Count', ascending=False).head(10)
    
    all_artists = []
    for artists in df['Artist'].str.split(', '):
        all_artists.extend(artists)
    top_artists = pd.Series(all_artists).value_counts().head(10).reset_index()
    top_artists.columns = ['Artist', 'Play Count']
    
    all_genres = []
    for genres in df['Genres'].astype(str).str.split(', '):
        if isinstance(genres, list):
            all_genres.extend([g.strip() for g in genres if g.strip() and g.strip() != 'nan'])
    if all_genres:
        genre_counts = pd.Series(all_genres).value_counts().head(10).reset_index()
        genre_counts.columns = ['Genre', 'Count']
    else:
        genre_counts = pd.DataFrame(columns=['Genre', 'Count'])
    
    df['Date'] = df['Played At'].dt.date
    daily_counts = df.groupby('Date').size().reset_index(name='Count')
    daily_counts['Date'] = daily_counts['Date'].astype(str)
    
    # Hourly breakdown (useful for monthly view)
    df['Hour'] = df['Played At'].dt.hour
    hourly_counts = df.groupby('Hour').size().reset_index(name='Count')
    hourly_counts.columns = ['Hour', 'Count']
    
    # Weekly breakdown (useful for monthly view)
    df['Week'] = df['Played At'].dt.isocalendar().week.astype(int)
    df['WeekStart'] = df['Played At'].dt.tz_localize(None).dt.to_period('W').apply(lambda r: r.start_time).dt.strftime('%b %d')
    weekly_counts = df.groupby('WeekStart').size().reset_index(name='Count')
    weekly_counts.columns = ['Week', 'Count']
    
    avg_popularity = df['Popularity'].mean()
    if pd.isna(avg_popularity):
        avg_popularity = 0
    
    # Total and average listening time
    if 'Duration (ms)' in df.columns:
        dur = pd.to_numeric(df['Duration (ms)'], errors='coerce').fillna(0)
        total_duration_ms = int(dur.sum())
        avg_duration_ms = int(dur[dur > 0].mean()) if (dur > 0).any() else 0
    else:
        total_duration_ms = 0
        avg_duration_ms = 0
    
    def clean_dict_for_json(data):
        if data.empty:
            return []
        data = data.fillna('').copy()
        records = data.to_dict('records')
        return [clean_for_json(record) for record in records]
    
    return jsonify({
        'top_tracks': clean_dict_for_json(top_tracks),
        'top_artists': clean_dict_for_json(top_artists),
        'genres': clean_dict_for_json(genre_counts),
        'daily_activity': clean_dict_for_json(daily_counts),
        'hourly_activity': clean_dict_for_json(hourly_counts),
        'weekly_activity': clean_dict_for_json(weekly_counts),
        'avg_popularity': round(float(avg_popularity), 2) if not pd.isna(avg_popularity) else 0.0,
        'unique_tracks': int(df['Track'].nunique()),
        'unique_artists': int(df['Artist'].nunique()),
        'total_plays': len(df),
        'total_duration_ms': total_duration_ms,
        'avg_duration_ms': avg_duration_ms
    })

@app.route('/api/artists')
def get_artists():
    """Return all distinct artist names from listening history for the dropdown"""
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("SELECT DISTINCT artist_names FROM listening_history", conn)
        col = 'artist_names'
    except sqlite3.OperationalError:
        df = pd.read_sql_query("SELECT DISTINCT artist FROM listening_history", conn)
        col = 'artist'
    conn.close()

    # Split comma-separated artists and deduplicate
    artists = set()
    for val in df[col].dropna():
        for a in val.split(', '):
            a = a.strip()
            if a:
                artists.add(a)

    return jsonify(sorted(artists, key=str.lower))


@app.route('/api/artist')
def get_artist():
    """API endpoint to search listening history by artist name"""
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Please provide an artist name.'}), 400

    conn = sqlite3.connect(DB_FILE)

    # Try new schema first, fall back to old
    try:
        query = '''
            SELECT track_name, artist_names, album_name, release_date,
                   duration_ms, popularity, genres, played_at
            FROM listening_history
            WHERE LOWER(artist_names) LIKE LOWER(?)
            ORDER BY played_at DESC
        '''
        df = pd.read_sql_query(query, conn, params=(f'%{name}%',))
        if not df.empty:
            df.columns = ['Track', 'Artist', 'Album', 'Release Date',
                          'Duration (ms)', 'Popularity', 'Genres', 'Played At']
    except sqlite3.OperationalError:
        query = '''
            SELECT track, artist, album, release_date,
                   NULL as duration_ms, popularity, genres, played_at
            FROM listening_history
            WHERE LOWER(artist) LIKE LOWER(?)
            ORDER BY played_at DESC
        '''
        df = pd.read_sql_query(query, conn, params=(f'%{name}%',))
        if not df.empty:
            df.columns = ['Track', 'Artist', 'Album', 'Release Date',
                          'Duration (ms)', 'Popularity', 'Genres', 'Played At']

    conn.close()

    if df.empty:
        return jsonify({'plays': [], 'stats': None, 'query': name})

    # Parse dates BEFORE fillna (which turns the column into mixed strings)
    # Use utc=True to handle mixed timezones, then convert to Central
    parsed_dates = pd.to_datetime(df['Played At'], errors='coerce', utc=True)
    dates = parsed_dates.dropna()

    # Listening timeline (plays per day)
    date_only = dates.dt.tz_convert(CENTRAL_TZ).dt.date
    timeline_df = pd.DataFrame({'Date': date_only})
    timeline = timeline_df.groupby('Date').size().reset_index(name='Count')
    timeline['Date'] = timeline['Date'].astype(str)
    timeline = timeline.sort_values('Date')

    # Duration stats before fillna
    dur = pd.to_numeric(df['Duration (ms)'], errors='coerce').fillna(0)
    total_duration_ms = int(dur.sum())

    # Now clean NaN values for JSON output
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('')
        else:
            df[col] = df[col].fillna(0)

    plays = [clean_for_json(r) for r in df.to_dict('records')]

    # Stats
    total_plays = len(df)
    unique_tracks = int(df['Track'].nunique())
    unique_albums = int(df['Album'].nunique())

    avg_pop = df['Popularity'].mean()
    avg_popularity = round(float(avg_pop), 2) if not pd.isna(avg_pop) else 0.0

    # Top tracks by play count
    top_tracks = (df.groupby('Track').size()
                    .reset_index(name='Play Count')
                    .sort_values('Play Count', ascending=False)
                    .head(10))

    # Top albums by play count
    top_albums = (df[df['Album'] != '']
                    .groupby('Album').size()
                    .reset_index(name='Play Count')
                    .sort_values('Play Count', ascending=False)
                    .head(10))

    # Genres
    all_genres = []
    for genres in df['Genres'].astype(str).str.split(', '):
        if isinstance(genres, list):
            all_genres.extend([g.strip() for g in genres if g.strip() and g.strip() != 'nan'])
    if all_genres:
        genre_counts = pd.Series(all_genres).value_counts().head(10).reset_index()
        genre_counts.columns = ['Genre', 'Count']
    else:
        genre_counts = pd.DataFrame(columns=['Genre', 'Count'])

    def to_list(frame):
        if frame.empty:
            return []
        return [clean_for_json(r) for r in frame.to_dict('records')]

    stats = {
        'total_plays': total_plays,
        'unique_tracks': unique_tracks,
        'unique_albums': unique_albums,
        'avg_popularity': avg_popularity,
        'total_duration_ms': total_duration_ms,
        'top_tracks': to_list(top_tracks),
        'top_albums': to_list(top_albums),
        'timeline': to_list(timeline),
        'genres': to_list(genre_counts),
    }

    return jsonify({'plays': plays, 'stats': stats, 'query': name})


# Initialize database on startup
init_database()

if __name__ == '__main__':
    app.run(debug=True, port=4000)