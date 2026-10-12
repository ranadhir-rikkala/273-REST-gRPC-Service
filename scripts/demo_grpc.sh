#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
LOGS=evidence/logs
mkdir -p "$LOGS"
export NO_COLOR=1 PYTHONUNBUFFERED=1

wait_port() {
  for _ in $(seq 1 100); do nc -z localhost "$1" 2>/dev/null && return 0; sleep 0.1; done
  echo "port $1 did not open"; exit 1
}

start_inventory() {
  (cd grpc_version && INVENTORY_DELAY_SECONDS="$1" exec python inventory_server.py) >> "$LOGS/grpc_inventory.log" 2>&1 &
  INV_PID=$!
  wait_port 50061
}

call() {
  echo
  echo "\$ python order_client.py $*"
  (cd grpc_version && /usr/bin/time -p python order_client.py "$@" 2>&1 | grep -v -E '^(user|sys)')
}

rm -f "$LOGS"/grpc_*.log
(cd grpc_version && exec python order_server.py) > "$LOGS/grpc_order.log" 2>&1 &
ORDER_PID=$!
wait_port 50062
trap 'kill $ORDER_PID $INV_PID 2>/dev/null' EXIT

echo "=== 1. Normal operation (inventory delay = 0s, deadline = 2s) ==="
start_inventory 0
call apple 2
call banana 1
call unicorn 1

echo
echo "=== 2. Slow inventory (delay = 5s > 2s deadline) ==="
kill $INV_PID; wait $INV_PID 2>/dev/null
start_inventory 5
call apple 2

echo
echo "=== 3. Order Service still running after the deadline was exceeded ==="
echo "\$ ps -p $ORDER_PID -o pid,command"
ps -p $ORDER_PID -o pid,command
call laptop 1

echo
echo "=== 4. Inventory restored (delay = 0s), same Order Service process ==="
kill $INV_PID; wait $INV_PID 2>/dev/null
start_inventory 0
call laptop 1

echo
echo "=== Order Service log ==="
sed -E "s/\x1b\[[0-9;]*m//g" "$LOGS/grpc_order.log"
echo
echo "=== Inventory Service log ==="
sed -E "s/\x1b\[[0-9;]*m//g" "$LOGS/grpc_inventory.log"
