# CMPE 273 - Module 3: REST & gRPC

Order service + inventory service, done twice: once with REST (Flask + requests) and once with gRPC. Written in Python.

The order service takes an `item_id` and `quantity` and asks the inventory service if it's in stock. Stock is hardcoded in `inventory_data.py` (apple 10, banana 0, laptop 3).

- `rest_version/` - Flask order service (port 5050) and inventory service (port 5051)
- `grpc_version/` - gRPC order service (50062), inventory service (50061), a small client, and the .proto files
- `scripts/` - demo scripts I used to get the output below
- `evidence/` - full output from the demo scripts

Status codes I used:

| Case | REST | gRPC |
|---|---|---|
| ok | 201 (order) / 200 (inventory) | OK |
| bad input | 400 | INVALID_ARGUMENT |
| unknown item | 404 | NOT_FOUND |
| not enough stock | 409 | FAILED_PRECONDITION |
| inventory too slow | 504 | DEADLINE_EXCEEDED |
| inventory down | 503 | UNAVAILABLE |

The timeout (REST) and deadline (gRPC) are both 2 seconds.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the REST version

Start the inventory service and the order service in separate terminals:

```bash
python rest_version/inventory_service.py
```

```bash
python rest_version/order_service.py
```

Then send an order:

```bash
curl -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '{"item_id": "apple", "quantity": 2}'
```

To test the timeout, restart the inventory service with a delay:

```bash
INVENTORY_DELAY_SECONDS=5 python rest_version/inventory_service.py
```

`scripts/demo_rest.sh` does all of this automatically.

## Running the gRPC version

The generated `_pb2` files are already in the repo. If you change the .proto files, run `./grpc_version/generate.sh`.

```bash
cd grpc_version
python inventory_server.py
```

```bash
cd grpc_version
python order_server.py
```

```bash
cd grpc_version
python order_client.py apple 2
```

For the deadline test:

```bash
INVENTORY_DELAY_SECONDS=5 python inventory_server.py
```

`scripts/demo_grpc.sh` does all of this automatically.

## Results

Output is from `evidence/rest_demo.txt` and `evidence/grpc_demo.txt`. In both scripts the order service is started once and left running while the inventory service is restarted with and without the delay.

### Successful REST request and response

```
$ curl -s -w '\nHTTP %{http_code} in %{time_total}s\n' -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '{"item_id": "apple", "quantity": 2}'
{"item_id":"apple","order_id":"fb2cc815-f066-4b9c-932d-f332739d2ffd","quantity":2,"status":"CONFIRMED"}

HTTP 201 in 0.005205s
```

Inventory log for that call:
```
[inventory-rest] check item_id=apple quantity=2 -> 200 available
[inventory-rest] 127.0.0.1 - - "POST /inventory/check HTTP/1.1" 200 -
```

Error cases:
```
$ curl ... -d '{"item_id": "banana", "quantity": 1}'
{"error":"insufficient stock for 'banana'","in_stock":0,"item_id":"banana","requested":1}
HTTP 409

$ curl ... -d '{"item_id": "unicorn", "quantity": 1}'
{"error":"item 'unicorn' not found"}
HTTP 404

$ curl ... -d '{"item_id": "apple"}'
{"error":"item_id must be a string and quantity a positive integer"}
HTTP 400
```

### Successful gRPC request and response

```
$ python order_client.py apple 2
-> PlaceOrder(item_id='apple', quantity=2)
<- OK
order_id: "47366206-56fc-43e0-b520-d450bc5c8fcc"
item_id: "apple"
quantity: 2
status: "CONFIRMED"

real 0.06
```

Error cases:
```
$ python order_client.py banana 1
<- FAILED_PRECONDITION: insufficient stock for 'banana': requested 1, in stock 0

$ python order_client.py unicorn 1
<- NOT_FOUND: item 'unicorn' not found
```

### REST timeout handling

Restarted inventory with `INVENTORY_DELAY_SECONDS=5`. Order service times out after 2s and returns 504:

```
$ curl -s -w '\nHTTP %{http_code} in %{time_total}s\n' -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '{"item_id": "apple", "quantity": 2}'
{"error":"inventory service timed out after 2.0s"}

HTTP 504 in 2.005026s
```

Order service log:
```
2026-10-11 21:42:32,873 [order-rest] inventory call timed out after 2.0s for item_id=apple
2026-10-11 21:42:32,874 [order-rest] 127.0.0.1 - - [11/Oct/2026 21:42:32] "POST /orders HTTP/1.1" 504 -
```

### gRPC deadline handling

Same 5s delay. The 2s deadline runs out and the order service returns DEADLINE_EXCEEDED:

```
$ python order_client.py apple 2
-> PlaceOrder(item_id='apple', quantity=2)
<- DEADLINE_EXCEEDED: inventory service exceeded 2.0s deadline
real 2.08
```

Order service log:
```
2026-10-11 21:43:01,918 [order-grpc] inventory call exceeded 2.0s deadline for item_id=apple
```

### Order service keeps running

REST: the PID is the same, /health still returns 200, and the next order works once inventory is back to normal.

```
=== 3. Order Service still running after the timeout ===
$ ps -p 58260 -o pid,command
  PID COMMAND
58260 .../Python rest_version/order_service.py

$ curl -s -w '\nHTTP %{http_code}\n' localhost:5050/health
{"status":"ok"}
HTTP 200

$ curl ... -d '{"item_id": "laptop", "quantity": 1}'
{"error":"inventory service timed out after 2.0s"}
HTTP 504 in 2.005373s

=== 4. Inventory restored (delay = 0s), same Order Service process ===
$ curl ... -d '{"item_id": "laptop", "quantity": 1}'
{"item_id":"laptop","order_id":"7115c010-25c4-4cb8-aa6f-e95ffda4e125","quantity":1,"status":"CONFIRMED"}
HTTP 201 in 0.002865s
```

gRPC: same thing.

```
=== 3. Order Service still running after the deadline was exceeded ===
$ ps -p 58404 -o pid,command
  PID COMMAND
58404 .../Python order_server.py

$ python order_client.py laptop 1
<- DEADLINE_EXCEEDED: inventory service exceeded 2.0s deadline
real 2.09

=== 4. Inventory restored (delay = 0s), same Order Service process ===
$ python order_client.py laptop 1
<- OK
order_id: "474d1ac3-63b3-4e9c-ac7e-742ceeb8a158"
item_id: "laptop"
quantity: 1
status: "CONFIRMED"
```

The order service logs at the bottom of each evidence file show all of these requests going through the same process without a restart.

## REST vs gRPC

With REST I had to define the request/response format myself and validate the JSON by hand on both services, but with gRPC the .proto file defined the types and generated the client and server code. For errors, REST meant picking HTTP codes and making up my own JSON error format, while gRPC already had status codes like NOT_FOUND and DEADLINE_EXCEEDED that fit. The REST timeout is just a setting on the requests call, but the gRPC deadline is sent along with the call so both sides know about it, and the client gets DEADLINE_EXCEEDED without any extra work. REST was easier to test since I could just use curl and read the JSON, while for gRPC I had to write a client script because the messages are binary. Overall REST was quicker to get started with, but gRPC was stricter about the contract and needed less custom code for errors and timeouts.
