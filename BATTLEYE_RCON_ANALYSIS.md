# BattlEye RCon Protocol Accuracy Assessment
## For Arma Reforger with Docker Setup

---

## Executive Summary

The information provided is **mostly accurate** but contains **critical inaccuracies** specific to Arma Reforger and your Docker environment. Below is a detailed breakdown.

---

## ✅ What Is CORRECT

### 1. Protocol & Concept
- ✅ BattlEye RCon protocol is the correct approach for automated banning
- ✅ Libraries `rcon` and `berconpy` are legitimate Python options
- ✅ Command syntax (`ban`, `addBan`, `writeBans`, `players`) is accurate
- ✅ The general workflow (connect → execute → parse response) is sound
- ✅ GUID vs Player # distinction is valid

### 2. Command Reference
| Command | Purpose | Accuracy |
|---------|---------|----------|
| `players` | List connected players | ✅ Correct |
| `ban [player #] [time] [reason]` | Ban online player | ✅ Correct |
| `addBan [GUID] [time] [reason]` | Ban by GUID | ✅ Correct |
| `writeBans` | Save ban list | ✅ Correct |

### 3. Library Recommendations
Both libraries work, but for your use case:

**Recommendation: `berconpy`**
- Async/await (matches your Discord.py architecture)
- Auto-reconnection (critical for 24/7 bots)
- Built-in keep-alive packets
- Better for long-running applications

---

## ❌ What Is INCORRECT for Arma Reforger

### 1. Configuration File Location ⚠️ CRITICAL
**WRONG:**
```
beserver.cfg or beserver_x64.cfg (Arma 3 paths)
```

**CORRECT for Arma Reforger:**
```
/srv/armareforger/[container_id]/profile/BattlEye/BEServer.cfg
```

For your servers:
```bash
# TTT1
/srv/armareforger/ub1d584ced/profile/BattlEye/BEServer.cfg

# TTT2
/srv/armareforger/uf74498006/profile/BattlEye/BEServer.cfg

# TTT3
/srv/armareforger/u98fbb3f3c/profile/BattlEye/BEServer.cfg
```

### 2. Configuration Format
The file should contain:
```ini
RConPassword YourStrongPassword123
RConPort 2306
RestrictRCon 0
```

**Note:** `RestrictRCon 0` allows full command access (required for automated banning)

### 3. Docker Networking Issues ⚠️ CRITICAL

**The example uses:**
```python
IP = '127.0.0.1'
PORT = 2306
```

**This will NOT work with your Docker containers unless:**

#### Option A: Host Network Mode (If configured)
```python
IP = '127.0.0.1'  # Works if containers use --net=host
PORT = 2306       # Different port per server!
```

**Problem:** You'd need different RCon ports per server:
- TTT1: `RConPort 2306`
- TTT2: `RConPort 2307`
- TTT3: `RConPort 2308`

#### Option B: Port Mapping (Recommended)
Your containers need `-p` flags:
```bash
docker run -p 2306:2306 ...  # TTT1
docker run -p 2307:2306 ...  # TTT2
docker run -p 2308:2306 ...  # TTT3
```

Then connect from host:
```python
RCON_CONFIG = {
    'ttt1': {'host': '127.0.0.1', 'port': 2306},
    'ttt2': {'host': '127.0.0.1', 'port': 2307},
    'ttt3': {'host': '127.0.0.1', 'port': 2308},
}
```

#### Option C: Internal Docker Network
```python
IP = 'ub1d584ced'  # Use container ID directly
PORT = 2306         # Internal port (no mapping needed)
```

**Your Current Setup:** Check with `docker inspect ub1d584ced` to see if RCon ports are mapped.

### 4. GUID vs BEGUID Confusion ⚠️

**The example is incomplete.** Your database already tracks **TWO** identifiers:

| Identifier | Source | Purpose |
|------------|--------|---------|
| `guid` | Game identity | Session tracking |
| `beguid` | BattlEye GUID | **Used for bans** |

**CRITICAL:** BattlEye RCon uses `BEGUID`, not `GUID`!

**Your database already extracts this:**
```python
# From player_log_monitor.py:62-63
beguid_match = self.beguid_pattern.search(log_line)
beguid = beguid_match.group(1) if beguid_match else None
```

**Correct ban implementation:**
```python
def ban_player_by_beguid(beguid: str, duration: int, reason: str):
    """Ban using BattlEye GUID (BEGUID), not game GUID"""
    with Client(IP, PORT, passwd=PASSWORD) as client:
        response = client.run('addBan', beguid, str(duration), reason)
        return response
```

---

## 🔍 Current State Analysis

### What You Already Have
From analyzing your codebase:

✅ **Player Tracking System**
- SQLite database with GUIDs and BEGUIDs
- IP geolocation with VPN/proxy detection
- Name change detection
- Alt account finding
- Discord alerts for suspicious activity

✅ **Infrastructure**
- 3 Arma Reforger servers (TTT1/TTT2/TTT3)
- Docker containers with log access
- Discord bot with slash commands
- ipgeolocation.io API integration

❌ **Missing Components**
- No BattlEye RCon implementation
- BEServer.cfg files may not be configured
- RCon ports not exposed in Docker containers
- No automated ban execution

---

## 📋 Prerequisites Checklist

Before implementing RCon, verify:

### 1. Check if BEServer.cfg Exists
```bash
# Check each server
ls -la /srv/armareforger/ub1d584ced/profile/BattlEye/
ls -la /srv/armareforger/uf74498006/profile/BattlEye/
ls -la /srv/armareforger/u98fbb3f3c/profile/BattlEye/
```

**Expected output:**
```
BEServer.cfg
BEServer_x64.cfg (symlink)
bans.txt
```

### 2. Check Current RCon Configuration
```bash
# For each server
cat /srv/armareforger/ub1d584ced/profile/BattlEye/BEServer.cfg
```

**Look for:**
```
RConPassword somepassword
RConPort 2306
```

**If missing, you need to add these lines.**

### 3. Check Docker Port Mappings
```bash
docker inspect ub1d584ced | grep -A 10 "PortBindings"
docker inspect uf74498006 | grep -A 10 "PortBindings"
docker inspect u98fbb3f3c | grep -A 10 "PortBindings"
```

**Look for:** `"2306/tcp"` or similar RCon port mappings.

**If empty:** Your containers don't expose RCon ports and need to be recreated with `-p` flags.

### 4. Test RCon Connectivity (After Configuration)
```python
# Quick test script
from rcon.battleye import Client

try:
    with Client('127.0.0.1', 2306, passwd='YourPassword') as client:
        response = client.run('players')
        print(f"✅ RCon connected: {response}")
except Exception as e:
    print(f"❌ RCon failed: {e}")
```

---

## 🎯 Recommended Implementation Path

### Phase 1: Configuration
1. **Configure BEServer.cfg** for each server
2. **Restart containers** to apply RCon settings
3. **Verify RCon ports** are accessible
4. **Test manual connection** with test script

### Phase 2: Integration
1. **Install library:** `pip install berconpy --break-system-packages`
2. **Create RCon wrapper** for your 3 servers
3. **Add ban command** to Discord bot
4. **Integrate with VPN detection** system

### Phase 3: Automation
1. **Auto-ban VPN users** when detected
2. **Create ban queue** for offline players
3. **Sync bans** across TTT1/TTT2/TTT3
4. **Log all bans** to database

---

## 💡 Integration Example for Your Bot

Based on your existing code structure:

```python
import berconpy

# RCon configuration (add to bot.py)
RCON_CONFIG = {
    'ttt1': {
        'host': '127.0.0.1',  # Adjust based on Docker networking
        'port': 2306,         # Map different ports per server
        'password': 'YourRConPassword1'
    },
    'ttt2': {
        'host': '127.0.0.1',
        'port': 2307,
        'password': 'YourRConPassword2'
    },
    'ttt3': {
        'host': '127.0.0.1',
        'port': 2308,
        'password': 'YourRConPassword3'
    }
}

async def ban_player_via_rcon(server: str, beguid: str, duration: int, reason: str):
    """Ban player using BattlEye RCon (async for Discord.py)"""
    config = RCON_CONFIG.get(server)
    if not config:
        return f"❌ Unknown server: {server}"

    try:
        rcon = berconpy.RConClient(config['host'], config['port'], config['password'])
        await rcon.connect()

        # Use BEGUID from database (not GUID!)
        response = await rcon.command(f'addBan {beguid} {duration} {reason}')

        await rcon.disconnect()
        return f"✅ Ban executed: {response}"

    except Exception as e:
        return f"❌ RCon error: {e}"

# New Discord command example
@bot.tree.command(name="rcon-ban", description="Ban player via RCon")
@app_commands.describe(
    server="Server (ttt1, ttt2, ttt3)",
    player_identifier="Player name or GUID",
    duration="Ban duration in minutes (0 = permanent)",
    reason="Reason for ban"
)
async def rcon_ban(interaction: discord.Interaction, server: str,
                   player_identifier: str, duration: int, reason: str):
    """Ban player using RCon and update database"""

    if not player_db:
        await interaction.response.send_message("❌ Database not available", ephemeral=True)
        return

    # Lookup player in database
    player = player_db.get_player_by_guid(player_identifier)
    if not player:
        await interaction.response.send_message(f"❌ Player not found: {player_identifier}", ephemeral=True)
        return

    # Get BEGUID (required for RCon)
    beguid = player.get('beguid')
    if not beguid:
        await interaction.response.send_message(f"❌ No BEGUID found for player", ephemeral=True)
        return

    await interaction.response.defer()

    # Execute RCon ban
    result = await ban_player_via_rcon(server, beguid, duration, reason)

    # Update database
    if "✅" in result:
        player_db.ban_player(player['guid'], reason)

    await interaction.followup.send(result)
```

---

## 🚨 Critical Corrections Summary

| Original Claim | Reality for Your Setup |
|----------------|------------------------|
| Config: `beserver.cfg` | `/srv/armareforger/[container]/profile/BattlEye/BEServer.cfg` |
| Connect to `127.0.0.1:2306` | May not work with Docker; need port mapping or internal network |
| Ban with `GUID` | Must use `BEGUID` (BattlEye GUID), not game GUID |
| Single RCon port | Need 3 different ports (one per server) |
| Library: either works | `berconpy` better for your async Discord bot |

---

## 🔧 Next Steps

To implement RCon for automated banning:

1. **Verify Docker Setup**
   - Check if RCon ports are mapped
   - Determine networking approach (host/bridge/custom)

2. **Configure BattlEye**
   - Add RCon settings to BEServer.cfg files
   - Use unique ports per server
   - Set strong passwords

3. **Test Connectivity**
   - Use simple test script to verify RCon works
   - Test on each server (TTT1/TTT2/TTT3)

4. **Integrate with Bot**
   - Install `berconpy`
   - Add RCon wrapper functions
   - Create Discord commands
   - Link with VPN detection system

5. **Implement Automation**
   - Auto-ban VPN users
   - Sync bans across servers
   - Log all actions to database

---

## 📚 Additional Resources

- **BattlEye RCon Protocol Spec:** https://www.battleye.com/support/documentation/
- **berconpy Documentation:** https://github.com/ttoine/berconpy
- **rcon Library:** https://github.com/conqp/rcon
- **Arma Reforger Server Docs:** https://community.bistudio.com/wiki/Arma_Reforger:Server_Hosting

---

## ❓ Questions to Answer Before Implementation

1. Are your Docker containers using `--net=host` or bridge networking?
2. Do you have access to recreate containers with new port mappings?
3. What RCon ports do you want to use (2306/2307/2308)?
4. Should bans sync across all 3 servers or be independent?
5. Do you want auto-ban for VPN users or manual approval?

---

*Analysis Date: 2025-12-24*
*Based on: Skeeters_Clanker codebase*
*Servers: TTT1 (ub1d584ced), TTT2 (uf74498006), TTT3 (u98fbb3f3c)*
