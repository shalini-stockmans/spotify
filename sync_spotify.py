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

def fetch_artist_genres(sp, artist_id):
    """Fetch genres for an artist"""
    try:
        artist = sp.artist(artist_id)
        return artist.get('genres', [])
    except Exception as e:
        print(f"Error fetching genres for artist {artist_id}: {e}")
        return []

def fetch_recently_played_paginated(sp, limit=50, max_batches=20):
    """Fetch recently played tracks from Spotify API with pagination"""
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
                    track_genres = fetch_artist_genres(sp, track['artists'][0]['id'])

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
    print(f"[{datetime.now()}] Starting Spotify sync...")
    
    # Initialize Spotify client
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_url,
            scope=scope
        ))
    except Exception as e:
        print(f"Spotify authentication error: {e}")
        return
    
    # Initialize database
    init_database()
    
    # Fetch new tracks
    new_tracks = fetch_recently_played_paginated(sp, limit=50, max_batches=20)
    
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
            else:
                skipped_count += 1
        except Exception as e:
            print(f"Error inserting track: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"[{datetime.now()}] Sync complete: {added_count} new tracks added, {skipped_count} duplicates skipped")
    print(f"Total tracks fetched: {len(new_tracks)}")

if __name__ == '__main__':
    sync_spotify_data()
