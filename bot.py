#!/usr/bin/env python3
"""
Skeeters_Clanker - Discord Bot for Arma Reforger Server Management
Monitors Docker containers running Arma Reforger game servers
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import docker
import asyncio
import re
import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import defaultdict
import berconpy

# Import the player database system
import sys
sys.path.insert(0, '/srv/armareforger/player_database')
from player_database import PlayerDatabase
from player_log_monitor import PlayerLogMonitor

# =============================================================================
# DATA STORAGE (persists to JSON files)
# =============================================================================

DATA_DIR = "/srv/armareforger/Skeeters_Clanker/data"
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.json")
PLAYER_DATA_FILE = os.path.join(DATA_DIR, "player_data.json")

def ensure_data_dir():
    """Create data directory if it doesn't exist"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_watchlist():
    """Load watchlist from file"""
    ensure_data_dir()
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_watchlist(data):
    """Save watchlist to file"""
    ensure_data_dir()
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_player_data():
    """Load player history data from file"""
    ensure_data_dir()
    if os.path.exists(PLAYER_DATA_FILE):
        try:
            with open(PLAYER_DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_player_data(data):
    """Save player history data to file"""
    ensure_data_dir()
    with open(PLAYER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Global data stores
WATCHLIST = load_watchlist()  # {name_or_guid: {reason, added_by, added_at}}
PLAYER_DATA = load_player_data()  # {guid: {names: [], ips: [], sessions: []}}

# VPN Alert channel (set with /vpn-alert-channel)
VPN_ALERT_CHANNEL = None

# =============================================================================
# IP LOOKUP FUNCTION
# =============================================================================

# Get your free API key at: https://ipgeolocation.io/signup
IPGEO_API_KEY = "aa519b371cdb46fc869e690cbba6e25c"  # ipgeolocation.io API key (1000 free requests/day)

# Initialize player database (after IPGEO_API_KEY is defined)
DB_PATH = "/srv/armareforger/Skeeters_Clanker/data/players.db"
try:
    player_db = PlayerDatabase(DB_PATH)
    player_monitor = PlayerLogMonitor(DB_PATH, IPGEO_API_KEY)
    print(f"✅ Player database initialized: {DB_PATH}")
except Exception as e:
    print(f"⚠️ Player database initialization failed: {e}")
    player_db = None
    player_monitor = None

# =============================================================================
# RCON CONFIGURATION
# =============================================================================

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


def lookup_ip(ip_address):
    """Get geolocation, ISP, and security info for an IP address using ipgeolocation.io"""
    try:
        result = {}
        
        # Primary lookup with ipgeolocation.io
        if IPGEO_API_KEY:
            url = f"https://api.ipgeolocation.io/ipgeo?apiKey={IPGEO_API_KEY}&ip={ip_address}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if 'message' in data:  # Error response
                return {'error': data.get('message', 'Lookup failed')}
            
            result = {
                'ip': data.get('ip', ip_address),
                'country': data.get('country_name', 'Unknown'),
                'region': data.get('state_prov', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'zip': data.get('zipcode', ''),
                'lat': data.get('latitude', '0'),
                'lon': data.get('longitude', '0'),
                'isp': data.get('isp', 'Unknown'),
                'org': data.get('organization', 'Unknown'),
                'as': f"AS{data.get('asn', 'Unknown')}" if data.get('asn') else 'Unknown',
                'country_flag': data.get('country_flag', ''),
                'currency': data.get('currency', {}).get('code', '') if isinstance(data.get('currency'), dict) else '',
                'timezone': data.get('time_zone', {}).get('name', '') if isinstance(data.get('time_zone'), dict) else '',
            }
        
        # Secondary lookup with ip-api.com for proxy/VPN detection (free)
        try:
            proxy_response = requests.get(f"http://ip-api.com/json/{ip_address}?fields=proxy,hosting", timeout=5)
            proxy_data = proxy_response.json()
            result['is_proxy'] = proxy_data.get('proxy', False)
            result['is_hosting'] = proxy_data.get('hosting', False)
        except:
            pass
        
        return result if result else {'error': 'Lookup failed'}
        
    except Exception as e:
        return {'error': str(e)}

# =============================================================================
# SERVER CONFIGURATION
# Map friendly names to full Docker container IDs
# Update these when containers are recreated!
# =============================================================================

SERVERS = {
    "ttt1": "ub1d584ced",   # Port 2002
    "ttt2": "uf74498006",   # Port 2003
    "ttt3": "u98fbb3f3c",   # Port 2001
}

# Log file paths on disk
LOG_PATHS = {
    "ttt1": "/srv/armareforger/ub1d584ced/logs",
    "ttt2": "/srv/armareforger/uf74498006/logs",
    "ttt3": "/srv/armareforger/u98fbb3f3c/logs",
}

def get_latest_log_dir(server_name):
    """Get the most recent log directory for a server"""
    import os
    log_path = LOG_PATHS.get(server_name.lower())
    if not log_path or not os.path.exists(log_path):
        return None
    
    # Get all dated directories
    dirs = [d for d in os.listdir(log_path) if os.path.isdir(os.path.join(log_path, d)) and d.startswith('20')]
    if not dirs:
        return None
    
    # Sort by name (they're date-formatted, so this works)
    dirs.sort(reverse=True)
    return os.path.join(log_path, dirs[0])

def get_all_log_dirs(server_name, max_sessions=10):
    """Get log directories for a server (limited for performance)"""
    import os
    log_path = LOG_PATHS.get(server_name.lower())
    if not log_path or not os.path.exists(log_path):
        return []
    
    # Get all dated directories
    dirs = [d for d in os.listdir(log_path) if os.path.isdir(os.path.join(log_path, d)) and d.startswith('20')]
    dirs.sort(reverse=True)  # Most recent first
    return [os.path.join(log_path, d) for d in dirs[:max_sessions]]

def read_current_session_log(server_name, log_type='console'):
    """Read ENTIRE current session log file - for player tracking"""
    import os
    
    log_dir = get_latest_log_dir(server_name)
    if not log_dir:
        return ""
    
    log_file = os.path.join(log_dir, f"{log_type}.log")
    if not os.path.exists(log_file):
        return ""
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except:
        return ""

def read_log_file_tail(server_name, log_type='console', lines=500):
    """Read last N lines from a server's log file - memory efficient for monitoring"""
    import os
    from collections import deque
    
    log_dir = get_latest_log_dir(server_name)
    if not log_dir:
        return ""
    
    log_file = os.path.join(log_dir, f"{log_type}.log")
    if not os.path.exists(log_file):
        return ""
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            last_lines = deque(f, maxlen=lines)
        return ''.join(last_lines)
    except:
        return ""

def update_player_database(server_name, player_info):
    """Update player database when we parse a player from logs"""
    if not player_db:
        return []
    
    try:
        # Extract geolocation data if we have it
        geo_data = None
        if player_info.get('ip'):
            # Use cached IP lookup
            ip_clean = player_info['ip'].split(':')[0]
            geo_result = lookup_ip(ip_clean)
            if 'error' not in geo_result:
                geo_data = {
                    'country_name': geo_result.get('country'),
                    'isp': geo_result.get('isp'),
                    'security': {
                        'is_vpn': geo_result.get('is_proxy', False),
                        'is_proxy': geo_result.get('is_hosting', False)
                    }
                }
        
        # Update database and get alerts
        alerts = player_db.update_player(
            guid=player_info['guid'],
            name=player_info['name'],
            ip=player_info.get('ip'),
            beguid=player_info.get('beguid'),
            server_name=server_name,
            geo_data=geo_data
        )
        
        # If VPN alert channel is set, send alerts there
        if alerts and VPN_ALERT_CHANNEL:
            asyncio.create_task(send_database_alerts(alerts, server_name))
        
        return alerts
    except Exception as e:
        print(f"Error updating player database: {e}")
        return []

async def send_database_alerts(alerts, server_name):
    """Send database alerts to VPN alert channel"""
    try:
        if not VPN_ALERT_CHANNEL:
            return
        
        channel = bot.get_channel(VPN_ALERT_CHANNEL)
        if not channel:
            return
        
        # Format alerts for Discord
        alert_text = "\n".join(f"• {alert}" for alert in alerts)
        
        embed = discord.Embed(
            title=f"🚨 Player Alert - {server_name.upper()}",
            description=alert_text,
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Error sending database alerts: {e}")


def search_logs_for_player(server_name, search_term, max_sessions=10):
    """Search logs efficiently without loading everything into memory"""
    import os
    
    results = []
    search_lower = search_term.lower()
    max_results = 100  # Higher limit with 128GB RAM
    
    for log_dir in get_all_log_dirs(server_name, max_sessions):
        if len(results) >= max_results:
            break
            
        log_file = os.path.join(log_dir, "console.log")
        if not os.path.exists(log_file):
            continue
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if len(results) >= max_results:
                        break
                    if search_lower in line.lower():
                        # Only keep lines with player info
                        if 'BattlEye' in line or 'Player joined' in line:
                            results.append(line.strip())
        except:
            pass
    
    return results

def get_container_id(name_or_id: str) -> str:
    """Convert friendly name (ttt1, ttt2, ttt3) to full container ID"""
    return SERVERS.get(name_or_id.lower(), name_or_id)

# =============================================================================
# BOT SETUP
# =============================================================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
docker_client = docker.from_env()

# Store active log monitoring tasks
log_monitors = {}

# Permission check - add your admin role IDs here
ADMIN_ROLES = [1390425301519044759]  # Admin role ID

async def check_permission(interaction: discord.Interaction) -> bool:
    """Check if user has permission. If not, warn and timeout."""
    # Check if user has admin role
    has_admin = any(role.id in ADMIN_ROLES for role in interaction.user.roles)
    
    if has_admin:
        return True
    
    # User is not authorized - warn them publicly and timeout
    try:
        # Send public warning
        await interaction.response.send_message(
            f"⛔ **{interaction.user.display_name}**, you are not authorized to run bot commands!",
            ephemeral=False
        )
        
        # Timeout for 30 seconds
        from datetime import timedelta
        await interaction.user.timeout(timedelta(seconds=30), reason="Unauthorized bot command attempt")
    except discord.Forbidden:
        # Bot doesn't have permission to timeout
        await interaction.response.send_message(
            f"⛔ **{interaction.user.display_name}**, you are not authorized to run bot commands!",
            ephemeral=False
        )
    except discord.errors.InteractionResponded:
        # Already responded, send followup
        await interaction.followup.send(
            f"⛔ **{interaction.user.display_name}**, you are not authorized to run bot commands!",
            ephemeral=False
        )
    
    return False

# =============================================================================
# BOT EVENTS
# =============================================================================

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Serving {len(bot.guilds)} guild(s)')
    print(f'Configured servers: {", ".join(SERVERS.keys())}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# =============================================================================
# CONTAINER MANAGEMENT COMMANDS
# =============================================================================

@bot.tree.command(name="list-containers", description="List all Docker containers")
async def list_containers(interaction: discord.Interaction):
    """List all Docker containers with status"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        containers = docker_client.containers.list(all=True)
        
        if not containers:
            await interaction.followup.send("📦 No containers found.")
            return
        
        embed = discord.Embed(title="📦 Docker Containers", color=discord.Color.blue())
        
        for container in containers:
            status_emoji = "🟢" if container.status == "running" else "🔴"
            short_id = container.short_id
            name = container.name
            
            # Check if this is one of our game servers
            friendly_name = None
            for fname, cid in SERVERS.items():
                if cid.startswith(container.id):
                    friendly_name = fname.upper()
                    break
            
            display_name = f"{friendly_name} ({name})" if friendly_name else name
            embed.add_field(
                name=f"{status_emoji} {display_name}",
                value=f"ID: `{short_id}`\nStatus: {container.status}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="server-status", description="Get Arma Reforger server status")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3) or container ID")
async def server_status(interaction: discord.Interaction, container_name: str):
    """Get detailed server status"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        # Get recent logs
        logs = container.logs(tail=200).decode('utf-8', errors='replace')
        
        # Count players from logs
        player_count = 0
        player_match = re.search(r'Players connected: (\d+)', logs)
        if player_match:
            player_count = int(player_match.group(1))
        
        # Check for recent errors
        error_count = logs.lower().count('error')
        
        # Create embed
        status_color = discord.Color.green() if container.status == "running" else discord.Color.red()
        embed = discord.Embed(
            title=f"🎮 {container_name.upper()} Status",
            color=status_color,
            timestamp=datetime.utcnow()
        )
        
        status_emoji = "🟢" if container.status == "running" else "🔴"
        embed.add_field(name="Status", value=f"{status_emoji} {container.status.upper()}", inline=True)
        
        # Calculate uptime
        started_at = container.attrs['State'].get('StartedAt', '')
        if started_at and container.status == "running":
            try:
                start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                uptime = datetime.now(start_time.tzinfo) - start_time
                days = uptime.days
                hours, remainder = divmod(uptime.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if days > 0:
                    uptime_str = f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    uptime_str = f"{hours}h {minutes}m"
                else:
                    uptime_str = f"{minutes}m"
                embed.add_field(name="Uptime", value=f"⏱️ {uptime_str}", inline=True)
            except:
                pass
        
        embed.add_field(name="Players", value=f"👥 {player_count}", inline=True)
        
        # Get resource stats
        try:
            stats = container.stats(stream=False)
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
            num_cpus = len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [1]))
            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0 if system_delta > 0 else 0.0
            
            mem_usage = stats['memory_stats'].get('usage', 0) / 1024 / 1024
            mem_limit = stats['memory_stats'].get('limit', 1) / 1024 / 1024
            
            embed.add_field(name="CPU", value=f"💻 {cpu_percent:.1f}%", inline=True)
            embed.add_field(name="Memory", value=f"🧠 {mem_usage:.0f}/{mem_limit:.0f} MB", inline=True)
        except:
            pass
        
        if error_count > 0:
            embed.add_field(name="Errors", value=f"⚠️ {error_count} in recent logs", inline=True)
        
        embed.set_footer(text=f"Container: {container.short_id}")
        await interaction.followup.send(embed=embed)
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="start-server", description="Start an Arma Reforger server")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3) or container ID")
async def start_server(interaction: discord.Interaction, container_name: str):
    """Start a server container"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        if container.status == "running":
            await interaction.followup.send(f"⚠️ **{container_name.upper()}** is already running!")
            return
        
        container.start()
        await interaction.followup.send(f"✅ **{container_name.upper()}** started successfully!")
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error starting container: {str(e)}")

@bot.tree.command(name="stop-server", description="Stop an Arma Reforger server")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3) or container ID")
async def stop_server(interaction: discord.Interaction, container_name: str):
    """Stop a server container"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        if container.status != "running":
            await interaction.followup.send(f"⚠️ **{container_name.upper()}** is not running!")
            return
        
        container.stop(timeout=30)
        await interaction.followup.send(f"🛑 **{container_name.upper()}** stopped successfully!")
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error stopping container: {str(e)}")

@bot.tree.command(name="restart-server", description="Restart an Arma Reforger server")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3) or container ID")
async def restart_server(interaction: discord.Interaction, container_name: str):
    """Restart a server container"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        await interaction.followup.send(f"🔄 Restarting **{container_name.upper()}**...")
        container.restart(timeout=30)
        await asyncio.sleep(5)
        
        container.reload()
        if container.status == "running":
            await interaction.channel.send(f"✅ **{container_name.upper()}** restarted successfully!")
        else:
            await interaction.channel.send(f"⚠️ **{container_name.upper()}** restart completed but status is: {container.status}")
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error restarting container: {str(e)}")

# =============================================================================
# LOG COMMANDS
# =============================================================================

@bot.tree.command(name="logs", description="Get recent server logs")
@app_commands.describe(
    container_name="Server name (ttt1, ttt2, ttt3) or container ID",
    lines="Number of lines to retrieve (default: 50)"
)
async def get_logs(interaction: discord.Interaction, container_name: str, lines: int = 50):
    """Get recent logs from a container"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        logs = container.logs(tail=min(lines, 100)).decode('utf-8', errors='replace')
        
        if len(logs) > 1900:
            logs = logs[-1900:]
        
        await interaction.followup.send(f"📜 **{container_name.upper()}** logs:\n```\n{logs}\n```")
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="search-logs", description="Search server logs for a pattern")
@app_commands.describe(
    container_name="Server name (ttt1, ttt2, ttt3) or container ID",
    pattern="Text pattern to search for",
    lines="Number of log lines to search (default: 500)"
)
async def search_logs(interaction: discord.Interaction, container_name: str, pattern: str, lines: int = 500):
    """Search logs for a specific pattern"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        logs = container.logs(tail=min(lines, 1000)).decode('utf-8', errors='replace')
        
        matches = [line for line in logs.split('\n') if pattern.lower() in line.lower()]
        
        if not matches:
            await interaction.followup.send(f"🔍 No matches found for `{pattern}` in **{container_name.upper()}**")
            return
        
        result = '\n'.join(matches[-20:])
        if len(result) > 1900:
            result = result[-1900:]
        
        await interaction.followup.send(f"🔍 Found {len(matches)} matches for `{pattern}`:\n```\n{result}\n```")
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# =============================================================================
# PLAYER TRACKING COMMANDS
# =============================================================================

@bot.tree.command(name="players", description="Get list of connected players")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3) or container ID")
async def get_players(interaction: discord.Interaction, container_name: str):
    """Get connected players from server logs"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        # Read ENTIRE current session (from game start to now)
        logs = read_current_session_log(container_name, 'console')
        if not logs:
            # Fallback to docker logs
            logs = container.logs(tail=2000).decode('utf-8', errors='replace')
        
        # Track players - use dict to track join/leave status
        players = {}  # name -> {'joined': bool, 'identity': str}
        
        for line in logs.split('\n'):
            # Player joined: "Player joined, id: 131, ... name: Heck Let Loose, identityId: xxx"
            join_match = re.search(r'Player joined, id: \d+,.*name: ([^,]+), identityId: ([a-f0-9-]+)', line)
            if join_match:
                name, identity = join_match.groups()
                players[name.strip()] = {'joined': True, 'identity': identity}
            
            # BattlEye connect: "BattlEye Server: 'Player #283 Crowbar™ (IP) connected'"
            be_connect = re.search(r"BattlEye Server: 'Player #\d+ ([^(]+) \([^)]+\) connected'", line)
            if be_connect:
                name = be_connect.group(1).strip()
                if name not in players:
                    players[name] = {'joined': True, 'identity': ''}
                else:
                    players[name]['joined'] = True
            
            # BattlEye disconnect: "BattlEye Server: 'Player #214 jimmyrobbo2102 disconnected'"
            be_disconnect = re.search(r"BattlEye Server: 'Player #\d+ ([^ ]+) disconnected'", line)
            if be_disconnect:
                name = be_disconnect.group(1).strip()
                if name in players:
                    players[name]['joined'] = False
            
            # Player disconnected via network
            if 'Player disconnected:' in line:
                # Mark recent players as potentially disconnected - will be overwritten if they reconnect
                pass
        
        # Filter to only currently connected players
        connected = [name for name, data in players.items() if data['joined']]
        
        embed = discord.Embed(
            title=f"👥 Players on {container_name.upper()}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if connected:
            # Split into columns if many players
            player_list = '\n'.join([f"• {name}" for name in sorted(connected)[:30]])
            if len(connected) > 30:
                player_list += f"\n... and {len(connected) - 30} more"
            embed.add_field(name=f"Online ({len(connected)})", value=player_list, inline=False)
        else:
            embed.description = "No players currently connected (or unable to determine from logs)"
        
        await interaction.followup.send(embed=embed)
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="find-player", description="Find a player by name or GUID")
@app_commands.describe(
    container_name="Server name (ttt1, ttt2, ttt3) or container ID",
    search="Player name or GUID to search for"
)
async def find_player(interaction: discord.Interaction, container_name: str, search: str):
    """Search for a player in logs"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        # Use efficient line-by-line search (doesn't load entire file)
        matching_lines = search_logs_for_player(container_name, search, max_sessions=10)
        
        if not matching_lines:
            await interaction.followup.send(f"🔍 No results found for `{search}`")
            return
        
        # Parse the matching lines
        seen_players = {}
        
        for line in matching_lines:
            # BattlEye connect: "BattlEye Server: 'Player #283 Crowbar™ (IP) connected'"
            be_connect = re.search(r"BattlEye Server: 'Player #(\d+) ([^(]+) \(([^)]+)\) connected'", line)
            if be_connect:
                name = be_connect.group(2).strip()
                if name not in seen_players:
                    seen_players[name] = {'ip': be_connect.group(3)}
                else:
                    seen_players[name]['ip'] = be_connect.group(3)
                continue
            
            # BattlEye GUID: "BattlEye Server: 'Player #283 Crowbar™ - BE GUID: xxx'"
            be_guid = re.search(r"BattlEye Server: 'Player #(\d+) ([^-]+) - BE GUID: ([a-f0-9]+)'", line)
            if be_guid:
                name = be_guid.group(2).strip()
                if name not in seen_players:
                    seen_players[name] = {'guid': be_guid.group(3)}
                else:
                    seen_players[name]['guid'] = be_guid.group(3)
                continue
            
            # ServerAdminTools: "Player joined, id: 131, ... name: Heck Let Loose, identityId: xxx"
            admin_match = re.search(r'Player joined, id: (\d+),.*name: ([^,]+), identityId: ([a-f0-9-]+)', line)
            if admin_match:
                name = admin_match.group(2).strip()
                if name not in seen_players:
                    seen_players[name] = {'identity': admin_match.group(3)}
                else:
                    seen_players[name]['identity'] = admin_match.group(3)
        
        if not seen_players:
            await interaction.followup.send(f"🔍 No player info found for `{search}`")
            return
        
        # Update database with parsed player info
        for name, info in seen_players.items():
            player_info = {
                'name': name,
                'guid': info.get('identity', info.get('guid', 'unknown')),
                'beguid': info.get('guid'),
                'ip': info.get('ip')
            }
            update_player_database(container_name, player_info)
        
        embed = discord.Embed(
            title=f"🔍 Search Results: {search}",
            description=f"Found {len(seen_players)} unique player(s)",
            color=discord.Color.blue()
        )
        
        for name, info in list(seen_players.items())[:15]:
            details = []
            if 'ip' in info:
                details.append(f"IP: `{info['ip']}`")
            if 'guid' in info:
                details.append(f"GUID: `{info['guid']}`")
            if 'identity' in info:
                details.append(f"ID: `{info['identity'][:20]}...`")
            
            embed.add_field(
                name=name,
                value='\n'.join(details) if details else "Found in logs",
                inline=True
            )
        
        if len(seen_players) > 15:
            embed.set_footer(text=f"Showing 15 of {len(seen_players)} unique players")
        
        await interaction.followup.send(embed=embed)
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# =============================================================================
# IP LOOKUP COMMANDS
# =============================================================================

@bot.tree.command(name="ip-lookup", description="Lookup geolocation and ISP info for an IP address")
@app_commands.describe(ip_address="IP address to lookup")
async def ip_lookup(interaction: discord.Interaction, ip_address: str):
    """Get geolocation and ISP info for an IP"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    # Validate IP format
    ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    if not ip_pattern.match(ip_address):
        await interaction.followup.send(f"❌ Invalid IP address format: `{ip_address}`")
        return
    
    result = lookup_ip(ip_address)
    
    if 'error' in result:
        await interaction.followup.send(f"❌ Lookup failed: {result['error']}")
        return
    
    embed = discord.Embed(
        title=f"🌐 IP Lookup: {result['ip']}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="📍 Location", value=f"{result['city']}, {result['region']}\n{result['country']} {result['zip']}", inline=True)
    embed.add_field(name="🌍 Coordinates", value=f"{result['lat']}, {result['lon']}", inline=True)
    embed.add_field(name="📡 ISP", value=result['isp'], inline=False)
    embed.add_field(name="🏢 Organization", value=result['org'], inline=True)
    embed.add_field(name="🔢 AS", value=result['as'], inline=True)
    
    # Show VPN/Proxy/TOR info if available
    security_info = []
    if result.get('is_proxy'):
        security_info.append("⚠️ **PROXY**")
    if result.get('is_vpn'):
        security_info.append("🔒 **VPN**")
    if result.get('is_tor'):
        security_info.append("🧅 **TOR**")
    if result.get('is_hosting'):
        security_info.append("☁️ **Hosting/DC**")
    if result.get('threat_score') is not None:
        security_info.append(f"Threat Score: {result['threat_score']}/100")
    
    if security_info:
        embed.add_field(name="🛡️ Security", value='\n'.join(security_info), inline=False)
    
    if result.get('timezone'):
        embed.add_field(name="🕐 Timezone", value=result['timezone'], inline=True)
    if result.get('currency'):
        embed.add_field(name="💰 Currency", value=result['currency'], inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="player-ip", description="Lookup a player's IP info from server logs")
@app_commands.describe(
    container_name="Server name (ttt1, ttt2, ttt3)",
    player_name="Player name to search for"
)
async def player_ip(interaction: discord.Interaction, container_name: str, player_name: str):
    """Find a player's IP and lookup their geolocation"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        # Search logs for player's IP
        matching_lines = search_logs_for_player(container_name, player_name, max_sessions=10)
        
        # Find IP from BattlEye connect line
        player_ip = None
        actual_name = None
        
        for line in matching_lines:
            be_connect = re.search(r"BattlEye Server: 'Player #\d+ ([^(]+) \(([^:]+):\d+\) connected'", line)
            if be_connect:
                actual_name = be_connect.group(1).strip()
                player_ip = be_connect.group(2)
                break
        
        if not player_ip:
            await interaction.followup.send(f"❌ Could not find IP for player `{player_name}`")
            return
        
        # Lookup the IP
        result = lookup_ip(player_ip)
        
        if 'error' in result:
            await interaction.followup.send(f"❌ Found IP `{player_ip}` but lookup failed: {result['error']}")
            return
        
        embed = discord.Embed(
            title=f"🎮 Player IP Info: {actual_name}",
            color=discord.Color.green()
        )
        
        embed.add_field(name="🔗 IP Address", value=f"`{player_ip}`", inline=True)
        embed.add_field(name="📍 Location", value=f"{result['city']}, {result['region']}\n{result['country']}", inline=True)
        embed.add_field(name="📡 ISP", value=result['isp'], inline=False)
        embed.add_field(name="🏢 Organization", value=result['org'], inline=True)
        embed.add_field(name="🔢 AS", value=result['as'], inline=True)
        
        # Show VPN/Proxy/TOR warning
        security_flags = []
        if result.get('is_proxy'):
            security_flags.append("⚠️ **PROXY**")
        if result.get('is_vpn'):
            security_flags.append("🔒 **VPN**")
        if result.get('is_tor'):
            security_flags.append("🧅 **TOR**")
        if result.get('is_hosting'):
            security_flags.append("☁️ **Hosting/DC**")
        
        if security_flags:
            embed.add_field(name="🛡️ Security Flags", value='\n'.join(security_flags), inline=False)
            embed.color = discord.Color.orange()  # Change color to warn
        
        embed.add_field(name="🌍 Coordinates", value=f"{result['lat']}, {result['lon']}", inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="player-ips", description="List all players with their IPs and locations (current session)")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3)")
async def player_ips(interaction: discord.Interaction, container_name: str):
    """List all connected players with IP info"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        # Read current session
        logs = read_current_session_log(container_name, 'console')
        if not logs:
            logs = container.logs(tail=2000).decode('utf-8', errors='replace')
        
        # Extract player IPs
        players = {}  # name -> {ip, connected}
        
        for line in logs.split('\n'):
            # BattlEye connect
            be_connect = re.search(r"BattlEye Server: 'Player #\d+ ([^(]+) \(([^:]+):\d+\) connected'", line)
            if be_connect:
                name = be_connect.group(1).strip()
                ip = be_connect.group(2)
                players[name] = {'ip': ip, 'connected': True}
            
            # BattlEye disconnect
            be_disconnect = re.search(r"BattlEye Server: 'Player #\d+ ([^ ]+) disconnected'", line)
            if be_disconnect:
                name = be_disconnect.group(1).strip()
                if name in players:
                    players[name]['connected'] = False
        
        # Filter to connected only
        connected = {k: v for k, v in players.items() if v.get('connected', False)}
        
        if not connected:
            await interaction.followup.send(f"📋 No players with IP data found on **{container_name.upper()}**")
            return
        
        # Lookup IPs (limit to first 10 to avoid rate limits)
        embed = discord.Embed(
            title=f"🌐 Player IPs on {container_name.upper()}",
            description=f"Showing {min(len(connected), 10)} of {len(connected)} players",
            color=discord.Color.blue()
        )
        
        count = 0
        for name, info in connected.items():
            if count >= 10:
                break
            
            ip_info = lookup_ip(info['ip'])
            if 'error' not in ip_info:
                location = f"{ip_info['city']}, {ip_info['country']}"
                embed.add_field(
                    name=name,
                    value=f"IP: `{info['ip']}`\n📍 {location}\n📡 {ip_info['isp'][:30]}",
                    inline=True
                )
            else:
                embed.add_field(
                    name=name,
                    value=f"IP: `{info['ip']}`\n❌ Lookup failed",
                    inline=True
                )
            count += 1
        
        if len(connected) > 10:
            embed.set_footer(text=f"Use /player-ip to lookup individual players. Rate limited to 10.")
        
        await interaction.followup.send(embed=embed)
        
    except docker.errors.NotFound:
        await interaction.followup.send(f"❌ Container `{container_name}` not found.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# =============================================================================
# PLAYER HISTORY & TRACKING
# =============================================================================

@bot.tree.command(name="player-history", description="Show a player's connection history across all sessions")
@app_commands.describe(
    container_name="Server name (ttt1, ttt2, ttt3)",
    player_name="Player name to search for"
)
async def player_history(interaction: discord.Interaction, container_name: str, player_name: str):
    """Show player's connection history"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        # Search logs - 20 sessions is fine with this hardware
        matching_lines = search_logs_for_player(container_name, player_name, max_sessions=20)
        
        if not matching_lines:
            await interaction.followup.send(f"🔍 No history found for `{player_name}`")
            return
        
        # Parse connection data - use sets with max size
        ips_used = set()
        names_used = set()
        guids = set()
        connect_count = 0
        
        for line in matching_lines:
            # BattlEye connect with IP
            be_connect = re.search(r"BattlEye Server: 'Player #(\d+) ([^(]+) \(([^:]+):\d+\) connected'", line)
            if be_connect:
                name = be_connect.group(2).strip()
                ip = be_connect.group(3)
                if len(names_used) < 20:
                    names_used.add(name)
                if len(ips_used) < 20:
                    ips_used.add(ip)
                connect_count += 1
                continue
            
            # BattlEye GUID
            be_guid = re.search(r"BattlEye Server: 'Player #\d+ ([^-]+) - BE GUID: ([a-f0-9]+)'", line)
            if be_guid:
                name = be_guid.group(1).strip()
                guid = be_guid.group(2)
                if len(names_used) < 20:
                    names_used.add(name)
                if len(guids) < 10:
                    guids.add(guid)
        
        embed = discord.Embed(
            title=f"📜 Player History: {player_name}",
            color=discord.Color.blue()
        )
        
        if names_used:
            embed.add_field(name="📛 Names Used", value='\n'.join(list(names_used)[:10]) or "Unknown", inline=True)
        
        if ips_used:
            ip_list = '\n'.join([f"`{ip}`" for ip in list(ips_used)[:5]])
            embed.add_field(name="🔗 IPs Used", value=ip_list or "Unknown", inline=True)
        
        if guids:
            guid_list = '\n'.join([f"`{g[:16]}...`" for g in list(guids)[:3]])
            embed.add_field(name="🔑 GUIDs", value=guid_list or "Unknown", inline=True)
        
        embed.add_field(name="📊 Total Connections", value=str(connect_count), inline=True)
        embed.add_field(name="🖥️ Unique IPs", value=str(len(ips_used)), inline=True)
        embed.add_field(name="📝 Name Changes", value=str(len(names_used)), inline=True)
        
        embed.set_footer(text="Use /player-ip to check for VPN/proxy")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="player-playtime", description="Estimate a player's playtime from logs")
@app_commands.describe(
    container_name="Server name (ttt1, ttt2, ttt3)",
    player_name="Player name to search for"
)
async def player_playtime(interaction: discord.Interaction, container_name: str, player_name: str):
    """Estimate player's total playtime"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        # 20 sessions with this hardware
        log_dirs = get_all_log_dirs(container_name, max_sessions=20)
        
        total_sessions = 0
        total_minutes = 0
        longest_session = 0
        player_lower = player_name.lower()
        
        for log_dir in log_dirs:
            log_file = os.path.join(log_dir, "console.log")
            if not os.path.exists(log_file):
                continue
            
            connect_time = None
            player_found = False
            
            try:
                with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        # Quick check before expensive operations
                        if player_lower not in line.lower():
                            continue
                        
                        player_found = True
                        
                        # Connect
                        if 'connected' in line and 'BattlEye' in line:
                            time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                            if time_match:
                                try:
                                    connect_time = datetime.strptime(time_match.group(1), '%H:%M:%S')
                                except:
                                    pass
                        
                        # Disconnect
                        elif 'disconnected' in line and connect_time:
                            time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                            if time_match:
                                try:
                                    disconnect_time = datetime.strptime(time_match.group(1), '%H:%M:%S')
                                    if disconnect_time < connect_time:
                                        disconnect_time += timedelta(days=1)
                                    session_length = (disconnect_time - connect_time).seconds // 60
                                    if 0 < session_length < 1440:
                                        total_minutes += session_length
                                        total_sessions += 1
                                        if session_length > longest_session:
                                            longest_session = session_length
                                    connect_time = None
                                except:
                                    pass
                
                if player_found and total_sessions == 0:
                    total_sessions = 1
                    
            except:
                pass
        
        if total_sessions == 0:
            await interaction.followup.send(f"🔍 No playtime data found for `{player_name}`")
            return
        
        hours = total_minutes // 60
        minutes = total_minutes % 60
        avg_session = total_minutes // total_sessions if total_sessions > 0 else 0
        
        embed = discord.Embed(
            title=f"⏱️ Playtime: {player_name}",
            color=discord.Color.green()
        )
        
        embed.add_field(name="📊 Total Playtime", value=f"**{hours}h {minutes}m**", inline=True)
        embed.add_field(name="🎮 Sessions", value=str(total_sessions), inline=True)
        embed.add_field(name="📈 Avg Session", value=f"{avg_session}m", inline=True)
        
        if longest_session > 0:
            embed.add_field(name="🏆 Longest Session", value=f"{longest_session // 60}h {longest_session % 60}m", inline=True)
        
        embed.set_footer(text=f"Based on last {len(log_dirs)} sessions analyzed")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# =============================================================================
# WATCHLIST
# =============================================================================

@bot.tree.command(name="watchlist-add", description="Add a player to the watchlist")
@app_commands.describe(
    player_name="Player name or GUID to watch",
    reason="Reason for watching this player"
)
async def watchlist_add(interaction: discord.Interaction, player_name: str, reason: str = "No reason provided"):
    """Add player to watchlist"""
    if not await check_permission(interaction):
        return
    
    global WATCHLIST
    
    WATCHLIST[player_name.lower()] = {
        'name': player_name,
        'reason': reason,
        'added_by': str(interaction.user),
        'added_at': datetime.utcnow().isoformat()
    }
    save_watchlist(WATCHLIST)
    
    embed = discord.Embed(
        title="👁️ Added to Watchlist",
        color=discord.Color.orange()
    )
    embed.add_field(name="Player", value=player_name, inline=True)
    embed.add_field(name="Reason", value=reason, inline=True)
    embed.add_field(name="Added By", value=str(interaction.user), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="watchlist-remove", description="Remove a player from the watchlist")
@app_commands.describe(player_name="Player name or GUID to remove")
async def watchlist_remove(interaction: discord.Interaction, player_name: str):
    """Remove player from watchlist"""
    if not await check_permission(interaction):
        return
    
    global WATCHLIST
    
    key = player_name.lower()
    if key in WATCHLIST:
        del WATCHLIST[key]
        save_watchlist(WATCHLIST)
        await interaction.response.send_message(f"✅ Removed `{player_name}` from watchlist")
    else:
        await interaction.response.send_message(f"❌ `{player_name}` not found in watchlist")

@bot.tree.command(name="watchlist", description="Show all players on the watchlist")
async def watchlist_show(interaction: discord.Interaction):
    """Show watchlist"""
    if not await check_permission(interaction):
        return
    
    if not WATCHLIST:
        await interaction.response.send_message("📋 Watchlist is empty")
        return
    
    embed = discord.Embed(
        title="👁️ Watchlist",
        description=f"{len(WATCHLIST)} player(s) being watched",
        color=discord.Color.orange()
    )
    
    for key, data in list(WATCHLIST.items())[:20]:
        embed.add_field(
            name=data.get('name', key),
            value=f"Reason: {data.get('reason', 'N/A')}\nAdded by: {data.get('added_by', 'Unknown')}",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="watchlist-check", description="Check if any watchlisted players are online")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3)")
async def watchlist_check(interaction: discord.Interaction, container_name: str):
    """Check for watchlisted players on server"""
    if not await check_permission(interaction):
        return
    
    if not WATCHLIST:
        await interaction.response.send_message("📋 Watchlist is empty")
        return
    
    await interaction.response.defer()
    
    try:
        # Fast NVMe reads
        logs = read_log_file_tail(container_name, 'console', 5000)
        logs_lower = logs.lower()
        
        found_players = []
        
        for key, data in WATCHLIST.items():
            if len(found_players) >= 10:
                break
                
            name = data.get('name', key)
            name_lower = name.lower()
            
            if name_lower in logs_lower:
                # Quick check - is last mention a connect or disconnect?
                last_connect = logs_lower.rfind(f"{name_lower}") 
                last_disconnect = logs_lower.rfind(f"{name_lower} disconnected")
                
                if last_connect > last_disconnect:
                    found_players.append(data)
        
        if found_players:
            embed = discord.Embed(
                title=f"⚠️ Watchlisted Players on {container_name.upper()}",
                color=discord.Color.red()
            )
            
            for player in found_players:
                embed.add_field(
                    name=f"🚨 {player.get('name', 'Unknown')}",
                    value=f"Reason: {player.get('reason', 'N/A')[:50]}",
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"✅ No watchlisted players found on **{container_name.upper()}**")
            
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# =============================================================================
# VPN/PROXY ALERTS
# =============================================================================

@bot.tree.command(name="vpn-alert-channel", description="Set channel for VPN/proxy alerts")
@app_commands.describe(channel="Channel to send VPN alerts to")
async def vpn_alert_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set VPN alert channel"""
    if not await check_permission(interaction):
        return
    
    global VPN_ALERT_CHANNEL
    VPN_ALERT_CHANNEL = channel.id
    
    await interaction.response.send_message(f"✅ VPN alerts will be sent to {channel.mention}")

@bot.tree.command(name="vpn-check", description="Check all current players for VPN/proxy usage")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3)")
async def vpn_check(interaction: discord.Interaction, container_name: str):
    """Check current players for VPN/proxy"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        container_id = get_container_id(container_name)
        container = docker_client.containers.get(container_id)
        
        # Use more log lines with 128GB RAM
        logs = read_log_file_tail(container_name, 'console', 5000)
        if not logs:
            logs = container.logs(tail=2000).decode('utf-8', errors='replace')
        
        # Get connected players with IPs - limit parsing
        players = {}
        for line in logs.split('\n'):
            if 'BattlEye' not in line:
                continue
                
            be_connect = re.search(r"BattlEye Server: 'Player #\d+ ([^(]+) \(([^:]+):\d+\) connected'", line)
            if be_connect:
                name = be_connect.group(1).strip()
                ip = be_connect.group(2)
                players[name] = {'ip': ip, 'connected': True}
                continue
            
            be_disconnect = re.search(r"BattlEye Server: 'Player #\d+ ([^ ]+) disconnected'", line)
            if be_disconnect:
                name = be_disconnect.group(1).strip()
                if name in players:
                    players[name]['connected'] = False
        
        # Filter connected only
        connected = {k: v for k, v in players.items() if v.get('connected', False)}
        
        if not connected:
            await interaction.followup.send(f"📋 No players found on **{container_name.upper()}**")
            return
        
        vpn_users = []
        checked = 0
        
        # Can handle more API calls with fast network
        for name, info in connected.items():
            if checked >= 20:
                break
            
            result = lookup_ip(info['ip'])
            if result.get('is_proxy') or result.get('is_hosting'):
                vpn_users.append({
                    'name': name,
                    'ip': info['ip'],
                    'isp': result.get('isp', 'Unknown')[:25],
                    'is_proxy': result.get('is_proxy', False),
                    'is_hosting': result.get('is_hosting', False)
                })
            checked += 1
        
        if vpn_users:
            embed = discord.Embed(
                title=f"🛡️ VPN/Proxy Users on {container_name.upper()}",
                description=f"Found {len(vpn_users)} suspicious connection(s)",
                color=discord.Color.red()
            )
            
            for user in vpn_users[:10]:
                flags = []
                if user['is_proxy']:
                    flags.append("⚠️ Proxy")
                if user['is_hosting']:
                    flags.append("☁️ Hosting/DC")
                
                embed.add_field(
                    name=user['name'],
                    value=f"IP: `{user['ip']}`\nISP: {user['isp']}\n{' '.join(flags)}",
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"✅ No VPN/proxy users detected on **{container_name.upper()}** (checked {checked} players)")
            
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# =============================================================================
# DUPLICATE/ALT ACCOUNT CHECK
# =============================================================================

@bot.tree.command(name="duplicate-check", description="Find players connecting from the same IP (potential alts)")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3)")
async def duplicate_check(interaction: discord.Interaction, container_name: str):
    """Find players with same IP"""
    if not await check_permission(interaction):
        return
    
    await interaction.response.defer()
    
    try:
        # More lines with NVMe RAID1
        logs = read_log_file_tail(container_name, 'console', 10000)
        
        # Map IPs to player names with limits
        ip_to_players = defaultdict(set)
        
        for line in logs.split('\n'):
            # Quick filter
            if 'BattlEye' not in line or 'connected' not in line:
                continue
                
            be_connect = re.search(r"BattlEye Server: 'Player #\d+ ([^(]+) \(([^:]+):\d+\) connected'", line)
            if be_connect:
                name = be_connect.group(1).strip()
                ip = be_connect.group(2)
                if len(ip_to_players[ip]) < 20:  # Limit names per IP
                    ip_to_players[ip].add(name)
        
        # Find IPs with multiple players
        duplicates = {ip: names for ip, names in ip_to_players.items() if len(names) > 1}
        
        if not duplicates:
            await interaction.followup.send(f"✅ No duplicate IPs found on **{container_name.upper()}**")
            return
        
        embed = discord.Embed(
            title=f"👥 Duplicate IPs on {container_name.upper()}",
            description=f"Found {len(duplicates)} IP(s) with multiple players",
            color=discord.Color.orange()
        )
        
        for ip, names in list(duplicates.items())[:8]:
            player_list = '\n'.join([f"• {n}" for n in list(names)[:5]])
            if len(names) > 5:
                player_list += f"\n... +{len(names) - 5} more"
            embed.add_field(
                name=f"🔗 {ip}",
                value=f"**{len(names)} players:**\n{player_list}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# =============================================================================
# ERROR LOG VIEWER
# =============================================================================

@bot.tree.command(name="errors", description="Show recent errors from server logs")
@app_commands.describe(
    container_name="Server name (ttt1, ttt2, ttt3)",
    count="Number of errors to show (default: 10, max: 20)"
)
async def show_errors(interaction: discord.Interaction, container_name: str, count: int = 10):
    """Show recent errors from logs"""
    if not await check_permission(interaction):
        return
    
    # Limit count
    count = min(count, 20)
    
    await interaction.response.defer()
    
    try:
        log_dir = get_latest_log_dir(container_name)
        errors = []
        
        # Read error.log with deque (memory efficient)
        if log_dir:
            error_file = os.path.join(log_dir, "error.log")
            if os.path.exists(error_file):
                try:
                    from collections import deque
                    with open(error_file, 'r', encoding='utf-8', errors='replace') as f:
                        last_lines = deque(f, maxlen=50)
                    
                    for line in last_lines:
                        line = line.strip()
                        if line and len(line) > 10 and len(errors) < count * 2:
                            errors.append(line[:150])
                except:
                    pass
        
        # Check console.log for errors (limited lines)
        console_log = read_log_file_tail(container_name, 'console', 300)
        for line in console_log.split('\n'):
            if len(errors) >= count * 2:
                break
            line_upper = line.upper()
            if 'ERROR' in line_upper or 'EXCEPTION' in line_upper or 'FATAL' in line_upper:
                errors.append(line.strip()[:150])
        
        if not errors:
            await interaction.followup.send(f"✅ No recent errors found on **{container_name.upper()}**")
            return
        
        # Deduplicate and limit
        unique_errors = list(dict.fromkeys(errors))[-count:]
        
        embed = discord.Embed(
            title=f"⚠️ Recent Errors on {container_name.upper()}",
            description=f"Showing {len(unique_errors)} error(s)",
            color=discord.Color.red()
        )
        
        error_text = ""
        for err in unique_errors:
            if len(error_text) + len(err) < 1800:
                error_text += f"• {err[:80]}\n"
        
        if error_text:
            embed.add_field(name="Errors", value=f"```{error_text}```", inline=False)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# =============================================================================
# LIVE MONITORING
# =============================================================================

@bot.tree.command(name="monitor-start", description="Start live log monitoring in this channel")
@app_commands.describe(
    container_name="Server name (ttt1, ttt2, ttt3) or container ID",
    filter_pattern="Optional: only show lines containing this text"
)
async def monitor_start(interaction: discord.Interaction, container_name: str, filter_pattern: str = None):
    """Start streaming logs to the channel"""
    if not await check_permission(interaction):
        return
    
    monitor_key = f"{interaction.channel_id}_{container_name}"
    
    if monitor_key in log_monitors and not log_monitors[monitor_key].done():
        await interaction.response.send_message(f"⚠️ Already monitoring **{container_name.upper()}** in this channel!")
        return
    
    await interaction.response.send_message(f"📡 Starting live monitor for **{container_name.upper()}**...")
    
    async def stream_logs():
        try:
            container_id = get_container_id(container_name)
            container = docker_client.containers.get(container_id)
            
            last_log = ""
            while True:
                logs = container.logs(tail=10).decode('utf-8', errors='replace')
                
                new_lines = []
                for line in logs.split('\n'):
                    if line and line not in last_log:
                        if filter_pattern is None or filter_pattern.lower() in line.lower():
                            new_lines.append(line)
                
                if new_lines:
                    msg = '\n'.join(new_lines[-5:])
                    if len(msg) > 1900:
                        msg = msg[:1900]
                    await interaction.channel.send(f"```\n{msg}\n```")
                
                last_log = logs
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            await interaction.channel.send(f"📡 Stopped monitoring **{container_name.upper()}**")
        except Exception as e:
            await interaction.channel.send(f"❌ Monitor error: {str(e)}")
    
    task = asyncio.create_task(stream_logs())
    log_monitors[monitor_key] = task

@bot.tree.command(name="monitor-stop", description="Stop live log monitoring")
@app_commands.describe(container_name="Server name (ttt1, ttt2, ttt3) or container ID")
async def monitor_stop(interaction: discord.Interaction, container_name: str):
    """Stop streaming logs"""
    if not await check_permission(interaction):
        return
    
    monitor_key = f"{interaction.channel_id}_{container_name}"
    
    if monitor_key in log_monitors:
        log_monitors[monitor_key].cancel()
        del log_monitors[monitor_key]
        await interaction.response.send_message(f"🛑 Stopped monitoring **{container_name.upper()}**")
    else:
        await interaction.response.send_message(f"⚠️ No active monitor for **{container_name.upper()}** in this channel")

@bot.tree.command(name="monitor-list", description="List active log monitors")
async def monitor_list(interaction: discord.Interaction):
    """List all active monitors"""
    if not await check_permission(interaction):
        return
    
    active = [key.split('_', 1)[1] for key, task in log_monitors.items() 
              if not task.done() and str(interaction.channel_id) in key]
    
    if active:
        container_list = '\n'.join([f"• `{name}`" for name in active])
        await interaction.response.send_message(f"📊 Active monitors in this channel:\n{container_list}")
    else:
        await interaction.response.send_message("📊 No active monitors in this channel.")

# =============================================================================
# UTILITY COMMANDS
# =============================================================================

@bot.tree.command(name="server-list", description="List all configured game servers")
async def server_list(interaction: discord.Interaction):
    """List all configured servers"""
    embed = discord.Embed(
        title="🎮 Configured Servers",
        color=discord.Color.blue()
    )
    
    for name, cid in SERVERS.items():
        try:
            container = docker_client.containers.get(cid)
            status = "🟢 Running" if container.status == "running" else f"🔴 {container.status}"
        except:
            status = "❓ Unknown"
        
        embed.add_field(name=name.upper(), value=status, inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show bot commands and usage")
async def help_command(interaction: discord.Interaction):
    """Show help information"""
    embed = discord.Embed(
        title="🤖 Skeeters Clanker - Help",
        description="Discord bot for managing Arma Reforger servers",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📦 Server Management",
        value="`/server-list` - List configured servers\n"
              "`/server-status` - Get server status\n"
              "`/start-server` - Start a server\n"
              "`/stop-server` - Stop a server\n"
              "`/restart-server` - Restart a server",
        inline=False
    )
    
    embed.add_field(
        name="📜 Logs",
        value="`/logs` - Get recent logs\n"
              "`/search-logs` - Search logs for pattern\n"
              "`/errors` - Show recent errors",
        inline=False
    )
    
    embed.add_field(
        name="👥 Players",
        value="`/players` - List connected players\n"
              "`/find-player` - Search for a player\n"
              "`/player-history` - Player's connection history\n"
              "`/player-playtime` - Estimate playtime",
        inline=False
    )
    
    embed.add_field(
        name="🌐 IP Lookup",
        value="`/ip-lookup` - Lookup any IP address\n"
              "`/player-ip` - Lookup a player's IP\n"
              "`/player-ips` - List players with IPs",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ Security",
        value="`/vpn-check` - Check players for VPN/proxy\n"
              "`/vpn-alert-channel` - Set VPN alert channel\n"
              "`/duplicate-check` - Find same-IP players (alts)",
        inline=False
    )
    
    embed.add_field(
        name="👁️ Watchlist",
        value="`/watchlist` - Show watchlist\n"
              "`/watchlist-add` - Add player to watchlist\n"
              "`/watchlist-remove` - Remove from watchlist\n"
              "`/watchlist-check` - Check for watchlisted players",
        inline=False
    )
    
    embed.add_field(
        name="📡 Live Monitoring",
        value="`/monitor-start` - Start live log stream\n"
              "`/monitor-stop` - Stop log stream\n"
              "`/monitor-list` - List active monitors",
        inline=False
    )
    
    embed.add_field(
        name="🗄️ Player Database",
        value="`/db-stats` - Database statistics\n"
              "`/player-db-history` - Complete history\n"
              "`/find-alts-by-ip` - Find alts by IP\n"
              "`/find-alts-by-name` - Find alts by name\n"
              "`/player-ban-database` - Ban in DB\n"
              "`/player-notes-add` - Add notes\n"
              "`/db-alerts` - View alerts",
        inline=False
    )

    embed.add_field(
        name="🔨 RCon Commands",
        value="`/rcon-ban` - Ban player via RCon\n"
              "`/rcon-players` - List online players\n"
              "`/rcon-kick` - Kick player from server\n"
              "`/rcon-command` - Execute raw RCon command",
        inline=False
    )

    embed.set_footer(text="Use ttt1, ttt2, or ttt3 for server names")

    await interaction.response.send_message(embed=embed)

# =============================================================================
# PLAYER DATABASE COMMANDS
# =============================================================================

@bot.tree.command(name="db-stats", description="View player database statistics")
async def db_stats(interaction: discord.Interaction):
    """Get database statistics"""
    if not await check_permission(interaction):
        return
    
    if not player_db:
        await interaction.response.send_message("❌ Player database not initialized", ephemeral=True)
        return
    
    stats = player_db.get_stats()
    
    embed = discord.Embed(
        title="📊 Player Database Statistics",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="Total Players", value=str(stats['total_players']), inline=True)
    embed.add_field(name="Banned", value=str(stats['banned_players']), inline=True)
    embed.add_field(name="Unack. Alerts", value=str(stats['unacknowledged_alerts']), inline=True)
    embed.add_field(name="VPN IPs", value=str(stats['vpn_ips_detected']), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="player-db-history", description="Get complete player history from database")
@app_commands.describe(
    server_name="Server name (ttt1, ttt2, ttt3)",
    player_identifier="Player name or GUID"
)
async def player_db_history(interaction: discord.Interaction, server_name: str, player_identifier: str):
    """Get detailed player history from database"""
    if not await check_permission(interaction):
        return
    
    if not player_db:
        await interaction.response.send_message("❌ Player database not initialized", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # Try to find player
    player = player_db.get_player_by_guid(player_identifier)
    if not player:
        player = player_db.get_player_by_name(player_identifier)
    
    if not player:
        await interaction.followup.send(f"❌ Player not found: `{player_identifier}`")
        return
    
    # Get complete history
    history = player_db.get_player_history(player['guid'])
    
    embed = discord.Embed(
        title=f"📜 Database History: {player['current_name']}",
        description=f"GUID: `{player['guid']}`\nTotal connections: {player['total_connections']}",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    # Names used
    if history['names']:
        names_list = []
        for name_data in history['names'][:10]:
            names_list.append(f"• {name_data['name']} ({name_data['use_count']}x)")
        embed.add_field(
            name=f"🏷️ Names ({len(history['names'])} total)",
            value="\n".join(names_list) or "None",
            inline=False
        )
    
    # IPs used
    if history['ips']:
        ips_list = []
        for ip_data in history['ips'][:10]:
            vpn = "🔒VPN" if ip_data['is_vpn'] else ""
            country = f"({ip_data['country']})" if ip_data['country'] else ""
            ips_list.append(f"• {ip_data['ip_address']} {country} {vpn}")
        embed.add_field(
            name=f"🌍 IPs ({len(history['ips'])} total)",
            value="\n".join(ips_list) or "None",
            inline=False
        )
    
    # Recent alerts
    if history['alerts']:
        alerts_list = []
        for alert in history['alerts'][:5]:
            alerts_list.append(f"• {alert['alert_message'][:60]}")
        embed.add_field(
            name=f"⚠️ Alerts ({len(history['alerts'])})",
            value="\n".join(alerts_list) or "None",
            inline=False
        )
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="find-alts-by-ip", description="Find alt accounts using same IP address")
@app_commands.describe(ip_address="IP address to search (without port)")
async def find_alts_by_ip(interaction: discord.Interaction, ip_address: str):
    """Find all accounts that have used a specific IP"""
    if not await check_permission(interaction):
        return
    
    if not player_db:
        await interaction.response.send_message("❌ Player database not initialized", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    ip_clean = ip_address.split(':')[0]
    alts = player_db.find_alts(ip_clean)
    
    if not alts:
        await interaction.followup.send(f"❌ No players found using IP: `{ip_clean}`")
        return
    
    embed = discord.Embed(
        title=f"🔍 Alt Accounts - IP: {ip_clean}",
        description=f"Found {len(alts)} account(s) using this IP",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    
    for alt in alts[:15]:
        embed.add_field(
            name=alt['current_name'],
            value=f"GUID: `{alt['guid'][:16]}...`\n"
                  f"First: {alt['first_seen'][:10]}\n"
                  f"Last: {alt['last_seen'][:10]}",
            inline=True
        )
    
    if len(alts) > 15:
        embed.set_footer(text=f"Showing 15 of {len(alts)} results")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="find-alts-by-name", description="Find all accounts using a specific name")
@app_commands.describe(player_name="Player name to search for")
async def find_alts_by_name(interaction: discord.Interaction, player_name: str):
    """Find all GUIDs that have used a specific name"""
    if not await check_permission(interaction):
        return
    
    if not player_db:
        await interaction.response.send_message("❌ Player database not initialized", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    alts = player_db.find_name_alts(player_name)
    
    if not alts:
        await interaction.followup.send(f"❌ No accounts found with name: `{player_name}`")
        return
    
    embed = discord.Embed(
        title=f"🔍 Accounts Using: {player_name}",
        description=f"Found {len(alts)} account(s)",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    
    for alt in alts[:15]:
        embed.add_field(
            name=f"{alt['current_name']} (now)",
            value=f"GUID: `{alt['guid'][:16]}...`\n"
                  f"IP: {alt['current_ip'] or 'Unknown'}\n"
                  f"Used: {alt['last_used'][:10]}",
            inline=True
        )
    
    if len(alts) > 15:
        embed.set_footer(text=f"Showing 15 of {len(alts)} results")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="player-ban-database", description="[ADMIN] Ban player in database")
@app_commands.describe(
    guid="Player GUID to ban",
    reason="Ban reason"
)
async def player_ban_database(interaction: discord.Interaction, guid: str, reason: str):
    """Ban a player in database"""
    if not await check_permission(interaction):
        return
    
    if not player_db:
        await interaction.response.send_message("❌ Player database not initialized", ephemeral=True)
        return
    
    player = player_db.get_player_by_guid(guid)
    if not player:
        await interaction.response.send_message(f"❌ Player not found: `{guid}`", ephemeral=True)
        return
    
    player_db.ban_player(guid, reason)
    
    await interaction.response.send_message(
        f"✅ Banned in database: **{player['current_name']}**\nReason: {reason}"
    )

@bot.tree.command(name="player-notes-add", description="[ADMIN] Add notes to player")
@app_commands.describe(
    guid="Player GUID",
    notes="Admin notes"
)
async def player_notes_add(interaction: discord.Interaction, guid: str, notes: str):
    """Add admin notes to player"""
    if not await check_permission(interaction):
        return
    
    if not player_db:
        await interaction.response.send_message("❌ Player database not initialized", ephemeral=True)
        return
    
    player = player_db.get_player_by_guid(guid)
    if not player:
        await interaction.response.send_message(f"❌ Player not found: `{guid}`", ephemeral=True)
        return
    
    player_db.add_notes(guid, notes)
    
    await interaction.response.send_message(
        f"✅ Added notes for: **{player['current_name']}**"
    )

@bot.tree.command(name="db-alerts", description="[ADMIN] View unacknowledged database alerts")
@app_commands.describe(limit="Number of alerts to show (max 25)")
async def db_alerts(interaction: discord.Interaction, limit: int = 10):
    """View unacknowledged alerts"""
    if not await check_permission(interaction):
        return
    
    if not player_db:
        await interaction.response.send_message("❌ Player database not initialized", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    limit = min(limit, 25)
    alerts = player_db.get_unacknowledged_alerts(limit)
    
    if not alerts:
        await interaction.followup.send("✅ No unacknowledged alerts")
        return
    
    embed = discord.Embed(
        title="⚠️ Database Alerts",
        description=f"Showing {len(alerts)} alert(s)",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    
    for alert in alerts[:10]:
        embed.add_field(
            name=f"Alert #{alert['id']} - {alert['current_name']}",
            value=f"{alert['alert_message']}\n"
                  f"Created: {alert['created_at'][:16]}",
            inline=False
        )
    
    await interaction.followup.send(embed=embed)

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
        player_count = len([l for l in lines if 'Player' in l or (len(l) > 0 and l[0].isdigit())])
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
    """Execute raw RCon command"""

    await interaction.response.defer()

    response = await execute_rcon_command(server, command)

    embed = discord.Embed(
        title=f"⚙️ RCon Command: {server.upper()}",
        description=f"**Command:** `{command}`\n\n**Response:**\n```\n{response[:1800]}\n```",
        color=discord.Color.purple()
    )

    await interaction.followup.send(embed=embed)

# =============================================================================
# RUN BOT
# =============================================================================

if __name__ == "__main__":
    load_dotenv()
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not found!")
        print("Set it with: export DISCORD_BOT_TOKEN=your_token_here")
        exit(1)
    bot.run(token)
