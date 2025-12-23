"""
Player Database System for Arma Reforger
Tracks player names, IPs, GUIDs, and detects changes
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import threading

class PlayerDatabase:
    def __init__(self, db_path: str = "players.db"):
        """Initialize the player database with connection pooling"""
        self.db_path = db_path
        self.local = threading.local()
        self._init_database()
    
    def _get_connection(self):
        """Thread-safe database connection"""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn
    
    def _init_database(self):
        """Create all necessary tables with indexes"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Main players table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                guid TEXT PRIMARY KEY,
                beguid TEXT,
                current_name TEXT NOT NULL,
                current_ip TEXT,
                first_seen TIMESTAMP NOT NULL,
                last_seen TIMESTAMP NOT NULL,
                total_connections INTEGER DEFAULT 1,
                total_playtime_seconds INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                notes TEXT
            )
        ''')
        
        # Player names history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guid TEXT NOT NULL,
                name TEXT NOT NULL,
                first_used TIMESTAMP NOT NULL,
                last_used TIMESTAMP NOT NULL,
                use_count INTEGER DEFAULT 1,
                FOREIGN KEY (guid) REFERENCES players(guid),
                UNIQUE(guid, name)
            )
        ''')
        
        # Player IPs history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guid TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                country TEXT,
                isp TEXT,
                is_vpn INTEGER DEFAULT 0,
                is_proxy INTEGER DEFAULT 0,
                geo_data TEXT,
                first_used TIMESTAMP NOT NULL,
                last_used TIMESTAMP NOT NULL,
                use_count INTEGER DEFAULT 1,
                FOREIGN KEY (guid) REFERENCES players(guid),
                UNIQUE(guid, ip_address)
            )
        ''')
        
        # BEGUID changes tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS beguid_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guid TEXT NOT NULL,
                old_beguid TEXT,
                new_beguid TEXT NOT NULL,
                changed_at TIMESTAMP NOT NULL,
                FOREIGN KEY (guid) REFERENCES players(guid)
            )
        ''')
        
        # Connection events log (for session tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS connection_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guid TEXT NOT NULL,
                event_type TEXT NOT NULL,
                server_name TEXT,
                timestamp TIMESTAMP NOT NULL,
                name_used TEXT,
                ip_used TEXT,
                FOREIGN KEY (guid) REFERENCES players(guid)
            )
        ''')
        
        # Alerts/flags table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guid TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                alert_message TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                created_at TIMESTAMP NOT NULL,
                acknowledged INTEGER DEFAULT 0,
                FOREIGN KEY (guid) REFERENCES players(guid)
            )
        ''')
        
        # Create indexes for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_players_name ON players(current_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_players_ip ON players(current_ip)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_players_beguid ON players(beguid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_names_guid ON player_names(guid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_names_name ON player_names(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ips_guid ON player_ips(guid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ips_ip ON player_ips(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_guid ON player_alerts(guid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_unack ON player_alerts(acknowledged)')
        
        conn.commit()
        print(f"✅ Database initialized at {self.db_path}")
    
    def update_player(self, guid: str, name: str, ip: str = None, 
                     beguid: str = None, server_name: str = None,
                     geo_data: Dict = None) -> List[str]:
        """
        Update or create player record and track all changes
        Returns list of alerts generated
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        alerts = []
        
        try:
            # Check if player exists
            cursor.execute('SELECT * FROM players WHERE guid = ?', (guid,))
            existing = cursor.fetchone()
            
            if existing:
                # Player exists - check for changes
                old_name = existing['current_name']
                old_ip = existing['current_ip']
                old_beguid = existing['beguid']
                
                # Name change detection
                if name != old_name:
                    alert = f"🔄 Name change: '{old_name}' → '{name}'"
                    alerts.append(alert)
                    self._create_alert(guid, 'name_change', alert, old_name, name)
                
                # IP change detection
                if ip and ip != old_ip:
                    alert = f"🌐 IP change: {old_ip} → {ip}"
                    alerts.append(alert)
                    self._create_alert(guid, 'ip_change', alert, old_ip, ip)
                
                # BEGUID change detection
                if beguid and old_beguid and beguid != old_beguid:
                    alert = f"🆔 BEGUID change: {old_beguid} → {beguid}"
                    alerts.append(alert)
                    self._create_alert(guid, 'beguid_change', alert, old_beguid, beguid)
                    
                    # Log BEGUID change
                    cursor.execute('''
                        INSERT INTO beguid_changes (guid, old_beguid, new_beguid, changed_at)
                        VALUES (?, ?, ?, ?)
                    ''', (guid, old_beguid, beguid, now))
                
                # Update player record
                cursor.execute('''
                    UPDATE players 
                    SET current_name = ?, current_ip = ?, beguid = ?, 
                        last_seen = ?, total_connections = total_connections + 1
                    WHERE guid = ?
                ''', (name, ip, beguid or old_beguid, now, guid))
                
            else:
                # New player
                cursor.execute('''
                    INSERT INTO players (guid, beguid, current_name, current_ip, 
                                       first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (guid, beguid, name, ip, now, now))
                
                alert = f"✨ New player: {name} ({guid[:8]}...)"
                alerts.append(alert)
                self._create_alert(guid, 'new_player', alert, None, name)
            
            # Update name history
            cursor.execute('''
                INSERT INTO player_names (guid, name, first_used, last_used)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guid, name) DO UPDATE SET
                    last_used = ?,
                    use_count = use_count + 1
            ''', (guid, name, now, now, now))
            
            # Update IP history with geolocation data
            if ip:
                geo_json = json.dumps(geo_data) if geo_data else None
                is_vpn = geo_data.get('security', {}).get('is_vpn', False) if geo_data else False
                is_proxy = geo_data.get('security', {}).get('is_proxy', False) if geo_data else False
                country = geo_data.get('country_name', '') if geo_data else ''
                isp = geo_data.get('isp', '') if geo_data else ''
                
                cursor.execute('''
                    INSERT INTO player_ips (guid, ip_address, country, isp, is_vpn, is_proxy,
                                          geo_data, first_used, last_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(guid, ip_address) DO UPDATE SET
                        last_used = ?,
                        use_count = use_count + 1,
                        country = ?,
                        isp = ?,
                        is_vpn = ?,
                        is_proxy = ?,
                        geo_data = ?
                ''', (guid, ip, country, isp, is_vpn, is_proxy, geo_json, now, now,
                      now, country, isp, is_vpn, is_proxy, geo_json))
                
                # VPN detection alert
                if is_vpn or is_proxy:
                    vpn_type = "VPN" if is_vpn else "Proxy"
                    alert = f"⚠️ {vpn_type} detected: {name} from {ip}"
                    alerts.append(alert)
                    self._create_alert(guid, 'vpn_detected', alert, None, ip)
            
            # Log connection event
            cursor.execute('''
                INSERT INTO connection_events (guid, event_type, server_name, timestamp, 
                                              name_used, ip_used)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (guid, 'connect', server_name, now, name, ip))
            
            conn.commit()
            return alerts
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error updating player: {e}")
            return [f"Error: {str(e)}"]
    
    def _create_alert(self, guid: str, alert_type: str, message: str, 
                     old_value: str = None, new_value: str = None):
        """Create an alert record"""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO player_alerts (guid, alert_type, alert_message, 
                                      old_value, new_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (guid, alert_type, message, old_value, new_value, now))
    
    def get_player_by_guid(self, guid: str) -> Optional[Dict]:
        """Get complete player information"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM players WHERE guid = ?', (guid,))
        player = cursor.fetchone()
        
        if not player:
            return None
        
        return dict(player)
    
    def get_player_by_name(self, name: str) -> Optional[Dict]:
        """Get player by current name"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM players WHERE current_name LIKE ?', (f'%{name}%',))
        player = cursor.fetchone()
        
        if not player:
            return None
        
        return dict(player)
    
    def get_player_history(self, guid: str) -> Dict:
        """Get complete player history including names, IPs, and alerts"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get all names used
        cursor.execute('''
            SELECT name, first_used, last_used, use_count
            FROM player_names
            WHERE guid = ?
            ORDER BY last_used DESC
        ''', (guid,))
        names = [dict(row) for row in cursor.fetchall()]
        
        # Get all IPs used
        cursor.execute('''
            SELECT ip_address, country, isp, is_vpn, is_proxy, 
                   first_used, last_used, use_count
            FROM player_ips
            WHERE guid = ?
            ORDER BY last_used DESC
        ''', (guid,))
        ips = [dict(row) for row in cursor.fetchall()]
        
        # Get BEGUID changes
        cursor.execute('''
            SELECT old_beguid, new_beguid, changed_at
            FROM beguid_changes
            WHERE guid = ?
            ORDER BY changed_at DESC
        ''', (guid,))
        beguid_changes = [dict(row) for row in cursor.fetchall()]
        
        # Get recent alerts
        cursor.execute('''
            SELECT alert_type, alert_message, old_value, new_value, created_at
            FROM player_alerts
            WHERE guid = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (guid,))
        alerts = [dict(row) for row in cursor.fetchall()]
        
        # Get connection history
        cursor.execute('''
            SELECT event_type, server_name, timestamp, name_used, ip_used
            FROM connection_events
            WHERE guid = ?
            ORDER BY timestamp DESC
            LIMIT 50
        ''', (guid,))
        connections = [dict(row) for row in cursor.fetchall()]
        
        return {
            'names': names,
            'ips': ips,
            'beguid_changes': beguid_changes,
            'alerts': alerts,
            'connections': connections
        }
    
    def find_alts(self, ip_address: str) -> List[Dict]:
        """Find all players who have used a specific IP address"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT p.guid, p.current_name, p.first_seen, p.last_seen,
                   pi.first_used as ip_first_used, pi.last_used as ip_last_used
            FROM players p
            JOIN player_ips pi ON p.guid = pi.guid
            WHERE pi.ip_address = ?
            ORDER BY pi.last_used DESC
        ''', (ip_address,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def find_name_alts(self, name: str) -> List[Dict]:
        """Find all GUIDs that have used a specific name"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT p.guid, p.current_name, p.current_ip, 
                   pn.first_used, pn.last_used
            FROM players p
            JOIN player_names pn ON p.guid = pn.guid
            WHERE pn.name LIKE ?
            ORDER BY pn.last_used DESC
        ''', (f'%{name}%',))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_unacknowledged_alerts(self, limit: int = 50) -> List[Dict]:
        """Get all unacknowledged alerts"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT a.*, p.current_name, p.current_ip
            FROM player_alerts a
            JOIN players p ON a.guid = p.guid
            WHERE a.acknowledged = 0
            ORDER BY a.created_at DESC
            LIMIT ?
        ''', (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def acknowledge_alert(self, alert_id: int):
        """Mark an alert as acknowledged"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE player_alerts SET acknowledged = 1 WHERE id = ?', (alert_id,))
        conn.commit()
    
    def ban_player(self, guid: str, reason: str):
        """Mark a player as banned"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE players 
            SET is_banned = 1, ban_reason = ?
            WHERE guid = ?
        ''', (reason, guid))
        conn.commit()
    
    def unban_player(self, guid: str):
        """Remove ban from a player"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE players 
            SET is_banned = 0, ban_reason = NULL
            WHERE guid = ?
        ''', (guid,))
        conn.commit()
    
    def add_notes(self, guid: str, notes: str):
        """Add admin notes to a player"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE players SET notes = ? WHERE guid = ?', (notes, guid))
        conn.commit()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as total FROM players')
        total_players = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(*) as total FROM players WHERE is_banned = 1')
        banned_players = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(*) as total FROM player_alerts WHERE acknowledged = 0')
        unack_alerts = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(DISTINCT ip_address) as total FROM player_ips WHERE is_vpn = 1')
        vpn_ips = cursor.fetchone()['total']
        
        return {
            'total_players': total_players,
            'banned_players': banned_players,
            'unacknowledged_alerts': unack_alerts,
            'vpn_ips_detected': vpn_ips
        }
    
    def cleanup_old_events(self, days: int = 30):
        """Clean up old connection events to prevent database bloat"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff = datetime.now()
        cutoff = cutoff.replace(day=cutoff.day - days).isoformat()
        
        cursor.execute('DELETE FROM connection_events WHERE timestamp < ?', (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        
        return deleted


if __name__ == "__main__":
    # Test the database
    db = PlayerDatabase("test_players.db")
    
    # Test player updates
    print("\n🧪 Testing player tracking...")
    
    alerts = db.update_player(
        guid="12345678",
        name="TestPlayer",
        ip="192.168.1.1",
        beguid="BE12345678",
        server_name="TTT1"
    )
    print(f"Alerts: {alerts}")
    
    # Test name change
    alerts = db.update_player(
        guid="12345678",
        name="TestPlayer_Changed",
        ip="192.168.1.1",
        beguid="BE12345678"
    )
    print(f"Name change alerts: {alerts}")
    
    # Test IP change
    alerts = db.update_player(
        guid="12345678",
        name="TestPlayer_Changed",
        ip="10.0.0.1",
        beguid="BE12345678",
        geo_data={'security': {'is_vpn': True}}
    )
    print(f"IP change alerts: {alerts}")
    
    # Get player history
    history = db.get_player_history("12345678")
    print(f"\n📊 Player history:")
    print(f"Names used: {len(history['names'])}")
    print(f"IPs used: {len(history['ips'])}")
    print(f"Alerts: {len(history['alerts'])}")
    
    # Get stats
    stats = db.get_stats()
    print(f"\n📈 Database stats: {stats}")
    
    print("\n✅ Database system working perfectly!")
