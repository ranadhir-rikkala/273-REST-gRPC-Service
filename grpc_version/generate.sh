#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/inventory.proto protos/order.proto
