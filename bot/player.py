import discord
from discord.ext import commands
import asyncio
from random import shuffle
from typing import Union
from math import ceil

from help_functions import *
from snong_class import *
from yt_handler import *
from spotify import *
from error import *

YOUTUBE_LOGO_URL = ""
SPOTIFY_LOGO_URL = ""

embed_color = 0x2f6dbf

ffmpeg_opts = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

playlist: list[Song] = []
msg_src_channel = None
voice_client = None
bot = None

to_loop = False
current_song: Song = None

last_search = {
    "type": "",
    "items": []
}

autoplay = False
autoplay_seeds = {
    "artists" : "",
    "genres" : "",
    "tracks" : ""
}

track_to_str = lambda track: track["name"] + " " + " ".join([artist["name"] for artist in track["artists"]])

async def handle_new_songs(ctx: commands.Context, songs: Union[str, list]):
    global playlist

    if isinstance(songs, str):
        songs_copy = create_list(songs)
        songs: list[str] = songs_copy
        for i, song in enumerate(songs_copy):
            if song.startswith("http"):
                if not song.find("list") == -1:
                    link_list = await get_link_list_from_playlist(song)
                    songs[i:i+1] = link_list
    

    if voice_client:
        if not (voice_client.is_playing() or voice_client.is_paused()):
            while songs:
                s = await get_Song_from_str(songs[0])
                if s:
                    if s == "404":
                        await ctx.send(f"{songs[0]} not found")
                    elif s.audio.startswith("http"):
                        playlist.append(s)
                        await play_next()
                        del(songs[0])
                        break
                del(songs[0])

    if songs:
        embed = discord.Embed(
            title="Added songs",
            description=f"by {ctx.author.display_name}",
            color=embed_color
        )
        embed.set_footer(text="YouTube", icon_url=YOUTUBE_LOGO_URL)
        append_embed = lambda s: embed.add_field(name=f"```{s.duration_string}``` {s.title}", value=s.upload, inline=False)

        orig_plist_len = len(playlist)

        tasks = [asyncio.ensure_future(get_Song_from_str(song)) for song in songs]
        song_list = await asyncio.gather(*tasks)


        i = 0
        embed_i = 0
        while i < len(song_list):
            if not song_list[i] or song_list[i] == "404":
                del(song_list[i])
                continue

            if embed_i < 10:
                    append_embed(song_list[i])
                    embed_i += 1

            playlist.append(song_list[i])
            i += 1

        if embed_i == 10 and len(playlist[orig_plist_len:]) > 10:
            embed.add_field(
                name=f"```And {len(playlist[orig_plist_len+10:])} more...```\nsee !queue [page] for more info",
                value="",
                inline=False
            )
        if embed_i:
            await ctx.send(embed=embed)

async def get_Song_from_str(song: str) -> Union[str, Song]:
    if not song.startswith("http"):
        song = await get_songlink_by_name(song)
        if not song:
            return None
        if song == "404":
            return "404"
        
    
    sng = await get_Song_by_link(song)
    return sng
    


async def play_next():
    global playlist
    global msg_src_channel
    global voice_client
    global current_song


    async def add_recomendations(needed: int):
        global playlist
        track_list = await get_recomendations_tracks(autoplay_seeds, needed)
        song_list = []
        for track in track_list:
            song_list.append(track_to_str(track))
        tasks = [asyncio.ensure_future(get_Song_from_str(song)) for song in song_list]
        song_list = await asyncio.gather(*tasks)
        rec_list = []
        for song in song_list:
            try:
                if song.audio.startswith("http"):
                    rec_list.append(song)
            except Exception:
                pass
        playlist += song_list
        if len(rec_list) < needed:
            await add_recomendations(needed-len(rec_list))

    if not voice_client:
        return
    
    if to_loop:
        player = discord.FFmpegPCMAudio(current_song.audio, **ffmpeg_opts)
        player = discord.PCMVolumeTransformer(player, volume=0.8)
        return

    was_paused = voice_client.is_paused()
    if len(playlist):

        if not playlist[0].audio.startswith("http"):
            del playlist[0]
            await play_next()
            return
    
        player = discord.FFmpegPCMAudio(playlist[0].audio, **ffmpeg_opts)
        player = discord.PCMVolumeTransformer(player, volume=0.8)
            
        voice_client.play(player, after=lambda e: bot.loop.create_task(play_next()))
        if to_loop:
            return
        current_song = playlist[0]
        embed = discord.Embed(
            title=playlist[0].title,
            url=playlist[0].original_link,
            description="Is now playing",
            color=embed_color
        )
        embed.set_thumbnail(url=playlist[0].cover_img)
        embed.set_footer(text="YouTube", icon_url=YOUTUBE_LOGO_URL)
        await msg_src_channel.send(embed=embed)
        del(playlist[0])

        if was_paused:
            voice_client.pause()

        if autoplay and len(playlist) < 5:
            needed = 5-len(playlist)
            await add_recomendations(needed)
    else:
        if autoplay:
            await add_recomendations(6)
            await play_next()

        else:
            await voice_client.disconnect()
            voice_client = None

#########################################################################################
####################### Commands ########################################################
#########################################################################################

async def setup_player(bott: commands.Bot):
    global bot
    bot = bott

    @bot.command()
    async def leave(ctx: commands.Context):
        global voice_client
        global playlist
        global autoplay

        try:
            autoplay = False
            if voice_client:
                if ctx.author.voice.channel == voice_client.channel:
                    await voice_client.disconnect()
                    playlist = []
                    voice_client = None
                else:
                    ctx.send("You're not in my vocie channel")
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def join(ctx: commands.Context):
        global voice_client
        
        try:
            if ctx.author.voice:
                if voice_client:
                    if voice_client.is_playing():
                        ctx.send("I'm bussy right now")
                        return
                channel = ctx.message.author.voice.channel
                if voice_client:
                    await leave(ctx)

                await channel.connect()
                voice_client = ctx.guild.voice_client
            else:
                await ctx.send("You're not in a voice channel")
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def play(ctx: commands.Context):
        global playlist
        global msg_src_channel
        global voice_client
        try:
            string = ctx.message.content
            string = string.lstrip("!play")
            string = string.lstrip()

            search_num = 0
            try:
                search_num = int(string)
                if not (search_num < 11 and search_num > 0):
                    search_num = 0
                if search_num > len(last_search["items"]):
                    search_num = 0
            except Exception:
                pass

            msg_src_channel = ctx.channel
            if not ctx.author.voice:
                await ctx.send("You're not in a voice channel")
                return

            author_channel = ctx.author.voice.channel
            if voice_client:
                if author_channel is not voice_client.channel:
                    await ctx.send("I'm bussy right now sorry :(")
                    return
            else:
                await join(ctx)

            if search_num:
                if last_search["type"]:


                    if last_search["type"] == "top10":
                        try:
                            track = last_search["items"][search_num-1]
                            string = track_to_str(track)
                        except Exception:
                            pass

                    elif last_search["type"] == "artist":
                        try:
                            artist_id = last_search["items"][search_num-1]["id"]
                            track_list = await get_track_list_of_artist(artist_id)
                            string = []
                            for track in track_list:
                                track_str = track_to_str(track)
                                string.append(track_str)
                            shuffle(string)
                        except Exception:
                            pass

                    elif last_search["type"] == "album":
                        try:
                            album_id = last_search["items"][search_num-1]["id"]
                            track_list = await get_songs_from_album(album_id)
                            string = []
                            for track in track_list:
                                track_str = track_to_str(track)
                                string.append(track_str)
                        except Exception:
                            pass

            await handle_new_songs(ctx, string)
        except Exception as err:
            await err_log(err, ctx)


    @bot.command()
    async def queue(ctx: commands.Context):
        global playlist

        try:
            string = ctx.message.content.lstrip("!queue")
            string = string.lstrip()

            page = 0
            try:
                page = int(string)-1
            except Exception:
                pass

            if not len(playlist):
                await ctx.send("There is nothing in the queue")
                return
            plist_len = len(playlist)
            page_count = ceil(len(playlist)/10)

            if page+1 > page_count:
                await ctx.send(f"The queue only has {page_count} page{"s" if page_count-1 else ""}")
                return


            embed = discord.Embed(
                title="Queue",
                description=f"{plist_len} song{f" - {page+1}/{page_count}" if page_count-1 else ""}",
                color=embed_color
            )
            embed.set_footer(text="YouTube", icon_url=YOUTUBE_LOGO_URL)
            for i, song in enumerate(playlist[page*10:(page+1)*10]):
                embed.add_field(
                    name=f"```{(page*10)+i+1}.``` {song.title}",
                    value=f"{song.duration_string} | {song.channel} - {song.upload}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def remove(ctx: commands.Context):
        global playlist

        try:
            if ctx.author.voice.channel == voice_client.channel:
                arg = ctx.message.content
                arg = arg.lstrip("!remove")
                arg = arg.lstrip()
                try:
                    num = int(arg)-1
                except Exception:
                    await ctx.send("Usage: !remove <queue number>")
                    return
                
                if not len(playlist):
                    await ctx.send("There's nothing in the queue to remove")
                    return

                if not num < len(playlist):
                    await ctx.send(f"The queue only has {len(playlist)} song{"s" if len(playlist)-1 else ""}")
                    return
                
                embed = discord.Embed(
                    title=f"Removed {playlist[num].title}",
                    color=embed_color
                )
                embed.set_thumbnail(url=playlist[num].cover_img)
                embed.set_footer(text="YouTube", icon_url=YOUTUBE_LOGO_URL)
                await ctx.send(embed=embed)
                del(playlist[num])
            else:
                await ctx.send("You're not in my voice channel")
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def clear(ctx: commands.Context):
        global playlist

        try:
            if len(playlist):
                ctx.send("There's notghing in the queue")
            if ctx.author.voice and voice_client:
                if ctx.author.voice.channel == voice_client.channel:
                    playlist = []
                    await ctx.send("Queue cleared")
                else:
                    await ctx.send("You're not in my voice channel")
            else:
                if (not ctx.author.voice) and voice_client:
                    ctx.send("You're not in my voice channel")
                else:
                    ctx.send("There's notghing in the queue")
                

        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def skip(ctx: commands.Context):
        try:
            if ctx.author.voice:
                if voice_client:
                    author_channel = ctx.author.voice.channel
                    isPlaying = voice_client.is_playing()
                    isPaused = voice_client.is_paused()

                    if ctx.author.voice.channel == voice_client.channel:
                        if not (isPlaying or isPaused):
                            ctx.send("There is nothing to skip")
                        elif (isPlaying or isPaused) and author_channel == voice_client.channel:
                            voice_client.stop()
                            if isPaused:
                                voice_client.pause()

                            await ctx.send("Skipped")
                    else:
                        await ctx.send("You're not in my voice channel")
                else:
                    ctx.send("I'm not playing")
            else:
                ctx.send("You're not in my voice channel")

        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def stop(ctx: commands.Context):
        global playlist
        global voice_client
        global autoplay
        try:
            if ctx.author.voice:
                if voice_client:
                    autoplay = False
                    if ctx.author.voice.channel == voice_client.channel:
                        if voice_client.is_playing():
                            playlist = []
                            voice_client.stop()
                            await leave(ctx)
                    else:
                        await ctx.send("You're not in my voice channel")
                else:
                    ctx.send("I'm not playing")
            else:
                await ctx.send("You're not in my voice channel")

        except Exception as err:
            await err_log(err, ctx)
        
    @bot.command()
    async def pause(ctx: commands.Context):
        try:
            if ctx.author.voice:
                if voice_client:
                    if ctx.author.voice.channel == voice_client.channel:
                        if voice_client.is_playing():
                            voice_client.pause()
                            await ctx.send("Paused")
                    else:
                        await ctx.send("You're not in my voice channel")
                else:
                    await ctx.send("I'm not playing")
            else:
                await ctx.send("You're not in my voice channel")
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def resume(ctx: commands.Context):
        try:
            if ctx.author.voice:
                if voice_client:
                    if ctx.author.voice.channel == voice_client.channel:
                        if voice_client.is_paused():
                            voice_client.resume()
                            await ctx.send("Resumed")
                    else:
                        await ctx.send("You're not in my voice channel")
                else:
                    await ctx.send("I'm not playing")
            else:
                await ctx.send("You're not in my voice channel")
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def search(ctx: commands.Context):
        try:
            string = ctx.message.content
            string = string.lstrip("!search")
            string = string.lstrip()

            if not string:
                await ctx.send("Usage: !search <query>")

            results = await search_yt_for_Songs(string)
            if not results:
                await ctx.send("Something went wrong")
                return
            
            embed = discord.Embed(
                title=string,
                description=f"{len(results)} result",
                color=embed_color
            )
            embed.set_author(name="Search results")
            embed.set_footer(text="YouTube", icon_url=YOUTUBE_LOGO_URL)
            for res in results:
                embed.add_field(
                    name=res.title,
                    value=f"{res.duration_string} | {res.channel}",
                    inline=False
                )
            await ctx.send(embed=embed)

        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def shuffle(ctx: commands.Context):
        global playlist
        try:
            shuffle(playlist)
            await ctx.send("Queue shuffled!")
        except Exception as err:
            await err_log(err, ctx)
    
    @bot.command()
    async def playnow(ctx: commands.Context):
        global playlist
        try:
            need_to_skip = False
            if voice_client:
                voice_client.pause()
                need_to_skip = voice_client.is_playing() or voice_client.is_paused()
                
            old_playlist = playlist
            playlist = []
            ctx.message.content = ctx.message.content.lstrip("!playnow")
            await play(ctx)
            playlist += old_playlist
            if need_to_skip:
                await play_next()
            voice_client.resume()
            
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def autoplayoff(ctx: commands.Context):
        global autoplay
        global autoplay_seeds

        try:
            autoplay = False
            autoplay_seeds = {
                "artists" : "",
                "genres" : "",
                "tracks" : ""
            }
            await ctx.send("Autoplay turned off")

        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def loop(ctx: commands.Context):
        global to_loop
        try:
            to_loop = True
            await ctx.send("looping current song")


        except Exception as err:
            await err_log(err, ctx)



    @bot.command()
    async def endloop(ctx: commands.Context):
        global to_loop
        try:
            to_loop = False
            await ctx.send("Stopped looping")
        
        except Exception as err:
            await err_log(err, ctx)

################################################################################
#############################   SPOTIFY   ######################################
################################################################################
        
    @bot.command()
    async def searchartist(ctx: commands.Context):
        global last_search

        try:
            string = ctx.message.content
            string = string.lstrip("!searchartist")
            string = string.lstrip()

            data = await search_spotify(string, 10, "artist")
            if not data:
                await ctx.send("Something went wrong")
                return
            
            data = data["artists"]
            artist_list = data["items"]
            last_search["type"] = "artist"
            last_search["items"] = artist_list

            embed = discord.Embed(
                title=string,
                description=f"{min(data["total"], 10)} result{"s" if data["total"]-1 else ""}",
                color=embed_color
            )
            embed.set_author(name="Search results")
            embed.set_footer(text="Spotify", icon_url=SPOTIFY_LOGO_URL)

            for i, artist in enumerate(artist_list):
                genres = ", ".join(artist["genres"]) if artist["genres"] else "Unknown genres"
                embed.add_field(
                    name=f"```{i+1}.``` {artist["name"]}",
                    value=genres,
                    inline=False
                )
            
            await ctx.send(embed=embed)
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def topsongs(ctx: commands.Context):
        global last_search
        try:
            string = ctx.message.content
            string = string.lstrip("!topsongs")
            string = string.lstrip()
            prev_search = 0
            try:
                prev_search = int(string)
                if not (artist < 11 and artist > 0):
                    prev_search = 0
            except Exception:
                pass

            artist_id = 0
            while True:
                if prev_search:
                    if last_search["type"] == "artist":
                        try:
                            artist = last_search["items"][prev_search-1]
                            artist_id = artist.get("id")
                            break
                        except Exception:
                            pass
                    else:
                        prev_search = 0
                        continue

                else:
                    data = await search_spotify(string, 1, "artist")
                    if not data:
                        await ctx.send("Something went wrong")
                        return
                    artist = data["artists"]["items"]
                    if not len(artist):
                        await ctx.send("Unknown artist")
                        return
                    
                    artist = artist[0]
                    artist_id = artist["id"]
                    break

            data = await get_artist_top_songs_data(artist_id)
            tracks = data["tracks"]
            last_search["type"] = "top10"
            last_search["items"] = tracks
            if not tracks:
                await ctx.send("Something went wrong")
                return

            embed = discord.Embed(
                title=artist["name"],
                url=artist["external_urls"]["spotify"],
                color=embed_color
            )
            embed.set_author(name="Top songs")
            embed.set_thumbnail(url=artist["images"][1]["url"])
            embed.set_footer(text="Spotify", icon_url=SPOTIFY_LOGO_URL)
            for i, track in enumerate(tracks):
                artist_str = ""
                if not len(track["artists"]):
                    artist_str = "Unknown artists"
                for a in track["artists"]:
                    if a["name"] == artist["name"]:
                        continue
                    artist_str += f", {a["name"]}"
                artist_str = artist_str.lstrip(",")
                artist_str = artist_str.lstrip()
                if artist_str:
                    artist_str = " / feat " + artist_str
                
                embed.add_field(
                    name=f"```{i+1}.``` {track["name"]}",
                    value=f"{get_duration_string(round(track["duration_ms"]/1000))}{artist_str}",
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as err:
            await err_log(err, ctx)

    @bot.command()
    async def searchalbum(ctx: commands.Context):
        global last_search

        try:
            string = ctx.message.content
            string = string.lstrip("!searchalbum")
            string = string.lstrip()

            data = await search_spotify(string, 10, "album")
            if not data:
                ctx.send("Something went wrong")
                return
            data = data["albums"]
            album_list = data["items"]

            embed = discord.Embed(
                title=string,
                description=f"{min(data["total"], 10)} result{"s" if data["total"]-1 else ""}",
                color=embed_color
            )
            embed.set_author(name="Search results")
            embed.set_footer(text="Spotify", icon_url=SPOTIFY_LOGO_URL)
            for i, album in enumerate(album_list):
                artists = ", ".join([artist["name"] for artist in album["artists"]])
                embed.add_field(
                    name=f"```{i+1}.``` {album["name"]}",
                    value="",
                    inline=False
                )
                embed.add_field(
                    name=f"{artists}  ```{album["total_tracks"]} song{"s" if album["total_tracks"]-1 else ""}```",
                    value=album["release_date"],
                    inline=False
                )
            
            await ctx.send(embed=embed)
            last_search["type"] = "album"
            last_search["items"] = album_list


        except Exception as err:
            await err_log(err, ctx)


    @bot.command()
    async def autoplay(ctx: commands.Context):
        global autoplay
        global autoplay_seeds
        global playlist
        global msg_src_channel

        try:
            string = ctx.message.content
            autoplay = autoplay_seeds = {
                "artists" : "",
                "genres" : "",
                "tracks" : ""
            }
            remaining = 5
            genres_seed = ""
            track_seed = ""
            artist_seed = ""
            string = string.lstrip("!autoplay")
            string = string.lstrip()

            if string:
                artist_seed = ""
                artist_names = []
                if "--a=" in string:
                    start = string.find("--a=")
                    end = string.find("--t=") if "--t" in string else len(string)
                    if end < start:
                        end = len(string)
                    artist_seed = string[start:end]
                    string = string[:start] + string[end:]
                track_names = []
                if "--t=" in string:
                    start = string.find("--t=")
                    track_seed = string[start:]
                    string = string[:start]

                if string:
                    genres_list = string.split(",")
                    for gen in genres_list:
                        gen = gen.strip()
                        gen = gen.lstrip()

                    genres_list = await check_genres_list(genres_list)
                    remaining = max(5-len(genres_list), 0)
                    genres_list = genres_list[:5]
                    genres_seed = ",".join(genres_list)
                
                if remaining and artist_seed:
                    artist_seed = artist_seed.lstrip("--a=")
                    artist_seed = artist_seed.lstrip()
                    artist_seed = artist_seed.strip()
                    artist_list = artist_seed.split(",")

                    for i, artist in enumerate(artist_list):
                        artist_list[i] = artist.strip()
                        artist_list[i] = artist_list[i].lstrip()

                    remaining = max(remaining-len(artist_list), 0)
                    artist_list = artist_list[:remaining]
                    artist_id_list = []
                    tasks = [asyncio.ensure_future(search_spotify(a, 1, "artist")) for a in artist_list]
                    data_list = await asyncio.gather(*tasks)
                    for data in data_list:
                        try:
                            artist_names.append(data["artists"]["items"][0]["name"])
                            artist_id_list.append(data["artists"]["items"][0]["id"])
                        except Exception:
                            pass
                    artist_seed = ",".join(artist_id_list)
                    
                if remaining and track_seed:
                    track_seed = track_seed.lstrip("--t=")
                    track_seed = track_seed.lstrip()
                    track_seed = track_seed.strip()
                    track_list = track_seed.split(",")

                    for i, track in enumerate(track_list):
                        track_list[i] = track.strip()
                        track_list[i] = track_list[i].lstrip()

                    remaining = max(remaining-len(track_list), 0)
                    track_list = track_list[:remaining]
                    track_id_list = []
                    tasks = [asyncio.ensure_future(search_spotify(t, 1, "track")) for t in track_list]
                    data_list = await asyncio.gather(*tasks)
                    for data in data_list:
                        try:
                            track_names.append(data["tracks"]["items"][0]["name"])
                            track_id_list.append(data["tracks"]["items"][0]["id"])
                        except Exception:
                            pass
                    track_seed = ",".join(track_id_list)

            autoplay_seeds["tracks"] = track_seed
            autoplay_seeds["genres"] = genres_seed
            autoplay_seeds["artists"] = artist_seed

            embed = discord.Embed(
                title="Autoplay on",
                description=f"by {ctx.author.display_name}",
                color=embed_color
            )
            embed.set_footer(text="YouTube", icon_url=YOUTUBE_LOGO_URL)

            if not autoplay_seeds["genres"] and not autoplay_seeds["artists"] and not autoplay_seeds["tracks"]:
                embed.add_field(
                    name="With no specified seeds",
                    value="",
                    inline=False
                )
            else:
                embed.add_field(
                    name="With the following seeds",
                    value="",
                    inline=False
                )
                if autoplay_seeds["genres"]:
                    embed.add_field(
                        name="Genres",
                        value="\n".join(autoplay_seeds["genres"].split(",")),
                        inline=True
                    )
                if autoplay_seeds["artists"]:
                    embed.add_field(
                        name="Artists",
                        value="\n".join(artist_names),
                        inline=True
                    )
                if autoplay_seeds["tracks"]:
                    embed.add_field(
                        name="Tracks",
                        value="\n".join(track_names),
                        inline=True
                    )

            await ctx.send(embed=embed)

            autoplay = True
            msg_src_channel = ctx.channel

            if not voice_client:
                await join(ctx)
            if not (voice_client.is_playing() or voice_client.is_paused()):
                await play_next()

        except Exception as err:
            await err_log(err, ctx)
