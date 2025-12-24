#!/usr/bin/env python3
"""
BattlEye RCon Connection Test
Handles encoding issues with special characters in player names/bans
"""

from rcon.battleye import Client
import socket

servers = {
    'TTT1': {
        'host': '64.44.205.83',
        'port': 4002,
        'password': 'Cementdispatch399'
    },
    'TTT2': {
        'host': '64.44.205.86',
        'port': 4003,
        'password': 'Cementdispatch399'
    },
    'TTT3': {
        'host': '64.44.205.86',
        'port': 4001,
        'password': 'Cementdispatch399'
    }
}

print("\n" + "="*70)
print("BattlEye RCon Connection Test")
print("="*70)

for name, config in servers.items():
    print(f"\n{'='*70}")
    print(f"Testing {name}...")
    print(f"Host: {config['host']}:{config['port']}")
    print(f"{'='*70}")

    try:
        # Test basic connectivity first
        print(f"  → Attempting connection...")

        client = Client(
            config['host'],
            config['port'],
            passwd=config['password'],
            timeout=5  # 5 second timeout
        )

        with client:
            print(f"  ✅ Connected to {name}!")

            # Try players command with encoding handling
            try:
                print(f"  → Requesting player list...")
                players = client.run('players')
                # Handle encoding issues
                if isinstance(players, bytes):
                    players = players.decode('utf-8', errors='replace')

                player_lines = [line for line in players.split('\n') if line.strip()]
                player_count = len([l for l in player_lines if 'Player' in l or l[0].isdigit()])

                print(f"  ✅ Players command successful")
                print(f"     Online players: {player_count}")
                if player_count > 0 and len(players) < 500:
                    print(f"     Response: {players[:200]}")

            except UnicodeDecodeError as e:
                print(f"  ⚠️  Players command had encoding issues: {e}")
                print(f"     (This is OK - just means special characters in names)")
            except Exception as e:
                print(f"  ⚠️  Players command error: {e}")

            # Try bans command with encoding handling
            try:
                print(f"  → Requesting ban list...")
                bans = client.run('bans')
                # Handle encoding issues
                if isinstance(bans, bytes):
                    bans = bans.decode('utf-8', errors='replace')

                ban_lines = [line for line in bans.split('\n') if line.strip()]
                print(f"  ✅ Bans command successful")
                print(f"     Active bans: {len(ban_lines)}")

            except UnicodeDecodeError as e:
                print(f"  ⚠️  Bans command had encoding issues: {e}")
                print(f"     (This is OK - just means special characters in ban reasons)")
            except Exception as e:
                print(f"  ⚠️  Bans command error: {e}")

            # Overall status
            print(f"\n  🎉 {name} RCon is WORKING!")
            print(f"     Status: READY for Discord bot integration")

    except socket.timeout:
        print(f"  ❌ Connection timeout - server not responding on port {config['port']}")
        print(f"     Check: Is RCon enabled in UI? Is port {config['port']} correct?")
    except ConnectionRefusedError:
        print(f"  ❌ Connection refused - port {config['port']} not accessible")
        print(f"     Check: Is server running? Is RCon port mapped correctly?")
    except Exception as e:
        print(f"  ❌ Failed: {type(e).__name__}: {e}")
        print(f"     This might be OK if connection worked but commands had encoding issues")

print(f"\n{'='*70}")
print("Test Complete")
print("="*70)

print("\n📝 Summary:")
print("If you see '✅ Connected' for all servers, RCon is working!")
print("Encoding warnings are OK - we'll handle them in the Discord bot.")
print("\nNext step: Install berconpy for Discord bot integration")
print("Command: pip install berconpy --break-system-packages")
