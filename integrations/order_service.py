import httpx
import os
from icecream import ic
from dotenv import load_dotenv

load_dotenv()

ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://127.0.0.1:8007")

async def check_product_sales_exists(shop_id: str, product_id: str) -> bool:
    """
    Checks if any orders contain the given product_id for a shop
    by querying the Order Service via HTTP API.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{ORDER_SERVICE_URL}/orders/{shop_id}",
                params={"limit": 100, "offset": 1}
            )
            if response.status_code == 200:
                data = response.json()
                payload = data.get("data") if isinstance(data, dict) and "data" in data else data
                
                orders = []
                if isinstance(payload, list):
                    orders = payload
                elif isinstance(payload, dict):
                    orders = payload.get("datas") or payload.get("orders") or []

                for order in orders:
                    items = order.get("items") or []
                    for item in items:
                        if isinstance(item, dict) and item.get("product_id") == product_id:
                            return True
            return False
    except Exception as e:
        ic(f"Error calling Order Service to check sales for product {product_id}: {e}")
        return False
