# BattlEye RCon Investigation & Setup Guide
## Based on Your Docker Configuration

---

## 🔍 What We Found

### Docker Port Bindings (TTT1 - ub1d584ced)
```
2002/udp → 64.44.205.83:2002  (Game port - public)
3002/udp → 127.0.0.1:3002      (Local only - unknown service)
```

**CRITICAL FINDINGS:**
- ❌ No RCon port (2306/tcp) is currently mapped
- ❌ BattlEye directory not found at `/srv/armareforger/ub1d584ced/profile/BattlEye/`
- ✅ Game server is running and accessible

---

## 📋 Investigation Commands

Run these commands to find your BattlEye configuration:

### 1. Find ALL Files in Container Directory
```bash
find /srv/armareforger/ub1d584ced -name "*.cfg" -o -name "*BattlEye*" -o -name "bans.txt" 2>/dev/null
```

### 2. Check Inside Docker Container
```bash
docker exec ub1d584ced find /reforger -name "BEServer*" -o -name "bans.txt" 2>/dev/null
```

### 3. List Container's Full Directory Structure
```bash
docker exec ub1d584ced ls -la /reforger/profile/
```

### 4. Check for ANY BattlEye Files Inside Container
```bash
docker exec ub1d584ced find /reforger -type d -name "BattlEye"
```

### 5. Inspect Container's Full Configuration
```bash
docker inspect ub1d584ced > /tmp/container_config.json
cat /tmp/container_config.json | grep -i "volume\|mount" -A 5
```

### 6. Check if BattlEye is Even Enabled
```bash
docker exec ub1d584ced cat /reforger/config.json | grep -i battleye
```

### 7. Check Recent Logs for BattlEye Messages
```bash
docker logs ub1d584ced 2>&1 | grep -i "battleye\|rcon" | tail -20
```

---

## 🎯 Likely Scenarios

Based on the missing directory, here are the possibilities:

### Scenario A: BattlEye Files Are Inside Container
**Path probably:** `/reforger/profile/BattlEye/` (inside container)
**Why not found:** Host path doesn't have volume mount to that location
**Solution:** Must exec into container to access files

### Scenario B: BattlEye Not Yet Configured
**Evidence:** No BEServer.cfg file exists
**Why:** Fresh server install without RCon setup
**Solution:** Need to create the configuration

### Scenario C: BattlEye Disabled Entirely
**Evidence:** No BattlEye directory at all
**Why:** Server started with BattlEye disabled
**Solution:** Enable BattlEye in server config, recreate container

### Scenario D: Volume Mount Location Different
**Evidence:** Files exist but at different mount point
**Why:** Custom Docker setup
**Solution:** Check `docker inspect` output for actual mount paths

---

## 🔧 Quick Diagnostic Script

Save this as `/tmp/find_battleye.sh` and run it:

```bash
#!/bin/bash

echo "=== BattlEye RCon Diagnostic ==="
echo ""

echo "1. Checking host filesystem..."
find /srv/armareforger/ub1d584ced -name "*BattlEye*" -o -name "bans.txt" -o -name "BEServer*" 2>/dev/null

echo ""
echo "2. Checking inside container..."
docker exec ub1d584ced find /reforger -name "*BattlEye*" -type d 2>/dev/null

echo ""
echo "3. Looking for BEServer.cfg..."
docker exec ub1d584ced find /reforger -name "BEServer*" 2>/dev/null

echo ""
echo "4. Checking server config for BattlEye..."
docker exec ub1d584ced cat /reforger/config.json 2>/dev/null | grep -i "battleye" || echo "No BattlEye config found"

echo ""
echo "5. Checking logs for BattlEye initialization..."
docker logs ub1d584ced 2>&1 | grep -i "battleye" | head -10

echo ""
echo "6. Checking volume mounts..."
docker inspect ub1d584ced | grep -A 10 "Mounts"

echo ""
echo "7. Current port bindings..."
docker inspect ub1d584ced | grep -A 20 "PortBindings"

echo ""
echo "=== Diagnostic Complete ==="
```

**Run it:**
```bash
chmod +x /tmp/find_battleye.sh
bash /tmp/find_battleye.sh
```

---

## 📝 What To Do Next

### Step 1: Run Investigation Commands
Paste the diagnostic script output here so we can determine the exact situation.

### Step 2: Based on Results, We'll Need To:

#### If BattlEye is Inside Container:
1. Access the files via `docker exec`
2. Add RCon configuration
3. Add port mapping to container
4. Restart container

#### If BattlEye Doesn't Exist:
1. Check if BattlEye is enabled in server config
2. Create BattlEye directory structure
3. Create BEServer.cfg
4. Add port mapping
5. Restart container

#### If BattlEye is Disabled:
1. Enable in `/reforger/config.json`
2. Recreate container with BattlEye support
3. Set up RCon from scratch

---

## 🚨 Current Limitations

**Without RCon ports mapped, you CANNOT:**
- Connect to RCon from outside container
- Use automated ban scripts
- Execute remote commands

**You CAN still:**
- Edit ban files manually inside container
- Use Discord bot for monitoring (already working)
- Track players in database (already working)

---

## 🎮 Understanding Your Current Setup

### What's Working Now:
```
Discord Bot (bot.py)
    ↓
Docker API (docker.py library)
    ↓
Container Logs (docker logs ub1d584ced)
    ↓
Parse Player Data → SQLite Database
```

### What RCon Would Add:
```
Discord Bot (bot.py)
    ↓
RCon Client (berconpy)
    ↓
BattlEye RCon Protocol (port 2306)
    ↓
BattlEye Server → Execute Bans in Real-Time
```

**BUT:** RCon requires:
1. ✅ BattlEye enabled (unknown)
2. ❌ BEServer.cfg with RCon settings (missing)
3. ❌ Docker port mapping (missing)
4. ❌ Network access to RCon port (missing)

---

## 🔍 Alternative: Manual Ban File Management

If RCon setup is too complex, you can still automate bans by:

### Option 1: Direct File Manipulation
```python
# Add ban to bans.txt inside container
def add_ban_to_file(container_id: str, guid: str, duration: int, reason: str):
    """Add ban directly to BattlEye bans.txt file"""
    ban_line = f'{guid} {duration} {reason}'

    # Append to bans.txt inside container
    docker_client.containers.get(container_id).exec_run(
        f'echo "{ban_line}" >> /reforger/profile/BattlEye/bans.txt'
    )

    # Reload bans (requires BattlEye RCon or server restart)
    # Without RCon, ban takes effect after server restart
```

**Pros:** No RCon needed
**Cons:** Requires server restart to apply bans

### Option 2: Docker Exec for RCon
```python
# Execute RCon commands via docker exec
def docker_exec_rcon(container_id: str, command: str):
    """Execute RCon command via docker exec (if BERConClient exists in container)"""
    result = docker_client.containers.get(container_id).exec_run(
        f'/path/to/rcon-cli -H 127.0.0.1 -p 2306 -P password "{command}"'
    )
    return result.output.decode()
```

**Pros:** No external port mapping needed
**Cons:** Requires RCon client installed inside container

---

## 📞 Next Steps

**Please run the diagnostic script and share the output.**

Based on the results, I'll provide:
1. Exact path to BEServer.cfg (or how to create it)
2. Docker run command with proper port mapping
3. Complete RCon setup guide for your specific configuration
4. Integration code for your Discord bot

**Copy/paste the output from:**
```bash
bash /tmp/find_battleye.sh
```

This will tell us exactly where BattlEye is and how to enable RCon.

---

## 🔄 Quick Reference: Your Server Details

| Server | Container ID | Game Port | Local Port | RCon Port |
|--------|--------------|-----------|------------|-----------|
| TTT1 | ub1d584ced | 2002 (public) | 3002 (local) | **NOT MAPPED** ❌ |
| TTT2 | uf74498006 | 2003 (?) | (?) | **NOT MAPPED** ❌ |
| TTT3 | u98fbb3f3c | 2001 (?) | (?) | **NOT MAPPED** ❌ |

---

*Next: Run diagnostic and report findings*
