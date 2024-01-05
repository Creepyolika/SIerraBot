import base64
import json
import aiohttp
from requests import post
import asyncio
from itertools import chain
from fuzzywuzzy import fuzz
import random
import asyncio

CLIENT_ID = ""
CLIENT_SECRET = ""

token = None
auth_header = None

def update_token():
    auth_string = CLIENT_ID + ":" + CLIENT_SECRET
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    heathers = {
        "Authorization": "Basic " + auth_base64
    }
    data = {
        "grant_type": "client_credentials"
    }
    result = post(url, headers=heathers, data=data, auth=(CLIENT_ID, CLIENT_SECRET))
    json_res = json.loads(result.content)
    token = json_res["access_token"]
    with open("spotify_token.txt", 'w') as file:
        token = file.write(token)
        file.close()
    load_spotify_token()
    print("[Spotify-API] Token updated")

def load_spotify_token():
    global token
    global auth_header

    try:
        with open("spotify_token.txt", 'r') as file:
            token = file.read()
            file.close()
            auth_header = {"Authorization": f"Bearer {token}"}
    except FileNotFoundError:
        update_token()

async def spotify_get(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url=url, headers=auth_header) as response:
            if response.status == 200:
                json_res = await response.json()
                return json_res
            elif response.status == 401:
                update_token()
                return await spotify_get(url)
            elif response.status == 429:
                print(f"[Spotify-API] We're rate limited. {response}")
                return None
            else:
                print(f"[Spotify-API] Failed to get answer from {url} with heathers {auth_header} response: {response}")
                return None

def get_auth_headers(token):
    return {"Authorization": "Bearer " + token}

async def search_spotify(query: str, limit: int, type: str):
    global last_artist_results

    url = f"https://api.spotify.com/v1/search?q={query}&type={type}&market=HU&limit={limit}"
    return await spotify_get(url)



async def get_artist_top_songs_data(artist_id: str):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?market=HU"
    return await spotify_get(url)

async def get_albums_data(artist_id: str):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/albums?market=HU&limit=50&include_groups=single,album"
    albums = await spotify_get(url)
    return albums

async def get_songs_from_album(album_id: str):
    url = f"https://api.spotify.com/v1/albums/{album_id}/tracks?market=HU&limit=50"
    data = await spotify_get(url)
    if not data:
        return None
    track_list = data["items"]

    while data["next"]:
        data = await spotify_get(data["next"])
        if data:
            track_list += data["items"]

    return track_list

async def get_track_list_of_artist(artist_id: str):
    data = await get_albums_data(artist_id)
    if not data:
        return None
    
    album_list = data.get("items")

    while data["next"]:
        data = await spotify_get(data["next"])
        album_list += data["items"]

    tasks = [asyncio.ensure_future(get_songs_from_album(album["id"])) for album in album_list]
    songs = await asyncio.gather(*tasks)
    track_list = list(chain.from_iterable(songs))

    seen_names = {}
    filtered_track_list = []
    for song in track_list:
        name: str = song["name"][:5]
        if "remix" in name.lower():
            continue

        if name not in seen_names:
            seen_names[name] = True
            filtered_track_list.append(song)
            continue

    return filtered_track_list

async def check_genres_list(list: list[str]):
    data = await spotify_get("https://api.spotify.com/v1/recommendations/available-genre-seeds")
    genres = data["genres"]

    return_list = []

    for g in list:
        closest = ""
        highest_similarity = -1
        for gen in genres:
            if g == gen:
                closest = gen
                break

            similarity = fuzz.ratio(g, gen)
            if similarity > highest_similarity:
                highest_similarity = similarity
                closest = gen
        return_list.append(closest)

    return return_list

async def get_recomendations_tracks(seed: dict, limit:int):
    genres = ""
    artist = ""
    tracks  = ""
    if seed["genres"]:
        genres = f"&seed_genres={seed["genres"]}"
    if seed["artists"]:
        artist = f"&seed_artists={seed["artists"]}"
    if seed["tracks"]:
        tracks = f"&seed_tracks={seed["tracks"]}"

    tracks_list = []
    if not artist and not tracks and not genres:
        genres_data = await spotify_get("https://api.spotify.com/v1/recommendations/available-genre-seeds")
        for i in range(limit):
            genres = f"&seed_genres={random.choice(genres_data["genres"])}"
            data = await spotify_get(f"https://api.spotify.com/v1/recommendations?limit=1&market=HU{artist}{tracks}{genres}")
            tracks_list += data["tracks"]
    else:
        data = await spotify_get(f"https://api.spotify.com/v1/recommendations?limit={limit}&market=HU{artist}{tracks}{genres}")
        tracks_list = data["tracks"]

    return tracks_list
