from datetime import datetime, timezone

import aiohttp

EPIC_API = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"


async def fetch_games(session, country="RU", locale="ru-RU"):
    params = {"country": country, "locale": locale}
    async with session.get(EPIC_API, params=params) as response:
        response.raise_for_status()
        data = await response.json()
        return data["data"]["Catalog"]["searchStore"]["elements"]


async def get_free_games():
    async with aiohttp.ClientSession() as session:
        ru_games = await fetch_games(session, country="RU", locale="ru-RU")
        us_games = await fetch_games(session, country="US", locale="en-US")

    now = datetime.now(timezone.utc)

    def extract_games(game_list):
        free_games = {}
        for game in game_list:
            title = game["title"]
            promotions = game.get("promotions")
            if not promotions:
                continue

            current = promotions.get("promotionalOffers", [])
            if current:
                offer = current[0]["promotionalOffers"][0]
                start = datetime.fromisoformat(
                    offer["startDate"].replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(offer["endDate"].replace("Z", "+00:00"))
                if start <= now <= end:
                    free_games[title] = {
                        "title": title,
                        "start": start,
                        "end": end,
                        "id": game["id"],
                        "slug": game.get("productSlug")
                        or game.get("catalogNs", {})
                        .get("mappings", [{}])[0]
                        .get("pageSlug"),
                        "url": f'https://store.epicgames.com/p/{game.get("productSlug") or game.get("catalogNs", {}).get("mappings", [{}])[0].get("pageSlug")}',
                    }
        return free_games

    games_ru = extract_games(ru_games)
    games_us = extract_games(us_games)
    unavailable_ru = {k: v for k, v in games_us.items() if k not in games_ru}
    available_ru = games_ru

    return available_ru, unavailable_ru
