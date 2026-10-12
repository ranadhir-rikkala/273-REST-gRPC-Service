import logging
import os
import uuid

import requests
from flask import Flask, jsonify, request

PORT = int(os.getenv("ORDER_PORT", "5050"))
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:5051")
TIMEOUT_SECONDS = float(os.getenv("INVENTORY_TIMEOUT_SECONDS", "2"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [order-rest] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.post("/orders")
def create_order():
    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    quantity = body.get("quantity")

    if not isinstance(item_id, str) or not isinstance(quantity, int) or quantity <= 0:
        return jsonify(error="item_id must be a string and quantity a positive integer"), 400

    try:
        resp = requests.post(
            f"{INVENTORY_URL}/inventory/check",
            json={"item_id": item_id, "quantity": quantity},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        log.warning("inventory call timed out after %.1fs for item_id=%s", TIMEOUT_SECONDS, item_id)
        return jsonify(error=f"inventory service timed out after {TIMEOUT_SECONDS}s"), 504
    except requests.exceptions.ConnectionError:
        log.warning("inventory service unreachable at %s", INVENTORY_URL)
        return jsonify(error="inventory service unavailable"), 503

    if resp.status_code == 200:
        order_id = str(uuid.uuid4())
        log.info("order %s created for item_id=%s quantity=%d", order_id, item_id, quantity)
        return jsonify(order_id=order_id, item_id=item_id, quantity=quantity, status="CONFIRMED"), 201

    if resp.status_code in (400, 404, 409):
        log.info("order rejected for item_id=%s: inventory returned %d", item_id, resp.status_code)
        return jsonify(resp.json()), resp.status_code

    log.warning("unexpected inventory status %d", resp.status_code)
    return jsonify(error="unexpected response from inventory service"), 502


if __name__ == "__main__":
    log.info("listening on :%d -> inventory %s (timeout=%.1fs)", PORT, INVENTORY_URL, TIMEOUT_SECONDS)
    app.run(host="0.0.0.0", port=PORT)
