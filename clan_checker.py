import aiohttp
import os

from dotenv import load_dotenv

from database import (
    get_users,
    update_missing
)


load_dotenv()


API_URL = "https://static.ninjasaga.cc/data/clan_rankings.json"

CLAN_NAME = os.getenv(
    "CLAN_NAME",
    "Hidden Cloud Village"
)



async def get_clan_members():

    try:

        timeout = aiohttp.ClientTimeout(
            total=10
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(API_URL) as response:

                if response.status != 200:

                    print(
                        f"API returned HTTP {response.status}"
                    )

                    return []


                data = await response.json()


    except Exception as e:

        print(
            f"API connection error: {e}"
        )

        return []



    for clan in data.get("clans", []):

        if clan.get("name") == CLAN_NAME:

            return [
                member["id"]
                for member in clan.get(
                    "member_list",
                    []
                )
            ]



    print(
        f"Clan not found: {CLAN_NAME}"
    )

    return []





async def check_members():

    clan_members = await get_clan_members()


    if not clan_members:

        return []



    users = await get_users()


    results = []



    for (
        discord_id,
        game_id,
        ign,
        missing,
        removed
    ) in users:



        # Already removed, ignore

        if removed:

            continue



        if game_id not in clan_members:

            missing += 1


        else:

            missing = 0



        await update_missing(
            discord_id,
            missing
        )



        # Require 6 failed checks
        # 6 x 10 seconds = about 1 minute

        if missing >= 3:

            results.append(
                {
                    "discord_id": discord_id,
                    "game_id": game_id,
                    "ign": ign
                }
            )



    return results