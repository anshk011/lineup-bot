"""
Telegram ConversationHandler for the lineup search flow.

Flow:
  /lineup
    → pick agent (inline keyboard, paginated)
    → pick map
    → pick side
    → pick type (Lineup / Setup / All)
    → results with ◀ ▶ navigation
    → tap a result → full detail images
"""

from __future__ import annotations

import logging
import math
from typing import Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from src.lineups.scraper import fetch_lineups, fetch_lineup_images, Lineup
from src.lineups.constants import AGENTS, MAPS, SIDES, LINEUP_TYPES, PAGE_SIZE
from src.config import settings

logger = logging.getLogger(__name__)

# Conversation states
(
    STATE_AGENT,
    STATE_MAP,
    STATE_SIDE,
    STATE_TYPE,
    STATE_RESULTS,
) = range(5)

# Callback data prefixes
CB_AGENT = "lu_agent"
CB_MAP = "lu_map"
CB_SIDE = "lu_side"
CB_TYPE = "lu_type"
CB_RESULT = "lu_result"
CB_NAV = "lu_nav"
CB_DETAIL = "lu_detail"
CB_BACK = "lu_back"
CB_CANCEL = "lu_cancel"

# Keys stored in context.user_data
KEY_AGENT = "lu_sel_agent"
KEY_MAP = "lu_sel_map"
KEY_SIDE = "lu_sel_side"
KEY_TYPE = "lu_sel_type"
KEY_RESULTS = "lu_results"
KEY_PAGE = "lu_page"
KEY_TOTAL = "lu_total"


def _is_allowed(update: Update) -> bool:
    return (
        update.effective_user is not None
        and update.effective_user.id == settings.telegram_allowed_user_id
    )


def _chunk(lst: list, size: int) -> list[list]:
    """Split a list into chunks of given size."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def _agent_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """Build paginated agent selection keyboard (3 per row, 3 rows per page)."""
    per_page = 9
    total_pages = math.ceil(len(AGENTS) / per_page)
    agents_slice = AGENTS[page * per_page : (page + 1) * per_page]

    rows = []
    for chunk in _chunk(agents_slice, 3):
        rows.append([InlineKeyboardButton(a, callback_data=f"{CB_AGENT}:{a}") for a in chunk])

    # Navigation row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"{CB_AGENT}_page:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if (page + 1) < total_pages:
        nav.append(InlineKeyboardButton("Next ▶", callback_data=f"{CB_AGENT}_page:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL)])
    return InlineKeyboardMarkup(rows)


def _map_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for chunk in _chunk(MAPS, 3):
        rows.append([InlineKeyboardButton(m, callback_data=f"{CB_MAP}:{m}") for m in chunk])
    rows.append([InlineKeyboardButton("🗺 Any Map", callback_data=f"{CB_MAP}:Any")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL)])
    return InlineKeyboardMarkup(rows)


def _side_keyboard() -> InlineKeyboardMarkup:
    icons = {"Attack": "🟥", "Defense": "🟦", "Any": "⚪"}
    rows = [[
        InlineKeyboardButton(f"{icons[s]} {s}", callback_data=f"{CB_SIDE}:{s}")
        for s in SIDES
    ]]
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL)])
    return InlineKeyboardMarkup(rows)


def _type_keyboard() -> InlineKeyboardMarkup:
    icons = {"Lineup": "🎯", "Setup": "🛠", "All": "📋"}
    rows = [[
        InlineKeyboardButton(f"{icons[t]} {t}", callback_data=f"{CB_TYPE}:{t}")
        for t in LINEUP_TYPES
    ]]
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL)])
    return InlineKeyboardMarkup(rows)


def _results_keyboard(lineups: list[Lineup], page: int, total: int) -> InlineKeyboardMarkup:
    """Build results list keyboard with lineup buttons and prev/next navigation."""
    rows = []

    start = page * PAGE_SIZE
    page_lineups = lineups[start : start + PAGE_SIZE]

    for i, lu in enumerate(page_lineups):
        label = f"{lu.agent} • {lu.title[:35]}{'…' if len(lu.title) > 35 else ''}"
        rows.append([InlineKeyboardButton(label, callback_data=f"{CB_DETAIL}:{lu.id}")])

    # Navigation
    total_pages = math.ceil(total / PAGE_SIZE)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"{CB_NAV}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if (page + 1) < total_pages:
        nav.append(InlineKeyboardButton("Next ▶", callback_data=f"{CB_NAV}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("🔄 New Search", callback_data=CB_BACK),
        InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL),
    ])
    return InlineKeyboardMarkup(rows)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_lineup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /lineup"""
    if not _is_allowed(update):
        await update.message.reply_text("🚫 Access denied.")
        return ConversationHandler.END

    # Clear previous session data
    for key in (KEY_AGENT, KEY_MAP, KEY_SIDE, KEY_TYPE, KEY_RESULTS, KEY_PAGE, KEY_TOTAL):
        context.user_data.pop(key, None)

    await update.message.reply_text(
        "🎯 *Lineup Finder*\n\nStep 1/4 — Pick an agent:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_agent_keyboard(0),
    )
    return STATE_AGENT


async def on_agent_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle agent keyboard pagination."""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[1])
    await query.edit_message_reply_markup(reply_markup=_agent_keyboard(page))
    return STATE_AGENT


async def on_agent_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Agent selected — move to map selection."""
    query = update.callback_query
    await query.answer()
    agent = query.data.split(":")[1]
    context.user_data[KEY_AGENT] = agent

    await query.edit_message_text(
        f"✅ Agent: *{agent}*\n\nStep 2/4 — Pick a map:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_map_keyboard(),
    )
    return STATE_MAP


async def on_map_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Map selected — move to side selection."""
    query = update.callback_query
    await query.answer()
    map_name = query.data.split(":")[1]
    context.user_data[KEY_MAP] = "" if map_name == "Any" else map_name
    agent = context.user_data.get(KEY_AGENT, "?")

    await query.edit_message_text(
        f"✅ Agent: *{agent}*  |  Map: *{map_name}*\n\nStep 3/4 — Pick a side:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_side_keyboard(),
    )
    return STATE_SIDE


async def on_side_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Side selected — move to type selection."""
    query = update.callback_query
    await query.answer()
    side = query.data.split(":")[1]
    context.user_data[KEY_SIDE] = "" if side == "Any" else side
    agent = context.user_data.get(KEY_AGENT, "?")
    map_name = context.user_data.get(KEY_MAP, "Any")

    await query.edit_message_text(
        f"✅ Agent: *{agent}*  |  Map: *{map_name}*  |  Side: *{side}*\n\nStep 4/4 — Lineup or Setup?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_type_keyboard(),
    )
    return STATE_TYPE


async def on_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Type selected — fetch results."""
    query = update.callback_query
    await query.answer()
    lu_type = query.data.split(":")[1]
    context.user_data[KEY_TYPE] = "" if lu_type == "All" else lu_type
    context.user_data[KEY_PAGE] = 0

    agent = context.user_data.get(KEY_AGENT, "")
    map_name = context.user_data.get(KEY_MAP, "")
    side = context.user_data.get(KEY_SIDE, "")
    lineup_type = context.user_data.get(KEY_TYPE, "")

    await query.edit_message_text(
        f"🔍 Searching lineups for *{agent}* on *{map_name or 'any map'}*...\n_(this takes ~10 seconds)_",
        parse_mode=ParseMode.MARKDOWN,
    )

    result = await fetch_lineups(
        agent=agent,
        map_name=map_name,
        side=side,
        lineup_type=lineup_type,
    )

    if not result.lineups:
        await query.edit_message_text(
            "😕 No lineups found for that combination. Try different filters.\n\nUse /lineup to search again.",
        )
        return ConversationHandler.END

    context.user_data[KEY_RESULTS] = [
        {
            "id": lu.id,
            "title": lu.title,
            "agent": lu.agent,
            "ability": lu.ability,
            "from": lu.from_location,
            "to": lu.to_location,
            "thumbnail": lu.thumbnail_url,
            "url": lu.lineup_url,
            "type": lu.lineup_type,
            "side": side,
            "map": map_name,
        }
        for lu in result.lineups
    ]
    context.user_data[KEY_TOTAL] = result.total

    await _send_results_page(query, context, page=0)
    return STATE_RESULTS


async def _send_results_page(query: Any, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Edit the current message to show a results page."""
    lineups_data: list[dict] = context.user_data.get(KEY_RESULTS, [])
    total: int = context.user_data.get(KEY_TOTAL, len(lineups_data))
    agent = context.user_data.get(KEY_AGENT, "")
    map_name = context.user_data.get(KEY_MAP, "any map")
    side = context.user_data.get(KEY_SIDE, "any side")

    # Reconstruct Lineup objects for keyboard builder
    lineups = [
        type("L", (), {"id": d["id"], "title": d["title"], "agent": d["agent"]})()
        for d in lineups_data
    ]

    total_pages = math.ceil(total / PAGE_SIZE)
    start = page * PAGE_SIZE + 1
    end = min((page + 1) * PAGE_SIZE, total)

    header = (
        f"📋 *{agent}* lineups on *{map_name or 'any map'}* ({side or 'any side'})\n"
        f"Showing {start}–{end} of {total}  •  Page {page+1}/{total_pages}\n\n"
        f"Tap a lineup to see the full setup 👇"
    )

    await query.edit_message_text(
        header,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_results_keyboard(lineups, page, total),
    )


async def on_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle ◀ / ▶ navigation in results."""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[1])
    context.user_data[KEY_PAGE] = page
    await _send_results_page(query, context, page)
    return STATE_RESULTS


async def on_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show all step images for a selected lineup."""
    query = update.callback_query
    await query.answer("Loading lineup... ⏳")
    lineup_id = query.data.split(":")[1]

    lineups_data: list[dict] = context.user_data.get(KEY_RESULTS, [])
    cached = next((d for d in lineups_data if d["id"] == lineup_id), None)

    await query.edit_message_text(f"🔍 Loading lineup `{lineup_id}`...", parse_mode=ParseMode.MARKDOWN)

    is_setup = cached.get("type", "lineup") == "setup" if cached else False
    images = await fetch_lineup_images(lineup_id, is_setup=is_setup)

    # Build caption
    title = cached["title"] if cached else f"Lineup {lineup_id}"
    agent = cached.get("agent", "") if cached else ""
    ability = cached.get("ability", "") if cached else ""
    from_loc = cached.get("from", "") if cached else ""
    to_loc = cached.get("to", "") if cached else ""
    side = cached.get("side", "") if cached else ""
    map_name = cached.get("map", "") if cached else ""

    caption_lines = [f"*{title}*"]
    if agent:
        caption_lines.append(f"🧑 {agent}" + (f" — {ability}" if ability else ""))
    if map_name:
        caption_lines.append(f"🗺 {map_name}")
    if side:
        caption_lines.append("🟥 Attack" if side == "Attack" else "🟦 Defense")
    if from_loc and to_loc:
        caption_lines.append(f"📍 {from_loc} → {to_loc}")
    elif to_loc:
        caption_lines.append(f"📍 {to_loc}")
    caption_lines.append(f"🖼 {len(images)} step{'s' if len(images) != 1 else ''}")
    caption = "\n".join(caption_lines)

    back_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀ Back to Results", callback_data=f"{CB_NAV}:{context.user_data.get(KEY_PAGE, 0)}"),
        InlineKeyboardButton("🔄 New Search", callback_data=CB_BACK),
    ]])

    if not images:
        # No images found — send thumbnail as fallback
        thumbnail = cached.get("thumbnail", "") if cached else ""
        if thumbnail:
            await query.message.reply_photo(
                photo=thumbnail,
                caption=caption + "\n\n_(thumbnail only — step images unavailable)_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_keyboard,
            )
        else:
            await query.edit_message_text(
                caption + "\n\n⚠️ No images found.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_keyboard,
            )
        return STATE_RESULTS

    # Send images in batches of 10 (Telegram media group limit)
    # First batch gets the caption, rest are silent
    try:
        for batch_start in range(0, len(images), 10):
            batch = images[batch_start : batch_start + 10]
            is_first_batch = batch_start == 0
            is_last_batch = batch_start + 10 >= len(images)

            media_group = [
                InputMediaPhoto(
                    media=img,
                    caption=caption if (is_first_batch and i == 0) else None,
                    parse_mode=ParseMode.MARKDOWN if (is_first_batch and i == 0) else None,
                )
                for i, img in enumerate(batch)
            ]
            await query.message.reply_media_group(media=media_group)

            if is_last_batch:
                await query.message.reply_text(
                    "Navigate:",
                    reply_markup=back_keyboard,
                )

        await query.delete_message()

    except Exception as e:
        logger.warning("Media group send failed: %s", e)
        # Fallback: send images one by one
        for i, img_url in enumerate(images[:10]):
            cap = caption if i == 0 else None
            kb = back_keyboard if i == len(images) - 1 else None
            await query.message.reply_photo(
                photo=img_url,
                caption=cap,
                parse_mode=ParseMode.MARKDOWN if cap else None,
                reply_markup=kb,
            )
        await query.delete_message()

    return STATE_RESULTS


async def on_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Restart the search flow."""
    query = update.callback_query
    await query.answer()

    for key in (KEY_AGENT, KEY_MAP, KEY_SIDE, KEY_TYPE, KEY_RESULTS, KEY_PAGE, KEY_TOTAL):
        context.user_data.pop(key, None)

    await query.edit_message_text(
        "🎯 *Lineup Finder*\n\nStep 1/4 — Pick an agent:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_agent_keyboard(0),
    )
    return STATE_AGENT


async def on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Lineup search cancelled. Use /lineup to start again.")
    return ConversationHandler.END


async def on_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle no-op buttons (page counter display)."""
    await update.callback_query.answer()
    return STATE_RESULTS


def build_lineup_conversation() -> ConversationHandler:
    """Build and return the ConversationHandler for lineup search."""
    return ConversationHandler(
        entry_points=[CommandHandler("lineup", cmd_lineup)],
        states={
            STATE_AGENT: [
                CallbackQueryHandler(on_agent_page, pattern=f"^{CB_AGENT}_page:"),
                CallbackQueryHandler(on_agent_select, pattern=f"^{CB_AGENT}:"),
                CallbackQueryHandler(on_cancel, pattern=f"^{CB_CANCEL}$"),
            ],
            STATE_MAP: [
                CallbackQueryHandler(on_map_select, pattern=f"^{CB_MAP}:"),
                CallbackQueryHandler(on_cancel, pattern=f"^{CB_CANCEL}$"),
            ],
            STATE_SIDE: [
                CallbackQueryHandler(on_side_select, pattern=f"^{CB_SIDE}:"),
                CallbackQueryHandler(on_cancel, pattern=f"^{CB_CANCEL}$"),
            ],
            STATE_TYPE: [
                CallbackQueryHandler(on_type_select, pattern=f"^{CB_TYPE}:"),
                CallbackQueryHandler(on_cancel, pattern=f"^{CB_CANCEL}$"),
            ],
            STATE_RESULTS: [
                CallbackQueryHandler(on_nav, pattern=f"^{CB_NAV}:"),
                CallbackQueryHandler(on_detail, pattern=f"^{CB_DETAIL}:"),
                CallbackQueryHandler(on_back, pattern=f"^{CB_BACK}$"),
                CallbackQueryHandler(on_cancel, pattern=f"^{CB_CANCEL}$"),
                CallbackQueryHandler(on_noop, pattern="^noop$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", on_cancel),
            CommandHandler("lineup", cmd_lineup),
        ],
        per_user=True,
        per_chat=True,
    )
