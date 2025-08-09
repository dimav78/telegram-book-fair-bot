from telegram import Bot
from config import TELEGRAM_TOKEN
import asyncio

async def test():
    bot = Bot(TELEGRAM_TOKEN)
    me = await bot.get_me()
    print(f'Bot connected: {me.first_name} (@{me.username})')

if __name__ == '__main__':
    asyncio.run(test())