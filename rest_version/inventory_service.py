import logging
import os
import sys
import time

from flask import Flask, jsonify, request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from inventory_data import STOCK

PORT = int(os.getenv("INVENTORY_PORT", "5051"))
DELAY_SECONDS = float(os.getenv("INVENTORY_DELAY_SECONDS", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [inventory-rest] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


@app.post("/inventory/check")
def check_inventory():
    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    quantity = body.get("quantity")

    if not isinstance(item_id, str) or not isinstance(quantity, int) or quantity <= 0:
        return jsonify(error="item_id must be a string and quantity a positive integer"), 400

    if DELAY_SECONDS > 0:
        log.info("simulating slow response: sleeping %.1fs", DELAY_SECONDS)
        time.sleep(DELAY_SECONDS)

    if item_id not in STOCK:
        log.info("check item_id=%s quantity=%d -> 404 unknown item", item_id, quantity)
        return jsonify(error=f"item '{item_id}' not found"), 404

    in_stock = STOCK[item_id]
    if in_stock < quantity:
        log.info("check item_id=%s quantity=%d -> 409 insufficient stock (%d)", item_id, quantity, in_stock)
        return jsonify(
            error=f"insufficient stock for '{item_id}'",
            item_id=item_id,
            requested=quantity,
            in_stock=in_stock,
        ), 409

    log.info("check item_id=%s quantity=%d -> 200 available", item_id, quantity)
    return jsonify(item_id=item_id, requested=quantity, in_stock=in_stock, available=True), 200


if __name__ == "__main__":
    log.info("listening on :%d (delay=%.1fs)", PORT, DELAY_SECONDS)
    app.run(host="0.0.0.0", port=PORT)
