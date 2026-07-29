import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    PurchasePaymentInfos, PurchaseBatchInfosType
)
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods

async def test_all_types():
    shop_id = "shop-all-" + str(uuid.uuid4())[:8]
    supplier_id = "sup-" + str(uuid.uuid4())[:8]
    
    prod_simple_batch_id = "prod-sb-" + str(uuid.uuid4())[:8]
    prod_var_batch_id = "prod-vb-" + str(uuid.uuid4())[:8]
    prod_serial_id = "prod-sn-" + str(uuid.uuid4())[:8]
    
    batch_1_id = "batch-1-" + str(uuid.uuid4())[:8]
    batch_2_id = "batch-2-" + str(uuid.uuid4())[:8]
    variant_1_id = "var-1-" + str(uuid.uuid4())[:8]
    
    invoice_no = "INV-ALL-" + str(uuid.uuid4())[:6]
    purchase_id = str(uuid.uuid4())

    # 1. Setup Mongo ProdInvCollections documents
    prod_inv_coll = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
    await prod_inv_coll.insert_many([
        {
            "id": prod_simple_batch_id,
            "shop_id": shop_id,
            "name": "Simple Product With Batch",
            "type_infos": {"has_batch": True, "has_serialno": False},
            "stock_infos": {"physical_stocks": 100.0},
            "batch_infos": [
                {
                    "id": batch_1_id,
                    "name": "Batch-001",
                    "manufacturing_date": "2026-01-01",
                    "expiry_date": "2027-01-01",
                    "stock_infos": {"physical_stocks": 100.0}
                }
            ],
            "gst": "0%"
        },
        {
            "id": prod_var_batch_id,
            "shop_id": shop_id,
            "name": "Variant Product With Batch",
            "type_infos": {"has_batch": True, "has_serialno": False},
            "stock_infos": {"physical_stocks": 50.0},
            "variants": [
                {"id": variant_1_id, "name": "Size-L"}
            ],
            "batch_infos": [
                {
                    "id": batch_2_id,
                    "name": "Batch-002",
                    "manufacturing_date": "2026-02-01",
                    "expiry_date": "2027-02-01",
                    "stock_infos": {"physical_stocks": 50.0}
                }
            ],
            "gst": "0%"
        },
        {
            "id": prod_serial_id,
            "shop_id": shop_id,
            "name": "Serial Number Product",
            "type_infos": {"has_batch": False, "has_serialno": True},
            "stock_infos": {"physical_stocks": 10.0},
            "gst": "0%"
        }
    ])

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)
        
        print("\n=======================================================")
        print("STEP 1: CREATING INITIAL PURCHASE IN POSTGRES (Initial Item)")
        print("=======================================================")
        
        item_init_id = str(uuid.uuid4())
        pur_model = Purchase(
            id=purchase_id,
            ui_id="PUR-ALL",
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
        pur_item_model = PurchaseItems(
            id=item_init_id,
            purchase_id=purchase_id,
            product_id=prod_simple_batch_id,
            batch_id=batch_1_id,
            gst="0%",
            stocks=10.0,
            stocks_before=0.0,
            stocks_after=10.0
        )
        pur_pricing_model = PurchaseItemsPricing(
            purchase_id=purchase_id,
            purchase_item_id=item_init_id,
            buy_price=100.0,
            sell_price=150.0
        )
        
        session.add(pur_model)
        session.add(pur_item_model)
        session.add(pur_pricing_model)
        await session.commit()
        ic("Initial Purchase Created =>", purchase_id)

        print("\n=======================================================")
        print("STEP 2: UPDATING PURCHASE WITH ALL 3 PRODUCT TYPES (Replacing Initial Item)")
        print("=======================================================")
        
        update_payload = UpdatePurchaseSchema(
            id=purchase_id,
            shop_id=shop_id,
            supplier_id=supplier_id,
            invoice_no=invoice_no,
            purchase_date="2026-07-28",
            payment_infos=[
                PurchasePaymentInfos(amount=1000.0, method=PurchasePaymentMethods.CASH)
            ],
            items=[
                # 1. Update Existing Simple Product with Batch
                UpdatePurchaseItemsSchema(
                    id=item_init_id,
                    product_id=prod_simple_batch_id,
                    batch_infos=PurchaseBatchInfosType(id=batch_1_id, name="Batch-001"),
                    pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=5.0)
                ),
                # 2. Add Variant Product with Batch
                UpdatePurchaseItemsSchema(
                    id="", # New item
                    product_id=prod_var_batch_id,
                    variant_id=variant_1_id,
                    batch_infos=PurchaseBatchInfosType(id=batch_2_id, name="Batch-002"),
                    pricing_infos=PurchasePricingInfos(buy_price=80.0, sell_price=120.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=5.0)
                ),
                # 3. Add Serial Number Product
                UpdatePurchaseItemsSchema(
                    id="", # New item
                    product_id=prod_serial_id,
                    serialno_numbers=["SN-001", "SN-002"],
                    pricing_infos=PurchasePricingInfos(buy_price=50.0, sell_price=80.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=2.0)
                )
            ]
        )
        
        upd_res = await service.update(update_payload)
        ic("Update All Types Result =>", upd_res)
        assert upd_res is True

        print("\n=======================================================")
        print("STEP 3: VERIFYING MONGO READ DB ITEMS & BATCH/VARIANT/SERIAL INFOS")
        print("=======================================================")
        
        pur_mongo_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]
        pur_mongo_doc = await pur_mongo_coll.find_one({"purchase_id": purchase_id, "shop_id": shop_id})
        assert pur_mongo_doc is not None
        
        read_items = pur_mongo_doc.get("items", [])
        ic("Read DB Items Count =>", len(read_items))
        assert len(read_items) == 3
        
        found_simple_batch = False
        found_variant_batch = False
        found_serial = False
        
        for item in read_items:
            ic("READ ITEM =>", item.get("name"), "BATCH INFOS =>", item.get("batch_infos"), "VARIANT INFOS =>", item.get("variant_infos"), "SERIALS =>", item.get("serial_numbers"))
            if item.get("product_id") == prod_simple_batch_id:
                assert item.get("batch_infos") is not None, "Simple product batch_infos should not be None"
                assert item["batch_infos"]["name"] == "Batch-001"
                found_simple_batch = True
            elif item.get("product_id") == prod_var_batch_id:
                assert item.get("batch_infos") is not None, "Variant product batch_infos should not be None"
                assert item["batch_infos"]["name"] == "Batch-002"
                assert item.get("variant_infos") is not None, "Variant product variant_infos should not be None"
                assert item["variant_infos"]["name"] == "Size-L"
                found_variant_batch = True
            elif item.get("product_id") == prod_serial_id:
                assert len(item.get("serial_numbers", [])) == 2
                assert "SN-001" in item["serial_numbers"]
                found_serial = True
                
        assert found_simple_batch and found_variant_batch and found_serial

        print("\n=======================================================")
        print("ALL 3 PRODUCT TYPES (Simple+Batch, Variant+Batch, Serials) VERIFIED SUCCESSFULLY!")
        print("=======================================================")

        # Clean up test documents
        await prod_inv_coll.delete_many({"shop_id": shop_id})
        await pur_mongo_coll.delete_many({"purchase_id": purchase_id})

if __name__ == "__main__":
    asyncio.run(test_all_types())
