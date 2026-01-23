"""
Database Viewer - View your Spotify listening history in a table format
"""
import sqlite3
import pandas as pd
from datetime import datetime
import pytz
import os

# US Central timezone
CENTRAL_TZ = pytz.timezone('America/Chicago')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "spotify_history.db")

def view_database(limit=100, days=None):
    """View listening history from database"""
    
    if not os.path.exists(DB_FILE):
        print(f"Database file not found: {DB_FILE}")
        return
    
    conn = sqlite3.connect(DB_FILE)
    
    # Check which schema we're using
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(listening_history)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Build query based on available columns
    if 'track_name' in columns:
        # New schema
        select_cols = """
            track_name as 'Track',
            artist_names as 'Artist',
            album_name as 'Album',
            release_date as 'Release Date',
            duration_ms as 'Duration (ms)',
            popularity as 'Popularity',
            genres as 'Genres',
            played_at as 'Played At',
            track_id as 'Track ID',
            artist_ids as 'Artist IDs'
        """
    else:
        # Old schema (migration)
        select_cols = """
            track as 'Track',
            artist as 'Artist',
            album as 'Album',
            release_date as 'Release Date',
            popularity as 'Popularity',
            genres as 'Genres',
            played_at as 'Played At'
        """
    
    # Build WHERE clause
    where_clause = ""
    params = []
    if days:
        # Calculate cutoff date in Central time
        central_now = datetime.now(CENTRAL_TZ)
        cutoff_date = (central_now - pd.Timedelta(days=days)).isoformat()
        where_clause = "WHERE played_at >= ?"
        params.append(cutoff_date)
    
    query = f"""
        SELECT {select_cols}
        FROM listening_history
        {where_clause}
        ORDER BY played_at DESC
        LIMIT ?
    """
    params.append(limit)
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            print("No records found in database.")
            return
        
        # Format the played_at column (already in Central time)
        if 'Played At' in df.columns:
            df['Played At'] = pd.to_datetime(df['Played At'])
            # Ensure timezone-aware (assume Central if not specified)
            if df['Played At'].dt.tz is None:
                df['Played At'] = df['Played At'].dt.tz_localize(CENTRAL_TZ)
            else:
                df['Played At'] = df['Played At'].dt.tz_convert(CENTRAL_TZ)
            # Format as Central time string
            df['Played At'] = df['Played At'].dt.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        # Format duration
        if 'Duration (ms)' in df.columns:
            df['Duration'] = (df['Duration (ms)'] / 1000 / 60).round(2).astype(str) + ' min'
            df = df.drop('Duration (ms)', axis=1)
        
        # Display statistics
        print("=" * 100)
        print("SPOTIFY LISTENING HISTORY DATABASE")
        print("=" * 100)
        print(f"\nTotal records shown: {len(df)}")
        if days:
            print(f"Filter: Last {days} days")
        print(f"Database file: {DB_FILE}")
        print("\n" + "=" * 100)
        
        # Display table
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 40)
        print(df.to_string(index=False))
        
        print("\n" + "=" * 100)
        
        # Show summary stats
        print("\nSUMMARY STATISTICS:")
        print("-" * 100)
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM listening_history")
        total_count = cursor.fetchone()[0]
        print(f"Total records in database: {total_count}")
        
        # Check for duplicates
        cursor.execute("""
            SELECT played_at, COUNT(*) as count 
            FROM listening_history 
            GROUP BY played_at 
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        print(f"Duplicate played_at values: {len(duplicates)}")
        
        if len(duplicates) > 0:
            print("WARNING: Found duplicates!")
            for dup in duplicates[:5]:  # Show first 5
                print(f"  - {dup[0]}: {dup[1]} occurrences")
        
        # Unique tracks
        if 'track_id' in columns:
            cursor.execute("SELECT COUNT(DISTINCT track_id) FROM listening_history")
            unique_tracks = cursor.fetchone()[0]
            print(f"Unique tracks (by track_id): {unique_tracks}")
        else:
            cursor.execute("SELECT COUNT(DISTINCT track) FROM listening_history")
            unique_tracks = cursor.fetchone()[0]
            print(f"Unique tracks (by name): {unique_tracks}")
        
        # Date range
        cursor.execute("SELECT MIN(played_at), MAX(played_at) FROM listening_history")
        min_date, max_date = cursor.fetchone()
        if min_date and max_date:
            print(f"Date range: {min_date} to {max_date}")
        
        print("-" * 100)
        
    except Exception as e:
        print(f"Error reading database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def show_schema():
    """Show database schema"""
    if not os.path.exists(DB_FILE):
        print(f"Database file not found: {DB_FILE}")
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("=" * 100)
    print("DATABASE SCHEMA")
    print("=" * 100)
    
    cursor.execute("PRAGMA table_info(listening_history)")
    columns = cursor.fetchall()
    
    print("\nColumns:")
    print("-" * 100)
    print(f"{'Column Name':<25} {'Type':<15} {'Not Null':<10} {'Default':<15} {'PK':<5}")
    print("-" * 100)
    
    for col in columns:
        cid, name, col_type, not_null, default, pk = col
        print(f"{name:<25} {col_type:<15} {'YES' if not_null else 'NO':<10} {str(default) if default else 'None':<15} {'YES' if pk else 'NO':<5}")
    
    # Check for unique constraints
    print("\n" + "-" * 100)
    print("UNIQUE CONSTRAINTS (for duplicate prevention):")
    print("-" * 100)
    
    cursor.execute("PRAGMA index_list(listening_history)")
    indexes = cursor.fetchall()
    
    for idx in indexes:
        idx_name = idx[1]
        cursor.execute(f"PRAGMA index_info({idx_name})")
        idx_info = cursor.fetchall()
        if idx_info:
            print(f"Index: {idx_name}")
            for info in idx_info:
                col_name = info[2]
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE name='{idx_name}'")
                sql = cursor.fetchone()
                if sql and 'UNIQUE' in sql[0]:
                    print(f"  → UNIQUE constraint on: {col_name}")
    
    # Check table creation SQL for UNIQUE
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='listening_history'")
    table_sql = cursor.fetchone()
    if table_sql:
        sql = table_sql[0]
        if 'UNIQUE' in sql:
            print("\nUNIQUE constraints in table definition:")
            import re
            unique_matches = re.findall(r'(\w+)\s+TEXT\s+NOT\s+NULL\s+UNIQUE', sql)
            for match in unique_matches:
                print(f"  → {match} (UNIQUE)")
    
    conn.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--schema':
            show_schema()
        elif sys.argv[1] == '--days' and len(sys.argv) > 2:
            days = int(sys.argv[2])
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 100
            view_database(limit=limit, days=days)
        elif sys.argv[1].isdigit():
            view_database(limit=int(sys.argv[1]))
        else:
            print("Usage:")
            print("  python view_database.py              # View last 100 records")
            print("  python view_database.py 50          # View last 50 records")
            print("  python view_database.py --days 7 50 # View last 50 records from past 7 days")
            print("  python view_database.py --schema    # Show database schema")
    else:
        view_database()
