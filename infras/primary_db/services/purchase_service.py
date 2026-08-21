from models.service_models.base_service_model import BaseServiceModel
from ..repos.purchase_repo import PurchaseRepo

from core.data_formats.enums.stock_adj_enums import StockAdjustmentMovementType,StockAdjustmentTypesEnum
from typing import Optional,List
from ..models.purchase_model import Purchase,PurchaseItems,PurchaseItemsPricing,PurchaseItemsStoragelocation,PurchaseItemsReorderPoint
from sqlalchemy.ext.asyncio import AsyncSession
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from schemas.v1.purchase_schemas.db_schemas import CreatePurchaseDbSchema,CreatePurchaseItemsDbSchema,CreatePurchasePricingDbSchema,CreateStorageLocationDbSchema,UpdatePurchaseDbSchema,UpdatePurchaseItemsDbSchema,UpdatePurchasePricingDbSchema,UpdateStorageLocationDbSchema,DeletePurchaseDbSchema,UpdateReorderPointDbSchema
from schemas.v1.purchase_schemas.request_schema import CreatePurchaseItemsSchema,CreatePurchasePricingSchema,CreatePurchaseSchema,CreateStorageLocationSchema,UpdatePurchaseItemsSchema,UpdatePurchasePricingSchema,UpdatePurchaseSchema,UpdateStorageLocationSchema,DeletePurchaseSchema,PurchaseItemInfos,GetPurchaseByIdSchema,GetAllPurchaseSchemas,GetPurchaseByShopIdSchema,CancelPurchaseSchema
from core.errors.messaging_errors import BussinessError,FatalError,RetryableError
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums,PurchaseViewsEnums
from icecream import ic
from typing import Union,List,Dict
from datetime import date
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
from infras.read_db.models.purchase_model import PurchaseReadModel, SupplierInfo, PurchaseItemReadModel, ReadVariantInfos, ReadBatchInfos, ReadStocksInfos, ReadReorderPointInfos, ReadStorageLocationInfos
import httpx
import json
from messaging.saga_producer import SagaProducer,CreateSagaStateSchema,SagaStatusEnum
from hyperlocal_platform.core.enums.saga_state_enum import SagaStepsValueEnum
from hyperlocal_platform.core.typed_dicts.saga_status_typ_dict import SagaStateExecutionTypDict
from infras.primary_db.services.customfield_service import CustomFieldsService
from schemas.v1.request_schemas.customfield_schema import CreateCustomFieldSchema,CreateCustomFieldValueSchema,BulkCreateCustomFieldValuesSchema,UpdateCustomFieldSchema,UpdateCustomFieldValueSchema,GetFieldByShopIdSchema,GetFieldById,GetFieldByName,GetValueByIdName,GetvaluesByCustomerId

from integrations.utility_service import get_ui_id

def normalize_serial_numbers(serials):
    if not serials:
        return []
    import uuid, json
    result = []
    for item in serials:
        if isinstance(item, str):
            try:
                parsed = json.loads(item)
                if isinstance(parsed, dict):
                    name_val = parsed.get("name") or parsed.get("serialno_name") or parsed.get("serial_no_name") or parsed.get("serial_no") or parsed.get("serialno") or ""
                    id_val = parsed.get("id") or parsed.get("serialno_id") or parsed.get("serial_no_id") or str(uuid.uuid4())
                    result.append({"id": str(id_val), "name": str(name_val)})
                    continue
            except Exception:
                pass
            result.append({"id": str(uuid.uuid4()), "name": item})
        elif isinstance(item, dict):
            name_val = item.get("name") or item.get("serialno_name") or item.get("serial_no_name") or item.get("serial_no") or item.get("serialno") or ""
            id_val = item.get("id") or item.get("serialno_id") or item.get("serial_no_id") or str(uuid.uuid4())
            result.append({"id": str(id_val), "name": str(name_val)})
        elif hasattr(item, "name"):
            name_val = getattr(item, "name", "") or getattr(item, "serialno_name", "") or ""
            id_val = getattr(item, "id", None) or getattr(item, "serialno_id", None) or str(uuid.uuid4())
            result.append({"id": str(id_val), "name": str(name_val)})
        else:
            result.append({"id": str(uuid.uuid4()), "name": str(item)})
    return result

def resolve_serials_from_inventory(itm_serials, db_serialno_infos=None):
    if not itm_serials:
        return []
    
    db_sn_map = {}
    if db_serialno_infos:
        for sn in db_serialno_infos:
            if isinstance(sn, dict):
                s_name = sn.get("name") or sn.get("serialno_name") or sn.get("serial_no_name") or sn.get("serial_no") or sn.get("serialno") or ""
                s_id = sn.get("id") or sn.get("serialno_id") or sn.get("serial_no_id")
                if s_name and s_id:
                    db_sn_map[str(s_name).strip()] = str(s_id)

    result = []
    normalized = normalize_serial_numbers(itm_serials)
    for sn_obj in normalized:
        sn_name = str(sn_obj.get("name", "")).strip()
        if sn_name in db_sn_map:
            sn_obj["id"] = db_sn_map[sn_name]
        result.append(sn_obj)
    return result

def extract_sn_info(sn):
    if not sn:
        return "", None
    if isinstance(sn, dict):
        sn_name = sn.get("name") or sn.get("serialno_name") or sn.get("serial_no_name") or sn.get("serial_no") or sn.get("serialno") or ""
        sn_id = sn.get("id") or sn.get("serialno_id") or sn.get("serial_no_id")
        return sn_name, sn_id
    elif isinstance(sn, str):
        import json
        try:
            parsed = json.loads(sn)
            if isinstance(parsed, dict):
                sn_name = parsed.get("name") or parsed.get("serialno_name") or parsed.get("serial_no_name") or parsed.get("serial_no") or parsed.get("serialno") or ""
                sn_id = parsed.get("id") or parsed.get("serialno_id") or parsed.get("serial_no_id")
                return sn_name, sn_id
            elif isinstance(parsed, str):
                return parsed, None
        except Exception:
            pass
        return sn, None
    elif hasattr(sn, "name"):
        return getattr(sn, "name", ""), getattr(sn, "id", None) or getattr(sn, "serialno_id", None)
    return str(sn), None

async def _send_activity_log(shop_id: str, action: str, entity_id: str, description: str, changes: list = None, entity_name: str = ""):
    try:
        from messaging.main import RabbitMQMessagingConfig
        rabbitmq_msg_obj = RabbitMQMessagingConfig()
        await rabbitmq_msg_obj.publish_event(
            routing_key="activity_logs.routing.key",
            exchange_name="activity_logs.exchange",
            payload={
                "shop_id": shop_id,
                "user_name": "Hyperlocal-User",
                "service": "PURCHASE",
                "action": action,
                "entity_type": "PURCHASE",
                "entity_id": str(entity_id),
                "entity_name": str(entity_name),
                "description": description,
                "changes": changes or []
            },
            headers={}
        )
    except Exception as e:
        ic(f"Failed to log activity: {e}")


async def get_supplier_name(shop_id: str, supplier_id: str) -> str:
    if not supplier_id:
        return "Supplier"
    try:
        from infras.read_db.main import MONGO_CLIENT
        supp_coll = MONGO_CLIENT["SupplierServiceReadDb"]["SupplierCollections"]
        doc = await supp_coll.find_one({"id": supplier_id, "shop_id": shop_id})
        if not doc:
            doc = await supp_coll.find_one({"_id": supplier_id})
        if not doc:
            doc = await supp_coll.find_one({"id": supplier_id})
        if doc and (doc.get("name") or doc.get("supplier_name")):
            return doc.get("name") or doc.get("supplier_name")
    except Exception as e:
        ic(f"Error querying Mongo for supplier_name: {e}")

    try:
        import os
        supplier_service_url = os.getenv("SUPPLIER_SERVICE_URL", "http://127.0.0.1:8002")
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(f"{supplier_service_url}/suppliers/by/{shop_id}/{supplier_id}")
            if res.status_code == 200:
                res_data = res.json()
                if res_data and res_data.get("data"):
                    s_data = res_data["data"]
                    if isinstance(s_data, dict) and (s_data.get("name") or s_data.get("supplier_name")):
                        return s_data.get("name") or s_data.get("supplier_name")
    except Exception as e:
        ic(f"Error calling Supplier Service HTTP for supplier_name: {e}")

    return "Supplier"


async def fetch_ui_id_from_utility(shop_id: str) -> str:
    from integrations.utility_service import get_ui_id
    ui_id_res = await get_ui_id(shop_id=shop_id, entity_name="PURCHASE")
    ic("utility get_ui_id res => ", ui_id_res)
    if isinstance(ui_id_res, str) and ui_id_res:
        return ui_id_res
    if isinstance(ui_id_res, dict):
        if "ui_id" in ui_id_res:
            return str(ui_id_res["ui_id"])
        if "formatted_ui_id" in ui_id_res:
            return str(ui_id_res["formatted_ui_id"])
        if "prefix" in ui_id_res and "current_number" in ui_id_res:
            return f"{ui_id_res['prefix']}-{ui_id_res['current_number']}"
        if "prefix" in ui_id_res and "number" in ui_id_res:
            return f"{ui_id_res['prefix']}-{ui_id_res['number']}"
    return f"PUR-{generate_uuid()[:6].upper()}"


class PurchaseService:
    def __init__(self, session:AsyncSession):
        self.session=session
        self.purchase_repo_obj=PurchaseRepo(session=session)


    async def check_invoice_conflict(self, shop_id: str, invoice_no: str, current_id: Optional[str], supplier_id: Optional[str] = None) -> bool:
        if not invoice_no:
            return False

        from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo

        # Check Primary DB
        pg_item = await self.purchase_repo_obj.find_existing_invoice(shop_id=shop_id, invoice_no=invoice_no, supplier_id=supplier_id)
        if pg_item:
            pg_id = pg_item.id
            if current_id and pg_id == current_id:
                return False
            # Found another purchase/draft with the same invoice for this supplier
            return True

        # Check Read DB
        read_item = await PurchaseReadDbRepo.find_existing_invoice(shop_id=shop_id, invoice_no=invoice_no, supplier_id=supplier_id)
        if read_item:
            read_id = read_item.get("purchase_id") or read_item.get("id")
            if current_id and read_id == current_id:
                return False
            # Found another purchase/draft with the same invoice for this supplier
            return True

        return False

    async def save_draft(self, data: CreatePurchaseSchema) -> dict:
        import datetime
        from infras.primary_db.models.purchase_model import (
            Purchase, PurchaseItems, PurchaseItemsPricing,
            PurchaseItemsStoragelocation, PurchaseItemsReorderPoint
        )
        from infras.read_db.models.purchase_model import (
            PurchaseReadModel, PurchaseItemReadModel, SupplierInfo,
            ReadVariantInfos, ReadBatchInfos, ReadStocksInfos,
            ReadReorderPointInfos, ReadStorageLocationInfos
        )
        from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
        from integrations.utility_service import get_ui_id
        from schemas.v1.purchase_schemas.db_schemas import DeletePurchaseDbSchema

        shop_id = data.shop_id
        supplier_id = data.supplier_id
        requested_id = data.id

        has_conflict = await self.check_invoice_conflict(
            shop_id=shop_id,
            invoice_no=data.invoice_no,
            current_id=requested_id,
            supplier_id=supplier_id
        )

        if has_conflict:
            ic("Invoice number already exists on another purchase")
            return {
                "success": False,
                "msg": "Invoice number already exists",
                "id": requested_id or "",
                "status": "DRAFT"
            }

        purchase_id = requested_id if requested_id else generate_uuid()

        existing = await self.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id))
        existing_read = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id))

        ui_id = None
        if existing:
            ui_id = getattr(existing, 'ui_id', None)
            await self.purchase_repo_obj.delete_purchase(DeletePurchaseDbSchema(id=purchase_id, shop_id=shop_id))
        elif existing_read:
            ui_id = existing_read.get("ui_id")

        if not ui_id:
            ui_id = await fetch_ui_id_from_utility(shop_id=shop_id)

        pur_items_toadd = []
        pur_pricing_toadd = []
        pur_stl_toadd = []
        pur_rop_toadd = []
        read_items = []

        total_pur_items = len(data.items)
        total_pur_cost = 0.0
        total_gst_amount = 0.0

        for item in data.items:
            item_id = generate_uuid()
            pricing_id = generate_uuid()
            stl_id = generate_uuid()
            rop_id = generate_uuid()

            qty = item.stock_infos.stocks
            buy_price = item.pricing_infos.buy_price
            sell_price = item.pricing_infos.sell_price
            gst_str = item.gst or "0%"
            gst_val = float(gst_str.replace("%", "").strip()) / 100.0 if "%" in gst_str else 0.0
            gst_amt = qty * buy_price * gst_val
            item_total = (qty * buy_price) + gst_amt

            total_pur_cost += qty * buy_price
            total_gst_amount += gst_amt

            batch_id = None
            if item.batch_infos:
                if isinstance(item.batch_infos, dict):
                    batch_id = item.batch_infos.get("id") or item.batch_infos.get("batch_id")
                else:
                    batch_id = getattr(item.batch_infos, "id", None)

            normalized_serials = normalize_serial_numbers(item.serialno_numbers)

            pur_items_toadd.append(PurchaseItems(
                id=item_id,
                purchase_id=purchase_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                batch_id=batch_id,
                serial_numbers=normalized_serials,
                gst=item.gst,
                stocks=qty,
                stocks_before=0,
                stocks_after=qty
            ))

            pur_pricing_toadd.append(PurchaseItemsPricing(
                purchase_item_id=item_id,
                purchase_id=purchase_id,
                buy_price=buy_price,
                sell_price=sell_price
            ))

            stl_name = item.storage_location_infos.name if item.storage_location_infos else "Default"
            pur_stl_toadd.append(PurchaseItemsStoragelocation(
                purchase_item_id=item_id,
                purchase_id=purchase_id,
                name=stl_name
            ))

            rop_val = item.reorder_point_infos.reorder_point if item.reorder_point_infos else 0.0
            pur_rop_toadd.append(PurchaseItemsReorderPoint(
                purchase_item_id=item_id,
                purchase_id=purchase_id,
                reorder_point=rop_val
            ))

            read_items.append(PurchaseItemReadModel(
                id=item_id,
                product_id=item.product_id,
                ui_id=item_id[:8],
                name="Draft Item",
                variant_infos=ReadVariantInfos(id=item.variant_id, name="Variant") if item.variant_id else None,
                stocks_infos=ReadStocksInfos(stocks=qty, stocks_before=0, stocks_after=qty),
                reorder_point_infos=ReadReorderPointInfos(id=rop_id, reorder_point=rop_val),
                storage_location_infos=ReadStorageLocationInfos(id=stl_id, name=stl_name),
                serial_numbers=normalized_serials,
                sell_price=sell_price,
                buy_price=buy_price,
                total_amount=item_total,
                gst=item.gst
            ))

        item_infos_dict = {
            "total_pur_items": total_pur_items,
            "total_pur_cost": total_pur_cost,
            "total_gst_amount": total_gst_amount
        }

        payment_infos_dict = [p.model_dump(mode="json") for p in data.payment_infos] if data.payment_infos else []
        calc_dict = data.calculation_infos.model_dump(mode="json") if data.calculation_infos else {}
        charges_dict = data.charges_infos.model_dump(mode="json") if data.charges_infos else {}
        gst_dict = data.gst_infos.model_dump(mode="json") if data.gst_infos else {}

        pur_type_val = data.type.value if hasattr(data.type, 'value') else str(data.type)

        purchase_model = Purchase(
            id=purchase_id,
            ui_id=ui_id,
            shop_id=shop_id,
            supplier_id=supplier_id,
            invoice_no=data.invoice_no,
            type=pur_type_val,
            status="DRAFT",
            purchase_view=True,
            calculation_infos=calc_dict,
            charges_infos=charges_dict,
            item_infos=item_infos_dict,
            payment_infos=payment_infos_dict,
            date=datetime.datetime.combine(data.purchase_date, datetime.time.min),
            gst_infos=gst_dict,
            version="v1"
        )

        await self.purchase_repo_obj.create_bulk_purchase([purchase_model])
        if pur_items_toadd:
            await self.purchase_repo_obj.create_bulk_items(pur_items_toadd)
        if pur_pricing_toadd:
            await self.purchase_repo_obj.create_bulk_pricing(pur_pricing_toadd)
        if pur_rop_toadd:
            await self.purchase_repo_obj.create_bulk_rop(pur_rop_toadd)
        if pur_stl_toadd:
            await self.purchase_repo_obj.create_bulk_stl(pur_stl_toadd)

        supplier_name = await get_supplier_name(shop_id, supplier_id)
        supplier_info = SupplierInfo(supplier_id=supplier_id, supplier_name=supplier_name)
        purchase_read_model = PurchaseReadModel(
            purchase_id=purchase_id,
            ui_id=ui_id,
            invoice_no=data.invoice_no or ui_id,
            shop_id=shop_id,
            purchase_date=datetime.datetime.combine(data.purchase_date, datetime.time.min),
            status="DRAFT",
            supplier=supplier_info,
            item_infos=item_infos_dict,
            payment_infos=payment_infos_dict,
            payment_status="DRAFT",
            outstanding_amount=0.0,
            charges_infos=charges_dict,
            calculations=calc_dict,
            gst_infos=gst_dict,
            custom_fields=data.custom_fields or {},
            items=read_items,
            version="v1",
            paid_amount=0.0
        )

        await PurchaseReadDbRepo.add_updatereaddb(purchase_read_model)

        return {
            "success": True,
            "id": purchase_id,
            "ui_id": ui_id,
            "status": "DRAFT",
            "msg": "Draft purchase saved successfully"
        }

    async def create(self, data: CreatePurchaseSchema, executing_user_id: Optional[str] = None):
        if getattr(data, 'status', None) == "DRAFT":
            return await self.save_draft(data)

        # Validate paid amount against total purchase cost (QTY * (BUY PRICE + GST)) + charges
        total_item_cost = 0.0
        for item in data.items:
            qty = item.stock_infos.stocks
            buy_price = item.pricing_infos.buy_price
            gst_str = item.gst or "0%"
            gst_val = float(gst_str.replace("%", "").strip()) / 100.0 if "%" in gst_str else 0.0
            item_cost = qty * (buy_price + (buy_price * gst_val))
            total_item_cost += item_cost
        
        total_purchase_cost = total_item_cost
        
        total_paid = sum(p.amount for p in data.payment_infos) if data.payment_infos else 0.0
        if total_paid > total_purchase_cost:
            ic("Paid amount exceeds total purchase cost, leading to negative outstanding balance.")
            return False

        shop_id = data.shop_id
        requested_id = data.id

        has_conflict = await self.check_invoice_conflict(
            shop_id=shop_id,
            invoice_no=data.invoice_no,
            current_id=requested_id,
            supplier_id=data.supplier_id
        )

        if has_conflict:
            ic("Invoice number already exists on another purchase")
            return False

        effective_id = requested_id if requested_id else generate_uuid()

        saga_id: str = generate_uuid()
        steps = {
            "SUPPLIER_VERIFY": SagaStepsValueEnum.PENDING,
            "PRODUCT_VERIFY_UPDATE": SagaStepsValueEnum.PENDING,
            "FETCHING_PRODUCTS": SagaStepsValueEnum.PENDING
        }

        payload_data = data.model_dump(mode="json")
        if effective_id:
            payload_data["id"] = effective_id
            data.id = effective_id

        saga_data = {"purchase": payload_data, "executing_user_id": executing_user_id}
        await SagaProducer.emit(
            saga_payload=CreateSagaStateSchema(
                id=saga_id,
                status=SagaStatusEnum.IN_PROGRESS,
                type="PURCHASE_CREATED",
                steps=steps,
                execution=SagaStateExecutionTypDict(
                    step="SUPPLIER_VERIFY",
                    service="SUPPLIERS"
                ),
                data=saga_data
            ),
            routing_key="suppliers.service.routing.key",
            exchange_name="suppliers.service.exchange",
            headers={
                "reply_key": "purchase.producer.routing.key",
                "reply_exchange": "purchase.producer.exchange",
                "reply_entity_name": "create_purchase",
                "reply_service_name": "PURCHASE",
                "service_name": "SUPPLIERS",
                "entity_name": "get_supplier_by_id",
                "body": {
                    "shop_id": data.shop_id,
                    "id": data.supplier_id
                }
            }
        )

        return True


        



    async def update(self,data:UpdatePurchaseSchema):
        purchase_repo_obj=PurchaseRepo(session=self.session)
        items_toadd=[]
        items_toupdate=[]
        pricing_toadd=[]
        pricing_toupdate=[]
        stl_toadd=[]
        stl_toupdate=[]
        rop_toadd=[]
        rop_toupdate=[]
        inventory_toupdate=[]

        item_infos = {
            'total_pur_items': 0,
            'total_pur_stocks': 0,
            'total_pur_cost': 0,
            'total_gst_amount': 0
        }

        pur_get_res=await purchase_repo_obj.get_purchase_by_id(data=GetPurchaseByIdSchema(id=data.id,shop_id=data.shop_id))
        ic(pur_get_res)
        if not pur_get_res:
            ic("The give purchase was not found")
            return False

        original_supplier_id = pur_get_res.supplier_id
        existing_read_doc_initial = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
        existing_read_doc = existing_read_doc_initial

        current_status = getattr(pur_get_res, 'status', None) or (existing_read_doc_initial.get("status") if existing_read_doc_initial else None)
        if current_status and str(current_status).upper() == "CANCELED":
            from fastapi import HTTPException
            from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Updating Purchase",
                    status_code=400,
                    description="Cannot edit or update a purchase that has been canceled.",
                    success=False
                )
            )
        original_outstanding = float(existing_read_doc_initial.get("outstanding_amount", 0.0)) if existing_read_doc_initial else 0.0
        original_supplier_name = existing_read_doc_initial.get("supplier", {}).get("supplier_name") if existing_read_doc_initial else None
        old_payments_list = existing_read_doc_initial.get("payment_infos", []) if existing_read_doc_initial else []
        original_paid_amount = sum(float(p.get("amount", 0.0)) for p in old_payments_list)

        effective_supplier_id = data.supplier_id or pur_get_res.supplier_id
        effective_invoice_no = data.invoice_no if data.invoice_no is not None else pur_get_res.invoice_no
        effective_pur_identifier = getattr(pur_get_res, "ui_id", None) or effective_invoice_no or data.id

        if effective_invoice_no:
            has_conflict = await self.check_invoice_conflict(
                shop_id=data.shop_id,
                invoice_no=effective_invoice_no,
                current_id=data.id,
                supplier_id=effective_supplier_id
            )
            if has_conflict:
                from fastapi import HTTPException
                from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Updating Purchase",
                        status_code=400,
                        description="Invoice number already exists for this supplier",
                        success=False
                    )
                )

        # Handle Item Removal / Skipping / Replacement
        incoming_item_ids = {item.id for item in data.items if item.id}
        incoming_product_ids = {item.product_id for item in data.items if item.product_id}

        items_todelete_ids = []
        removed_items = []

        for db_item in pur_get_res.items:
            if db_item.id not in incoming_item_ids and db_item.product_id not in incoming_product_ids:
                removed_items.append(db_item)
                items_todelete_ids.append(db_item.id)

        # Fetch product metadata from Mongo for both incoming and existing DB products
        all_product_ids = list(set([itm.product_id for itm in data.items] + [itm.product_id for itm in pur_get_res.items]))
        from infras.read_db.main import MONGO_CLIENT
        prod_inv_collection = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
        cursor = prod_inv_collection.find({"id": {"$in": all_product_ids}, "shop_id": data.shop_id})
        product_docs = {doc["id"]: doc async for doc in cursor}

        # Check stock sufficiency and revert stock for removed/skipped items
        for removed_item in removed_items:
            prod_doc = product_docs.get(removed_item.product_id) or {}
            type_infos = prod_doc.get("type_infos") or {}
            has_batch = type_infos.get("has_batch") if type_infos and "has_batch" in type_infos else prod_doc.get("has_batch", False)
            has_variant = type_infos.get("has_variant") if type_infos and "has_variant" in type_infos else prod_doc.get("has_variant", False)
            has_serialno = type_infos.get("has_serialno") if type_infos and "has_serialno" in type_infos else prod_doc.get("has_serialno", False)
            
            target_stock_infos = {}
            if has_variant and removed_item.variant_id:
                variants = prod_doc.get("variants") or {}
                variant_data = {}
                if isinstance(variants, dict):
                    variant_data = variants.get(removed_item.variant_id) or {}
                elif isinstance(variants, list):
                    for v in variants:
                        if v.get("id") == removed_item.variant_id:
                            variant_data = v
                            break
                if has_batch and removed_item.batch_id:
                    batches_list = variant_data.get("batch_infos") or []
                    for b in batches_list:
                        if b.get("id") == removed_item.batch_id or b.get("name") == removed_item.batch_id:
                            target_stock_infos = b.get("stock_infos") or {}
                            break
                else:
                    target_stock_infos = variant_data.get("stock_infos") or {}
            elif has_batch and removed_item.batch_id:
                batches_list = prod_doc.get("batch_infos") or []
                for b in batches_list:
                    if b.get("id") == removed_item.batch_id or b.get("name") == removed_item.batch_id:
                        target_stock_infos = b.get("stock_infos") or {}
                        break
            else:
                target_stock_infos = prod_doc.get("stock_infos") or {}

            physical_stock = float(target_stock_infos.get("physical_stocks") or 0.0)
            purchased_qty = float(removed_item.stocks or 0.0)

            if physical_stock < purchased_qty:
                from fastapi import HTTPException
                from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Updating Purchase",
                        status_code=400,
                        description=f"Cannot remove product '{removed_item.product_id}' because current physical stock ({physical_stock}) is less than purchased stock ({purchased_qty}) to revert.",
                        success=False
                    )
                )

            target_batch_id = removed_item.batch_id
            if not target_batch_id and existing_read_doc:
                for ex_itm in existing_read_doc.get("items", []):
                    if ex_itm.get("id") == removed_item.id or ex_itm.get("product_id") == removed_item.product_id:
                        if ex_itm.get("batch_infos"):
                            target_batch_id = ex_itm["batch_infos"].get("id")
                            break
            if not target_batch_id and has_batch:
                if has_variant and removed_item.variant_id:
                    variants = prod_doc.get("variants") or {}
                    variant_data = {}
                    if isinstance(variants, dict):
                        variant_data = variants.get(removed_item.variant_id) or {}
                    elif isinstance(variants, list):
                        for v in variants:
                            if v.get("id") == removed_item.variant_id:
                                variant_data = v
                                break
                    batches_list = variant_data.get("batch_infos") or []
                else:
                    batches_list = prod_doc.get("batch_infos") or []
                if batches_list:
                    target_batch_id = batches_list[0].get("id")

            removed_sn_infos = []
            if has_variant and removed_item.variant_id:
                variants = prod_doc.get("variants") or {}
                variant_data = {}
                if isinstance(variants, dict):
                    variant_data = variants.get(removed_item.variant_id) or {}
                elif isinstance(variants, list):
                    for v in variants:
                        if v.get("id") == removed_item.variant_id:
                            variant_data = v
                            break
                if has_batch and removed_item.batch_id:
                    batches_list = variant_data.get("batch_infos") or []
                    batch_data = {}
                    for b in batches_list:
                        if b.get("id") == removed_item.batch_id or b.get("name") == removed_item.batch_id:
                            batch_data = b
                            break
                    rem_prod_sns = batch_data.get("serialno_infos") or []
                else:
                    rem_prod_sns = variant_data.get("serialno_infos") or []
            elif has_batch and removed_item.batch_id:
                batches_list = prod_doc.get("batch_infos") or []
                batch_data = {}
                for b in batches_list:
                    if b.get("id") == removed_item.batch_id or b.get("name") == removed_item.batch_id:
                        batch_data = b
                        break
                rem_prod_sns = batch_data.get("serialno_infos") or []
            else:
                rem_prod_sns = prod_doc.get("serialno_infos") or []
            rem_sn_map = {sn.get("name"): sn.get("id") for sn in rem_prod_sns if isinstance(sn, dict) and sn.get("name")}
            for sn in (removed_item.serial_numbers or []):
                sn_name, sn_id = extract_sn_info(sn)
                resolved_id = sn_id or rem_sn_map.get(sn_name)
                if sn_name:
                    if resolved_id:
                        removed_sn_infos.append({"id": resolved_id, "name": sn_name})
                    else:
                        removed_sn_infos.append({"name": sn_name})

            inventory_toupdate.append({
                'shop_id': data.shop_id,
                'product_id': removed_item.product_id,
                'variant_id': removed_item.variant_id,
                'batch_infos': {'id': target_batch_id} if target_batch_id else None,
                'serialno_infos': removed_sn_infos,
                'storage_location': removed_item.storage_locations[0].name if removed_item.storage_locations else None,
                'reorder_point': removed_item.reorder_point[0].reorder_point if removed_item.reorder_point else None,
                'gst': removed_item.gst,
                'buy_price': removed_item.pricing_infos[0].buy_price if removed_item.pricing_infos else 0.0,
                'sell_price': removed_item.pricing_infos[0].sell_price if removed_item.pricing_infos else 0.0,
                'stocks': purchased_qty,
                'type': 'DECREMENT',
                "entity_name": 'PURCHASE_UPDATE',
                "entity_id": effective_pur_identifier,
                'create_stock_mov_adj': True
            })

        # Prevent duplicate item IDs in update payload
        incoming_item_ids_list = [item.id for item in data.items if item.id]
        if len(incoming_item_ids_list) != len(set(incoming_item_ids_list)):
            from fastapi import HTTPException
            from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Updating Purchase",
                    status_code=400,
                    description="Duplicate purchase item IDs are not allowed",
                    success=False
                )
            )

        # Prevent duplicate product/variant/batch combinations in update payload
        product_variant_combos = []
        for item in data.items:
            batch_name = item.batch_infos.name if item.batch_infos else None
            batch_id = item.batch_infos.id if item.batch_infos else None
            combo = (item.product_id, item.variant_id, batch_name, batch_id)
            if combo in product_variant_combos:
                from fastapi import HTTPException
                from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Updating Purchase",
                        status_code=400,
                        description="Duplicate products in purchase items are not allowed",
                        success=False
                    )
                )
            product_variant_combos.append(combo)

        # Verify that all product IDs in payload actually exist in the database
        for item in data.items:
            if item.product_id not in product_docs:
                from fastapi import HTTPException
                from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Updating Purchase",
                        status_code=400,
                        description=f"Product with ID {item.product_id} not found.",
                        success=False
                    )
                )
        
        mapped_items={item.id: item for item in pur_get_res.items}
        ic(mapped_items)

        # Secondary map: (product_id, variant_id, batch_id) → db_item
        # Used to detect when a payload item without an ID matches an existing DB item
        mapped_items_by_product_combo = {}
        for db_item_x in pur_get_res.items:
            combo_key = (db_item_x.product_id, db_item_x.variant_id, db_item_x.batch_id)
            mapped_items_by_product_combo[combo_key] = db_item_x
        
        # Validate paid amount before performing any database updates
        temp_total_pur_cost = 0.0
        temp_total_gst_amount = 0.0
        
        for item in data.items:
            prod_doc = product_docs.get(item.product_id) or {}
            type_infos = prod_doc.get("type_infos") or {}
            
            t_gst = item.gst
            t_stocks = item.stock_infos.stocks
            
            pur_item_id = item.id
            is_new = not pur_item_id or pur_item_id not in mapped_items

            # Check combo match (product_id + variant_id + batch_id) to detect
            # an item sent without ID that actually exists in this purchase already
            if is_new:
                _v_chk = item.variant_id
                _b_chk = (item.batch_infos.id if item.batch_infos else None)
                _combo_match = mapped_items_by_product_combo.get((item.product_id, _v_chk, _b_chk))
                if _combo_match:
                    pur_item_id = _combo_match.id
                    is_new = False

            if is_new:
                if not item.stock_infos or not item.pricing_infos or item.stock_infos.stocks is None:
                    from fastapi import HTTPException
                    from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                    raise HTTPException(
                        status_code=400,
                        detail=ErrorResponseTypDict(
                            msg="Error : Updating Purchase",
                            status_code=400,
                            description="Pricing infos and stock infos are mandatory for new items",
                            success=False
                        )
                    )
                prev_pricing = None
                prev_gst_infos = pur_get_res.gst_infos
                stock_toupdate = t_stocks
            else:
                db_item = mapped_items[pur_item_id]
                prev_pricing = db_item.pricing_infos[0] if db_item.pricing_infos else None
                prev_gst_infos = pur_get_res.gst_infos
                stock_toupdate = t_stocks

            db_item_local = mapped_items.get(pur_item_id) if not is_new else None
            item_gst = t_gst or (db_item_local.gst if db_item_local else (prod_doc.get("gst") or "0%"))
            buy_price_val = item.pricing_infos.buy_price if item.pricing_infos else (prev_pricing.buy_price if prev_pricing else 0.0)
            
            tot_pur_cost = buy_price_val * stock_toupdate
            temp_total_pur_cost += tot_pur_cost
            
            effective_gst_infos = getattr(data, "gst_infos", None) or prev_gst_infos
            gst_type = ""
            if effective_gst_infos:
                if isinstance(effective_gst_infos, dict):
                    gst_type = effective_gst_infos.get('type') or ""
                else:
                    gst_type = getattr(effective_gst_infos, 'type', '') or ""
            if not gst_type:
                gst_type = "EXCLUSIVE"

            if item_gst and item_gst.endswith('%') and gst_type == "EXCLUSIVE":
                try:
                    gst_rate = float(item_gst[:-1]) / 100.0
                    temp_total_gst_amount += gst_rate * tot_pur_cost
                except ValueError:
                    pass

        existing_read_doc = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
        payment_infos = data.payment_infos if data.payment_infos is not None else (existing_read_doc.get("payment_infos") if existing_read_doc else [])
        payment_infos_dicts = [p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in payment_infos]
        total_amount_paid = sum(float(payment.get('amount', 0)) for payment in payment_infos_dicts)
        
        final_total_cost = float(temp_total_pur_cost + temp_total_gst_amount)
        charges_infos = data.charges_infos.model_dump(mode="json") if data.charges_infos else (existing_read_doc.get("charges_infos") if existing_read_doc else {})
        total_purchase_cost = final_total_cost
        
        if round(total_amount_paid, 2) > round(total_purchase_cost, 2):
            from fastapi import HTTPException
            from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Updating Purchase",
                    status_code=400,
                    description=f"Paid amount ({total_amount_paid}) cannot exceed total purchase cost ({total_purchase_cost}).",
                    success=False
                )
            )
        
        for item in data.items:
            prod_doc = product_docs.get(item.product_id) or {}
            type_infos = prod_doc.get("type_infos") or {}
            has_batch = type_infos.get("has_batch") if type_infos and "has_batch" in type_infos else prod_doc.get("has_batch", False)
            has_serialno = type_infos.get("has_serialno") if type_infos and "has_serialno" in type_infos else prod_doc.get("has_serialno", False)
            has_variant = type_infos.get("has_variant") if type_infos and "has_variant" in type_infos else prod_doc.get("has_variant", False)
            
            if not has_batch:
                item.batch_infos = None
            if not has_serialno:
                item.serialno_numbers = []

            pur_item_id = item.id
            is_new_item = not pur_item_id or pur_item_id not in mapped_items

            # If the incoming item has no ID (or ID not in DB), check if an existing DB item
            # has the same product_id / variant_id / batch_id combo.  If so, treat it as an
            # UPDATE of that existing item rather than creating a duplicate new record.
            if is_new_item:
                inc_batch_id_check = (item.batch_infos.id if item.batch_infos else None) if has_batch else None
                inc_variant_id_check = item.variant_id if has_variant else None
                combo_key_check = (item.product_id, inc_variant_id_check, inc_batch_id_check)
                matching_db_item = mapped_items_by_product_combo.get(combo_key_check)
                if matching_db_item:
                    # Redirect to update path using the existing DB item's ID
                    pur_item_id = matching_db_item.id
                    is_new_item = False
                    ic(f"Redirecting item {item.product_id} from NEW to UPDATE using existing item id {pur_item_id}")

            db_item_local = mapped_items.get(pur_item_id) if not is_new_item else None
            item_gst = item.gst or (db_item_local.gst if db_item_local else (prod_doc.get("gst") or "0%"))
            
            if is_new_item:
                pur_item_id = generate_uuid()
                prev_batch_id = item.batch_infos.id if item.batch_infos else None
                prev_variant_id = item.variant_id
                prev_serialno_numbers = set()
                prev_stocks = 0.0
                target_stock_infos = {}
                b_id = item.batch_infos.id if item.batch_infos else None
                b_name = item.batch_infos.name if item.batch_infos else None
                
                if has_variant and prev_variant_id:
                    variants = prod_doc.get("variants") or {}
                    variant_data = {}
                    if isinstance(variants, dict):
                        variant_data = variants.get(prev_variant_id) or {}
                    elif isinstance(variants, list):
                        variant_data = next((v for v in variants if isinstance(v, dict) and v.get("id") == prev_variant_id), {})
                    
                    if has_batch:
                        batches = variant_data.get("batch_infos") or []
                        matched_b = next((b for b in batches if isinstance(b, dict) and ((b_id and b.get("id") == b_id) or (b_name and b.get("name") == b_name))), {})
                        if matched_b:
                            prev_batch_id = matched_b.get("id") or b_id
                        target_stock_infos = matched_b.get("stock_infos") or matched_b.get("stocks_infos") or {}
                        if not prev_batch_id and item.batch_infos:
                            prev_batch_id = item.batch_infos.id or item.batch_infos.name
                    else:
                        target_stock_infos = variant_data.get("stock_infos") or variant_data.get("stocks_infos") or {}
                elif has_batch:
                    batches = prod_doc.get("batch_infos") or []
                    matched_b = next((b for b in batches if isinstance(b, dict) and ((b_id and b.get("id") == b_id) or (b_name and b.get("name") == b_name))), {})
                    if matched_b:
                        prev_batch_id = matched_b.get("id") or b_id
                    target_stock_infos = matched_b.get("stock_infos") or matched_b.get("stocks_infos") or {}
                    if not prev_batch_id and item.batch_infos:
                        prev_batch_id = item.batch_infos.id or item.batch_infos.name
                else:
                    target_stock_infos = prod_doc.get("stock_infos") or prod_doc.get("stocks_infos") or {}
                
                prev_stocks_before = float(target_stock_infos.get("physical_stocks") if target_stock_infos.get("physical_stocks") is not None else (target_stock_infos.get("stocks") or 0.0))
                prev_stocks_after = prev_stocks_before + item.stock_infos.stocks
                prev_stl = None
                prev_rop = None
                prev_pricing = None
                prev_gst_infos = pur_get_res.gst_infos
                
                stock_toupdate = item.stock_infos.stocks
                stock_diff = stock_toupdate
            else:
                db_item = mapped_items[pur_item_id]
                old_product_id = db_item.product_id

                if item.product_id != old_product_id:
                    from integrations.order_service import check_product_sales_exists
                    sales_exist = await check_product_sales_exists(shop_id=data.shop_id, product_id=old_product_id)
                    if sales_exist:
                        from fastapi import HTTPException
                        from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                        raise HTTPException(
                            status_code=400,
                            detail=ErrorResponseTypDict(
                                msg="Error : Updating Purchase",
                                status_code=400,
                                description=f"Cannot change product '{old_product_id}' because sales have already occurred for this product",
                                success=False
                            )
                        )
                    
                    old_batch_id = db_item.batch_id
                    if not old_batch_id and existing_read_doc:
                        for ex_itm in existing_read_doc.get("items", []):
                            if ex_itm.get("id") == db_item.id or ex_itm.get("product_id") == old_product_id:
                                if ex_itm.get("batch_infos"):
                                    old_batch_id = ex_itm["batch_infos"].get("id")
                                    break
                    old_prod_doc = product_docs.get(old_product_id) or {}
                    old_type_infos = old_prod_doc.get("type_infos") or {}
                    old_has_batch = old_type_infos.get("has_batch", False)
                    old_has_variant = old_type_infos.get("has_variant", False)
                    if not old_batch_id and old_has_batch:
                        if old_has_variant and db_item.variant_id:
                            variants = old_prod_doc.get("variants") or {}
                            variant_data = {}
                            if isinstance(variants, dict):
                                variant_data = variants.get(db_item.variant_id) or {}
                            elif isinstance(variants, list):
                                for v in variants:
                                    if v.get("id") == db_item.variant_id:
                                        variant_data = v
                                        break
                            batches_list = variant_data.get("batch_infos") or []
                        else:
                            batches_list = old_prod_doc.get("batch_infos") or []
                        if batches_list:
                            old_batch_id = batches_list[0].get("id")

                    # Check stock sufficiency for old product before reverting
                    old_target_stock_infos = {}
                    if old_has_variant and db_item.variant_id:
                        variants = old_prod_doc.get("variants") or {}
                        variant_data = {}
                        if isinstance(variants, dict):
                            variant_data = variants.get(db_item.variant_id) or {}
                        elif isinstance(variants, list):
                            for v in variants:
                                if v.get("id") == db_item.variant_id:
                                    variant_data = v
                                    break
                        if old_has_batch and old_batch_id:
                            batches_list = variant_data.get("batch_infos") or []
                            for b in batches_list:
                                if b.get("id") == old_batch_id or b.get("name") == old_batch_id:
                                    old_target_stock_infos = b.get("stock_infos") or {}
                                    break
                        else:
                            old_target_stock_infos = variant_data.get("stock_infos") or {}
                    elif old_has_batch and old_batch_id:
                        batches_list = old_prod_doc.get("batch_infos") or []
                        for b in batches_list:
                            if b.get("id") == old_batch_id or b.get("name") == old_batch_id:
                                old_target_stock_infos = b.get("stock_infos") or {}
                                break
                    else:
                        old_target_stock_infos = old_prod_doc.get("stock_infos") or {}

                    old_physical_stock = float(old_target_stock_infos.get("physical_stocks") or 0.0)
                    old_purchased_qty = float(db_item.stocks or 0.0)

                    if old_physical_stock < old_purchased_qty:
                        from fastapi import HTTPException
                        from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                        raise HTTPException(
                            status_code=400,
                            detail=ErrorResponseTypDict(
                                msg="Error : Updating Purchase",
                                status_code=400,
                                description=f"Cannot remove product '{old_product_id}' because current physical stock ({old_physical_stock}) is less than purchased stock ({old_purchased_qty}) to revert.",
                                success=False
                            )
                        )

                    old_sn_infos = []
                    if old_has_variant and db_item.variant_id:
                        variants = old_prod_doc.get("variants") or {}
                        variant_data = {}
                        if isinstance(variants, dict):
                            variant_data = variants.get(db_item.variant_id) or {}
                        elif isinstance(variants, list):
                            for v in variants:
                                if v.get("id") == db_item.variant_id:
                                    variant_data = v
                                    break
                        if old_has_batch and old_batch_id:
                            batches_list = variant_data.get("batch_infos") or []
                            batch_data = {}
                            for b in batches_list:
                                if b.get("id") == old_batch_id or b.get("name") == old_batch_id:
                                    batch_data = b
                                    break
                            old_prod_sns = batch_data.get("serialno_infos") or []
                        else:
                            old_prod_sns = variant_data.get("serialno_infos") or []
                    elif old_has_batch and old_batch_id:
                        batches_list = old_prod_doc.get("batch_infos") or []
                        batch_data = {}
                        for b in batches_list:
                            if b.get("id") == old_batch_id or b.get("name") == old_batch_id:
                                batch_data = b
                                break
                        old_prod_sns = batch_data.get("serialno_infos") or []
                    else:
                        old_prod_sns = old_prod_doc.get("serialno_infos") or []
                    old_sn_map = {sn.get("name"): sn.get("id") for sn in old_prod_sns if isinstance(sn, dict) and sn.get("name")}
                    for sn in (db_item.serial_numbers or []):
                        sn_name, sn_id = extract_sn_info(sn)
                        resolved_id = sn_id or old_sn_map.get(sn_name)
                        if sn_name:
                            if resolved_id:
                                old_sn_infos.append({"id": resolved_id, "name": sn_name})
                            else:
                                old_sn_infos.append({"name": sn_name})

                    # Reverse stock for old product
                    inventory_toupdate.append({
                        'shop_id': data.shop_id,
                        'product_id': old_product_id,
                        'variant_id': db_item.variant_id,
                        'batch_infos': {'id': old_batch_id} if old_batch_id else None,
                        'serialno_infos': old_sn_infos,
                        'storage_location': db_item.storage_locations[0].name if db_item.storage_locations else None,
                        'reorder_point': db_item.reorder_point[0].reorder_point if db_item.reorder_point else None,
                        'gst': db_item.gst,
                        'buy_price': db_item.pricing_infos[0].buy_price if db_item.pricing_infos else 0.0,
                        'sell_price': db_item.pricing_infos[0].sell_price if db_item.pricing_infos else 0.0,
                        'stocks': db_item.stocks,
                        'type': 'DECREMENT',
                        "entity_name": 'PURCHASE_UPDATE',
                        "entity_id": effective_pur_identifier,
                        'create_stock_mov_adj': True
                    })

                    # Resolve batch_id and variant_id for the NEW product
                    prev_variant_id = item.variant_id
                    prev_batch_id = item.batch_infos.id if item.batch_infos else None
                    if has_batch:
                        b_id = item.batch_infos.id if item.batch_infos else None
                        b_name = item.batch_infos.name if item.batch_infos else None
                        if has_variant and prev_variant_id:
                            variants = prod_doc.get("variants") or {}
                            variant_data = {}
                            if isinstance(variants, dict):
                                variant_data = variants.get(prev_variant_id) or {}
                            elif isinstance(variants, list):
                                for v in variants:
                                    if v.get("id") == prev_variant_id:
                                        variant_data = v
                                        break
                            batches_list = variant_data.get("batch_infos") or []
                        else:
                            batches_list = prod_doc.get("batch_infos") or []
                        for b in batches_list:
                            if (b_id and b.get("id") == b_id) or (b_name and b.get("name") == b_name):
                                prev_batch_id = b.get("id") or b_id
                                break

                    # Get current stock in inventory of the NEW product before incrementing
                    new_target_stock_infos = {}
                    if has_variant and prev_variant_id:
                        variants = prod_doc.get("variants") or {}
                        variant_data = {}
                        if isinstance(variants, dict):
                            variant_data = variants.get(prev_variant_id) or {}
                        elif isinstance(variants, list):
                            for v in variants:
                                if v.get("id") == prev_variant_id:
                                    variant_data = v
                                    break
                        if has_batch and prev_batch_id:
                            batches_list = variant_data.get("batch_infos") or []
                            for b in batches_list:
                                if b.get("id") == prev_batch_id or b.get("name") == prev_batch_id:
                                    new_target_stock_infos = b.get("stock_infos") or {}
                                    break
                        else:
                            new_target_stock_infos = variant_data.get("stock_infos") or {}
                    elif has_batch and prev_batch_id:
                        for b in prod_doc.get("batch_infos", []):
                            if b.get("id") == prev_batch_id or b.get("name") == prev_batch_id:
                                new_target_stock_infos = b.get("stock_infos") or {}
                                break
                    else:
                        new_target_stock_infos = prod_doc.get("stock_infos") or {}

                    prev_stocks_before = float(new_target_stock_infos.get("physical_stocks") or 0.0)
                    prev_stocks = 0.0
                    prev_stocks_after = prev_stocks_before

                    # Increment stock for newly replaced product
                    inventory_toupdate.append({
                        'shop_id': data.shop_id,
                        'product_id': item.product_id,
                        'variant_id': prev_variant_id,
                        'batch_infos': item.batch_infos.model_dump(mode="json") if item.batch_infos else None,
                        'serialno_infos': normalize_serial_numbers(item.serialno_numbers),
                        'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                        'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                        'gst': item_gst,
                        'buy_price': item.pricing_infos.buy_price if item.pricing_infos else 0.0,
                        'sell_price': item.pricing_infos.sell_price if item.pricing_infos else 0.0,
                        'stocks': t_stocks,
                        'type': 'INCREMENT',
                        "entity_name": 'PURCHASE_UPDATE',
                        "entity_id": effective_pur_identifier,
                        'create_stock_mov_adj': True
                    })
                else:
                    prev_batch_id = db_item.batch_id
                    if prev_batch_id:
                        incoming_batch_id = item.batch_infos.id if item.batch_infos else None
                        incoming_batch_name = item.batch_infos.name if item.batch_infos else None
                        
                        existing_read_doc = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
                        db_batch_name = ""
                        if existing_read_doc and "items" in existing_read_doc:
                            for existing_itm in existing_read_doc["items"]:
                                if existing_itm.get("id") == pur_item_id:
                                    if existing_itm.get("batch_infos"):
                                        db_batch_name = existing_itm["batch_infos"].get("name") or ""
                                    break
                                    
                        if incoming_batch_id and incoming_batch_id != prev_batch_id:
                            ic("Existing batch ID cannot be modified.")
                            return False
                        if db_batch_name and incoming_batch_name and incoming_batch_name != db_batch_name:
                            ic("Existing batch name cannot be modified.")
                            return False

                    prev_variant_id = db_item.variant_id
                    prev_serialno_numbers = set(db_item.serial_numbers or [])
                    prev_stocks = db_item.stocks
                    prev_stocks_before = db_item.stocks_before
                    prev_stocks_after = db_item.stocks_after

                prev_stl = db_item.storage_locations[0] if db_item.storage_locations else None
                prev_rop = db_item.reorder_point[0] if db_item.reorder_point else None
                prev_gst_infos = pur_get_res.gst_infos
                prev_pricing = db_item.pricing_infos[0] if db_item.pricing_infos else None
                
                stock_toupdate = item.stock_infos.stocks
                stock_diff = stock_toupdate - prev_stocks
                if item.product_id == old_product_id and stock_diff < 0:
                    from integrations.order_service import check_product_sales_exists
                    sales_exist = await check_product_sales_exists(shop_id=data.shop_id, product_id=item.product_id)
                    if sales_exist:
                        from fastapi import HTTPException
                        from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                        raise HTTPException(
                            status_code=400,
                            detail=ErrorResponseTypDict(
                                msg="Error : Updating Purchase",
                                status_code=400,
                                description=f"Cannot decrease stock for product '{item.product_id}' because sales have already occurred for this product",
                                success=False
                            )
                        )
                    # Check stock sufficiency before decrementing for same product
                    target_stock_infos = {}
                    if has_variant and prev_variant_id:
                        variants = prod_doc.get("variants") or {}
                        variant_data = {}
                        if isinstance(variants, dict):
                            variant_data = variants.get(prev_variant_id) or {}
                        elif isinstance(variants, list):
                            for v in variants:
                                if v.get("id") == prev_variant_id:
                                    variant_data = v
                                    break
                        if has_batch and prev_batch_id:
                            batches_list = variant_data.get("batch_infos") or []
                            for b in batches_list:
                                if b.get("id") == prev_batch_id or b.get("name") == prev_batch_id:
                                    target_stock_infos = b.get("stock_infos") or {}
                                    break
                        else:
                            target_stock_infos = variant_data.get("stock_infos") or {}
                    elif has_batch and prev_batch_id:
                        for b in prod_doc.get("batch_infos", []):
                            if b.get("id") == prev_batch_id or b.get("name") == prev_batch_id:
                                target_stock_infos = b.get("stock_infos") or {}
                                break
                    else:
                        target_stock_infos = prod_doc.get("stock_infos") or {}

                    physical_stock = float(target_stock_infos.get("physical_stocks") or 0.0)
                    if physical_stock < abs(stock_diff):
                        from fastapi import HTTPException
                        from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                        raise HTTPException(
                            status_code=400,
                            detail=ErrorResponseTypDict(
                                msg="Error : Updating Purchase",
                                status_code=400,
                                description=f"Cannot decrease stock for product '{item.product_id}' because current physical stock ({physical_stock}) is less than stock difference ({abs(stock_diff)}) to revert.",
                                success=False
                            )
                        )

            # Validate serial numbers quantity matching total stock
            norm_new_serials = normalize_serial_numbers(item.serialno_numbers)
            if has_serialno and len(norm_new_serials) != stock_toupdate:
                ic("Invalid Serial Numbers count", len(norm_new_serials), stock_toupdate)
                return False

            curr_variant_id = item.variant_id if item.variant_id is not None else prev_variant_id
            curr_batch_id = (item.batch_infos.id if item.batch_infos else getattr(item, 'batch_id', None)) or prev_batch_id

            if is_new_item:
                items_toadd.append(
                    PurchaseItems(
                        id=pur_item_id,
                        purchase_id=data.id,
                        product_id=item.product_id,
                        variant_id=curr_variant_id,
                        batch_id=curr_batch_id,
                        gst=item_gst,
                        stocks=item.stock_infos.stocks,
                        stocks_before=prev_stocks_before,
                        stocks_after=prev_stocks_after,
                        serial_numbers=norm_new_serials
                    )
                )
            else:
                items_toupdate.append(
                    UpdatePurchaseItemsDbSchema(
                        id=pur_item_id,
                        product_id=item.product_id,
                        variant_id=curr_variant_id,
                        batch_id=curr_batch_id,
                        gst=item_gst,
                        stocks=item.stock_infos.stocks,
                        stocks_before=prev_stocks_before,
                        stocks_after=prev_stocks_before + item.stock_infos.stocks,
                        serial_numbers=norm_new_serials
                    )
                )

            buy_price_val = item.pricing_infos.buy_price if item.pricing_infos else (prev_pricing.buy_price if prev_pricing else 0.0)
            sell_price_val = item.pricing_infos.sell_price if item.pricing_infos else (prev_pricing.sell_price if prev_pricing else 0.0)

            if is_new_item:
                pricing_toadd.append(
                    PurchaseItemsPricing(
                        purchase_id=data.id,
                        purchase_item_id=pur_item_id,
                        buy_price=buy_price_val,
                        sell_price=sell_price_val
                    )
                )
            else:
                if item.pricing_infos:
                    pricing_toupdate.append(
                        UpdatePurchasePricingDbSchema(
                            purchase_id=data.id,
                            purchase_item_id=pur_item_id,
                            buy_price=buy_price_val,
                            sell_price=sell_price_val
                        )
                    )

            if item.storage_location_infos:
                if is_new_item:
                    stl_toadd.append(
                        PurchaseItemsStoragelocation(
                            purchase_item_id=pur_item_id,
                            purchase_id=data.id,
                            name=item.storage_location_infos.name
                        )
                    )
                else:
                    if prev_stl:
                        stl_toupdate.append(
                            UpdateStorageLocationDbSchema(
                                purchase_item_id=pur_item_id,
                                purchase_id=data.id,
                                name=item.storage_location_infos.name
                            )
                        )
                    else:
                        stl_toadd.append(
                            PurchaseItemsStoragelocation(
                                purchase_item_id=pur_item_id,
                                purchase_id=data.id,
                                name=item.storage_location_infos.name
                            )
                        )

            if item.reorder_point_infos:
                if is_new_item:
                    rop_toadd.append(
                        PurchaseItemsReorderPoint(
                            purchase_item_id=pur_item_id,
                            purchase_id=data.id,
                            reorder_point=item.reorder_point_infos.reorder_point
                        )
                    )
                else:
                    if prev_rop:
                        rop_toupdate.append(
                            UpdateReorderPointDbSchema(
                                purchase_item_id=pur_item_id,
                                purchase_id=data.id,
                                reorder_point=item.reorder_point_infos.reorder_point
                            )
                        )
                    else:
                        rop_toadd.append(
                            PurchaseItemsReorderPoint(
                                purchase_item_id=pur_item_id,
                                purchase_id=data.id,
                                reorder_point=item.reorder_point_infos.reorder_point
                            )
                        )

            # Construct Delta stock adjustments for Inventory updates
            prev_sn_dict = {}
            if not is_new_item and db_item:
                for sn in (db_item.serial_numbers or []):
                    sn_name, sn_id = extract_sn_info(sn)
                    if sn_name:
                        prev_sn_dict[sn_name] = {"id": sn_id, "name": sn_name} if sn_id else {"name": sn_name}

            new_sn_dict = {}
            for sn in norm_new_serials:
                sn_name = sn.get("name") or ""
                if sn_name:
                    new_sn_dict[sn_name] = sn

            added_names = set(new_sn_dict.keys()) - set(prev_sn_dict.keys())
            removed_names = set(prev_sn_dict.keys()) - set(new_sn_dict.keys())

            added_sn_infos = [new_sn_dict[name] for name in added_names]

            if is_new_item:
                inventory_toupdate.append({
                    'shop_id': data.shop_id,
                    'product_id': item.product_id,
                    'variant_id': curr_variant_id,
                    'batch_infos': item.batch_infos.model_dump(mode="json") if item.batch_infos else ({'id': curr_batch_id} if curr_batch_id else None),
                    'serialno_infos': norm_new_serials,
                    'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                    'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                    'gst': item_gst,
                    'buy_price': buy_price_val,
                    'sell_price': sell_price_val,
                    'stocks': stock_toupdate,
                    'type': 'INCREMENT',
                    "entity_name": 'PURCHASE_UPDATE',
                    "entity_id": effective_pur_identifier,
                    'create_stock_mov_adj': True
                })
            else:
                # Standard Delta stock adjustment only when product was NOT replaced (since product replacement handles its own DECREMENT/INCREMENT)
                if item.product_id == old_product_id:
                    # Existing item stock INCREMENT
                    if stock_diff > 0:
                        inventory_toupdate.append({
                            'shop_id': data.shop_id,
                            'product_id': item.product_id,
                            'variant_id': curr_variant_id,
                            'batch_infos': item.batch_infos.model_dump(mode="json") if item.batch_infos else ({'id': curr_batch_id} if curr_batch_id else None),
                            'serialno_infos': added_sn_infos,
                            'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                            'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                            'gst': item_gst,
                            'buy_price': buy_price_val,
                            'sell_price': sell_price_val,
                            'stocks': stock_diff,
                            'type': 'INCREMENT',
                            "entity_name": 'PURCHASE_UPDATE',
                            "entity_id": effective_pur_identifier,
                            'create_stock_mov_adj': True
                        })
                    # Existing item stock DECREMENT
                    elif stock_diff < 0:
                        rem_sn_infos = []
                        if has_variant and prev_variant_id:
                            variants = prod_doc.get("variants") or {}
                            variant_data = {}
                            if isinstance(variants, dict):
                                variant_data = variants.get(prev_variant_id) or {}
                            elif isinstance(variants, list):
                                for v in variants:
                                    if v.get("id") == prev_variant_id:
                                        variant_data = v
                                        break
                            if has_batch and prev_batch_id:
                                batches_list = variant_data.get("batch_infos") or []
                                batch_data = {}
                                for b in batches_list:
                                    if b.get("id") == prev_batch_id or b.get("name") == prev_batch_id:
                                        batch_data = b
                                        break
                                cur_prod_sns = batch_data.get("serialno_infos") or []
                            else:
                                cur_prod_sns = variant_data.get("serialno_infos") or []
                        elif has_batch and prev_batch_id:
                            batches_list = prod_doc.get("batch_infos") or []
                            batch_data = {}
                            for b in batches_list:
                                if b.get("id") == prev_batch_id or b.get("name") == prev_batch_id:
                                    batch_data = b
                                    break
                            cur_prod_sns = batch_data.get("serialno_infos") or []
                        else:
                            cur_prod_sns = prod_doc.get("serialno_infos") or []
                        cur_sn_map = {sn.get("name"): sn.get("id") for sn in cur_prod_sns if isinstance(sn, dict) and sn.get("name")}
                        for sn_name in removed_names:
                            prev_sn_obj = prev_sn_dict.get(sn_name) or {}
                            sn_id = prev_sn_obj.get("id") or cur_sn_map.get(sn_name)
                            if sn_id:
                                rem_sn_infos.append({"id": sn_id, "name": sn_name})
                            else:
                                rem_sn_infos.append({"name": sn_name})

                        inventory_toupdate.append({
                            'shop_id': data.shop_id,
                            'product_id': item.product_id,
                            'variant_id': db_item.variant_id if db_item else prev_variant_id,
                            'batch_infos': {'id': db_item.batch_id} if (db_item and db_item.batch_id) else ({'id': prev_batch_id} if prev_batch_id else None),
                            'serialno_infos': rem_sn_infos,
                            'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                            'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                            'gst': item_gst,
                            'buy_price': buy_price_val,
                            'sell_price': sell_price_val,
                            'stocks': abs(stock_diff),
                            'type': 'DECREMENT',
                            "entity_name": 'PURCHASE_UPDATE',
                            "entity_id": effective_pur_identifier,
                            'create_stock_mov_adj': True
                        })
                    # If stock quantity is unchanged, but serial numbers were swapped/replaced or just prices updated:
                    else:
                        if added_sn_infos:
                            inventory_toupdate.append({
                                'shop_id': data.shop_id,
                                'product_id': item.product_id,
                                'variant_id': curr_variant_id,
                                'batch_infos': item.batch_infos.model_dump(mode="json") if item.batch_infos else ({'id': curr_batch_id} if curr_batch_id else None),
                                'serialno_infos': added_sn_infos,
                                'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                                'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                                'gst': item_gst,
                                'buy_price': buy_price_val,
                                'sell_price': sell_price_val,
                                'stocks': 0.0,
                                'type': 'INCREMENT',
                                "entity_name": 'PURCHASE_UPDATE',
                                "entity_id": effective_pur_identifier,
                                'create_stock_mov_adj': True
                            })
                        if removed_names:
                            rem_swapped_infos = []
                            for sn_name in removed_names:
                                prev_sn_obj = prev_sn_dict.get(sn_name) or {}
                                sn_id = prev_sn_obj.get("id")
                                if sn_id:
                                    rem_swapped_infos.append({"id": sn_id, "name": sn_name})
                                else:
                                    rem_swapped_infos.append({"name": sn_name})
                            inventory_toupdate.append({
                                'shop_id': data.shop_id,
                                'product_id': item.product_id,
                                'variant_id': db_item.variant_id if db_item else prev_variant_id,
                                'batch_infos': {'id': db_item.batch_id} if (db_item and db_item.batch_id) else ({'id': prev_batch_id} if prev_batch_id else None),
                                'serialno_infos': rem_swapped_infos,
                                'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                                'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                                'gst': item_gst,
                                'buy_price': buy_price_val,
                                'sell_price': sell_price_val,
                                'stocks': 0.0,
                                'type': 'DECREMENT',
                                "entity_name": 'PURCHASE_UPDATE',
                                "entity_id": effective_pur_identifier,
                                'create_stock_mov_adj': True
                            })
                        if not added_sn_infos and not removed_names:
                            # Update prices and details even if stock quantity is unchanged
                            inventory_toupdate.append({
                                'shop_id': data.shop_id,
                                'product_id': item.product_id,
                                'variant_id': curr_variant_id,
                                'batch_infos': item.batch_infos.model_dump(mode="json") if item.batch_infos else ({'id': curr_batch_id} if curr_batch_id else None),
                                'serialno_infos': [],
                                'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                                'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                                'gst': item_gst,
                                'buy_price': buy_price_val,
                                'sell_price': sell_price_val,
                                'stocks': 0.0,
                                'type': 'INCREMENT',
                                "entity_name": 'PURCHASE_UPDATE',
                                "entity_id": effective_pur_identifier,
                                'create_stock_mov_adj': False
                            })

            tot_pur_cost=buy_price_val * stock_toupdate
            item_infos['total_pur_stocks']+=stock_toupdate
            item_infos['total_pur_cost']+=tot_pur_cost
            effective_gst_infos = getattr(data, "gst_infos", None) or prev_gst_infos
            gst_type = ""
            if effective_gst_infos:
                if isinstance(effective_gst_infos, dict):
                    gst_type = effective_gst_infos.get('type') or ""
                else:
                    gst_type = getattr(effective_gst_infos, 'type', '') or ""
            if not gst_type:
                gst_type = "EXCLUSIVE"

            if item_gst and item_gst.endswith('%') and gst_type == "EXCLUSIVE":
                try:
                    gst_rate = float(item_gst[:-1]) / 100.0
                    item_infos['total_gst_amount'] += gst_rate * (tot_pur_cost)
                except ValueError:
                    pass
            item_infos['total_pur_items']+=1

        old_version = getattr(pur_get_res, "version", "v1") or "v1"
        def increment_version(version_str: str) -> str:
            if not version_str or not version_str.startswith('v'):
                return 'v2'
            try:
                num = int(version_str[1:])
                return f"v{num + 1}"
            except ValueError:
                return 'v2'
        new_version = increment_version(old_version)

        effective_supplier_id = data.supplier_id or pur_get_res.supplier_id
        effective_invoice_no = data.invoice_no or pur_get_res.invoice_no
        effective_status = data.status or pur_get_res.status
        effective_date = data.purchase_date or pur_get_res.date

        purchase_toadd = UpdatePurchaseDbSchema(
            id=data.id,
            shop_id=data.shop_id,
            supplier_id=effective_supplier_id,
            invoice_no=effective_invoice_no,
            status=effective_status,
            date=effective_date,
            item_infos=item_infos,
            version=new_version,
            **data.model_dump(mode="json", exclude=['purchase_date', 'item_infos', 'id', 'shop_id', 'supplier_id', 'invoice_no', 'status'])
        )

        pur_add_res=await purchase_repo_obj.update_bulk_purchase(data=[purchase_toadd])
        self.session.expire_all()
        ic(pur_add_res)
        if pur_add_res:
            if data.custom_fields:
                cust_obj=await CustomFieldsService(session=self.session).upsert_values(
                data=CreateCustomFieldValueSchema(
                        shop_id=data.shop_id,
                        purchase_id=data.id,
                        value_infos=[
                            {'field_id':id,"value":value}
                            for id,value in data.custom_fields.items()
                        ]
                    )
                )
                ic(cust_obj)
                
            if items_todelete_ids:
                await purchase_repo_obj.delete_bulk_items(items_todelete_ids)
            if items_toadd:
                await purchase_repo_obj.create_bulk_items(data=items_toadd)
            await purchase_repo_obj.update_bulk_item(data=items_toupdate)
            if pricing_toadd:
                await purchase_repo_obj.create_bulk_pricing(data=pricing_toadd)
            if pricing_toupdate:
                await purchase_repo_obj.update_bulk_pricing(data=pricing_toupdate)
            if stl_toadd:
                await purchase_repo_obj.create_bulk_stl(data=stl_toadd)
            if stl_toupdate:
                await purchase_repo_obj.update_bulk_stl(data=stl_toupdate)
            if rop_toadd:
                await purchase_repo_obj.create_bulk_rop(data=rop_toadd)
            if rop_toupdate:
                await purchase_repo_obj.update_bulk_rop(data=rop_toupdate)

        # Update Read DB (MongoDB) and Analytics Event
        try:
            existing_read_doc = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
            fresh_pur = await purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
            
            existing_items_map = {}
            if existing_read_doc and "items" in existing_read_doc:
                for itm in existing_read_doc["items"]:
                    existing_items_map[itm["id"]] = itm
                    
            read_items = []
            total_pur_cost = 0.0
            total_pur_stocks = 0.0
            total_gst_amount = 0.0
            
            for db_item in fresh_pur.items:
                item_id = db_item.id
                existing_item = existing_items_map.get(item_id) or {}
                
                prod_doc = product_docs.get(db_item.product_id) or {}
                
                product_name = prod_doc.get("name") or existing_item.get("name") or "Product"
                product_ui_id = prod_doc.get("ui_id") or existing_item.get("ui_id") or "PROD"
                category_infos = prod_doc.get("category_infos") or existing_item.get("category_infos")
                unit_infos = prod_doc.get("unit_infos") or existing_item.get("unit_infos")
                
                buy_price = db_item.pricing_infos[0].buy_price if db_item.pricing_infos else 0.0
                sell_price = db_item.pricing_infos[0].sell_price if db_item.pricing_infos else 0.0
                stocks = db_item.stocks
                
                total_amount = buy_price * stocks
                total_pur_cost += total_amount
                total_pur_stocks += stocks
                
                gst = db_item.gst or "0%"
                gst_rate = 0.0
                if gst and gst.endswith('%'):
                    try:
                        gst_rate = float(gst[:-1]) / 100.0
                    except ValueError:
                        pass
                
                gst_infos_val = data.gst_infos if hasattr(data, "gst_infos") and data.gst_infos else (existing_read_doc.get("gst_infos") if existing_read_doc else {})
                if gst_infos_val and gst_infos_val.get("type") == "EXCLUSIVE":
                    total_gst_amount += gst_rate * total_amount
                    
                variant_infos_model = None
                resolved_v_id = db_item.variant_id or (existing_item.get("variant_infos", {}).get("id") if existing_item.get("variant_infos") else None)
                if resolved_v_id:
                    variants_raw = prod_doc.get("variants") or {}
                    match_var_name = ""
                    if isinstance(variants_raw, dict):
                        match_var = variants_raw.get(resolved_v_id) or {}
                        match_var_name = match_var.get("name") or ""
                    elif isinstance(variants_raw, list):
                        for v in variants_raw:
                            if v.get("id") == resolved_v_id:
                                match_var_name = v.get("name") or ""
                                break
                    if not match_var_name and existing_item.get("variant_infos"):
                        match_var_name = existing_item["variant_infos"].get("name") or ""
                    variant_infos_model = ReadVariantInfos(
                        id=resolved_v_id,
                        name=match_var_name or "Variant"
                    )
                    
                batch_infos_model = None
                resolved_b_id = db_item.batch_id or (existing_item.get("batch_infos", {}).get("id") if existing_item.get("batch_infos") else None)
                if resolved_b_id or existing_item.get("batch_infos"):
                    batches_list = []
                    if resolved_v_id:
                        variants_raw = prod_doc.get("variants") or {}
                        variant_data = {}
                        if isinstance(variants_raw, dict):
                            variant_data = variants_raw.get(resolved_v_id) or {}
                        elif isinstance(variants_raw, list):
                            for v in variants_raw:
                                if v.get("id") == resolved_v_id:
                                    variant_data = v
                                    break
                        batches_list = variant_data.get("batch_infos") or []
                    else:
                        batches_list = prod_doc.get("batch_infos") or []
                    match_batch = None
                    for b in batches_list:
                        if b.get("id") == resolved_b_id or b.get("name") == resolved_b_id:
                            match_batch = b
                            break
                    if match_batch:
                        batch_infos_model = ReadBatchInfos(
                            id=match_batch.get("id") or resolved_b_id or "",
                            name=match_batch.get("name") or "",
                            mfg_date=str(match_batch.get("manufacturing_date") or match_batch.get("mfg_date") or ""),
                            exp_date=str(match_batch.get("expiry_date") or match_batch.get("exp_date") or "")
                        )
                    elif existing_item.get("batch_infos"):
                        batch_infos_model = ReadBatchInfos(**existing_item["batch_infos"])
                    
                stock_infos_model = ReadStocksInfos(
                    stocks=stocks,
                    stocks_before=db_item.stocks_before,
                    stocks_after=db_item.stocks_after
                )
                
                reorder_point_model = None
                if db_item.reorder_point:
                    reorder_point_model = ReadReorderPointInfos(
                        id=str(db_item.reorder_point[0].id),
                        reorder_point=db_item.reorder_point[0].reorder_point
                    )
                    
                storage_location_model = None
                if db_item.storage_locations:
                    storage_location_model = ReadStorageLocationInfos(
                        id=str(db_item.storage_locations[0].id),
                        name=db_item.storage_locations[0].name
                    )
                    
                read_items.append(
                    PurchaseItemReadModel(
                        id=item_id,
                        product_id=db_item.product_id,
                        ui_id=product_ui_id,
                        name=product_name,
                        category_infos=category_infos,
                        unit_infos=unit_infos,
                        variant_infos=variant_infos_model,
                        batch_infos=batch_infos_model,
                        stocks_infos=stock_infos_model,
                        reorder_point_infos=reorder_point_model,
                        storage_location_infos=storage_location_model,
                        serial_numbers=db_item.serial_numbers or [],
                        sell_price=sell_price,
                        buy_price=buy_price,
                        total_amount=total_amount,
                        gst=gst
                    )
                )
                
            payment_infos = data.payment_infos if data.payment_infos is not None else (existing_read_doc.get("payment_infos") if existing_read_doc else [])
            payment_infos_dicts = [p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in payment_infos]
            total_amount_paid = sum(float(payment.get('amount', 0)) for payment in payment_infos_dicts)
            
            final_total_cost = float(total_pur_cost + total_gst_amount)
            charges_infos = data.charges_infos.model_dump(mode="json") if data.charges_infos else (existing_read_doc.get("charges_infos") if existing_read_doc else {})
            total_purchase_cost = final_total_cost
            
            if round(total_amount_paid, 2) > round(total_purchase_cost, 2):
                from fastapi import HTTPException
                from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Updating Purchase",
                        status_code=400,
                        description=f"Paid amount ({total_amount_paid}) cannot exceed total purchase cost ({total_purchase_cost}).",
                        success=False
                    )
                )
                
            outstanding_amount = max(0.0, round(total_purchase_cost - total_amount_paid, 2))
            
            if outstanding_amount == 0:
                outstanding_status = "COMPLETED"
            elif total_amount_paid == 0:
                outstanding_status = "NOT-PAID"
            else:
                outstanding_status = "PARTIALY-PAID"
                
            supplier_id = fresh_pur.supplier_id
            old_supplier_id = original_supplier_id
            old_supplier_name = original_supplier_name

            if old_supplier_id and supplier_id == old_supplier_id and old_supplier_name and old_supplier_name != "Supplier":
                supplier_name = old_supplier_name
            else:
                supplier_name = await get_supplier_name(fresh_pur.shop_id, supplier_id)
                
            supplier_info = SupplierInfo(supplier_id=supplier_id, supplier_name=supplier_name)
            
            cf_dict = {}
            cf_data = data.custom_fields or (existing_read_doc.get("custom_fields") if existing_read_doc else {})
            if isinstance(cf_data, dict):
                if "values" in cf_data:
                    for v in cf_data.get("values"):
                        if "field_name" in v and "value" in v:
                            cf_dict[v["field_name"]] = v["value"]
                else:
                    cf_dict = cf_data
                    
            purchase_read_model = PurchaseReadModel(
                purchase_id=fresh_pur.id,
                ui_id=fresh_pur.ui_id,
                invoice_no=fresh_pur.invoice_no or "",
                shop_id=fresh_pur.shop_id,
                purchase_date=fresh_pur.date,
                supplier=supplier_info,
                total_cost=final_total_cost,
                total_items=len(read_items),
                total_quantity=total_pur_stocks,
                payment_infos=payment_infos_dicts,
                charges_infos=data.charges_infos.model_dump(mode="json") if data.charges_infos else (existing_read_doc.get("charges_infos") if existing_read_doc else {}),
                gst_infos=gst_infos_val,
                payment_status=outstanding_status,
                outstanding_amount=outstanding_amount,
                calculations=data.calculation_infos.model_dump(mode="json") if data.calculation_infos else (existing_read_doc.get("calculations") if existing_read_doc else {}),
                custom_fields=cf_dict,
                items=read_items,
                item_infos=item_infos,
                version=new_version,
                paid_amount=total_amount_paid
            )
            
            # Save history copy to PG
            await purchase_repo_obj.create_history(
                purchase_id=fresh_pur.id,
                version=new_version,
                purchase_data=purchase_read_model.model_dump(mode="json", exclude={"history"})
            )
            
            await PurchaseReadDbRepo.update_purchase_with_history(purchase_read_model.model_dump(mode="json"), new_version)
            
            # Send delta analytics event
            try:
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                
                old_supplier_id = original_supplier_id
                old_outstanding = original_outstanding
                new_outstanding = outstanding_amount

                # Handle Supplier Transfer if Supplier ID Changed
                if old_supplier_id and supplier_id and old_supplier_id != supplier_id:
                    # 1. Reverse/remove outstanding from previous supplier
                    if old_outstanding > 0:
                        try:
                            old_supplier_payload = {
                                "id": old_supplier_id,
                                "shop_id": fresh_pur.shop_id,
                                "outstanding_infos": {
                                    "amount": float(old_outstanding)
                                },
                                "type": "DECREMENT",
                                "entity_name": "purchase",
                                "entity_id": fresh_pur.id,
                                "notes": "transferred outstanding to new supplier"
                            }
                            await rabbitmq_msg_obj.publish_event(
                                routing_key="suppliers.service.routing.key",
                                exchange_name="suppliers.service.exchange",
                                payload=old_supplier_payload,
                                headers={
                                    "entity_name": "update_supllier_outstanding",
                                    "service_name": "SUPPLIERS",
                                    "saga_id": "none",
                                    "reply_key": "none",
                                    "reply_exchange": "none",
                                    "reply_entity_name": "none",
                                    "body": old_supplier_payload
                                }
                            )
                        except Exception as e:
                            ic(f"Failed to publish old supplier outstanding decrement: {e}")

                    # 2. Add full new outstanding to new supplier
                    if new_outstanding > 0:
                        try:
                            new_supplier_payload = {
                                "id": supplier_id,
                                "shop_id": fresh_pur.shop_id,
                                "outstanding_infos": {
                                    "amount": float(new_outstanding)
                                },
                                "type": "INCREMENT"
                            }
                            await rabbitmq_msg_obj.publish_event(
                                routing_key="suppliers.service.routing.key",
                                exchange_name="suppliers.service.exchange",
                                payload=new_supplier_payload,
                                headers={
                                    "entity_name": "update_supllier_outstanding",
                                    "service_name": "SUPPLIERS",
                                    "saga_id": "none",
                                    "reply_key": "none",
                                    "reply_exchange": "none",
                                    "reply_entity_name": "none",
                                    "body": new_supplier_payload
                                }
                            )
                        except Exception as e:
                            ic(f"Failed to publish new supplier outstanding increment: {e}")

                    # Recalculate supplier stats for both old and new supplier
                    import asyncio
                    from infras.read_db.repos.purchase_repo import SupplierStatsReadDbRepo
                    asyncio.create_task(SupplierStatsReadDbRepo.update_supplier_stats(fresh_pur.shop_id, old_supplier_id))
                    asyncio.create_task(SupplierStatsReadDbRepo.update_supplier_stats(fresh_pur.shop_id, supplier_id))

                else:
                    paid_diff = round(total_amount_paid - original_paid_amount, 2)
                    outstanding_diff = round(new_outstanding - old_outstanding, 2)

                    if paid_diff != 0 or outstanding_diff != 0:
                        if paid_diff > 0:
                            update_type = "DECREMENT"
                            diff_amount = paid_diff
                            last_payment = payment_infos_dicts[-1] if payment_infos_dicts else {}
                            pay_method = last_payment.get("mode") or last_payment.get("method") or "ADJUSTMENT"
                            if hasattr(pay_method, "value"):
                                pay_method = pay_method.value
                            notes_str = last_payment.get("notes") or f"Additional payment of {paid_diff} for purchase {getattr(fresh_pur, 'invoice_no', '')}"
                            cleared_amt = float(paid_diff)
                        elif paid_diff < 0:
                            update_type = "INCREMENT"
                            diff_amount = abs(paid_diff)
                            last_payment = payment_infos_dicts[-1] if payment_infos_dicts else {}
                            pay_method = last_payment.get("mode") or last_payment.get("method") or "ADJUSTMENT"
                            if hasattr(pay_method, "value"):
                                pay_method = pay_method.value
                            notes_str = f"Payment reduced by {abs(paid_diff)} for purchase {getattr(fresh_pur, 'invoice_no', '')}"
                            cleared_amt = 0.0
                        elif outstanding_diff > 0:
                            update_type = "INCREMENT"
                            diff_amount = outstanding_diff
                            last_payment = payment_infos_dicts[-1] if payment_infos_dicts else {}
                            pay_method = last_payment.get("mode") or last_payment.get("method") or "ADJUSTMENT"
                            if hasattr(pay_method, "value"):
                                pay_method = pay_method.value
                            notes_str = f"Purchase updated (cost increased by {outstanding_diff})"
                            cleared_amt = 0.0
                        else:
                            update_type = "DECREMENT"
                            diff_amount = abs(outstanding_diff)
                            last_payment = payment_infos_dicts[-1] if payment_infos_dicts else {}
                            pay_method = last_payment.get("mode") or last_payment.get("method") or "ADJUSTMENT"
                            if hasattr(pay_method, "value"):
                                pay_method = pay_method.value
                            notes_str = f"Purchase updated (cost reduced by {abs(outstanding_diff)})"
                            cleared_amt = 0.0

                        try:
                            supplier_payload = {
                                "id": supplier_id,
                                "shop_id": fresh_pur.shop_id,
                                "outstanding_infos": {
                                    "amount": float(diff_amount)
                                },
                                "type": update_type,
                                "entity_name": "purchase",
                                "entity_id": fresh_pur.id,
                                "invoice_no": getattr(fresh_pur, "invoice_no", None),
                                "payment_method": str(pay_method),
                                "notes": notes_str,
                                "cleared_amount": cleared_amt,
                                "outstanding_amount": float(new_outstanding)
                            }
                            await rabbitmq_msg_obj.publish_event(
                                routing_key="suppliers.service.routing.key",
                                exchange_name="suppliers.service.exchange",
                                payload=supplier_payload,
                                headers={
                                    "entity_name": "update_supllier_outstanding",
                                    "service_name": "SUPPLIERS",
                                    "saga_id": "none",
                                    "reply_key": "none",
                                    "reply_exchange": "none",
                                    "reply_entity_name": "none",
                                    "body": supplier_payload
                                }
                            )
                        except Exception as e:
                            ic(f"Failed to publish supplier outstanding update: {e}")

                delta_outstanding = new_outstanding - old_outstanding
                
                old_items_map = {}
                if existing_read_doc and "items" in existing_read_doc:
                    for itm in existing_read_doc["items"]:
                        key = (itm["product_id"], itm.get("variant_infos", {}).get("id") if itm.get("variant_infos") else None, itm.get("batch_infos", {}).get("id") if itm.get("batch_infos") else None)
                        old_items_map[key] = itm
                        
                analytics_datas = []
                for i, item in enumerate(read_items):
                    key = (item.product_id, item.variant_infos.id if item.variant_infos else None, item.batch_infos.id if item.batch_infos else None)
                    old_item = old_items_map.get(key) or {}
                    
                    old_stocks = float(old_item.get("stocks_infos", {}).get("stocks", 0.0)) if old_item.get("stocks_infos") else 0.0
                    old_amount = float(old_item.get("total_amount", 0.0))
                    
                    delta_stocks = float(item.stocks_infos.stocks) - old_stocks
                    delta_amount = float(item.total_amount) - old_amount
                    
                    item_outstanding_delta = delta_outstanding if i == 0 else 0.0
                    
                    analytics_datas.append({
                        "purchase_id": fresh_pur.id,
                        "supplier_id": supplier_id,
                        "product_id": item.product_id,
                        "variant_id": item.variant_infos.id if item.variant_infos else None,
                        "batch_id": item.batch_infos.id if item.batch_infos else None,
                        "stocks": delta_stocks,
                        "purchase_amounts": delta_amount,
                        "outstanding_amounts": item_outstanding_delta
                    })
                    
                analytics_payload = {
                    "shop_id": fresh_pur.shop_id,
                    "total_purchase": 0,
                    "datas": analytics_datas
                }
                
                await rabbitmq_msg_obj.publish_event(
                    routing_key="analytics.service.routing.key",
                    exchange_name="analytics.service.exchange",
                    payload=analytics_payload,
                    headers={
                        "entity_name": "purchase_event",
                        "service_name": "ANALYTICS",
                        "saga_id": "none",
                        "reply_key": "none",
                        "reply_exchange": "none",
                        "reply_entity_name": "none",
                        "body": analytics_payload
                    }
                )
            except Exception as e:
                ic(f"Failed to publish analytics delta event: {e}")
                
        except Exception as e:
            ic(f"Failed to update MongoDB Read DB: {e}")

        # Saga Product update emission
        if inventory_toupdate:
            routing_key = "products.service.routing.key"
            exchange_name = "products.service.exchange"
            entity_name = "update_bulk_prodinv"
            service_name = "PRODUCTS"


            saga_id:str=generate_uuid()
            steps={
                "PRODUCT_VERIFY_UPDATE":SagaStepsValueEnum.PENDING
            }

            saga_data={"purchase":data.model_dump(mode="json")}
            await SagaProducer.emit(
                saga_payload=CreateSagaStateSchema(
                    id=saga_id,
                    status=SagaStatusEnum.IN_PROGRESS,
                    type="PURCHASE_UPDATED",
                    steps=steps,
                    execution=SagaStateExecutionTypDict(
                        step="PRODUCT_VERIFY_UPDATE",
                        service=service_name
                    ),
                    data=saga_data
                ),
                routing_key=routing_key,
                exchange_name=exchange_name,
                headers={
                    "reply_key":"None",
                    "reply_exchange":"None",
                    "reply_entity_name":"None",
                    "reply_service_name":"None",
                    "service_name":service_name,
                    "entity_name":entity_name,
                    "body":json.dumps(inventory_toupdate)

                }
            )


        try:
            invoice_no = getattr(data, 'invoice_no', None) or str(data.id)
            from messaging.main import RabbitMQMessagingConfig
            rabbitmq_msg_obj = RabbitMQMessagingConfig()

            def _is_empty_or_none(val):
                if val is None: return True
                if isinstance(val, (dict, list, set, str, tuple)) and len(val) == 0: return True
                return str(val).strip() in ("None", "{}", "[]", "", "null", "NoneType")

            dumped_updates = data.model_dump(exclude_unset=True, exclude_none=True)
            changes = []
            for key, new_val in dumped_updates.items():
                if key in ["id", "shop_id", "user_id", "cur_user_id"]:
                    continue
                prev_val = purchase_get_res.get(key) if 'purchase_get_res' in locals() and isinstance(purchase_get_res, dict) else None
                if _is_empty_or_none(prev_val) and _is_empty_or_none(new_val):
                    continue
                if prev_val != new_val and str(prev_val).strip() != str(new_val).strip():
                    changes.append({
                        "field": key,
                        "before": str(prev_val) if prev_val is not None else "None",
                        "after": str(new_val) if new_val is not None else "None"
                    })

            await rabbitmq_msg_obj.publish_event(
                routing_key="activity_logs.routing.key",
                exchange_name="activity_logs.exchange",
                payload={
                    "shop_id": data.shop_id,
                    "user_name": "Hyperlocal-User",
                    "service": "Purchase",
                    "action": "UPDATED",
                    "entity_type": "PURCHASE",
                    "entity_id": str(data.id),
                    "entity_name": str(invoice_no),
                    "description": f"Updated Purchase {invoice_no} ({data.id})",
                    "changes": changes
                },
                headers={}
            )
        except Exception as e:
            ic(f"Failed to publish activity log: {e}")

        return True

    async def delete(self,data:DeletePurchaseSchema):
        final_data=DeletePurchaseDbSchema(**data.model_dump(mode="json"))
        res = await self.purchase_repo_obj.delete_purchase(data=final_data)
        
        if res:
            try:
                invoice_no = str(data.id)
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                await rabbitmq_msg_obj.publish_event(
                    routing_key="activity_logs.routing.key",
                    exchange_name="activity_logs.exchange",
                    payload={
                        "shop_id": data.shop_id,
                        "user_name": "Hyperlocal-User",
                        "service": "Purchase",
                        "action": "DELETED",
                        "entity_type": "PURCHASE",
                        "entity_id": str(data.id),
                        "entity_name": str(invoice_no),
                        "description": f"Deleted Purchase {invoice_no} ({data.id})",
                        "changes": []
                    },
                    headers={}
                )
            except Exception as e:
                ic(f"Failed to publish activity log: {e}")

        return res


    async def get_purchases(self,data:GetAllPurchaseSchemas):
        return await self.purchase_repo_obj.get_purchases(data=data)

    async def get_purchase_by_id(self,data:GetPurchaseByIdSchema):
        return await self.purchase_repo_obj.get_purchase_by_id(data=data)
    
    async def get_purchase_by_shop_id(self,data:GetPurchaseByShopIdSchema):
        return await self.purchase_repo_obj.get_purchase_by_shop_id(data=data)
    
    async def get_history(self, purchase_id: str):
        return await self.purchase_repo_obj.get_history_by_purchase_id(purchase_id=purchase_id)

    async def cancel(self, data: CancelPurchaseSchema, executing_user_id: Optional[str] = None) -> dict:
        from sqlalchemy import update
        from fastapi import HTTPException
        from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
        from infras.read_db.main import PURCHAESE_COLLECTION, MONGO_CLIENT
        import asyncio
        from infras.read_db.repos.purchase_repo import SupplierStatsReadDbRepo, PurchaseStatsReadDbRepo

        shop_id = data.shop_id
        purchase_id = data.id

        pur_db_res = await self.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id))
        read_doc = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id))

        if not pur_db_res and not read_doc:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponseTypDict(
                    msg="Error : Canceling Purchase",
                    status_code=404,
                    description=f"Purchase with ID '{purchase_id}' not found.",
                    success=False
                )
            )

        current_status = getattr(pur_db_res, 'status', None) or (read_doc.get("status") if read_doc else None)
        if current_status and str(current_status).upper() == "CANCELED":
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Canceling Purchase",
                    status_code=400,
                    description="Purchase is already canceled.",
                    success=False
                )
            )

        # Check if purchase has any existing returns
        from sqlalchemy import select, func
        from infras.primary_db.models.purchase_model import PurchaseReturns

        stmt_ret = select(func.count(PurchaseReturns.id)).where(PurchaseReturns.purchase_id == purchase_id)
        res_ret = await self.session.execute(stmt_ret)
        pg_returns_count = res_ret.scalar() or 0

        has_mongo_returns = bool(read_doc and read_doc.get("returns") and len(read_doc.get("returns")) > 0)
        has_returned_items = False
        if read_doc and read_doc.get("items"):
            for itm in read_doc["items"]:
                if isinstance(itm, dict) and (float(itm.get("returned_quantity") or 0) > 0 or (itm.get("returns") and len(itm.get("returns")) > 0)):
                    has_returned_items = True
                    break

        if pg_returns_count > 0 or has_mongo_returns or has_returned_items:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Canceling Purchase",
                    status_code=400,
                    description="Cannot cancel purchase because it has existing purchase returns.",
                    success=False
                )
            )


        invoice_no = getattr(pur_db_res, 'invoice_no', None) or (read_doc.get("invoice_no") if read_doc else purchase_id)

        # Handle DRAFT status
        if current_status and str(current_status).upper() == "DRAFT":
            stmt = (
                update(Purchase)
                .where(Purchase.id == purchase_id, Purchase.shop_id == shop_id)
                .values(status="CANCELED")
            )
            await self.session.execute(stmt)

            await PURCHAESE_COLLECTION.update_one(
                {"$or": [{"purchase_id": purchase_id}, {"id": purchase_id}], "shop_id": shop_id},
                {"$set": {"status": "CANCELED"}}
            )

            await _send_activity_log(
                shop_id=shop_id,
                action="CANCELED",
                entity_id=purchase_id,
                description=f"Canceled Draft Purchase {invoice_no} ({purchase_id})",
                entity_name=str(invoice_no)
            )

            return {
                "success": True,
                "id": purchase_id,
                "status": "CANCELED",
                "msg": "Draft purchase canceled successfully"
            }

        # Handle COMPLETED / active purchase
        raw_items = pur_db_res.items if (pur_db_res and pur_db_res.items) else (read_doc.get("items") or [])
        read_items_map = {itm.get("id"): itm for itm in (read_doc.get("items") or []) if isinstance(itm, dict) and itm.get("id")}

        product_ids = set()
        items_to_process = []

        for item in raw_items:
            if isinstance(item, dict):
                p_id = item.get("product_id")
                item_id = item.get("id")
                v_id = item.get("variant_id") or (item.get("variant_infos", {}).get("id") if isinstance(item.get("variant_infos"), dict) else None)
                b_id = item.get("batch_id") or (item.get("batch_infos", {}).get("id") if isinstance(item.get("batch_infos"), dict) else None)
                stocks_info_dict = item.get("stocks_infos") or item.get("stock_infos") or {}
                purchased_qty = float(stocks_info_dict.get("stocks") if isinstance(stocks_info_dict, dict) and stocks_info_dict.get("stocks") is not None else (item.get("stocks") or item.get("quantity") or 0.0))
                serials = item.get("serial_numbers") or item.get("serialno_numbers") or item.get("serialno_infos") or []
                item_name = item.get("name") or p_id
                returned_qty = float(item.get("returned_quantity") or 0.0)
                buy_price = float(item.get("buy_price") or (item.get("pricing_infos", {}).get("buy_price") if isinstance(item.get("pricing_infos"), dict) else 0.0))
            else:
                p_id = item.product_id
                item_id = item.id
                v_id = item.variant_id
                b_id = item.batch_id
                purchased_qty = float(item.stocks or 0.0)
                serials = item.serial_numbers or []
                item_name = p_id
                read_item_doc = read_items_map.get(item_id) or {}
                returned_qty = float(read_item_doc.get("returned_quantity") or 0.0)
                if read_item_doc.get("name"):
                    item_name = read_item_doc.get("name")
                buy_price = float(item.pricing_infos[0].buy_price if item.pricing_infos else (read_item_doc.get("buy_price") or 0.0))

            if p_id:
                product_ids.add(p_id)
                items_to_process.append({
                    "item_id": item_id,
                    "product_id": p_id,
                    "variant_id": v_id,
                    "batch_id": b_id,
                    "purchased_qty": purchased_qty,
                    "returned_qty": returned_qty,
                    "qty_to_revert": max(0.0, purchased_qty - returned_qty),
                    "serials": serials,
                    "name": item_name,
                    "buy_price": buy_price
                })

        prod_inv_collection = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
        cursor = prod_inv_collection.find({"id": {"$in": list(product_ids)}, "shop_id": shop_id})
        product_docs = {doc["id"]: doc async for doc in cursor}

        # Check physical stock availability for ALL items before making changes
        for proc_item in items_to_process:
            qty_to_revert = proc_item["qty_to_revert"]
            if qty_to_revert <= 0:
                continue

            p_id = proc_item["product_id"]
            v_id = proc_item["variant_id"]
            b_id = proc_item["batch_id"]
            item_name = proc_item["name"]

            prod_doc = product_docs.get(p_id) or {}
            type_infos = prod_doc.get("type_infos") or {}
            has_batch = type_infos.get("has_batch") if type_infos and "has_batch" in type_infos else prod_doc.get("has_batch", False)
            has_variant = type_infos.get("has_variant") if type_infos and "has_variant" in type_infos else prod_doc.get("has_variant", False)

            target_stock_infos = {}
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

            physical_stock = float(target_stock_infos.get("physical_stocks") if target_stock_infos.get("physical_stocks") is not None else (target_stock_infos.get("stocks") or 0.0))

            if physical_stock < qty_to_revert:
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Canceling Purchase",
                        status_code=400,
                        description=f"Cannot cancel purchase because current physical stock for product '{item_name}' ({physical_stock}) is less than the purchased stock ({qty_to_revert}) required to revert.",
                        success=False
                    )
                )

        # Revert stocks and process cancellation
        inventory_toupdate = []
        for proc_item in items_to_process:
            qty_to_revert = proc_item["qty_to_revert"]
            if qty_to_revert <= 0:
                continue

            p_id = proc_item["product_id"]
            v_id = proc_item["variant_id"]
            b_id = proc_item["batch_id"]
            serials = proc_item["serials"]

            normalized_serials = normalize_serial_numbers(serials)

            inventory_toupdate.append({
                "shop_id": shop_id,
                "product_id": p_id,
                "variant_id": v_id,
                "batch_infos": {"id": b_id} if b_id else None,
                "serialno_infos": normalized_serials,
                "stocks": qty_to_revert,
                "type": "DECREMENT",
                "entity_name": "PURCHASE_CANCEL",
                "entity_id": purchase_id,
                "buy_price": proc_item.get("buy_price", 0.0),
                "create_stock_mov_adj": True
            })

            # Update local Mongo ProdInvCollections stock directly
            prod_doc = product_docs.get(p_id)
            if prod_doc:
                type_infos = prod_doc.get("type_infos") or {}
                has_batch = type_infos.get("has_batch") if type_infos and "has_batch" in type_infos else prod_doc.get("has_batch", False)
                has_variant = type_infos.get("has_variant") if type_infos and "has_variant" in type_infos else prod_doc.get("has_variant", False)

                try:
                    if has_variant and v_id:
                        if has_batch and b_id:
                            await prod_inv_collection.update_one(
                                {"id": p_id, "shop_id": shop_id},
                                {"$inc": {"variants.$[v].batch_infos.$[b].stock_infos.physical_stocks": -qty_to_revert}},
                                array_filters=[{"v.id": v_id}, {"b.id": b_id}]
                            )
                        else:
                            await prod_inv_collection.update_one(
                                {"id": p_id, "shop_id": shop_id},
                                {"$inc": {"variants.$[v].stock_infos.physical_stocks": -qty_to_revert}},
                                array_filters=[{"v.id": v_id}]
                            )
                    elif has_batch and b_id:
                        await prod_inv_collection.update_one(
                            {"id": p_id, "shop_id": shop_id},
                            {"$inc": {"batch_infos.$[b].stock_infos.physical_stocks": -qty_to_revert}},
                            array_filters=[{"b.id": b_id}]
                        )
                    else:
                        await prod_inv_collection.update_one(
                            {"id": p_id, "shop_id": shop_id},
                            {"$inc": {"stock_infos.physical_stocks": -qty_to_revert}}
                        )
                except Exception as ex:
                    ic(f"Error updating mongo physical_stocks directly on cancel: {ex}")

        # Update Postgres status
        supplier_id = (getattr(pur_db_res, 'supplier_id', None) if pur_db_res else None) or (read_doc.get("supplier_id") if read_doc else None) or (read_doc.get("supplier", {}).get("supplier_id") if isinstance(read_doc.get("supplier"), dict) else None)
        outstanding_amount = float(read_doc.get("outstanding_amount", 0.0)) if read_doc else 0.0

        stmt = (
            update(Purchase)
            .where(Purchase.id == purchase_id, Purchase.shop_id == shop_id)
            .values(status="CANCELED")
        )
        await self.session.execute(stmt)
        await self.session.commit()

        # Update Read DB Mongo status
        await PURCHAESE_COLLECTION.update_one(
            {"$or": [{"purchase_id": purchase_id}, {"id": purchase_id}], "shop_id": shop_id},
            {"$set": {"status": "CANCELED"}}
        )

        if supplier_id and outstanding_amount > 0:
            try:
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                supplier_payload = {
                    "id": supplier_id,
                    "shop_id": shop_id,
                    "outstanding_infos": {
                        "amount": float(outstanding_amount)
                    },
                    "type": "DECREMENT",
                    "entity_name": "purchase",
                    "entity_id": purchase_id,
                    "invoice_no": invoice_no,
                    "notes": f"canceled purchase {invoice_no}"
                }
                await rabbitmq_msg_obj.publish_event(
                    routing_key="suppliers.service.routing.key",
                    exchange_name="suppliers.service.exchange",
                    payload=supplier_payload,
                    headers={
                        "entity_name": "update_supllier_outstanding",
                        "service_name": "SUPPLIERS",
                        "saga_id": "none",
                        "reply_key": "none",
                        "reply_exchange": "none",
                        "reply_entity_name": "none",
                        "body": supplier_payload
                    }
                )
            except Exception as e:
                ic(f"Failed to publish supplier outstanding decrement on cancel: {e}")

        # Recalculate supplier stats and purchase stats in Mongo
        if supplier_id:
            asyncio.create_task(SupplierStatsReadDbRepo.update_supplier_stats(shop_id, supplier_id))
        asyncio.create_task(PurchaseStatsReadDbRepo.update_stats(shop_id))

        # Send Analytics Reversal Event
        try:
            from messaging.main import RabbitMQMessagingConfig
            rabbitmq_msg_obj = RabbitMQMessagingConfig()

            analytics_datas = []
            for i, proc_item in enumerate(items_to_process):
                qty_reverted = proc_item["qty_to_revert"]
                b_price = proc_item["buy_price"]
                item_amount = qty_reverted * b_price
                item_outstanding_delta = outstanding_amount if i == 0 else 0.0

                analytics_datas.append({
                    "purchase_id": purchase_id,
                    "supplier_id": supplier_id,
                    "product_id": proc_item["product_id"],
                    "variant_id": proc_item["variant_id"],
                    "batch_id": proc_item["batch_id"],
                    "stocks": -qty_reverted,
                    "purchase_amounts": -item_amount,
                    "outstanding_amounts": -item_outstanding_delta
                })

            analytics_payload = {
                "shop_id": shop_id,
                "total_purchase": -1,
                "datas": analytics_datas
            }

            await rabbitmq_msg_obj.publish_event(
                routing_key="analytics.service.routing.key",
                exchange_name="analytics.service.exchange",
                payload=analytics_payload,
                headers={
                    "entity_name": "purchase_event",
                    "service_name": "ANALYTICS",
                    "saga_id": "none",
                    "reply_key": "none",
                    "reply_exchange": "none",
                    "reply_entity_name": "none",
                    "body": analytics_payload
                }
            )
        except Exception as e:
            ic(f"Failed to publish analytics cancel event: {e}")

        # Emit Saga for product inventory update
        if inventory_toupdate:
            routing_key = "products.service.routing.key"
            exchange_name = "products.service.exchange"
            entity_name = "update_bulk_prodinv"
            service_name = "PRODUCTS"

            saga_id: str = generate_uuid()
            steps = {
                "PRODUCT_VERIFY_UPDATE": SagaStepsValueEnum.PENDING
            }

            saga_data = {"purchase": {"id": purchase_id, "shop_id": shop_id, "status": "CANCELED"}}
            try:
                await SagaProducer.emit(
                    saga_payload=CreateSagaStateSchema(
                        id=saga_id,
                        status=SagaStatusEnum.IN_PROGRESS,
                        type="PURCHASE_CANCELED",
                        steps=steps,
                        execution=SagaStateExecutionTypDict(
                            step="PRODUCT_VERIFY_UPDATE",
                            service=service_name
                        ),
                        data=saga_data
                    ),
                    routing_key=routing_key,
                    exchange_name=exchange_name,
                    headers={
                        "reply_key": "None",
                        "reply_exchange": "None",
                        "reply_entity_name": "None",
                        "reply_service_name": "None",
                        "service_name": service_name,
                        "entity_name": entity_name,
                        "body": json.dumps(inventory_toupdate)
                    }
                )
            except Exception as e:
                ic(f"Failed to emit PURCHASE_CANCELED saga: {e}")

        # Send Activity Log
        await _send_activity_log(
            shop_id=shop_id,
            action="CANCELED",
            entity_id=purchase_id,
            description=f"Canceled Purchase {invoice_no} ({purchase_id})",
            entity_name=str(invoice_no)
        )

        return {
            "success": True,
            "id": purchase_id,
            "status": "CANCELED",
            "msg": "Purchase canceled successfully"
        }


    
                    
            


        
        

            

            




        

    
    