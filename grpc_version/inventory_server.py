import logging
import os
import sys
import time
from concurrent import futures

import grpc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from inventory_data import STOCK

import inventory_pb2
import inventory_pb2_grpc

PORT = int(os.getenv("INVENTORY_PORT", "50061"))
DELAY_SECONDS = float(os.getenv("INVENTORY_DELAY_SECONDS", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [inventory-grpc] %(message)s")
log = logging.getLogger(__name__)


class InventoryService(inventory_pb2_grpc.InventoryServiceServicer):
    def CheckStock(self, request, context):
        if not request.item_id or request.quantity <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "item_id is required and quantity must be positive")

        if DELAY_SECONDS > 0:
            log.info("simulating slow response: sleeping %.1fs", DELAY_SECONDS)
            time.sleep(DELAY_SECONDS)

        if request.item_id not in STOCK:
            log.info("check item_id=%s quantity=%d -> NOT_FOUND", request.item_id, request.quantity)
            context.abort(grpc.StatusCode.NOT_FOUND, f"item '{request.item_id}' not found")

        in_stock = STOCK[request.item_id]
        if in_stock < request.quantity:
            log.info("check item_id=%s quantity=%d -> FAILED_PRECONDITION (%d)", request.item_id, request.quantity, in_stock)
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"insufficient stock for '{request.item_id}': requested {request.quantity}, in stock {in_stock}",
            )

        log.info("check item_id=%s quantity=%d -> OK", request.item_id, request.quantity)
        return inventory_pb2.CheckStockResponse(
            item_id=request.item_id,
            requested=request.quantity,
            in_stock=in_stock,
            available=True,
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryService(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    log.info("listening on :%d (delay=%.1fs)", PORT, DELAY_SECONDS)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
