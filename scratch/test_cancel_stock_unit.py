import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

# Test stock checking logic directly
async def check_cancellation_stock(items_to_process, product_docs):
    for proc_item in items_to_process:
        qty_to_revert = proc_item["qty_to_revert"]
        if qty_to_revert <= 0:
            continue

        p_id = proc_item["product_id"]
        v_id = proc_item["variant_id"]
        b_id = proc_item["batch_id"]
        item_name = proc_item["name"]
        purchased_qty = proc_item["purchased_qty"]

        prod_doc = product_docs.get(p_id) or {}
        type_infos = prod_doc.get("type_infos") or {}
        has_batch = type_infos.get("has_batch") if type_infos and "has_batch" in type_infos else prod_doc.get("has_batch", False)
        has_variant = type_infos.get("has_variant") if type_infos and "has_variant" in type_infos else prod_doc.get("has_variant", False)

        target_stock_infos = {}
        if prod_doc.get("inventory_units") and isinstance(prod_doc.get("inventory_units"), list):
            for unit in prod_doc["inventory_units"]:
                if not isinstance(unit, dict):
                    continue
                u_v_id = (unit.get("variant_infos") or {}).get("id") if isinstance(unit.get("variant_infos"), dict) else None
                u_b_id = (unit.get("batch_infos") or {}).get("id") if isinstance(unit.get("batch_infos"), dict) else None
                
                if v_id and b_id:
                    if u_v_id == v_id and u_b_id == b_id:
                        target_stock_infos = unit.get("stock_infos") or unit.get("stocks_infos") or {}
                        break
                elif v_id:
                    if u_v_id == v_id:
                        target_stock_infos = unit.get("stock_infos") or unit.get("stocks_infos") or {}
                        break
                elif b_id:
                    if u_b_id == b_id:
                        target_stock_infos = unit.get("stock_infos") or unit.get("stocks_infos") or {}
                        break
                else:
                    target_stock_infos = unit.get("stock_infos") or unit.get("stocks_infos") or {}
                    break

        if not target_stock_infos:
            if has_variant and v_id:
                variants = prod_doc.get("variants") or {}
                variant_data = {}
                if isinstance(variants, dict):
                    variant_data = variants.get(v_id) or {}
                elif isinstance(variants, list):
                    variant_data = next((v for v in variants if isinstance(v, dict) and v.get("id") == v_id), {})
                
                if has_batch and b_id:
                    batches = variant_data.get("batch_infos") or []
                    matched_b = next((b for b in batches if isinstance(b, dict) and (b.get("id") == b_id or b.get("name") == b_id)), {})
                    target_stock_infos = matched_b.get("stock_infos") or matched_b.get("stocks_infos") or {}
                else:
                    target_stock_infos = variant_data.get("stock_infos") or variant_data.get("stocks_infos") or {}
            elif has_batch and b_id:
                batches = prod_doc.get("batch_infos") or []
                matched_b = next((b for b in batches if isinstance(b, dict) and (b.get("id") == b_id or b.get("name") == b_id)), {})
                target_stock_infos = matched_b.get("stock_infos") or matched_b.get("stocks_infos") or {}
            else:
                target_stock_infos = prod_doc.get("stock_infos") or prod_doc.get("stocks_infos") or {}

        physical_stock = float(
            target_stock_infos.get("physical_stocks")
            if target_stock_infos.get("physical_stocks") is not None
            else (target_stock_infos.get("physical_Stocks") if target_stock_infos.get("physical_Stocks") is not None else (target_stock_infos.get("stocks") if target_stock_infos.get("stocks") is not None else (prod_doc.get("stocks") or 0.0)))
        )
        available_stock = float(
            target_stock_infos.get("available_stocks")
            if target_stock_infos.get("available_stocks") is not None
            else (target_stock_infos.get("available_Stocks") if target_stock_infos.get("available_Stocks") is not None else physical_stock)
        )

        current_stock = min(physical_stock, available_stock)

        if current_stock < qty_to_revert:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel purchase because current available stock for product '{item_name}' ({current_stock}) is less than the purchased quantity ({qty_to_revert}). Available stock must be greater than or equal to {qty_to_revert} to cancel."
            )
    return True

import asyncio

async def main():
    print("Testing Case 1: Purchased 10, current stock 8 (sales occurred) -> Should FAIL")
    items = [{
        "item_id": "item-1",
        "product_id": "prod-A",
        "variant_id": None,
        "batch_id": None,
        "purchased_qty": 10.0,
        "returned_qty": 0.0,
        "qty_to_revert": 10.0,
        "name": "Product A",
        "serials": [],
        "buy_price": 100.0
    }]
    docs = {
        "prod-A": {
            "id": "prod-A",
            "stock_infos": {"physical_stocks": 8.0, "available_stocks": 8.0}
        }
    }

    try:
        await check_cancellation_stock(items, docs)
        assert False, "Should have failed!"
    except HTTPException as e:
        print("-> SUCCESS: Caught expected error:", e.detail)
        assert "Cannot cancel purchase because current available stock for product 'Product A' (8.0) is less than the purchased quantity (10.0)" in e.detail

    print("\nTesting Case 2: Purchased 10, current stock 10 (no sales) -> Should PASS")
    docs["prod-A"]["stock_infos"] = {"physical_stocks": 10.0, "available_stocks": 10.0}
    res = await check_cancellation_stock(items, docs)
    assert res is True
    print("-> SUCCESS: Cancellation allowed when stock == 10.0")

    print("\nTesting Case 3: Purchased 10, current stock 15 (more stock added) -> Should PASS")
    docs["prod-A"]["stock_infos"] = {"physical_stocks": 15.0, "available_stocks": 15.0}
    res = await check_cancellation_stock(items, docs)
    assert res is True
    print("-> SUCCESS: Cancellation allowed when stock > 10.0")

    print("\nTesting Case 4: Product with inventory_units structure, available stock 8 -> Should FAIL")
    docs["prod-A"] = {
        "id": "prod-A",
        "inventory_units": [
            {
                "stock_infos": {"physical_stocks": 10.0, "available_Stocks": 8.0}
            }
        ]
    }
    try:
        await check_cancellation_stock(items, docs)
        assert False, "Should have failed!"
    except HTTPException as e:
        print("-> SUCCESS: Caught expected error with inventory_units:", e.detail)
        assert "is less than the purchased quantity (10.0)" in e.detail

    print("\nALL TEST CASES PASSED!")

if __name__ == "__main__":
    asyncio.run(main())
