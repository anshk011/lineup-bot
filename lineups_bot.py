"""
Standalone Lineup Finder Bot.
Run this independently — no Valorant required.

    python lineups_bot.py

Then send /lineup to your Telegram bot.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from telegram.ext import Application

from src.lineups.bot_handler import build_lineup_conversation
from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def main() -> None:
    logger.info("Starting Lineup Finder Bot...")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(build_lineup_conversation())

    logger.info("Lineup bot running. Send /lineup to your Telegram bot.")
    logger.info("Press Ctrl+C to stop.")

    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

        stop_event = asyncio.Event()

        def _handle_signal(*_) -> None:
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(sig, _handle_signal)
            except NotImplementedError:
                signal.signal(sig, _handle_signal)

        await stop_event.wait()

        await app.updater.stop()
        await app.stop()

    logger.info("Lineup bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
