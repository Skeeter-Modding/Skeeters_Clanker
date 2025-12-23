# Arma Reforger Server Management Quick Guide

This bot is specifically designed to help manage Arma Reforger game servers running in Docker containers with full BattleEye player tracking.

## Quick Start for Arma Reforger

**💡 Pro Tip:** Configure friendly server names in `bot.py` so you can use `ttt1` instead of long container IDs!

### 1. View All Players

See everyone who has connected to your server:

```
/players container_name: ttt1
```

This shows:
- Player names
- GUIDs and BEGUIDs
- IP addresses
- Player numbers

**Tip:** Increase `lines` parameter to see more history (e.g., `lines: 5000`)

### 2. Get Player Details

Look up a specific player:

```
/player-info container_name: your-arma-server player_name: PlayerName
```

Shows complete profile including GUID, BEGUID, IP, and recent activity.

### 3. Search by GUID or IP

Find a player using their identifiers:

```
/search-player container_name: your-arma-server search_term: 192.168.1.100
```

or

```
/search-player container_name: your-arma-server search_term: abc123def456
```

Perfect for tracking banned players or investigating issues.

### 4. Monitor Your Server in Real-Time

The most useful feature for game servers is live log monitoring:

```
/monitor-logs container_name: your-arma-server
```

This will stream all server logs to your Discord channel in real-time, with automatic highlighting:
- ✅ **Green check** - Player connected/authenticated (shows IP and GUID!)
- 👋 **Wave** - Player disconnected
- ❌ **Red X** - Errors, exceptions, crashes
- ⚠️ **Warning** - Warnings from the server
- 📝 **Note** - Regular log entries

**NEW:** When players connect, you'll see their IP and GUID automatically displayed!

### 5. Filter Logs

Only want to see player activity? Add a filter:

```
/monitor-logs container_name: your-arma-server filter: player
```

Or only see errors:

```
/monitor-logs container_name: your-arma-server filter: error
```

### 6. Check Server Status

Get a quick overview of your server:

```
/server-status container_name: your-arma-server
```

This shows:
- Server online/offline status
- CPU and memory usage
- Players currently online (parsed from logs)
- Recent errors
- Warning count

### 7. View Recent Logs

Want to check what happened without streaming?

```
/container-logs container_name: your-arma-server lines: 100
```

Search for specific events:

```
/container-logs container_name: your-arma-server lines: 200 search: kicked
```

### 8. Restart the Server

If your server is having issues, kill it and let your dashboard auto-restart:

```
/restart-container container_name: your-arma-server
```

This will kill the container and your UI dashboard will automatically bring it back up.

### 9. Stop Monitoring

When you're done watching logs:

```
/stop-monitor container_name: your-arma-server
```

## Common Workflows

### Player Investigation
1. `/players your-arma-server` - See all recent players
2. `/player-info your-arma-server player_name: SuspiciousPlayer` - Get full details
3. `/search-player your-arma-server search_term: their_guid` - Find all accounts with that GUID
4. Check their recent activity in the player-info results

### Ban Enforcement
1. `/search-player your-arma-server search_term: banned_player_guid` - Find if they rejoined
2. `/monitor-logs your-arma-server filter: player` - Watch for their connection attempts
3. Document their IP and BEGUID for server-side bans

### Morning Server Check
1. `/server-status your-arma-server` - Check if server is healthy
2. `/container-logs your-arma-server lines: 50 search: error` - Check for any overnight errors
3. If problems found: `/restart-container your-arma-server`

### Active Admin Session
1. `/monitor-logs your-arma-server filter: player` - Watch player activity
2. Keep the channel open to see who's joining/leaving in real-time
3. `/stop-monitor your-arma-server` when done

### Troubleshooting
1. `/container-logs your-arma-server lines: 200 search: error` - Find errors
2. `/server-status your-arma-server` - Check resource usage
3. `/restart-container your-arma-server` - Kill container (dashboard will auto-restart it)
4. `/monitor-logs your-arma-server` - Watch for issues on startup

## Tips

- **Player Data Persistence**: The bot tracks players in memory during monitoring sessions. For historical data, increase the `lines` parameter in commands.
- **BattleEye Log Format**: The bot automatically parses various BattleEye log formats including player connections, GUID verifications, and IP addresses.
- **Multiple Channels**: You can monitor different containers in different Discord channels
- **Filters are powerful**: Use them to reduce noise (e.g., `filter: error` or `filter: player`)
- **Log History**: The bot looks at the last 500-2000 lines for player/server status
- **Rate Limiting**: Log monitoring has a small delay to prevent Discord rate limits
- **GUID vs BEGUID**: GUID is the game identifier, BEGUID is BattleEye's unique identifier - both are useful for tracking players
- **IP Tracking**: IPs are shown with ports (e.g., `192.168.1.1:2302`), useful for identifying multiple connections from same network

## Container Naming

You have two options for referencing containers:

### Option 1: Friendly Names (Recommended)
Configure server mappings in `bot.py`:
```python
SERVERS = {
    "ttt1": "actual-container-id-here",
    "pvp": "another-container-id",
}
```
Then use: `/restart-container container_name: ttt1`

### Option 2: Direct Container Names/IDs
Use the actual Docker container name or ID directly.

**To see all configured friendly names:**
```
/servers
```

**To find container names/IDs:**
```
/list-containers all: true
```
