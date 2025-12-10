import asyncio

import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os, json, re
from mcstatus import JavaServer
from mcrcon import MCRcon
import requests, glob

# Gets Discord and Rcon password from .env

load_dotenv()
discord_token = os.getenv("DISCORD_TOKEN")
rcon_password = os.getenv("RCON_PASSWORD")

# Gets Server ip and latest log directory

with open("config.json", "r") as f:
    data = json.load(f)
server_ip = data.get("mcserverip")
print(f"Your server ip is {server_ip}")

with open("config.json", "r") as f:
    data = json.load(f)
server_port = data.get("serverport")

with open("config.json", "r") as f:
    data = json.load(f)
latest_log = data.get("latestlogdir")
print (f"Latest directory is {latest_log}")

with open("config.json", "r") as f:
    data = json.load(f)
channel_id = int(data.get("channelid"))
print (f"Your channel id is {channel_id}")

with open("config.json", "r") as f:
    data = json.load(f)
stats_dir = (data.get("stats"))
print (f"Stats directory is {stats_dir}")

# Intents and Prefixes

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!!', intents=intents)
bot.remove_command('help')

json_file = glob.glob(stats_dir)

# Function to get server status

def get_status():
    server = JavaServer.lookup(f"{server_ip}:{server_port}")
    return server.status()

# Prints a message when the bot is ready to use

@bot.event
async def on_ready():
    print(f"{bot.user.name} is online")
    bot.loop.create_task(mc_chat())

# Checks if a message is said in #chat-bridge
# If boolean is true it will send the message to minecraft chat

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.channel.id == channel_id:
        if "!!" in message.content:
            await bot.process_commands(message)
        else:
            await to_minecraft(message)



# Sends the message to Minecraft chat via RCON

async def to_minecraft(message):
    message_text = message.clean_content
    custom_emoji = re.compile(r"<:([a-zA-Z0-9_]+):\d+>")
    message_text = custom_emoji.sub(r"\1", message_text)
    for attachment in message.attachments:
        message_text += f" [Attachment: {attachment.url}]"

    def send_rcon():
        with MCRcon(server_ip, rcon_password, port=25575) as mcr:
            tellraw_payload = [
            {"text": f"<Chat-Bridge> <{message.author.display_name}>", "color": "green"},
            {"text": f" {message_text}", "color":"white"}
        ]
            # Send Text to server

            mcr.command(f"/tellraw @a {json.dumps(tellraw_payload)}")

    await asyncio.to_thread(send_rcon)

async def mc_chat():
    file = open(latest_log, "r")
    file.seek(0, 2)
    while True:
        line = file.readline()
        if not line:
            await asyncio.sleep(1)
            continue
        if "<" in line and ">" in line:
            try:
                player = line.split("<")[1].split(">")[0]
                message = line.split(">")[1].strip()
                mc_msg = f"<{player}> : {message}"

                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(mc_msg)
            except Exception as e:
                print("Error parsing line:", e)
        if "left the game" in line:
            player_name = line.split("]: ")[1].replace("left the game", "").strip()
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(f"`{player_name}` has left the game")
        if "joined the game" in line:
            player_name = line.split("]: ")[1].replace("joined the game", "").strip()
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(f"`{player_name}` has joined the game")

# ALL BELOW ARE COMMANDS!!!

# !!help
@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(title="Help Commands", colour=discord.Colour.orange())
    embed.add_field(name="List of commands:", value="```!!help: Shows this help message"
                                                    "\n!!online: Shows players online"
                                                    "\n!!status: Shows server status and ping"
                                                    "\n!!score <objective>```", inline=False)
    await ctx.send(embed=embed)

# !!online
@bot.command()
async def online(ctx):
    try:
        status = get_status()
        players = status.players.sample
        if not players:
            await ctx.reply("""`No players online`""")
            return
        for player in players:
            await ctx.reply(f"""`Players Online: {status.players.online}
{player.name}`""")
    except Exception as e:
        await ctx.reply("Could not fetch server status")
        print(e)

# !!status
@bot.command(name='status')
async def server_status(ctx):
    try:
        status = get_status()
        await ctx.reply(f"Latency: {status.latency:.2f}ms")
    except Exception as e:
        print(e)
        await ctx.reply("Could not fetch server status")

# !!score
@bot.command(name="score")
async def score(ctx, *, obj):
    obj = obj.lower().replace("_", "")

    try:
        for path in json_file:
            uuid = os.path.splitext(os.path.basename(path))[0]
            uuid_no_dash = uuid.replace("-", "")
            url = f"https://api.ashcon.app/mojang/v2/user/{uuid_no_dash}"
            response = requests.get(url)

            if response.status_code != 200:
                raise Exception("invalid UUID")

            username = response.json()
            username = username.get("username")
            print(username)

            try:
                with open(path, "r") as file:
                    stats = json.load(file)

                    for stat_key, stat_value in stats.items():
                        stat = stat_key.replace("stat.","").replace("minecraft.", "").replace("_", "")
                        if "." in stat:
                            start = stat[0]
                            dot_index = stat.index(".")
                            stat = start + stat[dot_index:]
                            if obj == stat:
                                print(f"{stat_key}: {stat_value}")
                                embed = discord.Embed(title=f"{stat}", colour=discord.Colour.orange())
                                embed.add_field(name="User", value=f"```{username:<8} | {stat_value:>8}```", inline=False)
                                await ctx.send(embed=embed)
                            else:
                                pass
                        else:
                            if obj == stat:
                                print(f"{stat_key}: {stat_value}")
                                embed = discord.Embed(title=f"{stat}", colour=discord.Colour.orange())
                                embed.add_field(name="User", value=f"```{username:<8} | {stat_value:>8}```", inline=False)
                                await ctx.send(embed=embed)
            except Exception as e:
                print(e)

    except Exception as e:
        print(e)
        await ctx.reply("Could not find any paths")



bot.run(discord_token, log_handler=handler, log_level=logging.DEBUG)