import discord
from discord.ext import commands
import asyncio
import json
from fuzzywuzzy import fuzz
from math import ceil

from player import setup_player
from spotify import load_spotify_token

TOKEN = ""

command_help = None
bot_prefix = '!'

with open('command_descriptions.json', 'r') as file:
    command_help = json.load(file)
    command_help = command_help["commands"]

cmd_help_embed = lambda: discord.Embed(
    title="Sierra help",
    url="https://discord.com/",
    description=f"***use prefix {bot_prefix}***",
    color=0x2f6dbf
).set_footer(text="Sierra", icon_url=bot.user.display_avatar.url)
class CustomHelpCommand(commands.DefaultHelpCommand):


    async def send_bot_help(self, mapping):
        await self.send_cmdlist_page(1)

    async def send_cmdlist_page(self, page: int):
        if page < 0:
            await self.context.send("There is no negative page")
            return
        if page > ceil(len(command_help)/6):
            await self.context.send(f"The help menu only has {ceil(len(command_help)/6)} page{"s" if ceil(len(command_help)/6)-1 else None}")
            return
        
        embed = cmd_help_embed()
        for command in command_help[(page-1)*6:page*6]:
            embed.add_field(
                name=f"```{command["name"]}{f" {command["args"]}" if command["args"] else ""}```",
                value=command["short_description"],
                inline=False
            )
        embed.description += f" - page {page}/{ceil(len(command_help)/6)}"
        embed.add_field(
            name="Use !help [page] for more command",
            value=f"{len(command_help)} total command",
            inline=False
        )
        await self.context.send(embed=embed)

    async def send_command_help(self, input):

        command = None
        for cmd in command_help:
            if cmd["name"] == input.name:
                command = cmd
    
        embed = cmd_help_embed()

        embed.add_field(
            name=f"```{command["name"]}{f" {command["args"]}" if command["args"] else ""}```",
            value="",
            inline=False
        )
        embed.add_field(
            name=command["short_description"],
            value=command["detailed_description"],
            inline=False
        )
        await self.context.send(embed=embed)


    async def send_error_message(self, error: str):
        if error.startswith("No command called"):
            error = error.lstrip("No command called ")
            error = error.strip(" found.")
            error = error.lstrip('"')
            error = error.strip('"')
            closest_command = None
            highest_similarity = -1

            def to_num(string):
                try:
                    num = int(string)
                    return num
                except Exception:
                    return None
            
            page = to_num(error)
            if page:
                await self.send_cmdlist_page(page)
                return

            for cmd in command_help:
                similarity = fuzz.ratio(error, cmd["name"])
                if similarity > highest_similarity:
                    highest_similarity = similarity
                    closest_command = cmd["name"]

            view = discord.ui.View()
            view.add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="Yes", custom_id="yes"))
            view.add_item(discord.ui.Button(style=discord.ButtonStyle.red, label="No", custom_id="no"))
            message = await self.context.send(content=f"There is no such command \"{error}\"\nDid you mean \"{closest_command}\"?", view=view)
            interaction = None
            try:
                interaction = await bot.wait_for("interaction", check=lambda i: i.user.id == self.context.author.id and i.message.id == message.id, timeout=30.0)
            except asyncio.TimeoutError:
                return

            if interaction:
                await interaction.response.defer(ephemeral=True, thinking=False)
                if interaction.data["custom_id"] == "yes":
                    input = commands.Command
                    input.name = closest_command
                    await self.send_command_help(input)
                elif interaction.data["custom_id"] == "no":
                    await self.send_bot_help("any")


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.integrations = True

bot = commands.Bot(command_prefix=bot_prefix, intents=intents, help_command=CustomHelpCommand())

@bot.event
async def on_ready():
    await setup_player(bot)
    print(f'We have logged in as {bot.user}')
    await bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="!<command>"))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"{ctx.message.content.split(" ")[0]} not found. Use !help [page] to see the avalibe commands")
    else:
        await ctx.send(f"An error occurred: {error}")

@bot.command()
async def hello(ctx: commands.Context):
    await ctx.send(f"hello {ctx.author.display_name}")

load_spotify_token()
bot.run(TOKEN)