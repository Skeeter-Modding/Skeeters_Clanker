# BattlEye RCon Setup - Exact Instructions for Your Servers
## Based on Diagnostic Results

---

## 📊 Current State Summary

### ✅ What's Working:
- **BattlEye is enabled** on all 3 servers
- **Ban files exist and are actively used:**
  - TTT1: 1787 bytes (active bans)
  - TTT2: 1530 bytes (active bans)
  - TTT3: Empty (no bans yet)

### ❌ What's Missing:
- **BEServer.cfg files** do NOT exist (never been configured)
- **RCon ports** not mapped in Docker containers
- **Cannot use RCon** until both are fixed

### Current Port Mappings:
| Server | Game Port | Local Port | Extra Ports | RCon Port |
|--------|-----------|------------|-------------|-----------|
| TTT1 | 2002/udp (public) | 3002/udp (local) | - | ❌ NOT MAPPED |
| TTT2 | 2003/udp (public) | 3003/udp (local) | 4003/udp, 5003/udp | ❌ NOT MAPPED |
| TTT3 | 2001/udp (public) | 3001/udp (local) | 4001/udp, 5001/udp | ❌ NOT MAPPED |

---

## 🔧 Step-by-Step Setup

### Step 1: Create BEServer.cfg Files

**Run these commands to create RCon configuration:**

```bash
# Generate strong passwords (save these!)
echo "TTT1 Password: $(openssl rand -base64 24)"
echo "TTT2 Password: $(openssl rand -base64 24)"
echo "TTT3 Password: $(openssl rand -base64 24)"
```

**Create BEServer.cfg for TTT1:**
```bash
cat > /srv/armareforger/ub1d584ced/battleye/BEServer.cfg << 'EOF'
RConPassword REPLACE_WITH_TTT1_PASSWORD
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF

# Set correct ownership
chown sub1d584ced:sub1d584ced /srv/armareforger/ub1d584ced/battleye/BEServer.cfg
chmod 644 /srv/armareforger/ub1d584ced/battleye/BEServer.cfg
```

**Create BEServer.cfg for TTT2:**
```bash
cat > /srv/armareforger/uf74498006/battleye/BEServer.cfg << 'EOF'
RConPassword REPLACE_WITH_TTT2_PASSWORD
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF

chown suf74498006:suf74498006 /srv/armareforger/uf74498006/battleye/BEServer.cfg
chmod 644 /srv/armareforger/uf74498006/battleye/BEServer.cfg
```

**Create BEServer.cfg for TTT3:**
```bash
cat > /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg << 'EOF'
RConPassword REPLACE_WITH_TTT3_PASSWORD
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF

chown su98fbb3f3c:su98fbb3f3c /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg
chmod 644 /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg
```

**Configuration Explained:**
- `RConPassword`: Unique strong password for each server
- `RConPort 2306`: Standard BattlEye RCon port (same internal port for all)
- `RestrictRCon 0`: Allow ALL commands (required for `ban`, `addBan`, etc.)
- `MaxPing 350`: Optional - auto-kick high ping players

**Verify files were created:**
```bash
ls -la /srv/armareforger/ub1d584ced/battleye/BEServer.cfg
ls -la /srv/armareforger/uf74498006/battleye/BEServer.cfg
ls -la /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg
```

---

### Step 2: Add Docker Port Mappings

**⚠️ CRITICAL DECISION POINT:**

You need to **recreate your Docker containers** with RCon port mappings. This requires:
1. Stopping the container
2. Removing it (data persists in volumes)
3. Recreating with additional `-p` flag for RCon
4. Starting it

**Before proceeding, we need to know:**

#### How were your containers created?

**Option A: Check for docker-compose.yml**
```bash
find /srv/armareforger -name "docker-compose.yml" -o -name "docker-compose.yaml"
```

**Option B: Check for startup scripts**
```bash
find /srv/armareforger -name "start*.sh" -o -name "run*.sh" | head -5
```

**Option C: View full container creation command**
```bash
# This shows the original docker run command (approximately)
docker inspect ub1d584ced --format='{{.Config.Cmd}}'
docker inspect ub1d584ced --format='{{.HostConfig.Binds}}'
docker inspect ub1d584ced --format='{{.Config.Image}}'
```

**⚠️ STOP HERE** - Run the commands above and share the output so I can provide exact recreation commands.

---

### Step 3: Restart Containers (After Port Mapping)

**Once containers are recreated with RCon ports, restart them:**

```bash
docker restart ub1d584ced
docker restart uf74498006
docker restart u98fbb3f3c
```

**Check logs for RCon initialization:**
```bash
docker logs ub1d584ced 2>&1 | grep -i "rcon" | tail -5
docker logs uf74498006 2>&1 | grep -i "rcon" | tail -5
docker logs u98fbb3f3c 2>&1 | grep -i "rcon" | tail -5
```

**Expected output:**
```
BattlEye Server: RCon initialized on port 2306
```

---

### Step 4: Test RCon Connectivity

**Create test script:**
```bash
cat > /tmp/test_rcon.py << 'EOF'
#!/usr/bin/env python3
from rcon.battleye import Client

servers = {
    'TTT1': ('127.0.0.1', 2306, 'YOUR_TTT1_PASSWORD'),
    'TTT2': ('127.0.0.1', 2307, 'YOUR_TTT2_PASSWORD'),
    'TTT3': ('127.0.0.1', 2308, 'YOUR_TTT3_PASSWORD'),
}

for name, (host, port, password) in servers.items():
    try:
        with Client(host, port, passwd=password) as client:
            response = client.run('players')
            print(f"✅ {name} RCon Connected")
            print(f"   Players: {response}")
    except Exception as e:
        print(f"❌ {name} RCon Failed: {e}")
    print()
EOF

python3 /tmp/test_rcon.py
```

---

## 🐳 Required Port Mapping Configuration

Your containers need these additional port mappings:

```bash
# TTT1 - Add this port mapping
-p 127.0.0.1:2306:2306/tcp

# TTT2 - Add this port mapping
-p 127.0.0.1:2307:2306/tcp

# TTT3 - Add this port mapping
-p 127.0.0.1:2308:2306/tcp
```

**Security Note:** Binding to `127.0.0.1` keeps RCon **local only** (secure!)

### Example Docker Run Command (Template)

**If recreating manually, your command should look like:**
```bash
docker run -d \
  --name ub1d584ced \
  -p 64.44.205.83:2002:2002/udp \
  -p 127.0.0.1:3002:3002/udp \
  -p 127.0.0.1:2306:2306/tcp \
  -v /srv/armareforger/ub1d584ced:/reforger \
  -u sub1d584ced:sub1d584ced \
  [YOUR_IMAGE_NAME]
```

---

## 🔐 Password Management

**Save your RCon passwords securely!**

Create a password file (outside the repository):
```bash
cat > /root/.rcon_passwords << 'EOF'
# BattlEye RCon Passwords
# DO NOT COMMIT TO GIT!

TTT1_RCON_PASSWORD="your_generated_password_1"
TTT2_RCON_PASSWORD="your_generated_password_2"
TTT3_RCON_PASSWORD="your_generated_password_3"
EOF

chmod 600 /root/.rcon_passwords
```

**Load in Discord bot startup:**
```bash
# In bot startup script
source /root/.rcon_passwords
export RCON_PASSWORD_TTT1="$TTT1_RCON_PASSWORD"
export RCON_PASSWORD_TTT2="$TTT2_RCON_PASSWORD"
export RCON_PASSWORD_TTT3="$TTT3_RCON_PASSWORD"
nohup python3 bot.py > bot_output.log 2>&1 &
```

---

## 📋 Complete Setup Checklist

- [ ] Generate 3 strong passwords (one per server)
- [ ] Create BEServer.cfg files with correct ownership
- [ ] Save passwords securely
- [ ] Determine how containers were created (docker-compose vs manual)
- [ ] Stop containers
- [ ] Recreate with RCon port mappings (2306/2307/2308)
- [ ] Start containers
- [ ] Check logs for "RCon initialized" message
- [ ] Install `rcon` library: `pip install rcon --break-system-packages`
- [ ] Test connectivity with test script
- [ ] Install `berconpy` for bot: `pip install berconpy --break-system-packages`
- [ ] Add RCon configuration to bot.py
- [ ] Create `/rcon-ban` Discord command
- [ ] Test ban execution
- [ ] Link with VPN detection for auto-bans

---

## 🚨 Important Notes

### BattlEye Will Only Load RCon If:
1. ✅ BEServer.cfg exists in `/srv/armareforger/[container]/battleye/`
2. ✅ File has correct ownership (matches container user)
3. ✅ RConPassword is set
4. ✅ RConPort is valid (usually 2306)
5. ✅ Container is restarted after config creation

### Port Mapping Is Required If:
- You want to connect from **outside** the container (your case)
- Your Discord bot runs on the **host** (not in Docker)

### Port Mapping Is NOT Required If:
- Discord bot runs inside a Docker container on same network
- You use `docker exec` to run RCon commands inside container

---

## 🎯 Quick Start Commands

**1. Generate passwords:**
```bash
PW1=$(openssl rand -base64 24)
PW2=$(openssl rand -base64 24)
PW3=$(openssl rand -base64 24)
echo "TTT1: $PW1"
echo "TTT2: $PW2"
echo "TTT3: $PW3"
```

**2. Create all config files at once:**
```bash
# TTT1
cat > /srv/armareforger/ub1d584ced/battleye/BEServer.cfg << EOF
RConPassword $PW1
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF
chown sub1d584ced:sub1d584ced /srv/armareforger/ub1d584ced/battleye/BEServer.cfg

# TTT2
cat > /srv/armareforger/uf74498006/battleye/BEServer.cfg << EOF
RConPassword $PW2
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF
chown suf74498006:suf74498006 /srv/armareforger/uf74498006/battleye/BEServer.cfg

# TTT3
cat > /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg << EOF
RConPassword $PW3
RConPort 2306
RestrictRCon 0
MaxPing 350
EOF
chown su98fbb3f3c:su98fbb3f3c /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg

# Save passwords
cat > /root/.rcon_passwords << EOF
TTT1_RCON_PASSWORD="$PW1"
TTT2_RCON_PASSWORD="$PW2"
TTT3_RCON_PASSWORD="$PW3"
EOF
chmod 600 /root/.rcon_passwords

echo "✅ Configuration files created!"
echo "📝 Passwords saved to /root/.rcon_passwords"
```

**3. Verify creation:**
```bash
ls -la /srv/armareforger/*/battleye/BEServer.cfg
cat /root/.rcon_passwords
```

---

## 🔄 Next Steps

**Before recreating containers, please run:**

```bash
# Check for docker-compose
find /srv/armareforger -name "docker-compose.yml"

# Check for startup scripts
find /srv/armareforger -name "*.sh" | grep -i "start\|run"

# View container details
docker inspect ub1d584ced --format='{{.Config.Image}}'
docker inspect ub1d584ced --format='{{.HostConfig.Binds}}'
```

**Share the output** so I can provide exact container recreation commands with RCon port mappings.

---

*Ready to proceed? Start with Step 1 (create BEServer.cfg files) and share results from the container investigation commands.*
