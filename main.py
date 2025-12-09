import asyncio

import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os, json, re
from mcstatus import JavaServer
from mcrcon import MCRcon

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

with open("config.json", "r") as f:
    data = json.load(f)
channel_id = int(data.get("channelid"))
print (f"Your channel id is {channel_id}")

# Intents and Prefixes

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!!', intents=intents)
bot.remove_command('help')

# Function to get server status

def get_status():
    server = JavaServer.lookup(f"{server_ip}:{server_port}")
    return server.status()

# Prints a message when the bot is ready to use

@bot.event
async def on_ready():
    print(f"{bot.user.name} is online")
    bot.loop.create_task(mc_chat(bot))

# Checks if a message is said in #chat-bridge
# If boolean is true it will send the message to minecraft chat

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.channel.id == channel_id:
        to_minecraft(message)

    await bot.process_commands(message)

# Sends the message to Minecraft chat via RCON

def to_minecraft(message):
    message_text = message.clean_content
    custom_emoji = re.compile(r"<:([a-zA-Z0-9_]+):\d+>")
    message_text = custom_emoji.sub(r"\1", message_text)
    for attachment in message.attachments:
        message_text += f" [Attachment: {attachment.url}]"
    with MCRcon(server_ip, rcon_password, port=25575) as mcr:
        tellraw_payload = [
        {"text": f"<Chat-Bridge> <{message.author.display_name}>", "color": "green"},
        {"text": f" {message_text}", "color":"white"}
    ]
        # Send Text to server

        mcr.command(f"/tellraw @a {json.dumps(tellraw_payload)}")


async def mc_chat(bot):
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
                await channel.send(f"```{player_name} has left the game```")
        if "joined the game" in line:
            player_name = line.split("]: ")[1].replace("joined the game", "").strip()
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(f"```{player_name} has joined the game```")


# ALL BELOW ARE COMMANDS!!!

# !!help
@bot.command(name='help')
async def help_command(ctx):
    await ctx.reply("""```List of commands:
!!online: Shows players online 
!!status: Shows server status and ping```""")

# !!online
@bot.command()
async def online(ctx):
    try:
        status = get_status()
        players = status.players.sample
        if not players:
            await ctx.reply("""```No players online```""")
            return
        for player in players:
            await ctx.reply(f"""```Players Online: {status.players.online}
{player.name}```""")
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
        await ctx.reply("Could not fetch server status")
        print(e)

bot.run(discord_token, log_handler=handler, log_level=logging.DEBUG)