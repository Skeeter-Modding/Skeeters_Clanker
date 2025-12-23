#!/usr/bin/env python3
"""
Arma Reforger Server Crash Monitor v2
Monitors for: crashes, restarts, packet loss, mass disconnects
"""

import docker
import requests
import time
import logging
import re
import gc
import os
from datetime import datetime
from collections import deque

WEBHOOK_URL = 'https://discord.com/api/webhooks/1452426838423900190/7q3iAx6EK3SFGeYRTotr9tv1Zm_m0AW6E7D-8FiE4WFhWFepED_AWdUy57pRXWBKFati'
CHECK_INTERVAL = 30
LOG_SCAN_LINES = 100
ALERT_COOLDOWN = 300

# Thresholds
PACKET_LOSS_THRESHOLD = 10  # Alert if any player has >10% packet loss
MASS_DISCONNECT_COUNT = 10  # Alert if this many players disconnect
MASS_DISCONNECT_WINDOW = 30  # Within this many seconds

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
    log_path = LOG_PATHS.get(server_name)
    if not log_path or not os.path.exists(log_path):
        return None
    
    # Get all dated directories
    dirs = [d for d in os.listdir(log_path) if os.path.isdir(os.path.join(log_path, d)) and d.startswith('20')]
    if not dirs:
        return None
    
    # Sort by name (they're date-formatted, so this works)
    dirs.sort(reverse=True)
    return os.path.join(log_path, dirs[0])

def read_log_file(server_name, log_type='console', lines=500):
    """Read last N lines from a server's log file - memory efficient"""
    from collections import deque
    
    log_dir = get_latest_log_dir(server_name)
    if not log_dir:
        return ""
    
    log_file = os.path.join(log_dir, f"{log_type}.log")
    if not os.path.exists(log_file):
        return ""
    
    try:
        # Use deque for memory-efficient tail reading
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            last_lines = deque(f, maxlen=lines)
        return ''.join(last_lines)
    except:
        return ""

CRASH_KEYWORDS = ["Application crash", "malloc()"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def send_webhook(title, description, color=0xFF0000, fields=None, server_name=None):
    embed = {"title": title, "description": description, "color": color, 
             "timestamp": datetime.utcnow().isoformat(), "footer": {"text": "Skeeters Crash Monitor"}}
    if fields:
        embed["fields"] = fields
    if server_name:
        embed["author"] = {"name": f"Server: {server_name.upper()}"}
    try:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        logger.info(f"Webhook sent: {title}")
    except Exception as e:
        logger.error(f"Webhook failed: {e}")

def scan_logs_for_crashes(container, lines=LOG_SCAN_LINES):
    try:
        logs = container.logs(tail=lines).decode('utf-8', errors='replace')
        for line in logs.split('\n'):
            for keyword in CRASH_KEYWORDS:
                if keyword.lower() in line.lower():
                    return (line.strip(), keyword)
    except:
        pass
    return None

def scan_logs_for_packet_loss(container, server_name, lines=500):
    """Scan for high packet loss in FPS/stats lines and map to player names"""
    try:
        # Read from log file for better player name mapping
        logs = read_log_file(server_name, 'console', lines)
        if not logs:
            # Fallback to docker logs
            logs = container.logs(tail=200).decode('utf-8', errors='replace')
        
        high_loss_players = []
        
        # Build connection ID to player name mapping from logs
        conn_to_player = {}
        for line in logs.split('\n'):
            # Match: "Player joined, id: 131, ... name: Heck Let Loose"
            admin_match = re.search(r'Player joined, id: (\d+),.*name: ([^,]+)', line)
            if admin_match:
                pid, name = admin_match.groups()
                conn_to_player[pid] = name.strip()
            
            # Match: "### Updating player: PlayerId=131, Name=Heck Let Loose"
            update_match = re.search(r'PlayerId=(\d+), Name=([^,]+)', line)
            if update_match:
                pid, name = update_match.groups()
                conn_to_player[pid] = name.strip()
            
            # Match BattlEye: "BattlEye Server: 'Player #283 Crowbar™ (IP) connected'"
            be_match = re.search(r"BattlEye Server: 'Player #(\d+) ([^(]+) \(", line)
            if be_match:
                player_num, name = be_match.groups()
                conn_to_player[player_num] = name.strip()
            
            # Match: "Player connected: connectionID=113" followed by name info
            conn_match = re.search(r'Player connected: connectionID=(\d+)', line)
            if conn_match:
                conn_id = conn_match.group(1)
                # Look for name in nearby context
        
        # Find packet loss entries (from most recent FPS line)
        fps_lines = [l for l in logs.split('\n') if 'PktLoss:' in l]
        if fps_lines:
            latest_fps = fps_lines[-1]  # Most recent stats
            matches = re.findall(r'\[C(\d+)\], PktLoss: (\d+)/100', latest_fps)
            for conn_id, loss in matches:
                loss = int(loss)
                if loss >= PACKET_LOSS_THRESHOLD:
                    # Try to find player name
                    player_name = conn_to_player.get(conn_id, f"Connection {conn_id}")
                    high_loss_players.append((conn_id, loss, player_name))
        
        return high_loss_players
    except Exception as e:
        logger.error(f"Error scanning packet loss: {e}")
    return []

def scan_logs_for_disconnects(container, lines=100):
    """Scan for recent player disconnects"""
    try:
        logs = container.logs(tail=lines).decode('utf-8', errors='replace')
        disconnects = []
        
        for line in logs.split('\n'):
            # Look for "Player disconnected: connectionID=X"
            if 'Player disconnected:' in line:
                # Extract timestamp if present (format: HH:MM:SS.mmm)
                time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                if time_match:
                    disconnects.append(time_match.group(1))
        
        return disconnects
    except:
        pass
    return []

def alert_crash(server_name, crash_line, keyword):
    if len(crash_line) > 500:
        crash_line = crash_line[:500] + "..."
    send_webhook(
        title=f"CRASH: {server_name.upper()}",
        description="Server crashed!",
        color=0xFF0000,
        fields=[
            {"name": "Type", "value": f"`{keyword}`", "inline": True},
            {"name": "Log", "value": f"```{crash_line}```", "inline": False},
        ],
        server_name=server_name
    )

def alert_server_down(server_name):
    send_webhook(
        title=f"RESTART: {server_name.upper()}",
        description="Server restarting (normal game end or manual restart)",
        color=0x3498DB,
        server_name=server_name
    )

def alert_server_up(server_name, was_crash=False):
    title = f"RECOVERED: {server_name.upper()}" if was_crash else f"SERVER UP: {server_name.upper()}"
    desc = "Recovered from crash!" if was_crash else "Server is back online!"
    send_webhook(title=title, description=desc, color=0x00FF00, server_name=server_name)

def alert_packet_loss(server_name, high_loss_players):
    players_str = "\n".join([f"• **{name}**: {loss}%" for cid, loss, name in high_loss_players[:10]])
    if len(high_loss_players) > 10:
        players_str += f"\n+{len(high_loss_players)-10} more..."
    send_webhook(
        title=f"⚠️ HIGH PACKET LOSS: {server_name.upper()}",
        description=f"Players experiencing >{PACKET_LOSS_THRESHOLD}% packet loss",
        color=0xFFA500,  # Orange
        fields=[
            {"name": f"Affected Players ({len(high_loss_players)})", "value": players_str or "Unknown", "inline": False},
        ],
        server_name=server_name
    )

def alert_mass_disconnect(server_name, count):
    send_webhook(
        title=f"MASS DISCONNECT: {server_name.upper()}",
        description=f"{count} players disconnected rapidly - possible server issue!",
        color=0xFF4500,  # Red-Orange
        fields=[
            {"name": "Players Lost", "value": str(count), "inline": True},
            {"name": "Threshold", "value": f"{MASS_DISCONNECT_COUNT} in {MASS_DISCONNECT_WINDOW}s", "inline": True},
        ],
        server_name=server_name
    )

def monitor_servers():
    client = docker.from_env()
    logger.info(f"Starting crash monitor for: {', '.join(SERVERS.keys())}")
    
    send_webhook("Crash Monitor Started", "Watching for crashes, restarts, packet loss, and mass disconnects", 0x2ECC71,
        [{"name": "Servers", "value": ", ".join(SERVERS.keys()), "inline": False},
         {"name": "Packet Loss Threshold", "value": f">{PACKET_LOSS_THRESHOLD}%", "inline": True},
         {"name": "Mass Disconnect", "value": f"{MASS_DISCONNECT_COUNT} players in {MASS_DISCONNECT_WINDOW}s", "inline": True}])
    
    states = {name: {
        'status': None, 
        'was_crash': False, 
        'last_crash': None,
        'last_pktloss_alert': None,
        'last_disconnect_alert': None,
        'disconnect_times': deque(maxlen=50),  # Track recent disconnect timestamps
        'last_disconnect_count': 0,
    } for name in SERVERS}
    
    while True:
        try:
            for name, cid in SERVERS.items():
                state = states[name]
                container = None
                
                try:
                    container = client.containers.get(cid)
                    status = container.status
                    prev = state['status']
                    now = datetime.now()
                    
                    # === CRASH/RESTART DETECTION ===
                    if prev == "running" and status != "running":
                        crash = scan_logs_for_crashes(container)
                        if crash and state['last_crash'] != crash[0]:
                            alert_crash(name, crash[0], crash[1])
                            state['was_crash'] = True
                            state['last_crash'] = crash[0]
                        else:
                            alert_server_down(name)
                            state['was_crash'] = False
                    
                    elif prev and prev != "running" and status == "running":
                        alert_server_up(name, was_crash=state['was_crash'])
                        state['was_crash'] = False
                        state['last_crash'] = None
                    
                    # === PACKET LOSS DETECTION (only when running) ===
                    elif status == "running":
                        # Check crash keywords while running
                        crash = scan_logs_for_crashes(container, lines=50)
                        if crash:
                            can_alert = True
                            if state.get('last_crash_alert'):
                                elapsed = (now - state['last_crash_alert']).total_seconds()
                                can_alert = elapsed > ALERT_COOLDOWN
                            if can_alert and state['last_crash'] != crash[0]:
                                alert_crash(name, crash[0], crash[1])
                                state['last_crash'] = crash[0]
                                state['last_crash_alert'] = now
                                state['was_crash'] = True
                        
                        # Check packet loss (with cooldown)
                        can_pktloss_alert = True
                        if state['last_pktloss_alert']:
                            elapsed = (now - state['last_pktloss_alert']).total_seconds()
                            can_pktloss_alert = elapsed > ALERT_COOLDOWN
                        
                        if can_pktloss_alert:
                            high_loss = scan_logs_for_packet_loss(container, name)
                            if high_loss:
                                alert_packet_loss(name, high_loss)
                                state['last_pktloss_alert'] = now
                        
                        # Check mass disconnects
                        disconnects = scan_logs_for_disconnects(container)
                        current_count = len(disconnects)
                        
                        # If disconnect count jumped significantly
                        if current_count > state['last_disconnect_count']:
                            new_disconnects = current_count - state['last_disconnect_count']
                            
                            # Check if we should alert (cooldown)
                            can_dc_alert = True
                            if state['last_disconnect_alert']:
                                elapsed = (now - state['last_disconnect_alert']).total_seconds()
                                can_dc_alert = elapsed > ALERT_COOLDOWN
                            
                            if can_dc_alert and new_disconnects >= MASS_DISCONNECT_COUNT:
                                alert_mass_disconnect(name, new_disconnects)
                                state['last_disconnect_alert'] = now
                        
                        state['last_disconnect_count'] = current_count
                    
                    state['status'] = status
                    
                except docker.errors.NotFound:
                    if state['status'] != 'missing':
                        logger.warning(f"{name}: Container not found!")
                    state['status'] = 'missing'
                finally:
                    if container:
                        del container
            
            gc.collect()
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            send_webhook("Crash Monitor Stopped", "Shut down", 0x95A5A6)
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor_servers()
