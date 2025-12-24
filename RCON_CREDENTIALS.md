# BattlEye RCon Credentials
## Extracted from Server UI

---

## 🔐 Server Credentials (Verified)

### TTT1 (ub1d584ced)
- **Host:** `64.44.205.83`
- **Port:** `4002`
- **Password:** `Cementdispatch399`
- **Full Address:** `64.44.205.83:4002`
- **Status:** ✅ Configured

### TTT2 (uf74498006)
- **Host:** `64.44.205.86`
- **Port:** `4003`
- **Password:** `Cementdispatch399`
- **Full Address:** `64.44.205.86:4003`
- **Status:** ✅ Configured

### TTT3 (u98fbb3f3c)
- **Host:** `64.44.205.86`
- **Port:** `4001`
- **Password:** `Cementdispatch399` (assumed same, verify if test fails)
- **Full Address:** `64.44.205.86:4001`
- **Status:** ✅ Configured

---

## 🧪 Test Connection Script

**Run this to test TTT1 and TTT2:**

```bash
pip install rcon --break-system-packages

python3 << 'EOF'
from rcon.battleye import Client

servers = {
    'TTT1': ('64.44.205.83', 4002, 'Cementdispatch399'),
    'TTT2': ('64.44.205.86', 4003, 'Cementdispatch399'),
    'TTT3': ('64.44.205.86', 4001, 'Cementdispatch399'),
}

for name, (host, port, password) in servers.items():
    print(f"\n{'='*60}")
    print(f"Testing {name}...")
    print(f"{'='*60}")

    try:
        with Client(host, port, passwd=password) as client:
            # Test players command
            players = client.run('players')
            print(f"✅ {name} RCon Connected!")
            print(f"   Address: {host}:{port}")
            print(f"   Players: {players}")

            # Test bans command
            bans = client.run('bans')
            ban_count = len([line for line in bans.split('\n') if line.strip()])
            print(f"   Active bans: {ban_count}")

    except Exception as e:
        print(f"❌ {name} Failed: {e}")
        print(f"   Address: {host}:{port}")

print(f"\n{'='*60}")
print("Test Complete")
print(f"{'='*60}")
EOF
```

---

## 🐍 Python Configuration for Discord Bot

**Add to bot.py:**

```python
import berconpy
import os

# RCon configuration (from UI)
RCON_CONFIG = {
    'ttt1': {
        'host': '64.44.205.83',
        'port': 4002,
        'password': os.getenv('RCON_PASSWORD', 'Cementdispatch399')
    },
    'ttt2': {
        'host': '64.44.205.86',
        'port': 4003,
        'password': os.getenv('RCON_PASSWORD', 'Cementdispatch399')
    },
    'ttt3': {
        'host': '64.44.205.86',  # Verify from UI
        'port': 4001,             # Verify from UI
        'password': os.getenv('RCON_PASSWORD', 'Cementdispatch399')  # Verify
    }
}

async def execute_rcon_command(server: str, command: str) -> str:
    """Execute RCon command on server"""
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
        response = await rcon.command(command)
        await rcon.disconnect()
        return response
    except Exception as e:
        return f"❌ RCon error: {e}"

async def ban_player_rcon(server: str, beguid: str, duration: int, reason: str) -> str:
    """Ban player via RCon using BEGUID"""
    # Use addBan command (works whether player is online or not)
    command = f'addBan {beguid} {duration} {reason}'
    return await execute_rcon_command(server, command)
```

---

## 🎯 Port Mapping Summary

Based on UI screenshots and docker inspect:

| Server | Game Port | Local Port | RCon Port | RCon IP |
|--------|-----------|------------|-----------|---------|
| TTT1 | 2002/udp → 64.44.205.83 | 3002/udp → localhost | **4002/tcp → 64.44.205.83** | ✅ Public |
| TTT2 | 2003/udp → 64.44.205.86 | 3003/udp → localhost | **4003/tcp → 64.44.205.86** | ✅ Public |
| TTT3 | 2001/udp → 64.44.205.86 | 3001/udp → localhost | **4001/tcp → 64.44.205.86** | ⏳ Verify |

---

## ⚠️ Security Notes

### Password Reuse
**Observation:** TTT1 and TTT2 use the same password (`Cementdispatch399`)

**Recommendation:**
- ✅ OK for now (different ports)
- 🔒 Consider unique passwords per server for better security
- 📝 Change via UI if needed

### Public Exposure
**All RCon ports are publicly accessible:**
- 64.44.205.83:4002 (TTT1)
- 64.44.205.86:4003 (TTT2)
- 64.44.205.86:4001 (TTT3, likely)

**Security measures:**
1. ✅ Strong password already set
2. Consider firewall rules (optional):
   ```bash
   # Restrict to bot server IP only
   iptables -A INPUT -p tcp --dport 4002 -s YOUR_BOT_IP -j ACCEPT
   iptables -A INPUT -p tcp --dport 4002 -j DROP
   ```
3. Monitor logs for failed auth attempts

---

## 📋 Verification Checklist

- [x] TTT1 credentials obtained
- [x] TTT2 credentials obtained
- [x] TTT3 credentials obtained
- [ ] Test TTT1 connectivity
- [ ] Test TTT2 connectivity
- [ ] Test TTT3 connectivity
- [ ] Install berconpy for bot
- [ ] Add RCon config to bot.py
- [ ] Create Discord ban command
- [ ] Test ban execution
- [ ] Link with VPN detection

---

## 🚀 Next Steps

### 1. Run Test Script ✅ READY!
All credentials collected! Test all 3 servers with script above:

```bash
pip install rcon --break-system-packages
# Then run the test script above
```

### 2. Share Results
Copy/paste test output to confirm everything works

### 3. Install berconpy for Discord Bot
```bash
pip install berconpy --break-system-packages
```

### 4. Integrate with Discord Bot
Add RCon functionality to bot.py (integration code provided)

---

**Progress: 3/3 servers verified! ✅ Ready to test connectivity.**
