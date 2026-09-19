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


def _normalize_name(name: str) -> str:
    """Trim + casefold so tiny formatting differences don't cause false mismatches."""

    return name.strip().casefold()


async def get_clan_data():
    """
    Fetches the live rankings JSON and returns the member_list
    (list of {"name", "premium", "level", "reputation"}) for CLAN_NAME.

    NOTE: as of the current API, member entries no longer include a
    numeric id - "name" (the in-game IGN) is the only identifier we
    have to match against.

    Returns None if the API could not be reached, returned a bad
    status, or the clan could not be found in the payload - callers
    should treat None as "could not verify right now", not as
    "clan is empty".
    """

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

                    return None


                data = await response.json()


    except Exception as e:

        print(
            f"API connection error: {e}"
        )

        return None



    for clan in data.get("clans", []):

        if _normalize_name(clan.get("name", "")) == _normalize_name(CLAN_NAME):

            return clan.get(
                "member_list",
                []
            )


    print(
        f"Clan not found: {CLAN_NAME}"
    )

    return None



async def get_clan_members():
    """Backwards-compatible helper: just the list of member IGNs (strings)."""

    member_list = await get_clan_data()

    if member_list is None:

        return []


    return [
        member.get("name", "")
        for member in member_list
    ]



async def check_clan_membership(ign: str):
    """
    Validates an ign against the live Hidden Cloud Village member list.

    Returns a dict with a "status" key, one of:

        "ok"        - ign (normalized) matches a current clan member
        "not_found" - ign is not in the clan's member list
        "error"     - couldn't reach / parse the API right now.

    There is no more "name_mismatch" case: the API only exposes names
    now, so there's nothing left to cross-check a name against.
    """

    member_list = await get_clan_data()

    if member_list is None:

        return {
            "status": "error"
        }


    normalized_ign = _normalize_name(ign)

    for member in member_list:

        if _normalize_name(member.get("name", "")) == normalized_ign:

            return {
                "status": "ok"
            }


    return {
        "status": "not_found"
    }




async def check_members():

    clan_members = await get_clan_members()


    if not clan_members:

        return []


    normalized_clan_members = {
        _normalize_name(name)
        for name in clan_members
    }


    users = await get_users()

    results = []



    for (
        discord_id,
        ign,
        missing,
        removed
    ) in users:



        # Already removed, ignore

        if removed:

            continue



        if _normalize_name(ign) not in normalized_clan_members:

            missing += 1

        else:

            missing = 0



        await update_missing(
            discord_id,
            missing
        )



        # Require 3 failed checks
        # 3 x 10 seconds = about 30 seconds

        if missing >= 3:

            results.append(
                {
                    "discord_id": discord_id,
                    "ign": ign
                }
            )



    return results
