# BattlEye RCon Setup Guide
## For Arma Reforger Docker Servers

---

## ✅ CORRECTED Path Information

**FOUND:** BattlEye directory is at `/srv/armareforger/[container_id]/battleye/` (lowercase)

**NOT** at: `/srv/armareforger/[container_id]/profile/BattlEye/` ❌

### Your Server Paths:
- TTT1: `/srv/armareforger/ub1d584ced/battleye/`
- TTT2: `/srv/armareforger/uf74498006/battleye/`
- TTT3: `/srv/armareforger/u98fbb3f3c/battleye/`

---

## 🔍 Step 1: Check Current Configuration

Run this diagnostic script to see what's already configured:

```bash
chmod +x /home/user/Skeeters_Clanker/CHECK_BATTLEYE.sh
bash /home/user/Skeeters_Clanker/CHECK_BATTLEYE.sh
```

Or manually check:
```bash
ls -la /srv/armareforger/ub1d584ced/battleye/
cat /srv/armareforger/ub1d584ced/battleye/BEServer.cfg
```

---

## 🔧 Step 2: Configure RCon (If BEServer.cfg Exists)

### Check Current BEServer.cfg
```bash
cat /srv/armareforger/ub1d584ced/battleye/BEServer.cfg
```

### Add RCon Configuration

**If file exists, add these lines:**
```bash
# For TTT1 (ub1d584ced)
cat >> /srv/armareforger/ub1d584ced/battleye/BEServer.cfg << 'EOF'
RConPassword YourStrongPassword123
RConPort 2306
RestrictRCon 0
EOF
```

**For TTT2 and TTT3, use different passwords:**
```bash
# TTT2
cat >> /srv/armareforger/uf74498006/battleye/BEServer.cfg << 'EOF'
RConPassword YourStrongPassword456
RConPort 2306
RestrictRCon 0
EOF

# TTT3
cat >> /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg << 'EOF'
RConPassword YourStrongPassword789
RConPort 2306
RestrictRCon 0
EOF
```

### If BEServer.cfg Doesn't Exist

**Create it from scratch:**
```bash
# TTT1
cat > /srv/armareforger/ub1d584ced/battleye/BEServer.cfg << 'EOF'
RConPassword YourStrongPassword123
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF

# TTT2
cat > /srv/armareforger/uf74498006/battleye/BEServer.cfg << 'EOF'
RConPassword YourStrongPassword456
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF

# TTT3
cat > /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg << 'EOF'
RConPassword YourStrongPassword789
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF
```

**Configuration Explained:**
- `RConPassword`: Strong password for RCon access (change these!)
- `RConPort`: Port for RCon (2306 is standard)
- `RestrictRCon 0`: Allow all RCon commands (required for banning)
- `MaxPing`: Optional - kick players with high ping

---

## 🐳 Step 3: Add Port Mapping to Docker Containers

**CRITICAL:** Your containers currently do NOT expose RCon ports.

### Current Port Mapping (TTT1):
```
2002/udp → 64.44.205.83:2002  (Game port)
3002/udp → 127.0.0.1:3002      (Unknown)
```

### Required Port Mapping:
```
2306/tcp → 127.0.0.1:2306  (RCon TTT1)
2307/tcp → 127.0.0.1:2307  (RCon TTT2)
2308/tcp → 127.0.0.1:2308  (RCon TTT3)
```

**Note:** Binding to `127.0.0.1` keeps RCon local only (secure). Do NOT bind to `0.0.0.0` or public IP!

### Option A: Modify Existing Containers (If Possible)

**Check how containers were created:**
```bash
docker inspect ub1d584ced | grep -i "cmd\|entrypoint" -A 5
```

**If using docker-compose:**
```bash
# Find docker-compose.yml
find /srv/armareforger -name "docker-compose.yml"

# Edit and add port mapping
ports:
  - "2306:2306/tcp"  # RCon
```

### Option B: Recreate Containers with Port Mapping

**⚠️ WARNING: This will restart your servers!**

**Get current container configuration:**
```bash
# Save current run command
docker inspect ub1d584ced | grep -A 50 "Cmd"
docker inspect ub1d584ced | grep -A 50 "Binds"
```

**Example recreation (adjust based on your actual config):**
```bash
# Stop container
docker stop ub1d584ced

# Remove container (data persists in volumes)
docker rm ub1d584ced

# Recreate with RCon port mapping
docker run -d \
  --name ub1d584ced \
  -p 64.44.205.83:2002:2002/udp \
  -p 127.0.0.1:3002:3002/udp \
  -p 127.0.0.1:2306:2306/tcp \
  -v /srv/armareforger/ub1d584ced:/reforger \
  [other-original-options] \
  [image-name]
```

### Option C: Use Docker Network (No Port Mapping Needed)

**Connect from another container on same network:**
```python
# Python bot connects via internal Docker network
rcon_config = {
    'ttt1': {
        'host': 'ub1d584ced',  # Container ID as hostname
        'port': 2306,
        'password': 'YourStrongPassword123'
    }
}
```

**This only works if:**
1. Bot runs inside a Docker container
2. Bot container shares network with game servers

**Check network:**
```bash
docker inspect ub1d584ced | grep -A 10 "Networks"
```

---

## 🧪 Step 4: Test RCon Connection

### Install RCon Testing Tool
```bash
pip install rcon --break-system-packages
```

### Test Connection (After Restarting Container)
```python
#!/usr/bin/env python3
# Save as /tmp/test_rcon.py

from rcon.battleye import Client

# Test TTT1
try:
    with Client('127.0.0.1', 2306, passwd='YourStrongPassword123') as client:
        response = client.run('players')
        print(f"✅ TTT1 RCon Connected")
        print(f"Response: {response}")
except Exception as e:
    print(f"❌ TTT1 RCon Failed: {e}")

# Test TTT2
try:
    with Client('127.0.0.1', 2307, passwd='YourStrongPassword456') as client:
        response = client.run('players')
        print(f"✅ TTT2 RCon Connected")
        print(f"Response: {response}")
except Exception as e:
    print(f"❌ TTT2 RCon Failed: {e}")

# Test TTT3
try:
    with Client('127.0.0.1', 2308, passwd='YourStrongPassword789') as client:
        response = client.run('players')
        print(f"✅ TTT3 RCon Connected")
        print(f"Response: {response}")
except Exception as e:
    print(f"❌ TTT3 RCon Failed: {e}")
```

**Run test:**
```bash
python3 /tmp/test_rcon.py
```

---

## 🎯 Step 5: Verify Configuration

### Check if BattlEye is Reading Config
```bash
# Check recent logs for BattlEye RCon initialization
docker logs ub1d584ced 2>&1 | grep -i "rcon\|battleye" | tail -20
```

**Look for:**
```
BattlEye Server: RCon initialized on port 2306
```

**If you see:**
```
BattlEye Server: Failed to initialize RCon
```

**Then:** Check if port 2306 is already in use:
```bash
docker exec ub1d584ced netstat -tuln | grep 2306
```

---

## 📊 Complete Setup Checklist

- [ ] BattlEye directory exists at `/srv/armareforger/[container]/battleye/`
- [ ] BEServer.cfg created with RCon settings
- [ ] RCon passwords set (different for each server)
- [ ] RestrictRCon set to 0 (allow all commands)
- [ ] Docker containers expose port 2306/tcp (or use internal network)
- [ ] Containers restarted after configuration changes
- [ ] RCon test script connects successfully
- [ ] Can execute `players` command
- [ ] Bot can connect from Python

---

## 🔐 Security Best Practices

### 1. Use Strong Passwords
```bash
# Generate random passwords
openssl rand -base64 24
```

### 2. Bind to Localhost Only
```bash
# GOOD (local only)
-p 127.0.0.1:2306:2306/tcp

# BAD (publicly accessible!)
-p 2306:2306/tcp
```

### 3. Store Passwords Securely
```python
# In bot.py, use environment variables
import os

RCON_CONFIG = {
    'ttt1': {
        'host': '127.0.0.1',
        'port': 2306,
        'password': os.getenv('RCON_PASSWORD_TTT1')
    }
}
```

**Set in environment:**
```bash
export RCON_PASSWORD_TTT1="YourStrongPassword123"
export RCON_PASSWORD_TTT2="YourStrongPassword456"
export RCON_PASSWORD_TTT3="YourStrongPassword789"
```

### 4. Restrict RCon Access
```bash
# Only allow from bot server's IP
iptables -A INPUT -p tcp --dport 2306 -s 127.0.0.1 -j ACCEPT
iptables -A INPUT -p tcp --dport 2306 -j DROP
```

---

## 🚀 Integration with Discord Bot

Once RCon is working, add to `bot.py`:

```python
# Add at top of bot.py
import berconpy
import os

# RCon configuration
RCON_CONFIG = {
    'ttt1': {
        'host': '127.0.0.1',
        'port': 2306,
        'password': os.getenv('RCON_PASSWORD_TTT1', 'YourStrongPassword123')
    },
    'ttt2': {
        'host': '127.0.0.1',
        'port': 2307,
        'password': os.getenv('RCON_PASSWORD_TTT2', 'YourStrongPassword456')
    },
    'ttt3': {
        'host': '127.0.0.1',
        'port': 2308,
        'password': os.getenv('RCON_PASSWORD_TTT3', 'YourStrongPassword789')
    }
}

async def execute_rcon_ban(server: str, beguid: str, duration: int, reason: str):
    """Execute ban via RCon"""
    config = RCON_CONFIG.get(server.lower())
    if not config:
        return f"❌ Unknown server: {server}"

    try:
        rcon = berconpy.RConClient(
            config['host'],
            config['port'],
            config['password']
        )
        await rcon.connect()

        # Execute ban command (use BEGUID!)
        response = await rcon.command(f'addBan {beguid} {duration} {reason}')

        await rcon.disconnect()
        return f"✅ Ban executed on {server.upper()}: {response}"

    except Exception as e:
        return f"❌ RCon error on {server.upper()}: {e}"

# New Discord command
@bot.tree.command(name="rcon-ban", description="Ban player via BattlEye RCon")
@app_commands.describe(
    server="Server (ttt1, ttt2, ttt3)",
    player_identifier="Player name or GUID",
    duration="Duration in minutes (0 = permanent)",
    reason="Ban reason"
)
async def rcon_ban_command(interaction: discord.Interaction, server: str,
                          player_identifier: str, duration: int, reason: str):
    """Ban player using RCon"""

    await interaction.response.defer()

    # Lookup player in database
    player = player_db.get_player_by_guid(player_identifier)
    if not player:
        # Try by name
        players = player_db.find_players_by_name(player_identifier)
        if players:
            player = players[0]

    if not player:
        await interaction.followup.send(
            f"❌ Player not found: `{player_identifier}`\n"
            "Use `/player-db-history` to search first.",
            ephemeral=True
        )
        return

    # Get BEGUID (required for RCon)
    beguid = player.get('beguid')
    if not beguid:
        await interaction.followup.send(
            f"❌ No BattlEye GUID found for player: {player['current_name']}\n"
            "Player may need to reconnect to get BEGUID.",
            ephemeral=True
        )
        return

    # Execute ban
    result = await execute_rcon_ban(server, beguid, duration, reason)

    # Update database if successful
    if "✅" in result:
        player_db.ban_player(player['guid'], reason)

    # Send result
    embed = discord.Embed(
        title="🔨 RCon Ban Executed",
        description=result,
        color=discord.Color.red() if "❌" in result else discord.Color.green()
    )
    embed.add_field(name="Player", value=player['current_name'])
    embed.add_field(name="BEGUID", value=f"`{beguid[:16]}...`")
    embed.add_field(name="Duration", value=f"{duration} min" if duration else "Permanent")
    embed.add_field(name="Reason", value=reason)

    await interaction.followup.send(embed=embed)
```

---

## 🐛 Troubleshooting

### RCon Connection Refused
```
Error: Connection refused
```

**Causes:**
1. Port not mapped in Docker
2. RCon not enabled in BEServer.cfg
3. Container not restarted after config change
4. Wrong IP/port

**Solutions:**
```bash
# Check port mapping
docker port ub1d584ced

# Check if port is listening
docker exec ub1d584ced netstat -tuln | grep 2306

# Restart container
docker restart ub1d584ced

# Check logs
docker logs ub1d584ced | grep -i rcon
```

### Invalid Password
```
Error: Authentication failed
```

**Solution:**
```bash
# Verify password in config
cat /srv/armareforger/ub1d584ced/battleye/BEServer.cfg | grep RConPassword

# Update if wrong
sed -i 's/RConPassword .*/RConPassword YourNewPassword/' /srv/armareforger/ub1d584ced/battleye/BEServer.cfg

# Restart
docker restart ub1d584ced
```

### RestrictRCon Error
```
Error: Command not allowed
```

**Solution:**
```bash
# Ensure RestrictRCon is 0
echo "RestrictRCon 0" >> /srv/armareforger/ub1d584ced/battleye/BEServer.cfg
docker restart ub1d584ced
```

### Port Already in Use
```
Error: Address already in use
```

**Solution:**
```bash
# Find what's using the port
netstat -tuln | grep 2306
lsof -i :2306

# Kill the process or use different port
```

---

## 📝 Next Steps After Setup

1. **Test RCon connection** with test script
2. **Install berconpy** for async support: `pip install berconpy`
3. **Add RCon commands** to Discord bot
4. **Create auto-ban system** for VPN users
5. **Set up ban synchronization** across all 3 servers

---

## 💾 Save Your Configuration

**Document your settings:**
```bash
# Create config backup
cat > /srv/armareforger/RCON_CONFIG.txt << EOF
Server: TTT1
Container: ub1d584ced
RCon Port: 127.0.0.1:2306
Password: [REDACTED]
Config Path: /srv/armareforger/ub1d584ced/battleye/BEServer.cfg

Server: TTT2
Container: uf74498006
RCon Port: 127.0.0.1:2307
Password: [REDACTED]
Config Path: /srv/armareforger/uf74498006/battleye/BEServer.cfg

Server: TTT3
Container: u98fbb3f3c
RCon Port: 127.0.0.1:2308
Password: [REDACTED]
Config Path: /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg
EOF
```

---

**Ready to proceed? Run the diagnostic script first:**

```bash
bash /home/user/Skeeters_Clanker/CHECK_BATTLEYE.sh
```

This will show us exactly what's already configured and what needs to be added.
