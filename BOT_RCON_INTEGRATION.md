# Discord Bot RCon Integration Guide
## Add Automated Banning to Your Bot

---

## 🎯 What We're Adding

New Discord commands:
- `/rcon-ban` - Ban a player via RCon (works offline or online)
- `/rcon-players` - List currently connected players
- `/rcon-kick` - Kick a player from server
- Auto-ban integration with VPN detection

---

## 📝 Step 1: Add RCon Configuration to bot.py

**Add this near the top of bot.py (after imports, around line 85):**

```python
# =============================================================================
# RCON CONFIGURATION
# =============================================================================

import berconpy

# RCon server configuration (from UI)
RCON_CONFIG = {
    'ttt1': {
        'host': '64.44.205.83',
        'port': 4002,
        'password': 'Cementdispatch399'
    },
    'ttt2': {
        'host': '64.44.205.86',
        'port': 4003,
        'password': 'Cementdispatch399'
    },
    'ttt3': {
        'host': '64.44.205.86',
        'port': 4001,
        'password': 'Cementdispatch399'
    }
}

# RCon helper functions
async def execute_rcon_command(server: str, command: str, timeout: int = 10) -> str:
    """Execute RCon command on server (async)"""
    config = RCON_CONFIG.get(server.lower())
    if not config:
        return f"❌ Unknown server: {server}. Use ttt1, ttt2, or ttt3"

    try:
        rcon = berconpy.RConClient(
            config['host'],
            config['port'],
            config['password'],
            timeout=timeout
        )
        await rcon.connect()

        # Execute command and handle encoding
        response = await rcon.command(command)

        await rcon.disconnect()

        # Handle response encoding
        if isinstance(response, bytes):
            response = response.decode('utf-8', errors='replace')

        return response if response else "Command executed (no response)"

    except asyncio.TimeoutError:
        return f"⚠️ Timeout - {server.upper()} server is slow or busy. Command may have executed."
    except ConnectionRefusedError:
        return f"❌ Cannot connect to {server.upper()} - server may be offline"
    except Exception as e:
        return f"❌ RCon error: {type(e).__name__}: {str(e)[:100]}"

async def ban_player_rcon(server: str, beguid: str, duration: int, reason: str) -> tuple[bool, str]:
    """
    Ban player via RCon using BEGUID
    Returns: (success: bool, message: str)
    """
    # Use addBan command (works whether player is online or not)
    command = f'addBan {beguid} {duration} {reason}'
    response = await execute_rcon_command(server, command, timeout=10)

    # Check if successful
    success = '❌' not in response and 'error' not in response.lower()

    return success, response
```

---

## 📝 Step 2: Add Discord Commands

**Add these command functions to bot.py (before `bot.run()`, around line 2000+):**

```python
# =============================================================================
# RCON COMMANDS
# =============================================================================

@bot.tree.command(name="rcon-ban", description="Ban player via BattlEye RCon")
@app_commands.describe(
    server="Server (ttt1, ttt2, ttt3)",
    player_identifier="Player name or GUID from database",
    duration="Ban duration in minutes (0 = permanent)",
    reason="Reason for ban"
)
async def rcon_ban_command(
    interaction: discord.Interaction,
    server: str,
    player_identifier: str,
    duration: int,
    reason: str
):
    """Ban player using BattlEye RCon"""

    await interaction.response.defer()

    if not player_db:
        await interaction.followup.send("❌ Player database not available", ephemeral=True)
        return

    # Lookup player in database
    player = player_db.get_player_by_guid(player_identifier)

    if not player:
        # Try searching by name
        players = player_db.find_players_by_name(player_identifier)
        if players and len(players) > 0:
            player = players[0]
        else:
            await interaction.followup.send(
                f"❌ Player not found: `{player_identifier}`\n"
                f"Use `/player-db-history` to search database first.",
                ephemeral=True
            )
            return

    # Get BEGUID (required for RCon ban)
    beguid = player.get('beguid')
    if not beguid:
        await interaction.followup.send(
            f"❌ No BattlEye GUID found for **{player['current_name']}**\n"
            f"Player needs to connect at least once to get BEGUID.",
            ephemeral=True
        )
        return

    # Execute RCon ban
    success, response = await ban_player_rcon(server, beguid, duration, reason)

    # Update database if successful
    if success:
        player_db.ban_player(player['guid'], reason)

    # Build embed response
    embed = discord.Embed(
        title="🔨 RCon Ban" + (" Executed" if success else " Failed"),
        description=response[:500],  # Truncate long responses
        color=discord.Color.green() if success else discord.Color.red()
    )

    embed.add_field(name="Server", value=server.upper(), inline=True)
    embed.add_field(name="Player", value=player['current_name'], inline=True)
    embed.add_field(
        name="Duration",
        value=f"{duration} min" if duration > 0 else "Permanent",
        inline=True
    )
    embed.add_field(name="BEGUID", value=f"`{beguid[:16]}...`", inline=True)
    embed.add_field(name="Reason", value=reason[:100], inline=False)

    if success:
        embed.add_field(
            name="Database",
            value="✅ Player marked as banned in database",
            inline=False
        )

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="rcon-players", description="List players connected to server via RCon")
@app_commands.describe(
    server="Server (ttt1, ttt2, ttt3)"
)
async def rcon_players_command(interaction: discord.Interaction, server: str):
    """Get list of connected players via RCon"""

    await interaction.response.defer()

    response = await execute_rcon_command(server, 'players', timeout=10)

    embed = discord.Embed(
        title=f"👥 Players on {server.upper()}",
        description=f"```\n{response[:1900]}\n```",  # Discord embed limit
        color=discord.Color.blue()
    )

    # Parse player count if possible
    try:
        lines = [l for l in response.split('\n') if l.strip()]
        player_count = len([l for l in lines if 'Player' in l or l[0].isdigit()])
        embed.set_footer(text=f"Players online: {player_count}")
    except:
        pass

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="rcon-kick", description="Kick player from server via RCon")
@app_commands.describe(
    server="Server (ttt1, ttt2, ttt3)",
    player_number="Player number from /rcon-players",
    reason="Reason for kick"
)
async def rcon_kick_command(
    interaction: discord.Interaction,
    server: str,
    player_number: int,
    reason: str
):
    """Kick player via RCon"""

    await interaction.response.defer()

    command = f'kick {player_number} {reason}'
    response = await execute_rcon_command(server, command)

    embed = discord.Embed(
        title=f"👢 Kick Player #{player_number}",
        description=response[:500],
        color=discord.Color.orange()
    )
    embed.add_field(name="Server", value=server.upper(), inline=True)
    embed.add_field(name="Reason", value=reason, inline=True)

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="rcon-command", description="Execute raw RCon command (admin only)")
@app_commands.describe(
    server="Server (ttt1, ttt2, ttt3)",
    command="RCon command to execute"
)
async def rcon_raw_command(
    interaction: discord.Interaction,
    server: str,
    command: str
):
    """Execute raw RCon command (dangerous!)"""

    # Check if user has admin role (optional security)
    # if not interaction.user.guild_permissions.administrator:
    #     await interaction.response.send_message("❌ Admin only", ephemeral=True)
    #     return

    await interaction.response.defer()

    response = await execute_rcon_command(server, command)

    embed = discord.Embed(
        title=f"⚙️ RCon Command: {server.upper()}",
        description=f"**Command:** `{command}`\n\n**Response:**\n```\n{response[:1800]}\n```",
        color=discord.Color.purple()
    )

    await interaction.followup.send(embed=embed)
```

---

## 📝 Step 3: Update Help Command

**Find the `/help` command in bot.py and add RCon section:**

```python
# Add this field to the help embed
embed.add_field(
    name="🔨 RCon Commands",
    value="`/rcon-ban` - Ban player via RCon\n"
          "`/rcon-players` - List online players\n"
          "`/rcon-kick` - Kick player\n"
          "`/rcon-command` - Execute raw command",
    inline=False
)
```

---

## 📝 Step 4: Auto-Ban VPN Users (Optional)

**Add this function to automatically ban detected VPN users:**

```python
async def auto_ban_vpn_user(server: str, player_data: dict):
    """
    Automatically ban VPN user via RCon
    Called from VPN detection system
    """
    if not player_data.get('beguid'):
        print(f"⚠️ Cannot auto-ban {player_data.get('name')} - no BEGUID")
        return

    # Ban for 1440 minutes (24 hours) - adjust as needed
    duration = 1440
    reason = "VPN/Proxy detected - contact admin to appeal"

    success, response = await ban_player_rcon(
        server,
        player_data['beguid'],
        duration,
        reason
    )

    if success:
        print(f"✅ Auto-banned VPN user: {player_data.get('name')} on {server}")

        # Send alert to VPN alert channel
        if VPN_ALERT_CHANNEL:
            embed = discord.Embed(
                title="🚨 Auto-Ban: VPN Detected",
                description=f"Player automatically banned via RCon",
                color=discord.Color.red()
            )
            embed.add_field(name="Player", value=player_data.get('name'), inline=True)
            embed.add_field(name="Server", value=server.upper(), inline=True)
            embed.add_field(name="IP", value=player_data.get('ip'), inline=True)
            embed.add_field(name="Country", value=player_data.get('country', 'Unknown'), inline=True)
            embed.add_field(name="ISP", value=player_data.get('isp', 'Unknown'), inline=False)
            embed.add_field(name="Duration", value=f"{duration} minutes (24 hours)", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)

            await VPN_ALERT_CHANNEL.send(embed=embed)
    else:
        print(f"❌ Auto-ban failed: {response}")
```

**Then call it from your VPN detection code:**

```python
# In your player monitoring code, when VPN is detected:
if is_vpn or is_proxy:
    # Existing alert code...

    # Auto-ban via RCon
    await auto_ban_vpn_user('ttt1', {  # or ttt2, ttt3 based on which server
        'name': player_name,
        'beguid': beguid,
        'ip': ip_address,
        'country': country,
        'isp': isp
    })
```

---

## 📝 Step 5: Restart Bot

```bash
cd /srv/armareforger/Skeeters_Clanker

# Stop current bot
pkill -f "python3 bot.py"

# Start with new RCon functionality
nohup python3 bot.py > bot_output.log 2>&1 &

# Check logs
tail -f bot_output.log
```

**Look for:**
```
✅ Player database initialized
Bot ready!
Logged in as...
```

---

## 🎮 Usage Examples

### Ban a VPN User
```
/rcon-ban ttt1 PlayerName 1440 VPN detected
```

### Ban Permanently by GUID
```
/rcon-ban ttt2 abc123def456 0 Cheating - permanent ban
```

### Check Who's Online
```
/rcon-players ttt1
```

### Kick Toxic Player
```
/rcon-players ttt1
# See player #5 is toxic
/rcon-kick ttt1 5 Offensive language
```

### Execute Custom Command
```
/rcon-command ttt1 bans
```

---

## 🔐 Security Considerations

### 1. Restrict RCon Commands (Optional)

Add permission checks:

```python
@bot.tree.command(name="rcon-ban", description="...")
async def rcon_ban_command(interaction: discord.Interaction, ...):
    # Check for admin role
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You need Administrator permission to use RCon commands",
            ephemeral=True
        )
        return

    # Rest of command...
```

### 2. Log All RCon Actions

```python
def log_rcon_action(user: str, server: str, command: str, result: str):
    """Log RCon commands to file"""
    with open('/srv/armareforger/Skeeters_Clanker/rcon_log.txt', 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] {user} executed on {server}: {command} -> {result}\n")

# Call in command:
log_rcon_action(
    interaction.user.name,
    server,
    f"ban {beguid} {duration} {reason}",
    "success" if success else "failed"
)
```

### 3. Rate Limiting

Prevent spam:

```python
from collections import defaultdict
import time

rcon_cooldowns = defaultdict(float)

async def check_rcon_cooldown(user_id: int, cooldown_seconds: int = 5) -> bool:
    """Check if user is on cooldown for RCon commands"""
    now = time.time()
    if now - rcon_cooldowns[user_id] < cooldown_seconds:
        return False
    rcon_cooldowns[user_id] = now
    return True

# In command:
if not await check_rcon_cooldown(interaction.user.id):
    await interaction.response.send_message(
        "⏰ Slow down! Wait 5 seconds between RCon commands.",
        ephemeral=True
    )
    return
```

---

## 🐛 Troubleshooting

### Command Timeouts
```python
# Increase timeout for slow servers
await execute_rcon_command(server, command, timeout=30)
```

### Encoding Errors
```python
# Already handled in execute_rcon_command with:
response.decode('utf-8', errors='replace')
```

### Connection Refused
- Check server is online: `docker ps | grep ttt`
- Verify RCon enabled in UI
- Check port: `netstat -tuln | grep 400[1-3]`

### Wrong BEGUID
- Player must connect at least once to get BEGUID
- Check database: `/player-db-history ttt1 PlayerName`
- BEGUID is different from GUID!

---

## ✅ Testing Checklist

- [ ] Bot starts without errors
- [ ] `/help` shows new RCon commands
- [ ] `/rcon-players ttt1` works
- [ ] `/rcon-ban` finds player in database
- [ ] Ban executes successfully
- [ ] Player database updated after ban
- [ ] Alert sent to channel
- [ ] VPN auto-ban triggers (if enabled)
- [ ] All 3 servers work (ttt1, ttt2, ttt3)

---

## 📊 Integration Summary

**Files Modified:**
- `bot.py` - Added RCon configuration and commands

**New Dependencies:**
- `berconpy` - Already installed ✅

**New Commands:**
- `/rcon-ban` - Ban player (online or offline)
- `/rcon-players` - List connected players
- `/rcon-kick` - Kick player
- `/rcon-command` - Raw RCon command

**Integration Points:**
- Player database (uses BEGUID for bans)
- VPN detection (auto-ban capability)
- Discord alerts (ban notifications)

---

## 🎉 You're Done!

Your Discord bot now has full BattlEye RCon integration!

**What you can do:**
✅ Ban players remotely from Discord
✅ Ban works even if player is offline
✅ List who's currently online
✅ Kick toxic players instantly
✅ Auto-ban VPN users
✅ Execute any BattlEye command

**Next steps:**
1. Copy the code sections into bot.py
2. Restart bot
3. Test `/rcon-players ttt1`
4. Try banning a test player
5. Celebrate! 🎊
