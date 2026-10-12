# CMPE 273 - Module 3: REST & gRPC

Order service calling an inventory service, implemented with REST and with gRPC in Python.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the REST version

```bash
python rest_version/inventory_service.py
```

```bash
python rest_version/order_service.py
```

```bash
curl -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '{"item_id": "apple", "quantity": 2}'
```

## Running the gRPC version

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

To test the timeout/deadline, start the inventory service with a 5s delay (timeout and deadline are 2s):

```bash
INVENTORY_DELAY_SECONDS=5 python rest_version/inventory_service.py
INVENTORY_DELAY_SECONDS=5 python grpc_version/inventory_server.py
```

## Successful REST request

```
$ curl -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '{"item_id": "apple", "quantity": 2}'
{"item_id":"apple","order_id":"fb2cc815-f066-4b9c-932d-f332739d2ffd","quantity":2,"status":"CONFIRMED"}
HTTP 201
```

## Successful gRPC request

```
$ python order_client.py apple 2
-> PlaceOrder(item_id='apple', quantity=2)
<- OK
order_id: "47366206-56fc-43e0-b520-d450bc5c8fcc"
item_id: "apple"
quantity: 2
status: "CONFIRMED"
```

## REST timeout

```
$ curl -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '{"item_id": "apple", "quantity": 2}'
{"error":"inventory service timed out after 2.0s"}
HTTP 504 in 2.005026s
```

```
[order-rest] inventory call timed out after 2.0s for item_id=apple
[order-rest] 127.0.0.1 - - "POST /orders HTTP/1.1" 504 -
```

## gRPC deadline

```
$ python order_client.py apple 2
-> PlaceOrder(item_id='apple', quantity=2)
<- DEADLINE_EXCEEDED: inventory service exceeded 2.0s deadline
```

```
[order-grpc] inventory call exceeded 2.0s deadline for item_id=apple
```

## Order service still running after the failures

REST (same process, health check works, next order succeeds after removing the delay):

```
$ ps -p 58260 -o pid,command
  PID COMMAND
58260 .../Python rest_version/order_service.py

$ curl localhost:5050/health
{"status":"ok"}
HTTP 200

$ curl -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '{"item_id": "laptop", "quantity": 1}'
{"item_id":"laptop","order_id":"7115c010-25c4-4cb8-aa6f-e95ffda4e125","quantity":1,"status":"CONFIRMED"}
HTTP 201
```

gRPC (same process, next order succeeds after removing the delay):

```
$ ps -p 58404 -o pid,command
  PID COMMAND
58404 .../Python order_server.py

$ python order_client.py laptop 1
<- OK
order_id: "474d1ac3-63b3-4e9c-ac7e-742ceeb8a158"
item_id: "laptop"
quantity: 1
status: "CONFIRMED"
```

## REST vs gRPC

With REST, I had to define the request and response formats myself and manually validate the JSON on both services. With gRPC, I just defined the types in the .proto file, and it generated the client and server code for me.

Error handling was also easier with gRPC because it already had standard status codes like NOT_FOUND and DEADLINE_EXCEEDED. With REST, I had to choose HTTP status codes and create my own JSON error format.

Timeouts were another difference. With REST, I had to configure the timeout on the client side. With gRPC, I could set a deadline that was passed along with the call, so the server also knew how much time was left.

Testing was easier with REST because I could use curl and easily read the JSON responses. With gRPC, I had to write a small client script to test the calls because the messages were sent in binary format.

Overall, REST was easier to get started with, but gRPC gave me a stricter contract and reduced the amount of custom code I needed for error handling and timeouts.
