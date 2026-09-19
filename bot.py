from discord.ext import tasks
from clan_checker import check_members, get_clan_members, check_clan_membership

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

import os

from database import (
    setup_database,
    add_user,
    mark_removed,
    get_verified_users,
    get_user_by_discord_id,
    get_active_user_by_ign,
    get_duplicate_igns
)


load_dotenv()


TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = int(
    os.getenv("GUILD_ID")
)

LOG_CHANNEL_ID = int(
    os.getenv("LOG_CHANNEL_ID")
)

ENABLE_KICK = (
    os.getenv(
        "ENABLE_KICK",
        "false"
    ).lower() == "true"
)


intents = discord.Intents.default()

intents.members = True
intents.message_content = True


class ClanGuard(commands.Bot):

    async def setup_hook(self):

        await setup_database()

        guild = discord.Object(
            id=GUILD_ID
        )

        # Copy the (currently global) commands into guild scope
        # BEFORE wiping the global ones, so they aren't lost.
        self.tree.copy_global_to(
            guild=guild
        )

        # Now clear the old global registrations so they stop
        # showing up as duplicates (run once, then this list stays empty).
        self.tree.clear_commands(
            guild=None
        )

        await self.tree.sync()  # pushes the empty global list -> deletes old globals

        synced = await self.tree.sync(
            guild=guild
        )  # pushes the guild-scoped copies -> instant, no dupes

        print(
            f"Synced {len(synced)} guild commands"
        )


bot = ClanGuard(
    command_prefix="!",
    intents=intents
)


processed_players = set()



@tasks.loop(seconds=10)
async def clan_check():

    try:

        players = await check_members()


    except Exception as e:

        print(
            f"Checker error: {e}"
        )

        return


    if not players:

        return


    guild = bot.get_guild(
        GUILD_ID
    )


    if guild is None:

        print(
            "Guild not found"
        )

        return


    log_channel = bot.get_channel(
        LOG_CHANNEL_ID
    )


    for player in players:

        discord_id = player["discord_id"]


        if discord_id in processed_players:

            continue


        processed_players.add(
            discord_id
        )


        member = guild.get_member(
            discord_id
        )


        if member is None:

            continue


        print(
            f"Detected removal candidate: "
            f"{player['ign']}"
        )


        if not ENABLE_KICK:


            print(
                "Kick disabled. Dry-run mode."
            )


            if log_channel:

                await log_channel.send(
                    f"🧪 **Dry Run Detection**\n\n"
                    f"Player: `{player['ign']}`\n"
                    f"Discord: {member.mention}\n\n"
                    f"Kick disabled."
                )


            continue



        if member.id == guild.owner_id:

            print(
                "Skipped server owner."
            )

            continue



        if not guild.me.guild_permissions.kick_members:

            print(
                "Bot missing Kick Members permission."
            )

            continue



        try:

            await member.kick(
                reason=
                "No longer in Hidden Cloud Village"
            )


            await mark_removed(
                discord_id
            )


            print(
                f"Kicked {member}"
            )


            if log_channel:

                await log_channel.send(
                    f"🚪 **Automatic Clan Removal**\n\n"
                    f"Player: `{player['ign']}`\n"
                    f"Discord: {member.mention}\n\n"
                    f"Reason: No longer in Hidden Cloud Village"
                )


        except Exception as e:

            print(
                f"Kick failed: {e}"
            )




@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user}"
    )

    print(
        "Clan Guard online"
    )


    print(
        f"Kick mode: {ENABLE_KICK}"
    )


    if not clan_check.is_running():

        clan_check.start()





@bot.tree.command(
    name="verify",
    description="Link your Discord account with your Ninja Saga character"
)
@app_commands.describe(
    ign="Your Ninja Saga character name (must match exactly)"
)
async def verify(
    interaction: discord.Interaction,
    ign: str
):

    # Talking to the clan API can take a moment, so acknowledge
    # the interaction immediately to avoid a 3s timeout.
    await interaction.response.defer()


    # 1) This Discord account already has an active link?
    existing = await get_user_by_discord_id(
        interaction.user.id
    )

    if existing and not existing[3]:  # existing[3] == removed

        await interaction.followup.send(
            f"❌ Your Discord account is already linked to "
            f"IGN `{existing[1]}`.\n\n"
            f"If this needs to change, please ask an admin to update it "
            f"with `/modifyverify`."
        )

        return


    # 2) Is this ign already claimed by a *different* Discord account?
    #
    # NOTE: the clan API no longer exposes a numeric user id - IGN is
    # the only identifier it gives us - so this is just a "no two
    # Discord accounts claim the same name at once" guard, not proof
    # of ownership.
    conflict = await get_active_user_by_ign(
        ign
    )

    if conflict and conflict[0] != interaction.user.id:

        await interaction.followup.send(
            f"❌ IGN `{ign}` is already linked to another "
            f"Discord account.\n\n"
            f"If this is a mistake, please contact an admin."
        )

        return


    # 3) Validate against the live Hidden Cloud Village member list
    result = await check_clan_membership(
        ign
    )

    if result["status"] == "error":

        await interaction.followup.send(
            "⚠️ Couldn't reach the clan API right now. Please try again "
            "in a moment."
        )

        return


    if result["status"] == "not_found":

        await interaction.followup.send(
            f"❌ `{ign}` was not found in Hidden Cloud "
            f"Village's member list.\n\n"
            f"Make sure you're in the clan and that you entered your "
            f"in-game name exactly as it appears there."
        )

        return


    # result["status"] == "ok"

    await add_user(
        interaction.user.id,
        ign
    )


    await interaction.followup.send(
        f"✅ Verified!\n\n"
        f"IGN: `{ign}`"
    )






@app_commands.checks.has_permissions(administrator=True)
@bot.tree.command(
    name="clancheck",
    description="Check Hidden Cloud Village API members"
)
async def clancheck(
    interaction: discord.Interaction
):

    members = await get_clan_members()


    await interaction.response.send_message(
        f"☁️ **Hidden Cloud Village API Check**\n\n"
        f"Members found: `{len(members)}`\n\n"
        f"`{members[:50]}`"
    )






@app_commands.checks.has_permissions(administrator=True)
@bot.tree.command(
    name="verified",
    description="Show all verified Hidden Cloud Village members"
)
async def verified(
    interaction: discord.Interaction
):

    users = await get_verified_users()


    if not users:

        await interaction.response.send_message(
            "No verified players found."
        )

        return


    # Flag any ign held by more than one active account (mainly a
    # leftover risk from migrating the old game_id-keyed data - see
    # /duplicates for details).
    dupe_igns = {
        member[1].strip().casefold()
        for group in await get_duplicate_igns()
        for member in group
    }


    embed = discord.Embed(
        title="☁️ Verified Clan Members",
        color=discord.Color.blue()
    )


    for discord_id, ign in users:


        member = interaction.guild.get_member(
            discord_id
        )


        if member:

            discord_name = member.display_name

        else:

            discord_name = "Unknown"


        is_dupe = ign.strip().casefold() in dupe_igns

        field_name = (
            f"⚠️ {ign} (duplicate)"
            if is_dupe
            else ign
        )


        embed.add_field(
            name=field_name,
            value=f"Discord: {discord_name}",
            inline=False
        )


    await interaction.response.send_message(
        embed=embed
    )


@app_commands.checks.has_permissions(administrator=True)
@bot.tree.command(
    name="duplicates",
    description="Admin: list IGNs currently claimed by more than one Discord account"
)
async def duplicates(
    interaction: discord.Interaction
):

    groups = await get_duplicate_igns()

    if not groups:

        await interaction.response.send_message(
            "✅ No duplicate IGNs found. Every verified account holds a "
            "unique name."
        )

        return


    embed = discord.Embed(
        title="⚠️ Duplicate IGNs",
        description=(
            "These names are each claimed by more than one active "
            "Discord account. This is almost always leftover from the "
            "old game_id-keyed data, where two different game_ids "
            "could share a display name. Use `/modifyverify` with "
            "`force: True` to correct or remove the wrong one(s)."
        ),
        color=discord.Color.orange()
    )


    for group in groups:

        lines = []

        for discord_id, ign in group:

            lines.append(
                f"<@{discord_id}> — IGN `{ign}`"
            )

        embed.add_field(
            name=group[0][1],
            value="\n".join(lines),
            inline=False
        )


    await interaction.response.send_message(
        embed=embed
    )




@app_commands.checks.has_permissions(administrator=True)
@bot.tree.command(
    name="modifyverify",
    description="Admin: change a user's verified IGN"
)
@app_commands.describe(
    member="The Discord member whose verification to modify",
    new_ign="New IGN",
    force="Bypass the duplicate-name safety check (default: off)"
)
async def modifyverify(
    interaction: discord.Interaction,
    member: discord.Member,
    new_ign: str,
    force: bool = False
):

    current = await get_user_by_discord_id(
        member.id
    )

    if current is None:

        current = (member.id, None, 0, 0)


    old_ign = current[1]


    if not force:

        conflict = await get_active_user_by_ign(
            new_ign
        )

        if conflict and conflict[0] != member.id:

            await interaction.response.send_message(
                f"❌ IGN `{new_ign}` is already "
                f"linked to another Discord account (<@{conflict[0]}>).\n\n"
                f"If this is intentional, re-run the command with "
                f"`force: True`.",
                ephemeral=True
            )

            return


    await add_user(
        member.id,
        new_ign
    )


    await interaction.response.send_message(
        f"✅ Updated verification for {member.mention}\n\n"
        f"IGN: `{old_ign}` → `{new_ign}`"
    )




@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    if isinstance(
        error,
        app_commands.MissingPermissions
    ):

        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )

        return

    raise error


bot.run(TOKEN)
