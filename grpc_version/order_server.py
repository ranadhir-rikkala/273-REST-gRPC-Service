import logging
import os
import uuid
from concurrent import futures

import grpc

import inventory_pb2
import inventory_pb2_grpc
import order_pb2
import order_pb2_grpc

PORT = int(os.getenv("ORDER_PORT", "50062"))
INVENTORY_ADDR = os.getenv("INVENTORY_ADDR", "localhost:50061")
DEADLINE_SECONDS = float(os.getenv("INVENTORY_DEADLINE_SECONDS", "2"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [order-grpc] %(message)s")
log = logging.getLogger(__name__)

PASS_THROUGH = {
    grpc.StatusCode.INVALID_ARGUMENT,
    grpc.StatusCode.NOT_FOUND,
    grpc.StatusCode.FAILED_PRECONDITION,
}


class OrderService(order_pb2_grpc.OrderServiceServicer):
    def __init__(self):
        self.channel = grpc.insecure_channel(INVENTORY_ADDR)
        self.inventory = inventory_pb2_grpc.InventoryServiceStub(self.channel)

    def PlaceOrder(self, request, context):
        if not request.item_id or request.quantity <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "item_id is required and quantity must be positive")

        try:
            self.inventory.CheckStock(
                inventory_pb2.CheckStockRequest(item_id=request.item_id, quantity=request.quantity),
                timeout=DEADLINE_SECONDS,
            )
        except grpc.RpcError as err:
            code = err.code()
            if code == grpc.StatusCode.DEADLINE_EXCEEDED:
                log.warning("inventory call exceeded %.1fs deadline for item_id=%s", DEADLINE_SECONDS, request.item_id)
                context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, f"inventory service exceeded {DEADLINE_SECONDS}s deadline")
            if code in PASS_THROUGH:
                log.info("order rejected for item_id=%s: inventory returned %s", request.item_id, code.name)
                context.abort(code, err.details())
            log.warning("inventory call failed: %s %s", code.name, err.details())
            context.abort(grpc.StatusCode.UNAVAILABLE, "inventory service unavailable")

        order_id = str(uuid.uuid4())
        log.info("order %s created for item_id=%s quantity=%d", order_id, request.item_id, request.quantity)
        return order_pb2.PlaceOrderResponse(
            order_id=order_id,
            item_id=request.item_id,
            quantity=request.quantity,
            status="CONFIRMED",
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    order_pb2_grpc.add_OrderServiceServicer_to_server(OrderService(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    log.info("listening on :%d -> inventory %s (deadline=%.1fs)", PORT, INVENTORY_ADDR, DEADLINE_SECONDS)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
