import asyncio
import uuid
import datetime
from icecream import ic
from schemas.v1.purchase_schemas.request_schema import (
    CreatePurchaseSchema, CreatePurchaseItemsSchema,
    UpdatePurchaseSchema,
    PurchasePricingInfos, PurchaseStocksInfosType,
    PurchaseCalculationInfos, PurchaseGstInfos,
    PurchaseChargeInfos, PurchasePaymentInfos
)
from schemas.v1.purchase_schemas.db_schemas import (
    CreatePurchaseDbSchema, UpdatePurchaseDbSchema
)
from infras.primary_db.models.purchase_model import Purchase
from infras.read_db.models.purchase_model import PurchaseReadModel
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums, PurchasePaymentMethods

def test_schema_and_models():
    test_notes = "Delivered at the rear warehouse entrance. Handle with care."
    
    # 1. Test CreatePurchaseSchema
    create_payload = CreatePurchaseSchema(
        shop_id="shop-123",
        supplier_id="sup-123",
        type=PurchaseTypeEnums.DIRECT,
        status="COMPLETED",
        invoice_no="INV-001",
        notes=test_notes,
        purchase_date=datetime.date.today(),
        calculation_infos=PurchaseCalculationInfos(
            total_pur_items=1,
            total_pur_cost=100.0,
            total_gst_amount=0.0,
            distribute_by="BY_VALUE",
            round_off=0.0
        ),
        gst_infos=PurchaseGstInfos(type="EXCLUSIVE"),
        charges_infos=PurchaseChargeInfos(transport_charge=0.0, other_charge=0.0),
        payment_infos=[
            PurchasePaymentInfos(amount=100.0, method=PurchasePaymentMethods.CASH)
        ],
        items=[
            CreatePurchaseItemsSchema(
                product_id="prod-1",
                pricing_infos=PurchasePricingInfos(buy_price=10.0, sell_price=15.0),
                gst="0%",
                stock_infos=PurchaseStocksInfosType(stocks=10.0, stocks_before=0.0, stocks_after=10.0)
            )
        ]
    )
    assert create_payload.notes == test_notes
    dumped = create_payload.model_dump(mode="json")
    assert dumped["notes"] == test_notes
    print("[PASS] CreatePurchaseSchema validated with notes")

    # 2. Test UpdatePurchaseSchema
    update_payload = UpdatePurchaseSchema(
        id="pur-123",
        shop_id="shop-123",
        notes="Updated notes"
    )
    assert update_payload.notes == "Updated notes"
    print("[PASS] UpdatePurchaseSchema validated with notes")

    # 3. Test CreatePurchaseDbSchema & UpdatePurchaseDbSchema
    create_db = CreatePurchaseDbSchema(
        shop_id="shop-123",
        supplier_id="sup-123",
        type=PurchaseTypeEnums.DIRECT,
        calculation_infos=create_payload.calculation_infos,
        charges_infos=create_payload.charges_infos,
        payment_infos=create_payload.payment_infos,
        purchase_date=datetime.date.today(),
        notes=test_notes
    )
    assert create_db.notes == test_notes

    update_db = UpdatePurchaseDbSchema(
        id="pur-123",
        shop_id="shop-123",
        notes="Updated notes"
    )
    assert update_db.notes == "Updated notes"
    print("[PASS] CreatePurchaseDbSchema & UpdatePurchaseDbSchema validated with notes")

    # 4. Test Purchase ORM Model
    p_model = Purchase(
        id="pur-123",
        ui_id="PUR-123456",
        shop_id="shop-123",
        supplier_id="sup-123",
        notes=test_notes,
        type="DIRECT",
        status="COMPLETED",
        purchase_view=True,
        calculation_infos={},
        charges_infos={},
        item_infos={},
        payment_infos=[],
        date=datetime.datetime.now(),
        gst_infos={}
    )
    assert p_model.notes == test_notes
    print("[PASS] Purchase ORM model column validated with notes")

    # 5. Test PurchaseReadModel
    p_read = PurchaseReadModel(
        purchase_id="pur-123",
        ui_id="PUR-123456",
        invoice_no="INV-001",
        notes=test_notes,
        shop_id="shop-123",
        purchase_date=datetime.datetime.now(),
        supplier={"supplier_id": "sup-123", "supplier_name": "Supplier A"}
    )
    assert p_read.notes == test_notes
    read_dumped = p_read.model_dump(mode="json")
    assert read_dumped["notes"] == test_notes
    print("[PASS] PurchaseReadModel validated with notes")

    print("\nALL SCHEMA & MODEL VALIDATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_schema_and_models()
