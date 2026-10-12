import os
import sys

import grpc

import order_pb2
import order_pb2_grpc

ORDER_ADDR = os.getenv("ORDER_ADDR", "localhost:50062")


def main():
    item_id = sys.argv[1] if len(sys.argv) > 1 else "apple"
    quantity = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    with grpc.insecure_channel(ORDER_ADDR) as channel:
        stub = order_pb2_grpc.OrderServiceStub(channel)
        print(f"-> PlaceOrder(item_id={item_id!r}, quantity={quantity})")
        try:
            resp = stub.PlaceOrder(order_pb2.PlaceOrderRequest(item_id=item_id, quantity=quantity), timeout=10)
            print(f"<- OK\n{resp}")
        except grpc.RpcError as err:
            print(f"<- {err.code().name}: {err.details()}")
            sys.exit(1)


if __name__ == "__main__":
    main()
