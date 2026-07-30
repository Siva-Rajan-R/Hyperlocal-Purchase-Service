import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import uuid
import datetime
from icecream import ic
from sqlalchemy import select
from fastapi import HTTPException
from infras.primary_db.main import AsyncInventoryLocalSession, init_inventory_pg_db
from infras.primary_db.models.purchase_model import Purchase, PurchaseItems, PurchaseItemsPricing, PurchaseReturns, PurchaseReturnItems
from infras.read_db.main import MONGO_CLIENT
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
from schemas.v1.purchase_schemas.return_schema import CreatePurchaseReturnSchema, ReturnItemRequestSchema
from infras.primary_db.services.return_service import ReturnService
from messaging.msgqueue_producers.purchase_return_msgqueue_producer import MessagingQueuePurchaseReturnProducer

async def test_full_return_flow():
    print("=== STEP 1: Initialize Database Tables ===")
    await init_inventory_pg_db()

    shop_id = "test-shop-" + str(uuid.uuid4())[:8]
    purchase_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    product_id = "prod-" + str(uuid.uuid4())[:8]

    # Seed Product Inventory document in Mongo ProdInvCollections with physical_stocks = 2.0
    prod_inv_coll = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
    await prod_inv_coll.insert_one({
        "id": product_id,
        "shop_id": shop_id,
        "name": "Test Physical Product",
        "stock_infos": {"physical_stocks": 2.0}
    })

    print(f"=== STEP 2: Inserting Initial Purchase (ID: {purchase_id}, Purchased Qty: 5.0) ===")
    async with AsyncInventoryLocalSession() as session:
        pur = Purchase(
            id=purchase_id,
            ui_id="PUR-TEST01",
            shop_id=shop_id,
            supplier_id="sup-01",
            invoice_no="INV-100",
            type="OFFLINE",
            status="COMPLETED",
            purchase_view=True,
            gst_infos={},
            calculation_infos={"sub_total": 500.0, "total": 500.0},
            charges_infos={},
            item_infos={},
            payment_infos=[{"method": "CASH", "amount": 500.0}],
            date=datetime.datetime.now().replace(tzinfo=None)
        )
        pur_item = PurchaseItems(
            id=item_id,
            purchase_id=purchase_id,
            product_id=product_id,
            stocks=5.0,
            stocks_before=0.0,
            stocks_after=5.0
        )
        pur_pricing = PurchaseItemsPricing(
            purchase_id=purchase_id,
            purchase_item_id=item_id,
            buy_price=100.0,
            sell_price=150.0
        )
        session.add_all([pur, pur_item, pur_pricing])
        await session.commit()

    # Insert into Mongo PurchaseReadDb
    pur_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]
    mongo_doc = {
        "id": purchase_id,
        "purchase_id": purchase_id,
        "shop_id": shop_id,
        "ui_id": "PUR-TEST01",
        "supplier_id": "sup-01",
        "status": "COMPLETED",
        "items": [
            {
                "id": item_id,
                "product_id": product_id,
                "name": "Test Physical Product",
                "ui_id": "PRD-001",
                "stocks_infos": {
                    "stocks": 5.0,
                    "stocks_before": 0.0,
                    "stocks_after": 5.0
                },
                "buy_price": 100.0,
                "sell_price": 150.0,
                "unit_infos": {"name": "Piece", "sub_units": []},
                "returned_quantity": 0.0,
                "returns": []
            }
        ],
        "returns": []
    }
    await pur_coll.insert_one(mongo_doc)

    print("\n=== STEP 3: Testing Physical Stock Insufficiency Check ===")
    # Try returning 4 units when physical stock in store is only 2.0 (because 3 were sold to customers)
    exceed_return_schema = CreatePurchaseReturnSchema(
        purchase_id=purchase_id,
        shop_id=shop_id,
        payment_infos={"CASH": {"amount": 400.0}},
        items=[
            ReturnItemRequestSchema(
                purchase_item_id=item_id,
                quantity=4.0,
                unit="Piece",
                reason="Attempt to return more than physical stock"
            )
        ]
    )

    async with AsyncInventoryLocalSession() as session:
        service = ReturnService(session=session)
        try:
            await service.process_return(data=exceed_return_schema)
            assert False, "Should have failed physical stock check!"
        except HTTPException as exc:
            print(f"SUCCESS: Physical stock check correctly blocked return: {exc.detail}")
            assert "physical stock" in str(exc.detail).lower()

    print("\n=== STEP 4: Testing Valid Purchase Return (Returning 2 units) ===")
    # Update physical stock in Mongo ProdInvCollections to 5.0 for valid return
    await prod_inv_coll.update_one({"id": product_id, "shop_id": shop_id}, {"$set": {"stock_infos.physical_stocks": 5.0}})

    valid_return_schema = CreatePurchaseReturnSchema(
        purchase_id=purchase_id,
        shop_id=shop_id,
        payment_infos={"CASH": {"amount": 200.0}},
        items=[
            ReturnItemRequestSchema(
                purchase_item_id=item_id,
                quantity=2.0,
                unit="Piece",
                reason="Damaged item return"
            )
        ]
    )

    async with AsyncInventoryLocalSession() as session:
        service = ReturnService(session=session)
        res = await service.process_return(data=valid_return_schema)
        print("Valid return process result:", res)
        assert res is True

    print("\n=======================================================")
    print("SUCCESS: ALL PHYSICAL STOCK CHECKS PASSED PERFECTLY!")
    print("1. Returns are blocked if physical stock < return quantity.")
    print("2. Returns succeed when physical stock is sufficient.")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(test_full_return_flow())
