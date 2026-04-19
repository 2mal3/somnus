import discord

TOTAL_PROGRESS_BAR_STEPS = 20

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
