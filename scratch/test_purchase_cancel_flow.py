import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import uuid
import datetime
from icecream import ic
from fastapi import HTTPException
from infras.primary_db.main import AsyncInventoryLocalSession, init_inventory_pg_db
from infras.primary_db.models.purchase_model import Purchase, PurchaseItems, PurchaseItemsPricing
from infras.read_db.main import MONGO_CLIENT
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
from schemas.v1.purchase_schemas.request_schema import CancelPurchaseSchema, GetPurchaseByIdSchema
from infras.primary_db.services.purchase_service import PurchaseService

async def test_purchase_cancel_flow():
    print("\n=== STEP 1: Initialize DB Tables & Setup Test Data ===")
    await init_inventory_pg_db()

    shop_id = "test-shop-cancel-" + str(uuid.uuid4())[:8]

    # Product IDs
    prod_1 = "prod-c1-" + str(uuid.uuid4())[:8]
    prod_2 = "prod-c2-" + str(uuid.uuid4())[:8]
    prod_insufficient = "prod-c3-" + str(uuid.uuid4())[:8]

    # Seed Product Inventory in Mongo
    prod_inv_coll = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
    await prod_inv_coll.insert_many([
        {"id": prod_1, "shop_id": shop_id, "name": "Item 1", "stock_infos": {"physical_stocks": 10.0}},
        {"id": prod_2, "shop_id": shop_id, "name": "Item 2", "stock_infos": {"physical_stocks": 5.0}},
        {"id": prod_insufficient, "shop_id": shop_id, "name": "Item Sold", "stock_infos": {"physical_stocks": 4.0}} # Purchased 10, sold 6 -> remaining 4
    ])

    print("\n=== TEST SCENARIO 1: Cancel DRAFT Purchase ===")
    draft_id = str(uuid.uuid4())
    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)

        # Seed Draft Purchase in Postgres
        pur_draft = Purchase(
            id=draft_id,
            ui_id="PUR-DRAFT-01",
            shop_id=shop_id,
            supplier_id="sup-01",
            invoice_no="INV-DRAFT-01",
            type="DIRECT",
            status="DRAFT",
            purchase_view=True,
            gst_infos={},
            calculation_infos={},
            charges_infos={},
            item_infos={},
            payment_infos=[],
            date=datetime.datetime.now().replace(tzinfo=None)
        )
        session.add(pur_draft)
        await session.commit()

        # Seed in Mongo Read DB
        await PurchaseReadDbRepo.add_updatereaddb(
            __import__('infras.read_db.models.purchase_model', fromlist=['PurchaseReadModel']).PurchaseReadModel(
                purchase_id=draft_id,
                ui_id="PUR-DRAFT-01",
                invoice_no="INV-DRAFT-01",
                shop_id=shop_id,
                status="DRAFT",
                supplier={"supplier_id": "sup-1", "supplier_name": "Test Supplier"},
                purchase_date=datetime.datetime.now().replace(tzinfo=None)
            )
        )

        # Cancel Draft
        res_draft = await service.cancel(CancelPurchaseSchema(id=draft_id, shop_id=shop_id))
        ic("Draft Cancel Result =>", res_draft)
        assert res_draft["success"] is True
        assert res_draft["status"] == "CANCELED"

        # Verify DB Status
        check_draft_db = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=draft_id, shop_id=shop_id))
        assert check_draft_db.status == "CANCELED"
        print("-> SUCCESS: Draft Purchase successfully canceled!")

    print("\n=== TEST SCENARIO 2: Cancel COMPLETED Purchase (Sufficient Stock) ===")
    comp_id = str(uuid.uuid4())
    item1_id = str(uuid.uuid4())
    item2_id = str(uuid.uuid4())

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)

        pur_comp = Purchase(
            id=comp_id,
            ui_id="PUR-COMP-01",
            shop_id=shop_id,
            supplier_id="sup-01",
            invoice_no="INV-COMP-01",
            type="DIRECT",
            status="COMPLETED",
            purchase_view=True,
            gst_infos={},
            calculation_infos={},
            charges_infos={},
            item_infos={},
            payment_infos=[],
            date=datetime.datetime.now().replace(tzinfo=None)
        )
        pi1 = PurchaseItems(id=item1_id, purchase_id=comp_id, product_id=prod_1, stocks=10.0, stocks_before=0.0, stocks_after=10.0)
        pi2 = PurchaseItems(id=item2_id, purchase_id=comp_id, product_id=prod_2, stocks=5.0, stocks_before=0.0, stocks_after=5.0)
        session.add_all([pur_comp, pi1, pi2])
        await session.commit()

        # Mongo Read DB doc
        pur_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]
        await pur_coll.insert_one({
            "id": comp_id,
            "purchase_id": comp_id,
            "shop_id": shop_id,
            "ui_id": "PUR-COMP-01",
            "invoice_no": "INV-COMP-01",
            "status": "COMPLETED",
            "items": [
                {"id": item1_id, "product_id": prod_1, "name": "Item 1", "stocks_infos": {"stocks": 10.0}},
                {"id": item2_id, "product_id": prod_2, "name": "Item 2", "stocks_infos": {"stocks": 5.0}}
            ]
        })

        # Cancel Completed Purchase
        res_comp = await service.cancel(CancelPurchaseSchema(id=comp_id, shop_id=shop_id))
        ic("Completed Cancel Result =>", res_comp)
        assert res_comp["success"] is True
        assert res_comp["status"] == "CANCELED"

        # Verify DB Status
        check_comp_db = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=comp_id, shop_id=shop_id))
        assert check_comp_db.status == "CANCELED"

        # Verify Mongo ProdInvCollections stock was decremented
        doc_p1 = await prod_inv_coll.find_one({"id": prod_1, "shop_id": shop_id})
        doc_p2 = await prod_inv_coll.find_one({"id": prod_2, "shop_id": shop_id})
        ic("P1 Stock After Cancel =>", doc_p1["stock_infos"]["physical_stocks"])
        ic("P2 Stock After Cancel =>", doc_p2["stock_infos"]["physical_stocks"])
        assert doc_p1["stock_infos"]["physical_stocks"] == 0.0
        assert doc_p2["stock_infos"]["physical_stocks"] == 0.0
        print("-> SUCCESS: Completed Purchase canceled & stocks decremented!")

    print("\n=== TEST SCENARIO 3: Reject Cancel on Insufficient Stock (Items Sold) ===")
    fail_pur_id = str(uuid.uuid4())
    fail_item_id = str(uuid.uuid4())

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)

        pur_fail = Purchase(
            id=fail_pur_id,
            ui_id="PUR-FAIL-01",
            shop_id=shop_id,
            supplier_id="sup-01",
            invoice_no="INV-FAIL-01",
            type="DIRECT",
            status="COMPLETED",
            purchase_view=True,
            gst_infos={},
            calculation_infos={},
            charges_infos={},
            item_infos={},
            payment_infos=[],
            date=datetime.datetime.now().replace(tzinfo=None)
        )
        pi_fail = PurchaseItems(id=fail_item_id, purchase_id=fail_pur_id, product_id=prod_insufficient, stocks=10.0, stocks_before=0.0, stocks_after=10.0)
        session.add_all([pur_fail, pi_fail])
        await session.commit()

        pur_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]
        await pur_coll.insert_one({
            "id": fail_pur_id,
            "purchase_id": fail_pur_id,
            "shop_id": shop_id,
            "ui_id": "PUR-FAIL-01",
            "invoice_no": "INV-FAIL-01",
            "status": "COMPLETED",
            "items": [
                {"id": fail_item_id, "product_id": prod_insufficient, "name": "Item Sold", "stocks_infos": {"stocks": 10.0}}
            ]
        })

        try:
            await service.cancel(CancelPurchaseSchema(id=fail_pur_id, shop_id=shop_id))
            assert False, "Expected cancellation to fail due to insufficient stock!"
        except HTTPException as ex:
            ic("Insufficient Stock Exception Caught =>", ex.detail)
            assert ex.status_code == 400
            assert "Cannot cancel purchase" in str(ex.detail)

        # Verify DB Status remains COMPLETED
        check_fail_db = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=fail_pur_id, shop_id=shop_id))
        assert check_fail_db.status == "COMPLETED"
        print("-> SUCCESS: Cancellation rejected when stock is insufficient!")

    print("\n=== TEST SCENARIO 4: Reject Cancel on Already Canceled Purchase ===")
    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)
        try:
            await service.cancel(CancelPurchaseSchema(id=comp_id, shop_id=shop_id))
            assert False, "Expected cancellation to fail on already canceled purchase!"
        except HTTPException as ex:
            ic("Already Canceled Exception Caught =>", ex.detail)
            assert ex.status_code == 400
            assert "already canceled" in str(ex.detail)
        print("-> SUCCESS: Already canceled purchase error correctly raised!")

    print("\n=== TEST SCENARIO 5: Reject Cancel on Purchase with Existing Returns ===")
    ret_pur_id = str(uuid.uuid4())
    ret_item_id = str(uuid.uuid4())

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)

        pur_ret = Purchase(
            id=ret_pur_id,
            ui_id="PUR-RET-01",
            shop_id=shop_id,
            supplier_id="sup-01",
            invoice_no="INV-RET-01",
            type="DIRECT",
            status="COMPLETED",
            purchase_view=True,
            gst_infos={},
            calculation_infos={},
            charges_infos={},
            item_infos={},
            payment_infos=[],
            date=datetime.datetime.now().replace(tzinfo=None)
        )
        pi_ret = PurchaseItems(id=ret_item_id, purchase_id=ret_pur_id, product_id=prod_1, stocks=10.0, stocks_before=0.0, stocks_after=10.0)
        session.add_all([pur_ret, pi_ret])
        await session.commit()

        pur_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]
        await pur_coll.insert_one({
            "id": ret_pur_id,
            "purchase_id": ret_pur_id,
            "shop_id": shop_id,
            "ui_id": "PUR-RET-01",
            "invoice_no": "INV-RET-01",
            "status": "COMPLETED",
            "returns": [{"id": "ret-01", "total_refund_qty": 2.0}],
            "items": [
                {"id": ret_item_id, "product_id": prod_1, "name": "Item Returned", "returned_quantity": 2.0, "stocks_infos": {"stocks": 10.0}}
            ]
        })

        try:
            await service.cancel(CancelPurchaseSchema(id=ret_pur_id, shop_id=shop_id))
            assert False, "Expected cancellation to fail due to existing returns!"
        except HTTPException as ex:
            ic("Existing Returns Exception Caught =>", ex.detail)
            assert ex.status_code == 400
            assert "existing purchase returns" in str(ex.detail)

        # Verify DB Status remains COMPLETED
        check_ret_db = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=ret_pur_id, shop_id=shop_id))
        assert check_ret_db.status == "COMPLETED"
        print("-> SUCCESS: Cancellation rejected when purchase has existing returns!")

    print("\n==========================================")
    print("ALL PURCHASE CANCEL TESTS PASSED SUCCESSFULLY!")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(test_purchase_cancel_flow())
