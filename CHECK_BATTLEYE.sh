#!/bin/bash
# Quick script to check BattlEye configuration for all servers

echo "=== BattlEye Configuration Check ==="
echo ""

for server in ub1d584ced uf74498006 u98fbb3f3c; do
    echo "========================================"
    echo "Server: $server"
    echo "========================================"

    # Check if battleye directory exists
    if [ -d "/srv/armareforger/$server/battleye" ]; then
        echo "✅ BattlEye directory found"
        echo ""

        echo "Directory contents:"
        ls -la "/srv/armareforger/$server/battleye/"
        echo ""

        # Check for BEServer.cfg
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

        # Check for bans.txt
        if [ -f "/srv/armareforger/$server/battleye/bans.txt" ]; then
            echo "✅ bans.txt exists ($(wc -l < /srv/armareforger/$server/battleye/bans.txt) bans)"
        else
            echo "❌ bans.txt NOT FOUND"
        fi
        echo ""

    else
        echo "❌ BattlEye directory NOT FOUND at /srv/armareforger/$server/battleye"
        echo ""
    fi

    echo ""
done

echo "========================================"
echo "Port Bindings Check"
echo "========================================"
for server in ub1d584ced uf74498006 u98fbb3f3c; do
    echo ""
    echo "Server: $server"
    docker inspect "$server" 2>/dev/null | grep -A 20 "PortBindings" | head -25
done
