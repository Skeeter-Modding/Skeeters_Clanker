#!/usr/bin/env python3
"""
Automatic Player Database Monitor
Reads your server logs and automatically populates the database
"""

import sys
import time
import os
from collections import deque

sys.path.insert(0, '/srv/armareforger/player_database')
from player_database import PlayerDatabase
from player_log_monitor import PlayerLogMonitor

# Configuration
DB_PATH = "/srv/armareforger/Skeeters_Clanker/data/players.db"
API_KEY = "aa519b371cdb46fc869e690cbba6e25c"

# Your server log paths
LOG_PATHS = {
    "TTT1": "/srv/armareforger/ub1d584ced/logs",
    "TTT2": "/srv/armareforger/uf74498006/logs", 
    "TTT3": "/srv/armareforger/u98fbb3f3c/logs",
}

def get_latest_log_file(server_name):
    """Get the most recent console.log file for a server"""
    log_path = LOG_PATHS.get(server_name)
    if not log_path or not os.path.exists(log_path):
        print(f"⚠️ Log path not found for {server_name}: {log_path}")
        return None
    
    # Get all dated directories
    dirs = [d for d in os.listdir(log_path) if os.path.isdir(os.path.join(log_path, d)) and d.startswith('20')]
    if not dirs:
        print(f"⚠️ No log directories found for {server_name}")
        return None
    
    # Get most recent
    dirs.sort(reverse=True)
    log_file = os.path.join(log_path, dirs[0], "console.log")
    
    if os.path.exists(log_file):
        return log_file
    return None

def import_all_logs(monitor, db):
    """Import all existing logs from all servers"""
    print("\n" + "="*60)
    print("📥 IMPORTING ALL EXISTING PLAYER DATA FROM LOGS")
    print("="*60 + "\n")
    
    total_players = 0
    
    for server_name in LOG_PATHS.keys():
        log_file = get_latest_log_file(server_name)
        if not log_file:
            continue
        
        print(f"\n📖 Processing {server_name}: {log_file}")
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                print(f"   Found {len(lines)} log lines")
                
                for i, line in enumerate(lines):
                    alerts = monitor.process_log_line(line, server_name)
                    if alerts:
                        total_players += 1
                        if total_players % 10 == 0:
                            print(f"   Processed {total_players} players...")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    stats = db.get_stats()
    print("\n" + "="*60)
    print(f"✅ IMPORT COMPLETE")
    print(f"   Total players in database: {stats['total_players']}")
    print(f"   VPN IPs detected: {stats['vpn_ips_detected']}")
    print("="*60 + "\n")

def monitor_logs_continuously(monitor):
    """Monitor logs in real-time"""
    print("\n📡 Starting continuous log monitoring...")
    print("   Press Ctrl+C to stop\n")
    
    # Track last position in each log file
    file_positions = {}
    
    try:
        while True:
            for server_name in LOG_PATHS.keys():
                log_file = get_latest_log_file(server_name)
                if not log_file:
                    continue
                
                # Initialize position tracking
                if log_file not in file_positions:
                    # Start at end of file
                    try:
                        with open(log_file, 'r') as f:
                            f.seek(0, 2)  # Go to end
                            file_positions[log_file] = f.tell()
                    except:
                        file_positions[log_file] = 0
                
                # Read new lines
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                        f.seek(file_positions[log_file])
                        new_lines = f.readlines()
                        file_positions[log_file] = f.tell()
                        
                        for line in new_lines:
                            alerts = monitor.process_log_line(line, server_name)
                            if alerts:
                                print(f"🚨 [{server_name}] {'; '.join(alerts)}")
                except Exception as e:
                    pass
            
            time.sleep(2)  # Check every 2 seconds
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Stopping monitor...")

if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════╗
║  Automatic Player Database Monitor                        ║
║  Triple Threat Tactical                                   ║
╚════════════════════════════════════════════════════════════╝
""")
    
    # Initialize
    print("Initializing database...")
    db = PlayerDatabase(DB_PATH)
    monitor = PlayerLogMonitor(DB_PATH, API_KEY)
    
    # Import all existing logs first
    import_all_logs(monitor, db)
    
    # Ask if user wants continuous monitoring
    print("\n" + "="*60)
    response = input("Start continuous monitoring? (y/n): ")
    
    if response.lower() == 'y':
        monitor_logs_continuously(monitor)
    else:
        print("\n✅ Initial import complete. Database populated!")
        print("   Run this script again with 'y' to enable continuous monitoring")
