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
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_url,
    scope=scope
))

# Get Global Top 50 playlist tracks
playlist_id = '37i9dQZF1DX0t8xK1eYx64'  # Spotify's Global Top 50 playlist ID
results = sp.playlist_tracks(playlist_id, limit=50)

# Create a list of tracks with their details
tracks = []
for track in results['items']:
    track_info = {
        'name': track['track']['name'],
        'artist': track['track']['artists'][0]['name'],
        'popularity': track['track']['popularity']
    }
    tracks.append(track_info)

# Sort tracks by popularity
tracks.sort(key=lambda x: x['popularity'], reverse=True)

print("\nGlobal Top 50 Most Popular Songs on Spotify:")
print("-" * 70)
print(f"{'Rank':<5} {'Popularity':<10} {'Song':<40} {'Artist':<30}")
print("-" * 70)

for idx, track in enumerate(tracks, 1):
    print(f"{idx:<5} {track['popularity']:<10} {track['name'][:40]:<40} {track['artist'][:30]:<30}")