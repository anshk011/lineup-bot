<div align="center">

# 🎯 Valorant Lineup Bot

**A Telegram bot that finds Valorant lineups and setups on demand.**  
Pick your agent, map, and side — get every step image sent straight to your phone.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)](https://python.org)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.3-blue?style=flat-square)](https://python-telegram-bot.org)
[![Playwright](https://img.shields.io/badge/Playwright-1.44-green?style=flat-square)](https://playwright.dev/python)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## ✨ What it does

Send `/lineup` to your bot and it walks you through 4 quick steps:

| Step | What you pick |
|------|--------------|
| 1 | Agent (Sova, Cypher, Brimstone...) |
| 2 | Map (Ascent, Bind, Haven...) |
| 3 | Side (Attack / Defense / Any) |
| 4 | Type (Lineup / Setup / All) |

Then it sends you **every step image** for each lineup — no tabbing out, no browser needed.

<div align="center">

```
/lineup
  → Pick agent   [Sova] [Cypher] [Brimstone] ...
  → Pick map     [Ascent] [Bind] [Haven] ...
  → Pick side    [🟥 Attack] [🟦 Defense] [⚪ Any]
  → Pick type    [🎯 Lineup] [🛠 Setup] [📋 All]
  → Results list with ◀ ▶ navigation
  → Tap any result → all step photos sent to chat
```

</div>

---

## 🚀 Setup

### 1. Clone the repo

```bash
git clone https://github.com/anshk011/lineup-bot.git
cd lineup-bot
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # Linux / Mac
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

> The `playwright install chromium` step downloads a headless browser (~150MB, one time only).

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ALLOWED_USER_ID=123456789
```

- **Bot token** → message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`
- **User ID** → message [@userinfobot](https://t.me/userinfobot) to get your numeric ID

### 5. Run

```bash
python lineups_bot.py
```

Open Telegram and send `/lineup` to your bot.

---

## 🗂 Project Structure

```
lineup-bot/
├── lineups_bot.py          # Entry point
├── src/
│   ├── config.py           # Settings (loaded from .env)
│   └── lineups/
│       ├── scraper.py      # Playwright scraper + CDN image fetcher
│       ├── bot_handler.py  # Telegram ConversationHandler
│       └── constants.py    # Agents, maps, sides lists
├── requirements.txt
└── .env.example
```

---

## ⚙️ How it works

1. **Scraper** — Playwright (headless Chromium) loads [lineupsvalorant.com](https://lineupsvalorant.com) with your filters applied as URL params. It reads `div.lineup-box[data-id]` cards to extract IDs, titles, agent names, and from/to locations.

2. **Image fetching** — Once you tap a lineup, the bot probes the CDN directly:
   ```
   https://lineupsvalorant.b-cdn.net/static/lineup_images/{ID}/1.webp
   https://lineupsvalorant.b-cdn.net/static/lineup_images/{ID}/2.webp
   ...
   ```
   It keeps going until it hits a 404 — no browser needed for this step, just fast HTTP HEAD requests.

3. **Telegram delivery** — Step images are sent as a media group (album) with the lineup info as caption. Supports up to 10 images per batch.

---

## 🔒 Privacy

- The bot only responds to the Telegram user ID set in `.env`
- No data is stored or logged beyond what python-telegram-bot handles in memory
- All image fetching is read-only from public CDN URLs

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `python-telegram-bot` | Telegram bot framework |
| `playwright` | Headless browser for scraping lineupsvalorant.com |
| `httpx` | Async HTTP for CDN image probing |
| `pydantic-settings` | `.env` config loading |

---

## 🙏 Credits

Lineup data sourced from [lineupsvalorant.com](https://lineupsvalorant.com) — go give them a visit.

---

<div align="center">
Made for the grind 🔥
</div>
