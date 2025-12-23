# Skeeters_Clanker - Arma Reforger Server Management

Discord bot and crash monitor for Triple Threat Tactical Arma Reforger servers.

## Files

| File | Purpose |
|------|---------|
| `bot.py` | Discord bot with slash commands for server management |
| `crash_monitor.py` | Standalone crash/packet loss/disconnect monitor (webhook alerts) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Bot token template |

## Current Server Configuration

| Server | Port | Container Name | Container ID |
|--------|------|----------------|--------------|
| TTT1 | 2002 | ub1d584ced | `17cc430c9c22...` |
| TTT2 | 2001 | u98fbb3f3c | `b8f4323f2161...` |
| TTT3 | 2003 | uf74498006 | `1b90e3689daf...` |

⚠️ **Container IDs change when containers are recreated!** Update both `bot.py` and `crash_monitor.py` when this happens.

## Deployment

### 1. Upload Files
Upload to `/srv/armareforger/Skeeters_Clanker/` via WinSCP

### 2. Install Dependencies (first time only)
```bash
pip install -r requirements.txt --break-system-packages
```

### 3. Start the Discord Bot
```bash
cd /srv/armareforger/Skeeters_Clanker
export DISCORD_BOT_TOKEN=MTQ0OTg2Mzc3OTEwOTMxMDUwNA.G9ixpY.EBj6JGb4PttlmHs3SBm_2USWzBar86JJ_crpGE
nohup python3 bot.py > bot_output.log 2>&1 &
```

### 4. Start the Crash Monitor
```bash
cd /srv/armareforger/Skeeters_Clanker
nohup python3 crash_monitor.py > crash_monitor_output.log 2>&1 &
```

## Management Commands

### Check Running Processes
```bash
ps aux | grep -E "bot.py|crash_monitor.py"
```

### Stop Bot
```bash
pkill -f "python3 bot.py"
```

### Stop Crash Monitor
```bash
pkill -f crash_monitor.py
```

### View Logs
```bash
tail -f /srv/armareforger/Skeeters_Clanker/bot_output.log
tail -f /srv/armareforger/Skeeters_Clanker/crash_monitor_output.log
```

## Crash Monitor Alerts

| Alert | Color | Trigger |
|-------|-------|---------|
| CRASH | 🔴 Red | `Application crash` or `malloc()` in logs |
| RESTART | 🔵 Blue | Server stopped without crash |
| SERVER UP | 🟢 Green | Server came back online |
| HIGH PACKET LOSS | 🟠 Orange | Any player >10% packet loss |
| MASS DISCONNECT | 🟠 Red-Orange | 10+ players disconnect in 30 seconds |

## Bot Commands

| Command | Description |
|---------|-------------|
| `/server-list` | List all configured servers with status |
| `/server-status ttt1` | Get detailed server status |
| `/start-server ttt1` | Start a server |
| `/stop-server ttt1` | Stop a server |
| `/restart-server ttt1` | Restart a server |
| `/logs ttt1` | Get recent logs |
| `/search-logs ttt1 pattern` | Search logs |
| `/players ttt1` | List connected players |
| `/find-player ttt1 name` | Find a player |
| `/monitor-start ttt1` | Start live log stream |
| `/monitor-stop ttt1` | Stop log stream |
| `/help` | Show all commands |

## Updating Container IDs

When containers are recreated, get new IDs:
```bash
docker ps --no-trunc
```

Then update the `SERVERS` dictionary in both:
- `bot.py` (line ~20)
- `crash_monitor.py` (line ~26)
