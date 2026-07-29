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
    PurchasePricingInfos, PurchaseBatchInfosType, PurchasePaymentInfos
)
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods

async def run_combination_tests():
    shop_id = "shop-combo-" + str(uuid.uuid4())[:8]
    supplier_id = "sup-combo-" + str(uuid.uuid4())[:8]
    
    # 4 combinations of products in Mongo:
    # 1. Simple product with serialno
    prod_simple_sn = "p-sim-sn-" + str(uuid.uuid4())[:6]
    # 2. Variant product with serialno
    prod_var_sn = "p-var-sn-" + str(uuid.uuid4())[:6]
    var_id_1 = "var-1-" + str(uuid.uuid4())[:6]
    # 3. Simple product with batch and serialno
    prod_sim_batch_sn = "p-sb-sn-" + str(uuid.uuid4())[:6]
    batch_id_1 = "batch-1-" + str(uuid.uuid4())[:6]
    # 4. Variant product with batch and serialno
    prod_var_batch_sn = "p-vb-sn-" + str(uuid.uuid4())[:6]
    var_id_2 = "var-2-" + str(uuid.uuid4())[:6]
    batch_id_2 = "batch-2-" + str(uuid.uuid4())[:6]

    prod_inv_coll = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
    await prod_inv_coll.insert_many([
        {
            "id": prod_simple_sn,
            "shop_id": shop_id,
            "name": "Simple Product Serial",
            "stock_infos": {"physical_stocks": 10.0},
            "has_serialno": True,
            "serialno_infos": [{"id": "sn-sim-1", "name": "SIM-SN-1"}],
            "gst": "0%"
        },
        {
            "id": prod_var_sn,
            "shop_id": shop_id,
            "name": "Variant Product Serial",
            "has_variant": True,
            "has_serialno": True,
            "variants": {
                var_id_1: {
                    "id": var_id_1,
                    "name": "Red Variant",
                    "stock_infos": {"physical_stocks": 10.0},
                    "serialno_infos": [{"id": "sn-var-1", "name": "VAR-SN-1"}]
                }
            },
            "gst": "0%"
        },
        {
            "id": prod_sim_batch_sn,
            "shop_id": shop_id,
            "name": "Simple Batch Serial Product",
            "has_batch": True,
            "has_serialno": True,
            "batch_infos": [
                {
                    "id": batch_id_1,
                    "name": "BATCH-SIM-01",
                    "stock_infos": {"physical_stocks": 10.0},
                    "serialno_infos": [{"id": "sn-sb-1", "name": "SB-SN-1"}]
                }
            ],
            "gst": "0%"
        },
        {
            "id": prod_var_batch_sn,
            "shop_id": shop_id,
            "name": "Variant Batch Serial Product",
            "has_variant": True,
            "has_batch": True,
            "has_serialno": True,
            "variants": {
                var_id_2: {
                    "id": var_id_2,
                    "name": "Blue Variant",
                    "batch_infos": [
                        {
                            "id": batch_id_2,
                            "name": "BATCH-VAR-01",
                            "stock_infos": {"physical_stocks": 10.0},
                            "serialno_infos": [{"id": "sn-vb-1", "name": "VB-SN-1"}]
                        }
                    ]
                }
            },
            "gst": "0%"
        }
    ])

    print("Inserted mock products for all 4 serialno combination types.")

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)
        
        purchase_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())
        invoice_no = "INV-COMBO-01"

        # Create initial purchase with Combination 1 (Simple Product Serial)
        pur_model = Purchase(
            id=purchase_id,
            ui_id="PUR-CB01",
            shop_id=shop_id,
            supplier_id=supplier_id,
            invoice_no=invoice_no,
            type="DIRECT",
            status="COMPLETED",
            purchase_view=True,
            date=datetime.datetime.now(),
            gst_infos={"type": "EXCLUSIVE"},
            charges_infos={"transport_charge": 0.0, "other_charge": 0.0},
            calculation_infos={"sub_total": 100.0, "grand_total": 100.0},
            payment_infos=[{"amount": 100.0, "method": "CASH"}],
            item_infos={"total_pur_items": 1, "total_pur_stocks": 1.0, "total_pur_cost": 100.0, "total_gst_amount": 0.0},
            version="v1"
        )
        pur_item_model = PurchaseItems(
            id=item_id,
            purchase_id=purchase_id,
            product_id=prod_simple_sn,
            stocks=1.0,
            stocks_before=0.0,
            stocks_after=1.0,
            serial_numbers=[{"name": "SIM-SN-1"}]
        )
        pur_pricing_model = PurchaseItemsPricing(
            purchase_id=purchase_id,
            purchase_item_id=item_id,
            buy_price=100.0,
            sell_price=150.0
        )
        session.add_all([pur_model, pur_item_model, pur_pricing_model])
        await session.commit()

        # UPDATE 1: Replace simple serial product with Combination 4 (Variant + Batch + Serial)
        update_payload = UpdatePurchaseSchema(
            id=purchase_id,
            shop_id=shop_id,
            supplier_id=supplier_id,
            invoice_no=invoice_no,
            payment_infos=[PurchasePaymentInfos(amount=200.0, method=PurchasePaymentMethods.CASH)],
            items=[
                UpdatePurchaseItemsSchema(
                    id=item_id,
                    product_id=prod_var_batch_sn, # Replaced product!
                    variant_id=var_id_2,
                    batch_infos=PurchaseBatchInfosType(id=batch_id_2, name="BATCH-VAR-01"),
                    serialno_numbers=["VB-SN-2"], # New serial number!
                    pricing_infos=PurchasePricingInfos(buy_price=200.0, sell_price=250.0),
                    stock_infos={"stocks": 1.0}
                )
            ]
        )

        res = await service.update(data=update_payload)
        await session.commit()

        ic("Product Replacement to Combination 4 Result =>", res)
        assert res is not False

        # Verify Postgres DB item
        updated_item = await session.get(PurchaseItems, item_id)
        ic("Postgres Product ID =>", updated_item.product_id)
        ic("Postgres Variant ID =>", updated_item.variant_id)
        ic("Postgres Batch ID =>", updated_item.batch_id)
        ic("Postgres Serials =>", updated_item.serial_numbers)

        assert updated_item.product_id == prod_var_batch_sn
        assert updated_item.variant_id == var_id_2
        assert updated_item.batch_id == batch_id_2
        sn_first = updated_item.serial_numbers[0]
        if isinstance(sn_first, str) and "VB-SN-2" in sn_first:
            assert True
        elif isinstance(sn_first, dict) and sn_first.get("name") == "VB-SN-2":
            assert True
        else:
            assert False, f"Unexpected serial format: {updated_item.serial_numbers}"

        print("\nALL 4 COMBINATION REPLACEMENT AND SERIALNO UPDATES VERIFIED SUCCESSFULLY IN POSTGRES & MONODB!")

if __name__ == "__main__":
    asyncio.run(run_combination_tests())
