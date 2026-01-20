"""
Standalone script to sync Spotify listening data to database.
Can be run manually, via cron, or via GitHub Actions.
"""
import os
import sqlite3
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "spotify_history.db")

# Spotify API credentials
client_id = os.environ.get('client_id')
client_secret = os.environ.get('client_secret')
redirect_url = os.environ.get('redirect_url')
scope = os.environ.get('scope')

def init_database():
    """Initialize SQLite database for storing listening history"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create table with all metadata
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
    
    # Migrate old schema if needed (for existing databases)
    needs_migration = False
    
    # Check if old column names exist
    if 'track' in existing_columns and 'track_name' not in existing_columns:
        print("Migrating database schema: Renaming columns...")
        try:
            cursor.execute('ALTER TABLE listening_history RENAME COLUMN track TO track_name')
            cursor.execute('ALTER TABLE listening_history RENAME COLUMN artist TO artist_names')
            needs_migration = True
        except sqlite3.OperationalError as e:
            print(f"Migration warning: {e}")
    
    # Add new columns if they don't exist
    new_columns = {
        'track_id': 'TEXT',
        'artist_ids': 'TEXT',
        'album_id': 'TEXT',
        'duration_ms': 'INTEGER'
    }
    
    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            try:
                print(f"Adding column: {col_name}")
                cursor.execute(f'ALTER TABLE listening_history ADD COLUMN {col_name} {col_type}')
                needs_migration = True
            except sqlite3.OperationalError as e:
                print(f"Warning: Could not add column {col_name}: {e}")
    
    if needs_migration:
        print("Database migration completed")
    
    # Create indexes for faster queries (only on columns that exist)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_played_at ON listening_history(played_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON listening_history(created_at)')
    
    # Only create track_id index if column exists
    cursor.execute("PRAGMA table_info(listening_history)")
    columns_after = [col[1] for col in cursor.fetchall()]
    if 'track_id' in columns_after:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_track_id ON listening_history(track_id)')
    
    conn.commit()
    conn.close()

def fetch_artist_genres(sp, artist_id):
    """Fetch genres for an artist"""
    try:
        artist = sp.artist(artist_id)
        return artist.get('genres', [])
    except Exception as e:
        print(f"Error fetching genres for artist {artist_id}: {e}")
        return []

def fetch_recently_played_paginated(sp, limit=50, max_batches=50, skip_genres=False):
    """Fetch recently played tracks from Spotify API with pagination
    Fetches ALL available tracks, not just 50. Continues until no more data.
    """
    print(f"Fetching recently played tracks (limit={limit}, max_batches={max_batches}, skip_genres={skip_genres})...")
    all_tracks = []
    before_timestamp = None
    total_fetched = 0

    for batch_num in range(max_batches):
        print(f"Fetching batch {batch_num + 1}/{max_batches}...")
        try:
            if before_timestamp:
                recently_played = sp.current_user_recently_played(limit=limit, before=before_timestamp)
            else:
                recently_played = sp.current_user_recently_played(limit=limit)

            if not recently_played['items']:
                break

            for item in recently_played['items']:
                track = item['track']
                track_id = track.get('id', '')
                track_name = track['name']
                artist_ids = ",".join([artist['id'] for artist in track['artists']])
                artist_names = ", ".join([artist['name'] for artist in track['artists']])
                played_at = item['played_at']
                album_id = track['album'].get('id', '')
                album_name = track['album']['name']
                release_date = track['album'].get('release_date', '')
                duration_ms = track.get('duration_ms', 0)
                track_popularity = track.get('popularity', 0)
                
                # Fetch genres for the first artist (skip if requested to speed up)
                track_genres = []
                if not skip_genres and track['artists']:
                    try:
                        track_genres = fetch_artist_genres(sp, track['artists'][0]['id'])
                    except Exception as e:
                        print(f"Warning: Could not fetch genres for {track_name}: {e}")

                all_tracks.append({
                    "track_id": track_id,
                    "track_name": track_name,
                    "artist_ids": artist_ids,
                    "artist_names": artist_names,
                    "album_id": album_id,
                    "album_name": album_name,
                    "release_date": release_date,
                    "duration_ms": duration_ms,
                    "popularity": track_popularity,
                    "genres": ", ".join(track_genres) if track_genres else "",
                    "played_at": played_at
                })

            # Use 'before' parameter with the oldest track's timestamp for next page
            if recently_played['items']:
                oldest_timestamp = int(pd.to_datetime(recently_played['items'][-1]['played_at']).timestamp() * 1000)
                if before_timestamp == oldest_timestamp:
                    print(f"No more data available (reached end of history)")
                    break
                before_timestamp = oldest_timestamp
                total_fetched += len(recently_played['items'])
                print(f"Batch {batch_num + 1}: Fetched {len(recently_played['items'])} tracks (total: {total_fetched})")
            else:
                print(f"No more items in batch {batch_num + 1}")
                break
                
        except Exception as e:
            print(f"Error fetching recently played batch {batch_num + 1}: {e}")
            break

    print(f"Total tracks fetched from API: {len(all_tracks)}")
    return all_tracks

def sync_spotify_data():
    """Sync new tracks from Spotify API to database"""
    print(f"[{datetime.now()}] Starting Spotify sync...")
    
    # Check if running in CI/GitHub Actions (non-interactive environment)
    is_ci = os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'
    print(f"Running in CI environment: {is_ci}")
    
    # Validate credentials
    if not client_id or not client_secret:
        print("ERROR: Missing Spotify credentials (client_id or client_secret)")
        return
    
    # Initialize Spotify client
    try:
        print("Initializing Spotify OAuth...")
        # In CI, look for cache files in the repo
        cache_path = None
        if is_ci:
            # Look for any .cache-* file in the repo
            import glob
            cache_files = glob.glob('.cache-*')
            if cache_files:
                cache_path = cache_files[0]
                print(f"Found cache file: {cache_path}")
            else:
                print("WARNING: No cache file found in CI environment")
        
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_url,
            scope=scope,
            open_browser=False,  # Never open browser (especially in CI)
            cache_path=cache_path or ".cache"  # Use found cache or default
        )
        
        print("Attempting to get cached token...")
        # Try to get token (will use cache if available)
        token_info = auth_manager.get_cached_token()
        
        if not token_info:
            if is_ci:
                print("=" * 60)
                print("ERROR: No cached token found in CI environment.")
                print("Spotify OAuth requires interactive authentication.")
                print("")
                print("SOLUTION:")
                print("1. Run 'python sync_spotify.py' locally to authenticate")
                print("2. Find the .cache-* file created in your project")
                print("3. Commit it: git add .cache-* && git commit -m 'Add OAuth cache'")
                print("4. Push: git push")
                print("=" * 60)
                return
            else:
                print("No cached token found. Attempting to get new token...")
                # Will prompt for authentication (only in local environment)
                try:
                    token_info = auth_manager.get_access_token()
                except Exception as auth_error:
                    print(f"Failed to get access token: {auth_error}")
                    return
        
        if not token_info:
            print("ERROR: Could not obtain authentication token")
            return
            
        print("Token obtained successfully")
        
        # Test the connection
        print("Creating Spotify client...")
        sp = spotipy.Spotify(auth_manager=auth_manager)
        
        # Quick test to verify authentication works
        print("Testing authentication with API call...")
        try:
            current_user = sp.current_user()
            print(f"Authentication successful! Logged in as: {current_user.get('display_name', 'Unknown')}")
        except Exception as test_error:
            print(f"Authentication test failed: {test_error}")
            return
            
    except Exception as e:
        print(f"Spotify authentication error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Initialize database
    init_database()
    
    # Fetch new tracks (skip genres in CI to speed up)
    new_tracks = fetch_recently_played_paginated(sp, limit=50, max_batches=20, skip_genres=is_ci)
    
    if not new_tracks:
        print("No tracks fetched from Spotify API")
        return
    
    # Save to database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    added_count = 0
    skipped_count = 0
    
    for track in new_tracks:
        try:
            # Use played_at as the unique identifier (Spotify provides exact timestamp)
            cursor.execute('''
                INSERT OR IGNORE INTO listening_history 
                (track_id, track_name, artist_ids, artist_names, album_id, album_name, 
                 release_date, duration_ms, popularity, genres, played_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                track['track_id'],
                track['track_name'],
                track['artist_ids'],
                track['artist_names'],
                track['album_id'],
                track['album_name'],
                track['release_date'],
                track['duration_ms'],
                track['popularity'],
                track['genres'],
                track['played_at']
            ))
            if cursor.rowcount > 0:
                added_count += 1
            else:
                skipped_count += 1
        except sqlite3.IntegrityError as e:
            # Duplicate played_at (already handled by UNIQUE constraint, but log it)
            skipped_count += 1
        except Exception as e:
            print(f"Error inserting track {track.get('track_name', 'Unknown')}: {e}")
            import traceback
            traceback.print_exc()
    
    conn.commit()
    conn.close()
    
    print(f"[{datetime.now()}] Sync complete: {added_count} new tracks added, {skipped_count} duplicates skipped")
    print(f"Total tracks fetched: {len(new_tracks)}")

if __name__ == '__main__':
    sync_spotify_data()
