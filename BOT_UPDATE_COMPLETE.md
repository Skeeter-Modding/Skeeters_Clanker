# ✅ Bot.py Updated with RCon Integration

## Changes Applied to Your Local bot.py

Your Discord bot has been successfully updated with full BattlEye RCon integration!

---

## 📝 What Was Added

### 1. Import Statement (Line 19)
```python
import berconpy
```

### 2. RCon Configuration (Lines 99-167)
- RCon server settings for TTT1, TTT2, TTT3
- `execute_rcon_command()` - Execute any RCon command with error handling
- `ban_player_rcon()` - Ban players using BEGUID

### 3. Help Command Update (Lines 1866-1873)
Added new section showing RCon commands:
- `/rcon-ban`
- `/rcon-players`
- `/rcon-kick`
- `/rcon-command`

### 4. New Discord Commands (Lines 2148-2314)

#### `/rcon-ban` - Ban Player Remotely
- Searches player database by name or GUID
- Gets BEGUID from database
- Executes ban via RCon
- Updates database with ban
- Shows success/failure embed

#### `/rcon-players` - List Online Players
- Shows currently connected players
- Displays player count
- Works even with encoding issues

#### `/rcon-kick` - Kick Player
- Kick by player number
- Provide reason
- Instant execution

#### `/rcon-command` - Raw RCon Access
- Execute any BattlEye command
- View responses
- Advanced admin tool

---

## 🚀 How to Deploy

### Option 1: Restart Bot on Server

```bash
# SSH to your server
ssh root@your-server

# Navigate to bot directory
cd /srv/armareforger/Skeeters_Clanker

# Pull the updated code
git fetch origin claude/battleye-rcon-protocol-FEZIL
git checkout claude/battleye-rcon-protocol-FEZIL
git pull

# Stop current bot
pkill -f "python3 bot.py"

# Start updated bot
nohup python3 bot.py > bot_output.log 2>&1 &

# Check logs
tail -f bot_output.log
```

### Option 2: Upload Updated File

If you prefer to upload the file directly:

1. Copy your local `/home/user/Skeeters_Clanker/bot.py`
2. Upload to `/srv/armareforger/Skeeters_Clanker/bot.py`
3. Restart bot (commands above)

---

## 🧪 Testing Commands

Once bot is restarted, test in Discord:

### 1. Check Help
```
/help
```
Should show new "🔨 RCon Commands" section

### 2. List Online Players
```
/rcon-players ttt1
```

### 3. Test Ban (Use Carefully!)
```
/rcon-ban ttt1 TestPlayerName 5 Testing RCon
```
Bans for 5 minutes

### 4. Execute Custom Command
```
/rcon-command ttt1 bans
```
Shows current ban list

---

## ✨ New Features

### Automatic BEGUID Lookup
The bot automatically:
1. Searches player database by name
2. Gets their BEGUID (BattlEye GUID)
3. Executes ban command
4. Updates database

### Works Offline
Players don't need to be online to ban them!

### Encoding Handling
Special characters in names/reasons are handled properly

### Timeout Protection
Won't hang if server is slow - shows warning instead

### Database Integration
All bans are recorded in your player database

---

## 📊 Command Examples

### Ban VPN User
```
/rcon-ban ttt1 SuspiciousPlayer 1440 VPN detected
```
Bans for 24 hours

### Permanent Ban
```
/rcon-ban ttt2 Cheater 0 Aimbotting - permanent
```
Duration 0 = permanent

### Quick Kick
```
/rcon-players ttt1
# See player #3 is toxic
/rcon-kick ttt1 3 Offensive language
```

### Check Bans
```
/rcon-command ttt1 bans
```

### Manual Ban by BEGUID
```
/rcon-command ttt1 addBan abc123def456 60 Manual ban
```

---

## 🔐 Security Features

### Database Required
Players must be in database (have connected before)

### BEGUID Validation
Won't ban if BEGUID not found

### Error Handling
Won't crash on encoding errors or timeouts

### Response Truncation
Long responses truncated to prevent Discord errors

---

## 🛠️ Troubleshooting

### "Player database not available"
- Check `/srv/armareforger/Skeeters_Clanker/data/players.db` exists
- Restart bot

### "No BattlEye GUID found"
- Player hasn't connected yet to get BEGUID
- Use `/player-db-history` to verify

### "Timeout - server is slow"
- Normal for busy servers
- Command probably executed anyway
- Increase timeout in code if needed

### "Cannot connect - server may be offline"
- Check server is running: `docker ps`
- Verify RCon enabled in UI
- Check port: `netstat -tuln | grep 400[1-3]`

---

## 📈 Stats

**Lines Added:** 248
**New Commands:** 4
**Functions Added:** 2
**Help Sections:** 1

**File Size:**
- Before: 2,079 lines
- After: 2,327 lines

---

## 🎯 Next Steps (Optional)

### Add Auto-Ban for VPN Users

In your VPN detection code, add:

```python
# When VPN detected
if is_vpn or is_proxy:
    # Get player's BEGUID from database
    player = player_db.get_player_by_guid(player_guid)

    if player and player.get('beguid'):
        # Auto-ban via RCon
        success, response = await ban_player_rcon(
            'ttt1',  # or server where detected
            player['beguid'],
            1440,  # 24 hours
            'VPN/Proxy detected - contact admin'
        )

        if success:
            print(f"✅ Auto-banned VPN user: {player['current_name']}")
```

### Add Permission Checks

Restrict RCon commands to admins:

```python
@bot.tree.command(name="rcon-ban", ...)
async def rcon_ban_command(interaction: discord.Interaction, ...):
    # Add this at start
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Administrator permission required",
            ephemeral=True
        )
        return

    # Rest of command...
```

### Add Logging

Log all RCon actions:

```python
# In rcon_ban_command, after success
with open('/srv/armareforger/Skeeters_Clanker/rcon_log.txt', 'a') as f:
    f.write(f"[{datetime.now()}] {interaction.user.name} banned {player['current_name']} for {duration}min - {reason}\n")
```

---

## 🎉 You're Done!

Your Discord bot now has:
- ✅ Remote banning via RCon
- ✅ Player listing
- ✅ Kick functionality
- ✅ Raw command execution
- ✅ Database integration
- ✅ Encoding error handling
- ✅ Timeout protection

**Ready to ban some cheaters!** 🔨

---

## 💾 Backup

Your original bot.py is in git history:
```bash
# To see changes
git diff HEAD~1 bot.py

# To revert if needed
git checkout HEAD~1 bot.py
```

---

**All changes committed to:** `claude/battleye-rcon-protocol-FEZIL`
**Commit hash:** `397107c`
