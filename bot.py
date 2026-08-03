from discord.ext import tasks
from clan_checker import check_members, get_clan_members

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

import os

from database import (
    setup_database,
    add_user,
    mark_removed,
    get_verified_users
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

        print("SETUP HOOK STARTED", flush=True)

        await setup_database()

        print("DATABASE READY", flush=True)




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
            f"{player['ign']} "
            f"({player['game_id']})"
        )


        if not ENABLE_KICK:


            print(
                "Kick disabled. Dry-run mode."
            )


            if log_channel:

                await log_channel.send(
                    f"🧪 **Dry Run Detection**\n\n"
                    f"Player: `{player['ign']}`\n"
                    f"Ninja Saga ID: `{player['game_id']}`\n"
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
                    f"Ninja Saga ID: `{player['game_id']}`\n"
                    f"Discord: {member.mention}\n\n"
                    f"Reason: No longer in Hidden Cloud Village"
                )


        except Exception as e:

            print(
                f"Kick failed: {e}"
            )





@bot.event
async def on_ready():

    guild = discord.Object(
        id=GUILD_ID
    )

    print(
        f"Commands loaded: {len(bot.tree.get_commands())}",
        flush=True
    )

    for command in bot.tree.get_commands():
        print(
            f"Command: {command.name}",
            flush=True
        )

    print("SYNCING COMMANDS...", flush=True)

    synced = await bot.tree.sync(
    guild=guild
    )

    print(
        f"Synced {len(synced)} guild commands",
        flush=True
    )

    print(
        f"Logged in as {bot.user}",
        flush=True
    )

    print(
        "Clan Guard online",
        flush=True
    )


    print(
    f"Kick mode: {ENABLE_KICK}",
    flush=True
    )


    if not clan_check.is_running():

        clan_check.start()






@bot.tree.command(
    name="verify",
    description="Link your Discord account with your Ninja Saga ID"
)
@app_commands.describe(
    game_id="Your Ninja Saga User ID",
    ign="Your Ninja Saga character name"
)
async def verify(
    interaction: discord.Interaction,
    game_id: int,
    ign: str
):

    await add_user(
        interaction.user.id,
        game_id,
        ign
    )


    await interaction.response.send_message(
        f"✅ Verified!\n\n"
        f"IGN: `{ign}`\n"
        f"Ninja Saga ID: `{game_id}`"
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



    embed = discord.Embed(
        title="☁️ Verified Clan Members",
        color=discord.Color.blue()
    )


    for discord_id, game_id, ign in users:


        member = interaction.guild.get_member(
            discord_id
        )


        if member:

            discord_name = member.display_name

        else:

            discord_name = "Unknown"



        embed.add_field(
            name=f"{game_id} - {ign}",
            value=f"Discord: {discord_name}",
            inline=False
        )


    await interaction.response.send_message(
        embed=embed
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