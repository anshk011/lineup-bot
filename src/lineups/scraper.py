"""
Scrapes lineupsvalorant.com using Playwright (headless Chromium).
Selectors confirmed from live HTML inspection.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)

BASE_URL = "https://lineupsvalorant.com"
CDN_BASE = "https://lineupsvalorant.b-cdn.net"


@dataclass
class Lineup:
    id: str
    title: str
    agent: str
    ability: str
    from_location: str
    to_location: str
    thumbnail_url: str
    lineup_url: str
    lineup_type: str  # "lineup" or "setup"


@dataclass
class LineupPage:
    lineups: list[Lineup]
    total: int
    page: int
    per_page: int = 12

    @property
    def has_next(self) -> bool:
        return (self.page * self.per_page) < self.total

    @property
    def has_prev(self) -> bool:
        return self.page > 1


async def _parse_cards(page: Page) -> list[Lineup]:
    """
    Extract all lineup cards from the current page state.
    Selector: div.lineup-box[data-id]
    """
    lineups: list[Lineup] = []

    try:
        await page.wait_for_selector("div.lineup-box[data-id]", timeout=15000)
    except PWTimeout:
        logger.warning("No lineup cards found within timeout.")
        return lineups

    cards = await page.query_selector_all("div.lineup-box[data-id]")
    logger.info("Found %d lineup cards", len(cards))

    for card in cards:
        try:
            lineup_id = await card.get_attribute("data-id") or ""
            if not lineup_id:
                continue

            # Title
            title_el = await card.query_selector("span.lineup-box-title")
            title = (await title_el.inner_text()).strip() if title_el else f"Lineup {lineup_id}"

            # Thumbnail
            thumb_el = await card.query_selector("img.lineup-box-image")
            thumbnail_url = ""
            if thumb_el:
                src = await thumb_el.get_attribute("src") or ""
                thumbnail_url = src if src.startswith("http") else f"{CDN_BASE}{src}"

            # Determine type from thumbnail URL
            lineup_type = "setup" if "setup_images" in thumbnail_url else "lineup"

            # Agent
            agent_el = await card.query_selector("img.lineup-box-agent")
            agent = ""
            if agent_el:
                agent = (await agent_el.get_attribute("alt") or "").strip()

            # Abilities (can be multiple)
            ability_els = await card.query_selector_all("div.lineup-box-abilities img")
            abilities = []
            for ab in ability_els:
                alt = (await ab.get_attribute("alt") or "").strip()
                if alt:
                    abilities.append(alt)
            ability = ", ".join(dict.fromkeys(abilities))  # deduplicate, preserve order

            # From / To — inside span.lineup-box-position
            pos_el = await card.query_selector("span.lineup-box-position")
            from_loc = ""
            to_loc = ""
            if pos_el:
                pos_text = (await pos_el.inner_text()).strip()
                # Patterns: "From X to Y" or "For X"
                if " to " in pos_text:
                    parts = pos_text.replace("From", "").replace("from", "").split(" to ", 1)
                    from_loc = parts[0].strip()
                    to_loc = parts[1].strip() if len(parts) > 1 else ""
                elif pos_text.lower().startswith("for "):
                    to_loc = pos_text[4:].strip()

            lineups.append(
                Lineup(
                    id=lineup_id,
                    title=title,
                    agent=agent,
                    ability=ability,
                    from_location=from_loc,
                    to_location=to_loc,
                    thumbnail_url=thumbnail_url,
                    lineup_url=f"{BASE_URL}/lineup/{lineup_id}",
                    lineup_type=lineup_type,
                )
            )

        except Exception as e:
            logger.debug("Error parsing card: %s", e)
            continue

    return lineups


async def fetch_lineups(
    agent: str = "",
    map_name: str = "",
    side: str = "",
    lineup_type: str = "",
    page_num: int = 1,
) -> LineupPage:
    """
    Fetch lineups from lineupsvalorant.com with the given filters.

    Args:
        agent: Agent name e.g. "Sova". Empty = any.
        map_name: Map name e.g. "Ascent". Empty = any.
        side: "Attack", "Defense", or "" for any.
        lineup_type: "Lineup", "Setup", or "" for all.
        page_num: Page number (1-indexed), client-side pagination of 12 per page.

    Returns:
        LineupPage with results and pagination info.
    """
    params: dict[str, str] = {}
    if agent:
        params["agent"] = agent
    if map_name:
        params["map"] = map_name
    if side and side.lower() != "any":
        params["side"] = side
    if lineup_type and lineup_type.lower() not in ("all", ""):
        params["type"] = lineup_type

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/?{query}" if query else BASE_URL

    logger.info("Fetching lineups: %s (page %d)", url, page_num)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=25000)

            all_lineups = await _parse_cards(page)

            per_page = 12
            total = len(all_lineups)
            start = (page_num - 1) * per_page
            page_lineups = all_lineups[start : start + per_page]

            return LineupPage(
                lineups=page_lineups,
                total=total,
                page=page_num,
                per_page=per_page,
            )

        except PWTimeout:
            logger.error("Timeout loading lineupsvalorant.com")
            return LineupPage(lineups=[], total=0, page=page_num)
        except Exception as e:
            logger.exception("Error fetching lineups: %s", e)
            return LineupPage(lineups=[], total=0, page=page_num)
        finally:
            await browser.close()


async def fetch_lineup_images(lineup_id: str, is_setup: bool = False) -> list[str]:
    """
    Fetch all step image URLs for a lineup by probing the CDN directly.

    CDN patterns:
      Lineups: https://lineupsvalorant.b-cdn.net/static/lineup_images/{ID}/{N}.webp
      Setups:  https://lineupsvalorant.b-cdn.net/static/setup_images/{ID}/{N}.webp

    Probes N=1,2,3,... until a 404 is returned. Fast — no browser needed.

    Args:
        lineup_id: Numeric lineup/setup ID.
        is_setup: True if this is a setup (uses setup_images path).

    Returns:
        List of valid image URLs in step order.
    """
    folder = "setup_images" if is_setup else "lineup_images"
    base = f"{CDN_BASE}/static/{folder}/{lineup_id}"
    images: list[str] = []

    async with httpx.AsyncClient(timeout=5.0) as client:
        for n in range(1, 20):  # max 19 steps — more than enough
            url = f"{base}/{n}.webp"
            try:
                resp = await client.head(url)
                if resp.status_code == 200:
                    images.append(url)
                else:
                    break  # first non-200 = no more steps
            except Exception:
                break

    logger.info("Found %d step images for %s %s", len(images), folder, lineup_id)
    return images
