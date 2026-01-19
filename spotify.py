import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# credentials
client_id = os.environ.get('client_id')
client_secret = os.environ.get('client_secret')
redirect_url = os.environ.get('redirect_url')   
scope = os.environ.get('scope')

# authentication
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=client_id
    ,
    client_secret=client_secret,
    redirect_uri=redirect_url,
    scope=scope
))

# get 50 most listed to songs and 
def fetch_recently_played(limit=50, max_batches=5):
    all_tracks = []
    after_timestamp = None

    for _ in range(max_batches):
        if after_timestamp:
            recently_played = sp.current_user_recently_played(limit=limit, after=after_timestamp)
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
            track_genres = fetch_artist_genres(track['artists'][0]['id'])

            all_tracks.append({
                "Track": track_name,
                "Artist": artist_name,
                
                "Album": album_name,
                "Release Date": release_date,
                "Popularity": track_popularity,
                "Genres": ", ".join(track_genres),
                "Played At": played_at
            })

        after_timestamp = int(pd.to_datetime(recently_played['items'][-1]['played_at']).timestamp() * 1000)

    return all_tracks

def fetch_artist_genres(artist_id):
    try:
        artist = sp.artist(artist_id)
        return artist.get('genres', [])
    except Exception as e:
        print(f"Error fetching genres for artist {artist_id}: {e}")
        return []

tracks = fetch_recently_played(max_batches=5)
df_new = pd.DataFrame(tracks)
df_new['Played At'] = pd.to_datetime(df_new['Played At'], format='ISO8601') 
df_new['Played At'] = df_new['Played At'].dt.tz_localize(None)

file_name = "C://Users//sstockmans//OneDrive - Virtus Real Estate//Documents//Personal//spotify//data//spotify_recently_played.xlsx"

try:
    df_existing = pd.read_excel(file_name)
    combined_data = pd.concat([df_existing, df_new])
    combined_data = combined_data.drop_duplicates(subset=["Track", "Played At"], keep="last")
except FileNotFoundError:
    combined_data = df_new

combined_data.to_excel(file_name, index=False)
print("Data saved to", file_name)
