# Quick BattlEye RCon Diagnostic Commands
## Run these directly on your server

**Copy/paste these commands one by one:**

## Check BattlEye directories exist
```bash
echo "=== Checking BattlEye Directories ==="
ls -la /srv/armareforger/ub1d584ced/battleye/ 2>&1
echo ""
ls -la /srv/armareforger/uf74498006/battleye/ 2>&1
echo ""
ls -la /srv/armareforger/u98fbb3f3c/battleye/ 2>&1
```

## Check BEServer.cfg contents
```bash
echo "=== TTT1 BEServer.cfg ==="
cat /srv/armareforger/ub1d584ced/battleye/BEServer.cfg 2>&1
echo ""
echo "=== TTT2 BEServer.cfg ==="
cat /srv/armareforger/uf74498006/battleye/BEServer.cfg 2>&1
echo ""
echo "=== TTT3 BEServer.cfg ==="
cat /srv/armareforger/u98fbb3f3c/battleye/BEServer.cfg 2>&1
```

## Check port bindings for all servers
```bash
echo "=== TTT1 Ports (ub1d584ced) ==="
docker inspect ub1d584ced | grep -A 20 "PortBindings"
echo ""
echo "=== TTT2 Ports (uf74498006) ==="
docker inspect uf74498006 | grep -A 20 "PortBindings"
echo ""
echo "=== TTT3 Ports (u98fbb3f3c) ==="
docker inspect u98fbb3f3c | grep -A 20 "PortBindings"
```

## Check for ban files
```bash
echo "=== Checking ban files ==="
ls -lh /srv/armareforger/ub1d584ced/battleye/bans.txt 2>&1
ls -lh /srv/armareforger/uf74498006/battleye/bans.txt 2>&1
ls -lh /srv/armareforger/u98fbb3f3c/battleye/bans.txt 2>&1
```

## Check if RCon is mentioned in logs
```bash
echo "=== Checking logs for RCon initialization ==="
docker logs ub1d584ced 2>&1 | grep -i "rcon" | tail -5
```

---

## OR: Create the full diagnostic script on your server

```bash
# Create script
cat > /tmp/check_battleye.sh << 'SCRIPT_END'
#!/bin/bash

echo "=== BattlEye Configuration Check ==="
echo ""

for server in ub1d584ced uf74498006 u98fbb3f3c; do
    case $server in
        ub1d584ced) name="TTT1" ;;
        uf74498006) name="TTT2" ;;
        u98fbb3f3c) name="TTT3" ;;
    esac

    echo "========================================"
    echo "Server: $name ($server)"
    echo "========================================"

    if [ -d "/srv/armareforger/$server/battleye" ]; then
        echo "✅ BattlEye directory found"
        echo ""

        echo "Directory contents:"
        ls -la "/srv/armareforger/$server/battleye/"
        echo ""

        if [ -f "/srv/armareforger/$server/battleye/BEServer.cfg" ]; then
            echo "✅ BEServer.cfg exists"
            echo ""
            echo "Current configuration:"
            cat "/srv/armareforger/$server/battleye/BEServer.cfg"
            echo ""
        else
            echo "❌ BEServer.cfg NOT FOUND"
            echo ""
        fi

        if [ -f "/srv/armareforger/$server/battleye/bans.txt" ]; then
            ban_count=$(wc -l < "/srv/armareforger/$server/battleye/bans.txt")
            echo "✅ bans.txt exists ($ban_count bans)"
        else
            echo "❌ bans.txt NOT FOUND"
        fi
        echo ""
    else
        echo "❌ BattlEye directory NOT FOUND"
        echo ""
    fi

    echo "Port bindings:"
    docker inspect "$server" 2>/dev/null | grep -A 20 "PortBindings" | head -25
    echo ""
done

echo "========================================"
echo "RCon Log Check"
echo "========================================"
for server in ub1d584ced uf74498006 u98fbb3f3c; do
    case $server in
        ub1d584ced) name="TTT1" ;;
        uf74498006) name="TTT2" ;;
        u98fbb3f3c) name="TTT3" ;;
    esac

    echo ""
    echo "$name ($server):"
    docker logs "$server" 2>&1 | grep -i "rcon" | tail -3
done

echo ""
echo "=== Diagnostic Complete ==="
SCRIPT_END

# Run it
chmod +x /tmp/check_battleye.sh
bash /tmp/check_battleye.sh
```
