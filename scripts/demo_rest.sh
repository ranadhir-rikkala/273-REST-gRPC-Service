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
  INVENTORY_DELAY_SECONDS="$1" python rest_version/inventory_service.py >> "$LOGS/rest_inventory.log" 2>&1 &
  INV_PID=$!
  wait_port 5051
}

call() {
  echo
  echo "\$ curl -s -w '\\nHTTP %{http_code} in %{time_total}s\\n' -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '$1'"
  curl -s -w '\nHTTP %{http_code} in %{time_total}s\n' -X POST localhost:5050/orders -H 'Content-Type: application/json' -d "$1"
}

rm -f "$LOGS"/rest_*.log
python rest_version/order_service.py > "$LOGS/rest_order.log" 2>&1 &
ORDER_PID=$!
wait_port 5050
trap 'kill $ORDER_PID $INV_PID 2>/dev/null' EXIT

echo "=== 1. Normal operation (inventory delay = 0s, client timeout = 2s) ==="
start_inventory 0
call '{"item_id": "apple", "quantity": 2}'
call '{"item_id": "banana", "quantity": 1}'
call '{"item_id": "unicorn", "quantity": 1}'
call '{"item_id": "apple"}'

echo
echo "=== 2. Slow inventory (delay = 5s > 2s timeout) ==="
kill $INV_PID; wait $INV_PID 2>/dev/null
start_inventory 5
call '{"item_id": "apple", "quantity": 2}'

echo
echo "=== 3. Order Service still running after the timeout ==="
echo "\$ ps -p $ORDER_PID -o pid,command"
ps -p $ORDER_PID -o pid,command
echo
echo "\$ curl -s -w '\\nHTTP %{http_code}\\n' localhost:5050/health"
curl -s -w '\nHTTP %{http_code}\n' localhost:5050/health
call '{"item_id": "laptop", "quantity": 1}'

echo
echo "=== 4. Inventory restored (delay = 0s), same Order Service process ==="
kill $INV_PID; wait $INV_PID 2>/dev/null
start_inventory 0
call '{"item_id": "laptop", "quantity": 1}'

echo
echo "=== Order Service log ==="
sed -E "s/\x1b\[[0-9;]*m//g" "$LOGS/rest_order.log"
echo
echo "=== Inventory Service log ==="
sed -E "s/\x1b\[[0-9;]*m//g" "$LOGS/rest_inventory.log"
