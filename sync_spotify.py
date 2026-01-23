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
import pytz
from dotenv import load_dotenv

# US Central timezone
CENTRAL_TZ = pytz.timezone('America/Chicago')
UTC_TZ = pytz.UTC

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
    
    # Check if old column names exist and need renaming
    if 'track' in existing_columns and 'track_name' not in existing_columns:
        print("Migrating database schema: Renaming columns...")
        try:
            cursor.execute('ALTER TABLE listening_history RENAME COLUMN track TO track_name')
            needs_migration = True
        except sqlite3.OperationalError as e:
            print(f"Migration warning (track->track_name): {e}")
    
    if 'artist' in existing_columns and 'artist_names' not in existing_columns:
        try:
            cursor.execute('ALTER TABLE listening_history RENAME COLUMN artist TO artist_names')
            needs_migration = True
        except sqlite3.OperationalError as e:
            print(f"Migration warning (artist->artist_names): {e}")
    
    # Handle album column - add album_name if it doesn't exist
    if 'album_name' not in existing_columns:
        if 'album' in existing_columns:
            # Try to rename first (SQLite 3.25.0+)
            try:
                cursor.execute('ALTER TABLE listening_history RENAME COLUMN album TO album_name')
                needs_migration = True
                print("Renamed album to album_name")
            except sqlite3.OperationalError:
                # If rename fails, add new column and copy data
                try:
                    cursor.execute('ALTER TABLE listening_history ADD COLUMN album_name TEXT')
                    cursor.execute('UPDATE listening_history SET album_name = album WHERE album_name IS NULL')
                    needs_migration = True
                    print("Added album_name column and copied data from album")
                except sqlite3.OperationalError as e:
                    print(f"Warning: Could not migrate album column: {e}")
        else:
            # No album column at all, just add album_name
            try:
                cursor.execute('ALTER TABLE listening_history ADD COLUMN album_name TEXT')
                needs_migration = True
                print("Added album_name column")
            except sqlite3.OperationalError as e:
                print(f"Warning: Could not add album_name column: {e}")
    
    # Refresh column list after renaming
    cursor.execute("PRAGMA table_info(listening_history)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    # Add new columns if they don't exist
    new_columns = {
        'track_id': 'TEXT',
        'artist_ids': 'TEXT',
        'album_id': 'TEXT',
        'album_name': 'TEXT',  # In case it doesn't exist after migration
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

def convert_to_central(utc_timestamp_str):
    """Convert UTC timestamp string to US Central timezone"""
    try:
        # Parse the UTC timestamp from Spotify (ISO format)
        utc_dt = pd.to_datetime(utc_timestamp_str)
        # Ensure it's timezone-aware (UTC)
        if utc_dt.tzinfo is None:
            utc_dt = UTC_TZ.localize(utc_dt)
        else:
            utc_dt = utc_dt.astimezone(UTC_TZ)
        # Convert to Central time
        central_dt = utc_dt.astimezone(CENTRAL_TZ)
        # Return as ISO string for storage
        return central_dt.isoformat()
    except Exception as e:
        print(f"Warning: Could not convert timestamp {utc_timestamp_str}: {e}")
        return utc_timestamp_str  # Return original if conversion fails

def get_latest_played_at():
    """Get the most recent played_at timestamp from database.
    Returns the raw timestamp string (could be UTC or Central).
    """
    if not os.path.exists(DB_FILE):
        return None
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT MAX(played_at) FROM listening_history")
        result = cursor.fetchone()
        latest = result[0] if result and result[0] else None
        return latest
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

def parse_timestamp_to_utc_millis(timestamp_str):
    """Parse a timestamp string (UTC or Central) and return UTC milliseconds for API comparison"""
    try:
        # Parse the timestamp
        dt = pd.to_datetime(timestamp_str)
        
        # If it ends with 'Z', it's UTC
        if timestamp_str.endswith('Z') or '+00:00' in timestamp_str:
            # Already UTC
            if dt.tzinfo is None:
                dt = UTC_TZ.localize(dt)
            else:
                dt = dt.astimezone(UTC_TZ)
        else:
            # Assume it's Central time (new format)
            if dt.tzinfo is None:
                dt = CENTRAL_TZ.localize(dt)
            else:
                dt = dt.astimezone(CENTRAL_TZ)
            # Convert to UTC
            dt = dt.astimezone(UTC_TZ)
        
        return int(dt.timestamp() * 1000)
    except Exception as e:
        print(f"Warning: Could not parse timestamp {timestamp_str}: {e}")
        return None

def fetch_new_tracks_only(sp, skip_genres=False):
    """Fetch only NEW tracks that aren't in the database yet.
    Stops when we encounter songs we already have.
    """
    print("=" * 60)
    print("Checking database for latest song...")
    latest_played_at = get_latest_played_at()
    
    if latest_played_at:
        print(f"✓ Latest song in database: {latest_played_at}")
        # Convert to UTC milliseconds for API comparison (handles both UTC and Central formats)
        latest_timestamp = parse_timestamp_to_utc_millis(latest_played_at)
        if latest_timestamp:
            print(f"✓ Latest timestamp (UTC ms): {latest_timestamp}")
        else:
            print("⚠️  Warning: Could not parse latest timestamp, fetching all")
            latest_timestamp = None
    else:
        print("ℹ️  Database is empty - fetching all available songs")
        latest_timestamp = None
    print("=" * 60)
    
    all_tracks = []
    before_timestamp = None
    found_existing = False
    
    print("Fetching new tracks from Spotify...")
    
    # Fetch in batches until we hit songs we already have
    for batch_num in range(50):  # Max 50 batches (2500 songs)
        try:
            if before_timestamp:
                recently_played = sp.current_user_recently_played(limit=50, before=before_timestamp)
            else:
                recently_played = sp.current_user_recently_played(limit=50)
            
            if not recently_played['items']:
                print(f"Batch {batch_num + 1}: No more items from Spotify API")
                break
            
            batch_new_count = 0
            for item in recently_played['items']:
                played_at = item['played_at']
                played_timestamp = int(pd.to_datetime(played_at).timestamp() * 1000)
                
                # If we've reached songs we already have, stop
                if latest_timestamp and played_timestamp <= latest_timestamp:
                    print(f"Reached existing songs in batch {batch_num + 1}")
                    print(f"  API song timestamp (UTC): {played_timestamp}")
                    print(f"  Database latest (UTC): {latest_timestamp}")
                    print(f"  Difference: {latest_timestamp - played_timestamp} ms")
                    found_existing = True
                    break
                
                # This is a new song - process it
                track = item['track']
                track_id = track.get('id', '')
                track_name = track['name']
                artist_ids = ",".join([artist['id'] for artist in track['artists']])
                artist_names = ", ".join([artist['name'] for artist in track['artists']])
                album_id = track['album'].get('id', '')
                album_name = track['album']['name']
                release_date = track['album'].get('release_date', '')
                duration_ms = track.get('duration_ms', 0)
                track_popularity = track.get('popularity', 0)
                
                # Convert played_at from UTC to Central time
                played_at_central = convert_to_central(played_at)
                
                # Fetch genres (skip in CI to speed up)
                track_genres = []
                if not skip_genres and track['artists']:
                    try:
                        track_genres = fetch_artist_genres(sp, track['artists'][0]['id'])
                    except Exception as e:
                        pass  # Skip genre fetch on error
                
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
                    "played_at": played_at_central  # Store in Central time
                })
                batch_new_count += 1
            
            if found_existing:
                print(f"⏹️  Stopping fetch - reached existing songs.")
                print(f"   Total new songs found: {len(all_tracks)}")
                break
            
            print(f"✓ Batch {batch_num + 1}: Found {batch_new_count} new songs (total so far: {len(all_tracks)})")
            
            # Get timestamp for next batch
            if recently_played['items']:
                oldest_timestamp = int(pd.to_datetime(recently_played['items'][-1]['played_at']).timestamp() * 1000)
                if before_timestamp == oldest_timestamp:
                    break
                before_timestamp = oldest_timestamp
            else:
                break
                
        except Exception as e:
            print(f"❌ Error fetching batch {batch_num + 1}: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print(f"✓ Fetch complete: Found {len(all_tracks)} new tracks total")
    return all_tracks

def sync_spotify_data():
    """Sync new tracks from Spotify API to database - only adds NEW songs"""
    print("=" * 60)
    print(f"[{datetime.now()}] Starting Spotify sync...")
    print("=" * 60)
    
    # Check if running in CI/GitHub Actions (non-interactive environment)
    is_ci = os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'
    print(f"Running in CI environment: {is_ci}")
    print(f"Database file: {DB_FILE}")
    print(f"Database exists: {os.path.exists(DB_FILE)}")
    
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
            # Look for any .cache or .cache-* file in the repo
            import glob
            cache_files = glob.glob('.cache') + glob.glob('.cache-*')
            if cache_files:
                cache_path = cache_files[0]
                print(f"✓ Found cache file: {cache_path}")
            else:
                print("=" * 60)
                print("⚠️  WARNING: No cache file found in CI environment")
                print("=" * 60)
                print("The sync will fail without a cached OAuth token.")
                print("")
                print("SOLUTION:")
                print("1. Run 'python sync_spotify.py' locally to authenticate")
                print("2. Find the .cache or .cache-* file created in your project")
                print("3. Commit it: git add .cache .cache-* && git commit -m 'Add OAuth cache'")
                print("4. Push: git push")
                print("=" * 60)
        
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
    
    # Fetch ONLY new tracks (stops when it hits existing songs)
    new_tracks = fetch_new_tracks_only(sp, skip_genres=is_ci)
    
    if not new_tracks:
        print("=" * 60)
        print("INFO: No new tracks found - database is up to date!")
        print("This means all recent songs are already in the database.")
        print("=" * 60)
        return
    
    print(f"Found {len(new_tracks)} new tracks to add")
    
    # Save to database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check schema once before the loop (more efficient)
    cursor.execute("PRAGMA table_info(listening_history)")
    columns = [col[1] for col in cursor.fetchall()]
    has_new_schema = 'track_name' in columns
    has_album_name = 'album_name' in columns
    
    print(f"Database schema: new_schema={has_new_schema}, has_album_name={has_album_name}")
    
    added_count = 0
    skipped_count = 0
    
    for track in new_tracks:
        try:
            # Use played_at as the unique identifier (Spotify provides exact timestamp)
            if has_new_schema:
                # New schema - use all columns
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
            elif has_album_name:
                # Partially migrated - has album_name but not track_name
                cursor.execute('''
                    INSERT OR IGNORE INTO listening_history 
                    (track, artist, album_name, release_date, popularity, genres, played_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    track['track_name'],
                    track['artist_names'],
                    track['album_name'],
                    track['release_date'],
                    track['popularity'],
                    track['genres'],
                    track['played_at']
                ))
            else:
                # Old schema - use old column names (album instead of album_name)
                cursor.execute('''
                    INSERT OR IGNORE INTO listening_history 
                    (track, artist, album, release_date, popularity, genres, played_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    track['track_name'],
                    track['artist_names'],
                    track['album_name'],
                    track['release_date'],
                    track['popularity'],
                    track['genres'],
                    track['played_at']
                ))
            
            if cursor.rowcount > 0:
                added_count += 1
            else:
                skipped_count += 1
        except sqlite3.IntegrityError:
            # Duplicate played_at (already handled by UNIQUE constraint)
            skipped_count += 1
        except Exception as e:
            print(f"Error inserting track {track.get('track_name', 'Unknown')}: {e}")
    
    # Get total count before closing
    cursor.execute("SELECT COUNT(*) FROM listening_history")
    total_count = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    print("=" * 60)
    print(f"[{datetime.now()}] Sync complete!")
    print(f"  - {added_count} new tracks added")
    print(f"  - {skipped_count} tracks skipped (duplicates)")
    print(f"  - Total tracks in database: {total_count}")
    print("=" * 60)

if __name__ == '__main__':
    sync_spotify_data()
