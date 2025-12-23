"""
Log Parser Integration for Player Database
Monitors BattleEye logs and automatically updates player database
"""

import re
import asyncio
from datetime import datetime
from typing import Optional, Dict
import requests
from collections import deque
import time

from player_database import PlayerDatabase

class PlayerLogMonitor:
    """
    Monitors Arma Reforger BattleEye logs and automatically updates player database
    Integrates with existing log monitoring systems
    """
    
    def __init__(self, db_path: str = "players.db", api_key: str = None):
        self.db = PlayerDatabase(db_path)
        self.api_key = api_key
        self.geo_cache = {}  # Cache IP lookups to reduce API calls
        self.cache_ttl = 3600  # 1 hour cache for IP lookups
        
        # Player connection regex patterns
        self.connect_pattern = re.compile(
            r"Player (?:id=(\d+) )?(.+?) \((\d+)\) has been authenticated\."
        )
        self.disconnect_pattern = re.compile(
            r"Player (?:id=\d+ )?(.+?) \((\d+)\) disconnected"
        )
        self.guid_pattern = re.compile(r"\((\d+)\)")
        self.beguid_pattern = re.compile(r"BE GUID: (\w+)")
        self.ip_pattern = re.compile(
            r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)"
        )
        
        print(f"✅ Player log monitor initialized with database: {db_path}")
    
    def parse_player_connection(self, log_line: str, server_name: str = None) -> Optional[Dict]:
        """
        Parse a player connection from log line
        Returns player data dictionary if connection found
        """
        # Match authenticated player line
        auth_match = self.connect_pattern.search(log_line)
        if not auth_match:
            return None
        
        player_id = auth_match.group(1)
        player_name = auth_match.group(2)
        guid = auth_match.group(3)
        
        # Extract IP address
        ip_match = self.ip_pattern.search(log_line)
        ip_address = ip_match.group(1) if ip_match else None
        
        # Extract BEGUID if present
        beguid_match = self.beguid_pattern.search(log_line)
        beguid = beguid_match.group(1) if beguid_match else None
        
        return {
            'player_id': player_id,
            'name': player_name,
            'guid': guid,
            'ip': ip_address,
            'beguid': beguid,
            'server_name': server_name,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_ip_geolocation(self, ip: str) -> Optional[Dict]:
        """
        Get geolocation data for an IP address with caching
        Returns cached data if available and not expired
        """
        if not self.api_key:
            return None
        
        # Check cache
        if ip in self.geo_cache:
            cached_data, cached_time = self.geo_cache[ip]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data
        
        # Fetch from API
        try:
            url = f"https://api.ipgeolocation.io/ipgeo"
            params = {
                'apiKey': self.api_key,
                'ip': ip,
                'fields': 'country_name,isp,organization',
                'include': 'security'
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.geo_cache[ip] = (data, time.time())
                return data
            else:
                print(f"⚠️ IP geolocation API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error fetching geolocation for {ip}: {e}")
            return None
    
    def process_log_line(self, log_line: str, server_name: str = None) -> Optional[list]:
        """
        Process a single log line and update database if player event detected
        Returns list of alerts if any generated
        """
        player_data = self.parse_player_connection(log_line, server_name)
        
        if not player_data:
            return None
        
        # Get geolocation data if IP available
        geo_data = None
        if player_data['ip']:
            geo_data = self.get_ip_geolocation(player_data['ip'])
        
        # Update database and get alerts
        alerts = self.db.update_player(
            guid=player_data['guid'],
            name=player_data['name'],
            ip=player_data['ip'],
            beguid=player_data['beguid'],
            server_name=player_data['server_name'],
            geo_data=geo_data
        )
        
        return alerts if alerts else None
    
    async def monitor_log_file(self, log_file_path: str, server_name: str, 
                               alert_callback=None):
        """
        Continuously monitor a log file for new entries
        Calls alert_callback(alerts) when changes detected
        """
        print(f"📡 Starting log monitor for {server_name}: {log_file_path}")
        
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Go to end of file
                f.seek(0, 2)
                
                while True:
                    line = f.readline()
                    
                    if line:
                        # Process the line
                        alerts = self.process_log_line(line, server_name)
                        
                        if alerts and alert_callback:
                            await alert_callback(alerts, server_name)
                    else:
                        # No new lines, wait a bit
                        await asyncio.sleep(1)
                        
        except FileNotFoundError:
            print(f"❌ Log file not found: {log_file_path}")
        except Exception as e:
            print(f"❌ Error monitoring log: {e}")
    
    def batch_process_log_file(self, log_file_path: str, server_name: str,
                               max_lines: int = 10000) -> Dict:
        """
        Process existing log file in batch mode (for historical data import)
        Returns statistics about processed players
        """
        print(f"📥 Batch processing log file: {log_file_path}")
        
        stats = {
            'lines_processed': 0,
            'players_found': 0,
            'alerts_generated': 0,
            'errors': 0
        }
        
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read from end if file is large
                lines = deque(f, maxlen=max_lines)
                
                for line in lines:
                    stats['lines_processed'] += 1
                    
                    try:
                        alerts = self.process_log_line(line, server_name)
                        
                        if alerts:
                            stats['players_found'] += 1
                            stats['alerts_generated'] += len(alerts)
                            
                    except Exception as e:
                        stats['errors'] += 1
                        print(f"⚠️ Error processing line: {e}")
                        continue
                
                print(f"✅ Batch processing complete: {stats}")
                return stats
                
        except FileNotFoundError:
            print(f"❌ Log file not found: {log_file_path}")
            stats['errors'] += 1
            return stats
        except Exception as e:
            print(f"❌ Error in batch processing: {e}")
            stats['errors'] += 1
            return stats
    
    def get_active_sessions(self) -> list:
        """
        Get list of currently active player sessions
        (Players who connected but haven't disconnected yet)
        """
        # This would track active sessions in memory
        # For now, return recent connections from database
        return []


# Example integration with existing Discord bot
class DatabaseAlertHandler:
    """
    Handles database alerts and sends them to Discord
    Integrates with your existing Discord webhook system
    """
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
    
    async def send_alert(self, alerts: list, server_name: str = None):
        """Send alerts to Discord webhook"""
        if not self.webhook_url or not alerts:
            return
        
        try:
            # Format alert message
            alert_text = "\n".join(f"• {alert}" for alert in alerts)
            
            message = {
                "embeds": [{
                    "title": f"🚨 Player Database Alert - {server_name or 'Server'}",
                    "description": alert_text,
                    "color": 0xFF6B35,  # Orange
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            
            response = requests.post(self.webhook_url, json=message, timeout=5)
            
            if response.status_code not in [200, 204]:
                print(f"⚠️ Webhook error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error sending alert: {e}")
    
    def format_player_history(self, history: Dict, player_name: str) -> str:
        """Format player history for Discord embed"""
        lines = [f"**Player History: {player_name}**\n"]
        
        # Names used
        if history['names']:
            lines.append("**Names:**")
            for name_data in history['names'][:5]:  # Top 5
                lines.append(f"• {name_data['name']} (used {name_data['use_count']}x)")
            lines.append("")
        
        # IPs used
        if history['ips']:
            lines.append("**IP Addresses:**")
            for ip_data in history['ips'][:5]:  # Top 5
                vpn = "🔒 VPN" if ip_data['is_vpn'] else ""
                proxy = "🌐 Proxy" if ip_data['is_proxy'] else ""
                flags = f" {vpn}{proxy}" if vpn or proxy else ""
                lines.append(f"• {ip_data['ip_address']} ({ip_data['country']}){flags}")
            lines.append("")
        
        # Recent alerts
        if history['alerts']:
            lines.append("**Recent Alerts:**")
            for alert in history['alerts'][:5]:
                lines.append(f"• {alert['alert_message']}")
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Test the monitor
    monitor = PlayerLogMonitor(db_path="test_players.db")
    
    # Test log line parsing
    test_log = "Player id=1 TestPlayer (12345678) has been authenticated. IP: 192.168.1.1:2302 BE GUID: BE12345678"
    
    print("\n🧪 Testing log parsing...")
    player_data = monitor.parse_player_connection(test_log, "TTT1")
    print(f"Parsed data: {player_data}")
    
    alerts = monitor.process_log_line(test_log, "TTT1")
    print(f"Alerts generated: {alerts}")
    
    print("\n✅ Log monitor working!")
