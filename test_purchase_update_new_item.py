"""
Test: Purchase Update - New Item Addition (Bug Reproduction & Fix Verification)

Scenario from the user:
- Create a purchase with Product A only
- Later, update the purchase to add Product B (genuinely new, no ID in payload)
- Verify: Only ONE Product B item is created (no duplicate)
- Verify: stocks_infos values are correct

Also tests:
- Re-sending an existing item WITHOUT its DB id -> should UPDATE, not duplicate
"""

import asyncio
import uuid
import datetime
from icecream import ic
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.services.purchase_service import PurchaseService
from infras.primary_db.models.purchase_model import Purchase, PurchaseItems, PurchaseItemsPricing
from infras.read_db.main import MONGO_CLIENT
from schemas.v1.purchase_schemas.request_schema import (
    UpdatePurchaseSchema, UpdatePurchaseItemsSchema,
    GetPurchaseByIdSchema,
    PurchasePricingInfos, PurchaseStocksInfosType,
    PurchasePaymentInfos
)
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods


async def setup_purchase_with_product_a(
    session, shop_id, purchase_id, item_a_id,
    prod_a_id, supplier_id, invoice_no
):
    pur_model = Purchase(
        id=purchase_id,
        ui_id="PUR-" + purchase_id[:6].upper(),
        shop_id=shop_id,
        supplier_id=supplier_id,
        invoice_no=invoice_no,
        type="DIRECT",
        status="COMPLETED",
        purchase_view=True,
        date=datetime.datetime.now(),
        gst_infos={"type": "EXCLUSIVE"},
        charges_infos={"transport_charge": 0.0, "other_charge": 0.0},
        calculation_infos={"sub_total": 1000.0, "grand_total": 1000.0},
        payment_infos=[{"amount": 1000.0, "method": "CASH"}],
        item_infos={
            "total_pur_items": 1,
            "total_pur_stocks": 10.0,
            "total_pur_cost": 1000.0,
            "total_gst_amount": 0.0
        },
        version="v1"
    )
    pur_item_a = PurchaseItems(
        id=item_a_id,
        purchase_id=purchase_id,
        product_id=prod_a_id,
        gst="0%",
        stocks=10.0,
        stocks_before=90.0,
        stocks_after=100.0
    )
    pur_pricing_a = PurchaseItemsPricing(
        purchase_id=purchase_id,
        purchase_item_id=item_a_id,
        buy_price=100.0,
        sell_price=150.0
    )
    session.add(pur_model)
    session.add(pur_item_a)
    session.add(pur_pricing_a)
    await session.commit()


async def test_add_genuinely_new_product_during_update():
    shop_id = "test-shop-" + str(uuid.uuid4())[:8]
    supplier_id = "sup-" + str(uuid.uuid4())[:8]
    prod_a_id = "prod-a-" + str(uuid.uuid4())[:8]
    prod_b_id = "prod-b-" + str(uuid.uuid4())[:8]
    purchase_id = str(uuid.uuid4())
    item_a_id = str(uuid.uuid4())
    invoice_no = "INV-NEW-" + str(uuid.uuid4())[:6]

    prod_inv_coll = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
    pur_mongo_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]

    await prod_inv_coll.insert_many([
        {
            "id": prod_a_id, "shop_id": shop_id, "name": "Product A",
            "stock_infos": {"physical_stocks": 100.0}, "gst": "0%",
            "type_infos": {"has_batch": False, "has_variant": False, "has_serialno": False},
            "have_tracking": True
        },
        {
            "id": prod_b_id, "shop_id": shop_id, "name": "Product B",
            "stock_infos": {"physical_stocks": 10.0}, "gst": "0%",
            "type_infos": {"has_batch": False, "has_variant": False, "has_serialno": False},
            "have_tracking": True
        }
    ])

    async with AsyncInventoryLocalSession() as session:
        await setup_purchase_with_product_a(
            session, shop_id, purchase_id, item_a_id, prod_a_id, supplier_id, invoice_no
        )

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)

        print("\n=== TEST 1: Add genuinely new Product B (no ID) to existing purchase ===")

        update_payload = UpdatePurchaseSchema(
            id=purchase_id,
            shop_id=shop_id,
            supplier_id=supplier_id,
            invoice_no=invoice_no,
            purchase_date="2026-07-27",
            payment_infos=[
                PurchasePaymentInfos(amount=1000.0, method=PurchasePaymentMethods.CASH)
            ],
            items=[
                UpdatePurchaseItemsSchema(
                    id=item_a_id,
                    product_id=prod_a_id,
                    pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=10.0, stocks_before=90.0, stocks_after=100.0)
                ),
                UpdatePurchaseItemsSchema(
                    id="",
                    product_id=prod_b_id,
                    pricing_infos=PurchasePricingInfos(buy_price=50.0, sell_price=75.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=10.0, stocks_before=10.0, stocks_after=20.0)
                ),
            ]
        )

        result = await service.update(update_payload)
        assert result is True, "Update should succeed"

        fresh_pur = await service.purchase_repo_obj.get_purchase_by_id(
            GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id)
        )

        assert len(fresh_pur.items) == 2, f"Expected 2 items, got {len(fresh_pur.items)}"
        
        b_items = [i for i in fresh_pur.items if i.product_id == prod_b_id]
        assert len(b_items) == 1, f"Expected exactly 1 Product B item, got {len(b_items)}"
        b_item = b_items[0]

        ic("B stocks:", b_item.stocks, "stocks_before:", b_item.stocks_before, "stocks_after:", b_item.stocks_after)
        assert b_item.stocks == 10.0, f"Product B stocks should be 10, got {b_item.stocks}"
        assert b_item.stocks_before == 10.0, f"stocks_before should be 10, got {b_item.stocks_before}"
        assert b_item.stocks_after == 20.0, f"stocks_after should be 20, got {b_item.stocks_after}"

        mongo_doc = await pur_mongo_coll.find_one({"purchase_id": purchase_id, "shop_id": shop_id})
        if mongo_doc:
            mongo_items = mongo_doc.get("items", [])
            ic("Mongo items count:", len(mongo_items))
            assert len(mongo_items) == 2, f"Mongo should have 2 items, got {len(mongo_items)}"
            item_infos = mongo_doc.get("item_infos", {})
            ic("item_infos:", item_infos)
            assert item_infos.get("total_pur_stocks") == 20.0, f"total_pur_stocks should be 20, got {item_infos.get('total_pur_stocks')}"

        print("PASSED: Genuinely new Product B added without duplication!")

    await prod_inv_coll.delete_many({"shop_id": shop_id})
    await pur_mongo_coll.delete_many({"purchase_id": purchase_id})


async def test_resend_existing_item_without_id_treated_as_update():
    shop_id = "test-shop-" + str(uuid.uuid4())[:8]
    supplier_id = "sup-" + str(uuid.uuid4())[:8]
    prod_a_id = "prod-a-" + str(uuid.uuid4())[:8]
    prod_b_id = "prod-b-" + str(uuid.uuid4())[:8]
    purchase_id = str(uuid.uuid4())
    item_a_id = str(uuid.uuid4())
    item_b_id = str(uuid.uuid4())
    invoice_no = "INV-DUP-" + str(uuid.uuid4())[:6]

    prod_inv_coll = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
    pur_mongo_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]

    await prod_inv_coll.insert_many([
        {
            "id": prod_a_id, "shop_id": shop_id, "name": "Product A",
            "stock_infos": {"physical_stocks": 95.0}, "gst": "0%",
            "type_infos": {"has_batch": False, "has_variant": False, "has_serialno": False},
            "have_tracking": True
        },
        {
            "id": prod_b_id, "shop_id": shop_id, "name": "Product B",
            "stock_infos": {"physical_stocks": 20.0}, "gst": "0%",
            "type_infos": {"has_batch": False, "has_variant": False, "has_serialno": False},
            "have_tracking": True
        }
    ])

    async with AsyncInventoryLocalSession() as session:
        pur_model = Purchase(
            id=purchase_id,
            ui_id="PUR-" + purchase_id[:6].upper(),
            shop_id=shop_id,
            supplier_id=supplier_id,
            invoice_no=invoice_no,
            type="DIRECT",
            status="COMPLETED",
            purchase_view=True,
            date=datetime.datetime.now(),
            gst_infos={"type": "EXCLUSIVE"},
            charges_infos={"transport_charge": 0.0, "other_charge": 0.0},
            calculation_infos={"sub_total": 1500.0, "grand_total": 1500.0},
            payment_infos=[{"amount": 1500.0, "method": "CASH"}],
            item_infos={
                "total_pur_items": 2, "total_pur_stocks": 15.0,
                "total_pur_cost": 1500.0, "total_gst_amount": 0.0
            },
            version="v1"
        )
        pur_item_a = PurchaseItems(id=item_a_id, purchase_id=purchase_id, product_id=prod_a_id, gst="0%", stocks=5.0, stocks_before=90.0, stocks_after=95.0)
        pur_item_b = PurchaseItems(id=item_b_id, purchase_id=purchase_id, product_id=prod_b_id, gst="0%", stocks=10.0, stocks_before=10.0, stocks_after=20.0)
        pur_pricing_a = PurchaseItemsPricing(purchase_id=purchase_id, purchase_item_id=item_a_id, buy_price=200.0, sell_price=300.0)
        pur_pricing_b = PurchaseItemsPricing(purchase_id=purchase_id, purchase_item_id=item_b_id, buy_price=100.0, sell_price=150.0)
        session.add_all([pur_model, pur_item_a, pur_item_b, pur_pricing_a, pur_pricing_b])
        await session.commit()

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)

        print("\n=== TEST 2: Re-send existing Product B WITHOUT ID => should UPDATE not duplicate ===")

        update_payload = UpdatePurchaseSchema(
            id=purchase_id,
            shop_id=shop_id,
            supplier_id=supplier_id,
            invoice_no=invoice_no,
            purchase_date="2026-07-27",
            payment_infos=[
                PurchasePaymentInfos(amount=1500.0, method=PurchasePaymentMethods.CASH)
            ],
            items=[
                UpdatePurchaseItemsSchema(
                    id=item_a_id,
                    product_id=prod_a_id,
                    pricing_infos=PurchasePricingInfos(buy_price=200.0, sell_price=300.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=5.0, stocks_before=90.0, stocks_after=95.0)
                ),
                UpdatePurchaseItemsSchema(
                    id="",
                    product_id=prod_b_id,
                    pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=10.0, stocks_before=10.0, stocks_after=20.0)
                ),
            ]
        )

        result = await service.update(update_payload)
        assert result is True, "Update should succeed"

        fresh_pur = await service.purchase_repo_obj.get_purchase_by_id(
            GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id)
        )

        assert len(fresh_pur.items) == 2, f"Expected 2 items (no duplicate B), got {len(fresh_pur.items)}"
        b_items = [i for i in fresh_pur.items if i.product_id == prod_b_id]
        assert len(b_items) == 1, f"Expected exactly 1 Product B, got {len(b_items)}"

        print("PASSED: Re-sending Product B without ID correctly treated as UPDATE, no duplicate!")

    await prod_inv_coll.delete_many({"shop_id": shop_id})
    await pur_mongo_coll.delete_many({"purchase_id": purchase_id})


async def run_all_tests():
    print("\n" + "=" * 60)
    print("PURCHASE UPDATE: NEW ITEM ADDITION BUG TESTS")
    print("=" * 60)
    await test_add_genuinely_new_product_during_update()
    await test_resend_existing_item_without_id_treated_as_update()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
