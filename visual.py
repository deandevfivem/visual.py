import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import re
import json
import os
import datetime
from collections import defaultdict

# =========================
# CONFIG
# =========================

CONFIG = {
    "TOKEN": "MTUxMTMwNjMwMDAxNTkwNjgxNg.GDP4nc.E8nryEZt9r9ziJtVjKk82VPJHx0KlcAiSzTlkQ",
    "FILES": {
        "GIVEAWAYS": "giveaways.json",
        "CASES": "cases.json",
        "CREDITS": "credits.json"
    }
}

APPLICATION_ID = 1511306300015906816

GIVEAWAY_ROLE_ID = 1504475271430930540
WELCOME_ROLE_ID = 1504475271452164201
WELCOME_CHANNEL_ID = 1504475272055881929
FEEDBACK_CHANNEL_ID = 1504475272194556080
FEEDBACK_ALLOWED_ROLE = 1511963033537351730
CASE_LOG_CHANNEL_ID = 1511660598033645740

BAD_WORDS = ["badword1", "badword2", "badword3"]  # edit as needed

# =========================
# INTENTS + BOT
# =========================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

class VisualBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="/",
            intents=intents,
            application_id="1511306300015906816"
        )
        self.giveaways = {}
        self.cases = []
        self.credits = {}

    async def setup_hook(self):
        ensure_files()
        load_all_data(self)
        await self.tree.sync()
        print("Slash commands synced.")

bot = VisualBot()

# =========================
# FILE HELPERS
# =========================

def ensure_files():
    for key, path in CONFIG["FILES"].items():
        if not os.path.exists(path):
            with open(path, "w") as f:
                if key == "GIVEAWAYS":
                    json.dump({}, f)
                elif key == "CASES":
                    json.dump([], f)
                elif key == "CREDITS":
                    json.dump({}, f)

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def load_all_data(bot: VisualBot):
    bot.giveaways = load_json(CONFIG["FILES"]["GIVEAWAYS"])
    bot.cases = load_json(CONFIG["FILES"]["CASES"])
    bot.credits = load_json(CONFIG["FILES"]["CREDITS"])

def save_giveaways(bot: VisualBot):
    save_json(CONFIG["FILES"]["GIVEAWAYS"], bot.giveaways)

def save_cases(bot: VisualBot):
    save_json(CONFIG["FILES"]["CASES"], bot.cases)

def save_credits(bot: VisualBot):
    save_json(CONFIG["FILES"]["CREDITS"], bot.credits)

# =========================
# CASE HELPERS
# =========================

def new_case_id(bot: VisualBot) -> int:
    if not bot.cases:
        return 1
    return max(c["id"] for c in bot.cases) + 1

async def log_case(bot: VisualBot, guild: discord.Guild, case: dict):
    channel = guild.get_channel(CASE_LOG_CHANNEL_ID)
    if channel is None:
        return
    embed = discord.Embed(
        title=f"Case #{case['id']} — {case['action']}",
        color=discord.Color.orange()
    )
    embed.add_field(name="User", value=f"<@{case['user_id']}>", inline=True)
    embed.add_field(name="Moderator", value=f"<@{case['mod_id']}>", inline=True)
    embed.add_field(name="Reason", value=case['reason'], inline=False)
    embed.add_field(name="Time", value=case['timestamp'], inline=False)
    await channel.send(embed=embed)

def add_case(bot: VisualBot, user_id: int, mod_id: int, action: str, reason: str):
    case = {
        "id": new_case_id(bot),
        "user_id": user_id,
        "mod_id": mod_id,
        "action": action,
        "reason": reason,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    bot.cases.append(case)
    save_cases(bot)
    return case

# =========================
# GIVEAWAY VIEWS
# =========================

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.green, custom_id="giveaway_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        g = bot.giveaways.get(msg_id)
        if not g:
            return await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
        if g["ended"]:
            return await interaction.response.send_message("❌ Giveaway already ended.", ephemeral=True)
        if interaction.user.id in g["participants"]:
            return await interaction.response.send_message("⚠️ You already joined.", ephemeral=True)
        g["participants"].append(interaction.user.id)
        save_giveaways(bot)
        await interaction.response.send_message("✅ You joined the giveaway!", ephemeral=True)

    @discord.ui.button(label="View Participants", style=discord.ButtonStyle.blurple, custom_id="giveaway_view")
    async def view_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        g = bot.giveaways.get(msg_id)
        if not g:
            return await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
        participants = g["participants"]
        if not participants:
            return await interaction.response.send_message("No participants yet.", ephemeral=True)
        guild = interaction.guild
        names = []
        for uid in participants[:50]:
            member = guild.get_member(uid)
            names.append(member.mention if member else f"`{uid}`")
        text = ", ".join(names)
        if len(participants) > 50:
            text += f"\n...and {len(participants) - 50} more."
        embed = discord.Embed(
            title="👥 Participants",
            description=text,
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RerollSelect(discord.ui.Select):
    def __init__(self, msg_id, winners):
        self.msg_id = msg_id
        options = [discord.SelectOption(label=str(uid), value=str(uid)) for uid in winners]
        super().__init__(placeholder="Select winner to reroll", options=options)

    async def callback(self, interaction: discord.Interaction):
        msg_id = self.msg_id
        g = bot.giveaways.get(msg_id)
        if not g:
            return await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
        required_role = interaction.guild.get_role(GIVEAWAY_ROLE_ID)
        if required_role not in interaction.user.roles:
            return await interaction.response.send_message("❌ No permission.", ephemeral=True)
        old = int(self.values[0])
        participants = g["participants"]
        winners = g["winners"]
        remaining = [uid for uid in participants if uid not in winners or uid == old]
        remaining = [uid for uid in remaining if uid != old]
        if not remaining:
            return await interaction.response.send_message("❌ No one left to reroll.", ephemeral=True)
        new = random.choice(remaining)
        idx = winners.index(old)
        winners[idx] = new
        g["winners"] = winners
        save_giveaways(bot)
        guild = interaction.guild
        winners_text = ", ".join(
            guild.get_member(uid).mention if guild.get_member(uid) else f"`{uid}`"
            for uid in winners
        )
        await interaction.response.edit_message(
            content=f"🔄 Winner updated!\nNew winners: {winners_text}",
            view=None
        )

class RerollView(discord.ui.View):
    def __init__(self, msg_id):
        super().__init__(timeout=None)
        self.msg_id = msg_id

    @discord.ui.button(label="Reroll Winner", style=discord.ButtonStyle.danger, custom_id="giveaway_reroll")
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = self.msg_id
        g = bot.giveaways.get(msg_id)
        if not g:
            return await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
        required_role = interaction.guild.get_role(GIVEAWAY_ROLE_ID)
        if required_role not in interaction.user.roles:
            return await interaction.response.send_message("❌ No permission.", ephemeral=True)
        if not g["ended"]:
            return await interaction.response.send_message("❌ Giveaway not ended.", ephemeral=True)
        winners = g["winners"]
        view = discord.ui.View(timeout=60)
        view.add_item(RerollSelect(msg_id, winners))
        await interaction.response.send_message("Select a winner to reroll:", view=view, ephemeral=True)

# =========================
# EVENTS
# =========================

@bot.event
async def on_ready():
    # Restore giveaway views
    for msg_id, g in bot.giveaways.items():
        try:
            channel = bot.get_channel(g["channel_id"])
            if not channel:
                continue
            msg = await channel.fetch_message(int(msg_id))
            if not g["ended"]:
                await msg.edit(view=GiveawayView())
            else:
                await channel.send(
                    f"🎉 Giveaway for **{g['prize']}** ended.\nWinners: " +
                    ", ".join(f"<@{uid}>" for uid in g["winners"]),
                    view=RerollView(msg_id)
                )
        except Exception:
            pass
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_member_join(member: discord.Member):
    role = member.guild.get_role(WELCOME_ROLE_ID)
    if role:
        try:
            await member.add_roles(role)
        except Exception:
            pass
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        return
    embed = discord.Embed(
        title="👋 Welcome!",
        description=f"{member.mention}, welcome to the server!",
        color=discord.Color.green()
    )
    embed.add_field(
        name="🎨 Visual Designs",
        value="Have fun and apply to become a design ASAP in a management support ticket Welcome to **Visual Designs!**",
        inline=False
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Member #{len(member.guild.members)}")
    await channel.send(embed=embed)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    content = message.content.lower()
    if any(bad in content for bad in BAD_WORDS):
        try:
            await message.delete()
        except Exception:
            pass
        case = add_case(
            bot,
            user_id=message.author.id,
            mod_id=bot.user.id,
            action="automod-warn",
            reason="Auto-moderation: banned word"
        )
        await log_case(bot, message.guild, case)
        try:
            await message.channel.send(
                f"{message.author.mention}, your message was removed for inappropriate language.",
                delete_after=5
            )
        except Exception:
            pass

# =========================
# GIVEAWAY COMMAND
# =========================

@bot.tree.command(name="giveaway", description="Create a giveaway.")
@app_commands.describe(
    duration="Duration like 1d2h30m",
    winners="Number of winners",
    prize="Prize name"
)
async def giveaway(
    interaction: discord.Interaction,
    duration: str,
    winners: int,
    prize: str
):
    required_role = interaction.guild.get_role(GIVEAWAY_ROLE_ID)
    if required_role not in interaction.user.roles:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    seconds = 0
    matches = re.findall(r"(\d+)([dhm])", duration.lower())
    for amount, unit in matches:
        amount = int(amount)
        if unit == "d":
            seconds += amount * 86400
        elif unit == "h":
            seconds += amount * 3600
        elif unit == "m":
            seconds += amount * 60
    if seconds <= 0:
        return await interaction.response.send_message("❌ Invalid duration.", ephemeral=True)
    end_time = int(discord.utils.utcnow().timestamp()) + seconds
    embed = discord.Embed(
        title="🎉 Giveaway",
        description="Click **Join Giveaway** to enter!",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Prize", value=prize, inline=False)
    embed.add_field(name="Winners", value=str(winners), inline=True)
    embed.add_field(name="Ends", value=f"<t:{end_time}:F>", inline=True)
    embed.set_footer(text="Good luck!")
    view = GiveawayView()
    await interaction.response.send_message("✅ Giveaway created.", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=view)
    bot.giveaways[str(msg.id)] = {
        "participants": [],
        "winners": [],
        "ended": False,
        "winners_count": winners,
        "channel_id": interaction.channel.id,
        "prize": prize
    }
    save_giveaways(bot)
    await asyncio.sleep(seconds)
    g = bot.giveaways.get(str(msg.id))
    if not g or g["ended"]:
        return
    participants = g["participants"]
    if not participants:
        g["ended"] = True
        save_giveaways(bot)
        return await msg.edit(content="Giveaway ended. No participants.", view=None)
    winners_count = min(g["winners_count"], len(participants))
    chosen = random.sample(participants, winners_count)
    g["winners"] = chosen
    g["ended"] = True
    save_giveaways(bot)
    guild = interaction.guild
    winners_text = ", ".join(
        guild.get_member(uid).mention if guild.get_member(uid) else f"`{uid}`"
        for uid in chosen
    )
    end_embed = discord.Embed(
        title="🎉 Giveaway Ended",
        description=f"Prize: **{g['prize']}**",
        color=discord.Color.gold()
    )
    end_embed.add_field(name="Winners", value=winners_text, inline=False)
    await msg.edit(embed=end_embed, view=None)
    await interaction.channel.send(
        f"🎉 Giveaway ended!\nWinners: {winners_text}",
        view=RerollView(str(msg.id))
    )

# =========================
# FEEDBACK
# =========================

@bot.tree.command(name="feedback", description="Submit feedback for a user with a star rating.")
@app_commands.describe(
    rating="1–5 stars",
    user="Who the feedback is for",
    message="Your feedback message"
)
async def feedback(
    interaction: discord.Interaction,
    rating: int,
    user: discord.Member,
    message: str
):
    if rating < 1 or rating > 5:
        return await interaction.response.send_message("❌ Rating must be between **1 and 5**.", ephemeral=True)
    allowed_role = interaction.guild.get_role(FEEDBACK_ALLOWED_ROLE)
    if allowed_role not in user.roles:
        return await interaction.response.send_message(
            f"❌ You can only submit feedback for users with the role {allowed_role.mention}.",
            ephemeral=True
        )
    channel = interaction.guild.get_channel(FEEDBACK_CHANNEL_ID)
    if channel is None:
        return await interaction.response.send_message("❌ Feedback channel not found.", ephemeral=True)
    stars = "⭐" * rating + "☆" * (5 - rating)
    rating_text = f"**{rating}/5 {stars}**"
    embed = discord.Embed(
        title="📝 New Feedback Submitted",
        description=message,
        color=discord.Color.orange()
    )
    embed.add_field(name="Rating", value=rating_text, inline=False)
    embed.add_field(name="Feedback For", value=user.mention, inline=False)
    embed.add_field(name="Submitted By", value=interaction.user.mention, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"Submitted by ID: {interaction.user.id}")
    await channel.send(embed=embed)
    await interaction.response.send_message("✅ Feedback submitted!", ephemeral=True)

# =========================
# CREDITS
# =========================

def get_balance(user_id: int) -> int:
    return int(bot.credits.get(str(user_id), 0))

def set_balance(user_id: int, amount: int):
    bot.credits[str(user_id)] = int(amount)
    save_credits(bot)

@bot.tree.command(name="addcredits", description="Add credits to a user (admin only).")
@app_commands.describe(user="Target user", amount="Amount to add")
async def addcredits(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    if amount <= 0:
        return await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
    bal = get_balance(user.id)
    set_balance(user.id, bal + amount)
    await interaction.response.send_message(
        f"✅ Added {amount} credits to {user.mention}. New balance: {get_balance(user.id)}"
    )

@bot.tree.command(name="removecredits", description="Remove credits from a user (admin only).")
@app_commands.describe(user="Target user", amount="Amount to remove")
async def removecredits(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    if amount <= 0:
        return await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
    bal = get_balance(user.id)
    new_bal = max(0, bal - amount)
    set_balance(user.id, new_bal)
    await interaction.response.send_message(
        f"✅ Removed {amount} credits from {user.mention}. New balance: {get_balance(user.id)}"
    )

@bot.tree.command(name="creditsbalance", description="Check your or another user's credit balance.")
@app_commands.describe(user="User to check (optional)")
async def creditsbalance(interaction: discord.Interaction, user: discord.Member | None = None):
    target = user or interaction.user
    bal = get_balance(target.id)
    await interaction.response.send_message(
        f"💰 {target.mention} has **{bal}** credits."
    )

# =========================
# MODERATION
# =========================

@bot.tree.command(name="warn", description="Warn a user.")
@app_commands.describe(user="User to warn", reason="Reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    case = add_case(bot, user.id, interaction.user.id, "warn", reason)
    await log_case(bot, interaction.guild, case)
    await interaction.response.send_message(
        f"⚠️ {user.mention} has been warned. Case #{case['id']}."
    )

@bot.tree.command(name="removewarning", description="Remove the latest warning for a user.")
@app_commands.describe(user="User to remove warning from")
async def removewarning(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    warnings = [c for c in bot.cases if c["user_id"] == user.id and c["action"] == "warn"]
    if not warnings:
        return await interaction.response.send_message("❌ No warnings found for that user.", ephemeral=True)
    last = max(warnings, key=lambda c: c["id"])
    bot.cases = [c for c in bot.cases if c["id"] != last["id"]]
    save_cases(bot)
    case = add_case(bot, user.id, interaction.user.id, "warn-removed", f"Removed case #{last['id']}")
    await log_case(bot, interaction.guild, case)
    await interaction.response.send_message(
        f"✅ Removed warning case #{last['id']} for {user.mention}."
    )

@bot.tree.command(name="history", description="View a user's moderation history.")
@app_commands.describe(user="User to view history for")
async def history(interaction: discord.Interaction, user: discord.Member):
    user_cases = [c for c in bot.cases if c["user_id"] == user.id]
    if not user_cases:
        return await interaction.response.send_message("No cases found for that user.")
    user_cases = sorted(user_cases, key=lambda c: c["id"], reverse=True)[:10]
    lines = []
    for c in user_cases:
        lines.append(
            f"**#{c['id']}** — {c['action']} by <@{c['mod_id']}> — {c['reason']} ({c['timestamp']})"
        )
    embed = discord.Embed(
        title=f"History for {user}",
        description="\n".join(lines),
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clearcases", description="Clear all cases for a user.")
@app_commands.describe(user="User to clear cases for")
async def clearcases(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    before = len(bot.cases)
    bot.cases = [c for c in bot.cases if c["user_id"] != user.id]
    after = len(bot.cases)
    save_cases(bot)
    removed = before - after
    case = add_case(bot, user.id, interaction.user.id, "cases-cleared", f"Cleared {removed} cases")
    await log_case(bot, interaction.guild, case)
    await interaction.response.send_message(
        f"✅ Cleared {removed} cases for {user.mention}."
    )

@bot.tree.command(name="timeout", description="Timeout a user.")
@app_commands.describe(user="User to timeout", minutes="Minutes to timeout", reason="Reason")
async def timeout(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    if minutes <= 0:
        return await interaction.response.send_message("❌ Minutes must be positive.", ephemeral=True)
    duration = datetime.timedelta(minutes=minutes)
    try:
        await user.timeout(duration, reason=reason)
    except Exception:
        return await interaction.response.send_message("❌ Failed to timeout user.", ephemeral=True)
    case = add_case(bot, user.id, interaction.user.id, "timeout", f"{minutes}m — {reason}")
    await log_case(bot, interaction.guild, case)
    await interaction.response.send_message(
        f"⏱️ {user.mention} has been timed out for {minutes} minutes. Case #{case['id']}."
    )

@bot.tree.command(name="untimeout", description="Remove timeout from a user.")
@app_commands.describe(user="User to untimeout", reason="Reason")
async def untimeout(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    try:
        await user.timeout(None, reason=reason)
    except Exception:
        return await interaction.response.send_message("❌ Failed to remove timeout.", ephemeral=True)
    case = add_case(bot, user.id, interaction.user.id, "untimeout", reason)
    await log_case(bot, interaction.guild, case)
    await interaction.response.send_message(
        f"✅ Timeout removed for {user.mention}. Case #{case['id']}."
    )

@bot.tree.command(name="kick", description="Kick a user.")
@app_commands.describe(user="User to kick", reason="Reason")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    try:
        await user.kick(reason=reason)
    except Exception:
        return await interaction.response.send_message("❌ Failed to kick user.", ephemeral=True)
    case = add_case(bot, user.id, interaction.user.id, "kick", reason)
    await log_case(bot, interaction.guild, case)
    await interaction.response.send_message(
        f"👢 {user.mention} has been kicked. Case #{case['id']}."
    )

@bot.tree.command(name="ban", description="Ban a user.")
@app_commands.describe(user="User to ban", reason="Reason")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    try:
        await user.ban(reason=reason)
    except Exception:
        return await interaction.response.send_message("❌ Failed to ban user.", ephemeral=True)
    case = add_case(bot, user.id, interaction.user.id, "ban", reason)
    await log_case(bot, interaction.guild, case)
    await interaction.response.send_message(
        f"🔨 {user.mention} has been banned. Case #{case['id']}."
    )

@bot.tree.command(name="unban", description="Unban a user by ID.")
@app_commands.describe(user_id="ID of the user to unban", reason="Reason")
async def unban(interaction: discord.Interaction, user_id: int, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    user = discord.Object(id=user_id)
    try:
        await interaction.guild.unban(user, reason=reason)
    except Exception:
        return await interaction.response.send_message("❌ Failed to unban user.", ephemeral=True)
    case = add_case(bot, user_id, interaction.user.id, "unban", reason)
    await log_case(bot, interaction.guild, case)
    await interaction.response.send_message(
        f"✅ Unbanned user with ID `{user_id}`. Case #{case['id']}."
    )

# =========================
# UTILITIES
# =========================

@bot.tree.command(name="designreview", description="Send a design review info message.")
async def designreview(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎨 Visual Designs — Review Request",
        description="Submit your designs here for feedback!",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="💡 Tips",
        value="- Be respectful\n- Be specific\n- Suggest improvements\n- Highlight strengths",
        inline=False
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="role", description="Add or remove a role from a member.")
@app_commands.describe(member="Target member", role="Role to add or remove")
async def role_cmd(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles:
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("❌ I cannot manage that role.", ephemeral=True)
    if role in member.roles:
        await member.remove_roles(role)
        action = f"Removed {role.mention} from {member.mention}"
        color = discord.Color.red()
    else:
        await member.add_roles(role)
        action = f"Added {role.mention} to {member.mention}"
        color = discord.Color.green()
    embed = discord.Embed(title="🔧 Role Updated", description=action, color=color)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Show user info.")
@app_commands.describe(member="User to inspect (optional)")
async def userinfo(interaction: discord.Interaction, member: discord.Member | None = None):
    member = member or interaction.user
    embed = discord.Embed(title=str(member), color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="User ID", value=str(member.id), inline=False)
    embed.add_field(name="Joined", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Created", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Show server info.")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=guild.name, color=discord.Color.blue())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    owner_text = guild.owner.mention if guild.owner else "Unknown"
    embed.add_field(name="Owner", value=owner_text, inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    roles_str = ", ".join(role.mention for role in guild.roles[::-1])
    if len(roles_str) > 1024:
        roles_str = roles_str[:1021] + "..."
    embed.add_field(name="Role List", value=roles_str or "None", inline=False)
    await interaction.response.send_message(embed=embed)

# =========================
# RUN
# =========================

bot.run("MTUxMTMwNjMwMDAxNTkwNjgxNg.GDP4nc.E8nryEZt9r9ziJtVjKk82VPJHx0KlcAiSzTlkQ")
