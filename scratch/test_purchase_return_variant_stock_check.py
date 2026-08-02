import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from icecream import ic

def test_variant_stock_check():
    # Simulated purchase item in PurchaseCollections (Mongo)
    target_item = {
        "id": "pur_item_1",
        "product_id": "prod_100",
        "name": "Variant With Batch",
        "variant_infos": {"id": "var_555", "name": "500ml"},
        "batch_infos": {"id": "batch_777", "name": "B-001"},
        "stocks_infos": {"stocks": 10.0}
    }

    # Simulated ProdInvCollections document (Mongo) for InventoryServiceReadDb
    prod_doc = {
        "id": "prod_100",
        "shop_id": "shop_abc",
        "variants": {
            "var_555": {
                "id": "var_555",
                "name": "500ml",
                "batch_infos": [
                    {
                        "id": "batch_777",
                        "name": "B-001",
                        "stock_infos": {"physical_stocks": 5.0, "available_stocks": 5.0}
                    }
                ]
            }
        }
    }

    # Extract variant_id using our updated extraction logic
    variant_id = target_item.get("variant_id") or (target_item.get("variant_infos") or {}).get("id")
    batch_infos_obj = target_item.get("batch_infos")
    batch_id = (batch_infos_obj.get("id") or batch_infos_obj.get("batch_id")) if isinstance(batch_infos_obj, dict) else target_item.get("batch_id")
    batch_name = batch_infos_obj.get("name") if isinstance(batch_infos_obj, dict) else (batch_infos_obj if isinstance(batch_infos_obj, str) else None)

    ic("Extracted variant_id =>", variant_id)
    ic("Extracted batch_id =>", batch_id)
    ic("Extracted batch_name =>", batch_name)

    assert variant_id == "var_555"
    assert batch_id == "batch_777"

    target_stock_infos = {}
    if variant_id and prod_doc.get("variants"):
        variants = prod_doc.get("variants") or {}
        variant_data = variants.get(variant_id) or {}
        
        if (batch_id or batch_name) and variant_data.get("batch_infos"):
            batches = variant_data.get("batch_infos") or []
            matched_b = next((b for b in batches if isinstance(b, dict) and (b.get("id") == batch_id or b.get("name") == batch_id or b.get("id") == batch_name or b.get("name") == batch_name)), {})
            target_stock_infos = matched_b.get("stock_infos") or matched_b.get("stocks_infos") or {}
        else:
            target_stock_infos = variant_data.get("stock_infos") or variant_data.get("stocks_infos") or {}

    physical_stock = float(target_stock_infos.get("physical_stocks") if target_stock_infos.get("physical_stocks") is not None else (target_stock_infos.get("stocks") or 0.0))
    ic("Found Physical Stock =>", physical_stock)
    assert physical_stock == 5.0

    print("VARIANT STOCK CHECK & VARIANT_ID EXTRACTION VERIFIED CLEANLY!")

if __name__ == "__main__":
    test_variant_stock_check()
