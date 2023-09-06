import json
import discord

from bot import Bot
from config_loader import load_config, save_config
from poker import set_image_channel

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

bot_list = {}

@client.event
async def on_ready():
    print(f'logged in as {client.user}')
    load_config()
    set_image_channel(client.get_channel(1148593469212860456))

@client.event
async def on_message(msg):
    guild = msg.guild

    if guild == None: # DM channel
        return
    
    if not guild.id in bot_list:
        bot_list[guild.id] = Bot(guild)

    if msg.content == '>>>save_config':
        save_config()
        await msg.channel.send("success")
        return

    await bot_list[guild.id].on_message(msg)



from bot_token import token
client.run(token)