import yt_dlp
from datetime import datetime
import asyncio
import concurrent.futures

from snong_class import *
from help_functions import *

ydl_opts = {
    'format': 'bestaudio/best',
    'skip_download': True,
    'match_filter': yt_dlp.match_filter_func([
        ('!is_live', 'true'),
        ('!url', '!contains', '/shorts/')
    ]),
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'extract_flat': True,
    'extractor_restriction': ['youtube'],
    'skip_download': True,
    'flat_playlist': True,
    'youtube_include_dash_manifest': False,
    'youtube_include_hls_manifest': False,
    'youtube_include_raw_manifest': False,
    'youtube_include_doodles': False,
    'youtube_include_chapters': False,
    'youtube_include_automatic_captions': False,
    'youtube_include_annotations': False,
    'youtube_include_subtitles': False,
    'youtube_include_contributions': False,
    'youtube_include_transcripts': False,
    'youtube_include_metadata': False,
    'youtube_include_live_chat': False,
    'youtube_include_heatmaps': False,
    'youtube_include_formats': 'bestaudio',
}

ytdlp = yt_dlp.YoutubeDL(ydl_opts)

def ytdl_extractor(url):
    data = None
    try:
        data = ytdlp.extract_info(url=url, download=False)
    except Exception as err:
        pass
    
    return data

def get_Song_info(data: dict) -> Song:
    if not data:
        return None
    keys = ["title", "thumbnails", "url", "duration_string", "channel", "upload_date"]

    for i, key in enumerate(keys):
        if key == "thumbnails":
            try:
                thumbnails = data[key]
                for thumbnail in reversed(thumbnails):
                    try:
                        res = thumbnail["resolution"]
                        keys[i] = thumbnail["url"]
                        break
                    except KeyError:
                        pass
            except KeyError:
                print(f"{key} Not found in data for {song}")
        elif key == "upload_date":
            try:
                input_date_str = data[key]
                input_date = datetime.strptime(input_date_str, "%Y%m%d")

                keys[i] = input_date.strftime("%Y.%m.%d")
            except KeyError:
                pass
        else: 
            try:
                keys[i] = data[key]
            except KeyError:
                print(f"{key} Not found in data for {song}")
    
    song = Song(
        title=keys[0],
        cover_img=keys[1],
        audio=keys[2],
        duration_string=keys[3],
        channel=keys[4],
        upload=keys[5]
    )
    
    return song

async def get_songlink_by_name(song: str) -> str:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        loop = asyncio.get_event_loop()
        search_results = await loop.run_in_executor(executor, ytdl_extractor, f"ytsearch1:{song}")
    if not search_results:
        return None
    
    entries = search_results.get('entries')
    if entries:
        if entries:
            try:
                result = entries[0]
                url = result["url"]
                return url
            except Exception as err:
                print(f"Failed to get url from search result. result: {result} Error: {err}")
    else:
        return "404"
    return None
    
async def get_Song_by_link(url: str) -> Song:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(executor, ytdl_extractor, url)
    if not data:
        return None
    song = get_Song_info(data)
    if not song:
        return None
    song.original_link = url
    return song


async def get_link_list_from_playlist(url: str) -> list[str]:
    data = ytdlp.extract_info(url=url, download=False)
    if not data:
        return None
    
    if not 'entries' in data:
        data = ytdlp.extract_info(url=data["url"], download=False)
        if not data:
            return None
    
    entries = data['entries']
    link_list = []

    for song in entries:
        try:
            link = song.get("url")
            link_list.append(link)
        except KeyError:
            pass
    return link_list

async def search_yt_for_Songs(string: str) -> list[Song]:
    search_results = ytdlp.extract_info(f"ytsearch6:{string}", download=False)
    
    if not search_results:
        return None

    results: list[Song] = []
    if 'entries' in search_results:
        for res in search_results.get("entries"):
            keys = ["title", "channel", "duration"]
            for i, key in enumerate(keys):
                try:
                    keys[i] = res.get(key)
                except KeyError:
                    print(f"failed to find {key}")
                    key[i] = "Unknown"
            song = Song(title=keys[0],
                        channel=keys[1],
                        duration_string=f"{get_duration_string(keys[2])}")
            
            results.append(song)
    return results