import requests
import base64
import os
from datetime import datetime, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import openpyxl

client_id = "b5494d2c0caf45f690bf1dbd33aa5249"
client_secret = "44050af30c294b41a1fa62bb1724f3c6"

url = "https://accounts.spotify.com/api/token"

auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

headers = {
    "Authorization": f"Basic {auth_header}"
}

data = {
    "grant_type": "client_credentials"
}

response = requests.post(url, headers=headers, data=data)

if response.status_code == 200:
    token = response.json().get("access_token")
    print("Access Token:", token)
else:
    print("Error:", response.json())


############################################## helper functions #######################################################

def get_album_tracks(album_id, access_token):
    url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        tracks = response.json().get("items", [])
        print(f"Tracks in Album {album_id}:")
        for idx, track in enumerate(tracks, start=1):
            print(f"{idx}. {track['name']}")
    else:
        print("Error:", response.json())



def get_recently_played_tracks(access_token):
    url = "https://api.spotify.com/v1/me/player/recently-played"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    params = {
        "limit": 50
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print("Your most listened-to songs today:")
        
        # Filter tracks played today
        today = datetime.now().date()
        for idx, item in enumerate(data.get("items", []), start=1):
            played_at = datetime.fromisoformat(item["played_at"][:-1])
            if played_at.date() == today:
                track = item["track"]
                print(f"{idx}. {track['name']} by {', '.join(artist['name'] for artist in track['artists'])}")
    else:
        print("Error:", response.json())


################################################ run functions ######################################################
# album_id = '07w0rG5TETcyihsEIZR3qG'

# get_album_tracks(album_id, token)

# get_recently_played_tracks(token)