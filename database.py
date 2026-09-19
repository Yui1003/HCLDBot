import aiosqlite


DB_NAME = "clan_guard.db"


async def setup_database():

    async with aiosqlite.connect(DB_NAME) as db:

        # Does an old-style table (with the now-defunct game_id column)
        # already exist? If so, migrate it instead of clobbering it.

        cursor = await db.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='users'
            """
        )

        table_exists = await cursor.fetchone()

        if table_exists:

            cursor = await db.execute(
                "PRAGMA table_info(users)"
            )

            columns = [
                row[1]
                for row in await cursor.fetchall()
            ]

            if "game_id" in columns:

                print(
                    "Migrating clan_guard.db: dropping game_id "
                    "(no longer provided by the clan API), "
                    "keying users by ign instead."
                )

                await db.execute(
                    """
                    CREATE TABLE users_new (

                        discord_id INTEGER PRIMARY KEY,

                        ign TEXT NOT NULL,

                        missing_checks INTEGER DEFAULT 0,

                        removed INTEGER DEFAULT 0

                    )
                    """
                )

                await db.execute(
                    """
                    INSERT INTO users_new
                        (discord_id, ign, missing_checks, removed)
                    SELECT
                        discord_id, ign, missing_checks, removed
                    FROM users
                    """
                )

                await db.execute("DROP TABLE users")

                await db.execute(
                    "ALTER TABLE users_new RENAME TO users"
                )

                await db.commit()


                dupes = await get_duplicate_igns()

                if dupes:

                    print(
                        "⚠️  Migration finished, but found IGNs shared by "
                        "more than one active Discord account (this can "
                        "happen since the old schema only guarded against "
                        "duplicate game_id, not duplicate ign). Resolve "
                        "these with /duplicates and /modifyverify:"
                    )

                    for group in dupes:

                        print(
                            f"    {group}"
                        )

                else:

                    print(
                        "Migration finished. No duplicate IGNs found."
                    )

                return


        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (

            discord_id INTEGER PRIMARY KEY,

            ign TEXT NOT NULL,

            missing_checks INTEGER DEFAULT 0,

            removed INTEGER DEFAULT 0

        )
        """)

        await db.commit()



async def add_user(
    discord_id,
    ign
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            INSERT INTO users
            (
                discord_id,
                ign,
                missing_checks,
                removed
            )

            VALUES (?, ?, 0, 0)

            ON CONFLICT(discord_id)

            DO UPDATE SET

                ign = excluded.ign,

                missing_checks = 0,

                removed = 0
            """,

            (
                discord_id,
                ign
            )
        )

        await db.commit()



async def get_users():

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT
                discord_id,
                ign,
                missing_checks,
                removed

            FROM users
            """
        )

        return await cursor.fetchall()



async def get_user_by_discord_id(
    discord_id
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT
                discord_id,
                ign,
                missing_checks,
                removed

            FROM users

            WHERE discord_id = ?
            """,

            (
                discord_id,
            )
        )

        return await cursor.fetchone()



async def get_active_user_by_ign(
    ign
):
    """Case/whitespace-insensitive lookup, since the API is name-based now."""

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT
                discord_id,
                ign,
                missing_checks,
                removed

            FROM users

            WHERE LOWER(TRIM(ign)) = LOWER(TRIM(?))
            AND removed = 0
            """,

            (
                ign,
            )
        )

        return await cursor.fetchone()



async def get_duplicate_igns():
    """
    Groups active users that share the same normalized ign.

    This can only really happen from data carried over from the old
    game_id-keyed schema, where two different game_ids could share a
    display name (the old duplicate guard checked game_id, not ign).
    Returns a list of groups, each a list of (discord_id, ign) tuples,
    for every ign held by more than one active account.
    """

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT discord_id, ign

            FROM users

            WHERE removed = 0
            """
        )

        rows = await cursor.fetchall()


    groups = {}

    for discord_id, ign in rows:

        key = ign.strip().casefold()

        groups.setdefault(key, []).append(
            (discord_id, ign)
        )


    return [
        group
        for group in groups.values()
        if len(group) > 1
    ]



# NEW COMMAND SUPPORT
async def get_verified_users():

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT
                discord_id,
                ign

            FROM users

            WHERE removed = 0

            ORDER BY ign
            """
        )

        return await cursor.fetchall()



async def update_missing(
    discord_id,
    missing
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE users

            SET missing_checks = ?

            WHERE discord_id = ?
            """,

            (
                missing,
                discord_id
            )
        )

        await db.commit()



async def mark_removed(
    discord_id
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE users

            SET removed = 1

            WHERE discord_id = ?
            """,

            (
                discord_id,
            )
        )

        await db.commit()
