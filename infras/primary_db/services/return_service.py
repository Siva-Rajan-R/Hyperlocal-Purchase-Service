from schemas.v1.purchase_schemas.return_schema import CreatePurchaseReturnSchema
from schemas.v1.purchase_schemas.request_schema import GetPurchaseByIdSchema
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
import httpx
from fastapi import HTTPException
from icecream import ic
from ..main import AsyncSession
from integrations.utility_service import get_ui_id
from messaging.saga_producer import SagaProducer, CreateSagaStateSchema, SagaStatusEnum
from hyperlocal_platform.core.enums.saga_state_enum import SagaStepsValueEnum
from hyperlocal_platform.core.typed_dicts.saga_status_typ_dict import SagaStateExecutionTypDict
from messaging.main import RabbitMQMessagingConfig
from typing import Optional, List

class ReturnService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def process_return(self, data: CreatePurchaseReturnSchema, executing_user_id: Optional[str] = None) -> bool | None:
        try:
            rabbitmq_connection = RabbitMQMessagingConfig()
            return_id = generate_uuid()

            # Fetch Mongo read DB purchase
            read_db_purchase = await PurchaseReadDbRepo.get_by_id(
                GetPurchaseByIdSchema(id=data.purchase_id, shop_id=data.shop_id)
            )
            if not read_db_purchase:
                raise HTTPException(status_code=404, detail="Purchase not found")

            ui_id_res = await get_ui_id(shop_id=data.shop_id)
            if ui_id_res and isinstance(ui_id_res, dict) and ui_id_res.get('prefix'):
                ui_id = f"{ui_id_res.get('prefix')}-{ui_id_res.get('current_number')}"
            else:
                ui_id = f"PUR-RET-{generate_uuid()[:6].upper()}"

            purchase_id = data.purchase_id
            shop_id = data.shop_id
            supplier_id = read_db_purchase.get("supplier", {}).get("supplier_id") if isinstance(read_db_purchase.get("supplier"), dict) else read_db_purchase.get("supplier_id")
            payment_infos = data.payment_infos

            items_map = {itm["id"]: itm for itm in (read_db_purchase.get("items") or [])}

            return_items_toadd = []
            products_toupdate = []
            total_refund_qty = 0.0
            total_refund_amount = 0.0

            for itm in data.items:
                itm_dict = itm.model_dump()
                inc_item_id = itm_dict['purchase_item_id']

                if inc_item_id not in items_map:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid Purchase Item ID '{inc_item_id}'"
                    )

                target_item = items_map[inc_item_id]
                
                # Extract original quantity from item document (checking stocks_infos, stock_infos, stocks, and quantity)
                stocks_info_dict = target_item.get('stocks_infos') or target_item.get('stock_infos') or {}
                extracted_stocks = stocks_info_dict.get('stocks') if isinstance(stocks_info_dict, dict) else None
                original_qty = float(extracted_stocks if extracted_stocks is not None else (target_item.get('stocks') or target_item.get('quantity') or 0.0))
                
                returned_qty = float(target_item.get('returned_quantity') or 0.0)
                already_consumed = returned_qty

                unit_infos = target_item.get("unit_infos") or {}
                base_unit_name = unit_infos.get("name", "")
                sub_units = unit_infos.get("sub_units", []) or []

                conversion_factor = 1.0
                entered_unit = itm_dict.get("unit")
                if entered_unit and base_unit_name:
                    if entered_unit.lower() == base_unit_name.lower():
                        conversion_factor = 1.0
                    else:
                        matched_sub = next((su for su in sub_units if su and su.get("name", "").lower() == entered_unit.lower()), None)
                        if not matched_sub:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Invalid unit '{entered_unit}'. Configured base unit: '{base_unit_name}'"
                            )
                        conversion_factor = float(matched_sub.get("factor", 1.0))

                inc_quantity = float(itm_dict["quantity"]) * conversion_factor

                if already_consumed >= original_qty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"All qty for this item has already been returned (original: {original_qty}, returned: {returned_qty})"
                    )

                delta = original_qty - already_consumed - inc_quantity
                if delta < 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Return qty ({inc_quantity}) exceeds available qty. Original: {original_qty}, returned: {returned_qty}, available: {original_qty - already_consumed}"
                    )

                # Check physical stock availability in inventory (ProdInvCollections)
                from infras.read_db.main import MONGO_CLIENT
                prod_inv_collection = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
                prod_doc = await prod_inv_collection.find_one({"id": target_item.get("product_id"), "shop_id": shop_id})
                if prod_doc:
                    variant_id = target_item.get("variant_id")
                    batch_id = (target_item.get("batch_infos") or {}).get("id") if isinstance(target_item.get("batch_infos"), dict) else target_item.get("batch_id")
                    
                    target_stock_infos = {}
                    if variant_id and prod_doc.get("variants"):
                        variants = prod_doc.get("variants") or {}
                        variant_data = {}
                        if isinstance(variants, dict):
                            variant_data = variants.get(variant_id) or {}
                        elif isinstance(variants, list):
                            variant_data = next((v for v in variants if isinstance(v, dict) and v.get("id") == variant_id), {})
                        
                        if batch_id and variant_data.get("batch_infos"):
                            batches = variant_data.get("batch_infos") or []
                            matched_b = next((b for b in batches if isinstance(b, dict) and (b.get("id") == batch_id or b.get("name") == batch_id)), {})
                            target_stock_infos = matched_b.get("stock_infos") or matched_b.get("stocks_infos") or {}
                        else:
                            target_stock_infos = variant_data.get("stock_infos") or variant_data.get("stocks_infos") or {}
                    elif batch_id and prod_doc.get("batch_infos"):
                        batches = prod_doc.get("batch_infos") or []
                        matched_b = next((b for b in batches if isinstance(b, dict) and (b.get("id") == batch_id or b.get("name") == batch_id)), {})
                        target_stock_infos = matched_b.get("stock_infos") or matched_b.get("stocks_infos") or {}
                    else:
                        target_stock_infos = prod_doc.get("stock_infos") or prod_doc.get("stocks_infos") or {}

                    physical_stock = float(target_stock_infos.get("physical_stocks") if target_stock_infos.get("physical_stocks") is not None else (target_stock_infos.get("stocks") or 0.0))
                    if physical_stock < inc_quantity:
                        item_name = target_item.get("name") or target_item.get("product_id")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Cannot return {inc_quantity} units of '{item_name}' because current physical stock in inventory is only {physical_stock} units."
                        )

                buy_price = target_item.get('buy_price', 0.0)
                if not buy_price and isinstance(target_item.get('pricing_infos'), dict):
                    buy_price = target_item['pricing_infos'].get('buy_price', 0.0)

                total_return_qty_amount = inc_quantity * float(buy_price or 0.0)

                founded_serialno = []
                existing_serials = target_item.get('serial_numbers') or target_item.get('serialno_infos') or []
                existing_serial_ids = [s.get('id') if isinstance(s, dict) else s for s in existing_serials]

                already_returned_sns = set()
                for ret in (read_db_purchase.get("returns") or []):
                    for r_item in (ret.get("items") or []):
                        if r_item.get("purchase_item_id") == inc_item_id:
                            for sn in (r_item.get("serialno_infos") or []):
                                if isinstance(sn, dict) and sn.get("id"):
                                    already_returned_sns.add(sn.get("id"))

                for serialno in (itm_dict.get("serialno_infos") or []):
                    sn_id = serialno['id'] if isinstance(serialno, dict) else serialno
                    if sn_id not in existing_serial_ids:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Serial number '{sn_id}' not found in the original purchased item."
                        )
                    if sn_id in already_returned_sns:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Serial number '{sn_id}' has already been returned."
                        )
                    matched_sn = next((s for s in existing_serials if (s.get('id') if isinstance(s, dict) else s) == sn_id), None)
                    if matched_sn:
                        if isinstance(matched_sn, dict):
                            founded_serialno.append(matched_sn)
                        else:
                            founded_serialno.append({"id": matched_sn, "name": matched_sn})

                # DECREMENT inventory stock upon returning to supplier
                products_toupdate.append({
                    "shop_id": shop_id,
                    "product_id": target_item.get('product_id'),
                    "variant_id": target_item.get('variant_id'),
                    "batch_infos": target_item.get('batch_infos'),
                    "serialno_infos": founded_serialno,
                    "stocks": inc_quantity,
                    "entity_name": "OFFLINE_PURCHASE_RETURN",
                    "type": "DECREMENT",
                    "create_stock_mov_adj": True
                })

                total_refund_qty += inc_quantity
                total_refund_amount += total_return_qty_amount

                return_items_toadd.append({
                    'id': generate_uuid(),
                    'return_id': return_id,
                    'purchase_item_id': inc_item_id,
                    'product_id': target_item.get('product_id'),
                    'quantity': inc_quantity,
                    'entered_qty': itm_dict['quantity'],
                    'entered_unit': itm_dict.get('unit') or base_unit_name,
                    'refund_amount': total_return_qty_amount,
                    'reason': itm_dict.get('reason'),
                    'serialno_infos': founded_serialno
                })

            return_toadd = {
                "id": return_id,
                "ui_id": ui_id,
                "purchase_id": purchase_id,
                "supplier_id": supplier_id,
                "shop_id": shop_id,
                "status": "COMPLETED",
                "payment_infos": payment_infos,
                "total_refund_qty": total_refund_qty,
                "total_refund_amount": total_refund_amount
            }

            purchase_return_data = {
                "purchase_return": {
                    "return_toadd": return_toadd,
                    "return_items_toadd": return_items_toadd
                }
            }

            saga_id: str = generate_uuid()
            steps = {
                "PRODUCT_VERIFY_UPDATE": SagaStepsValueEnum.PENDING,
            }

            saga_data = purchase_return_data
            saga_data["executing_user_id"] = executing_user_id

            await SagaProducer.emit(
                saga_payload=CreateSagaStateSchema(
                    id=saga_id,
                    status=SagaStatusEnum.IN_PROGRESS,
                    type="PURCHASE_RETURNED",
                    steps=steps,
                    execution=SagaStateExecutionTypDict(
                        step="PRODUCT_VERIFY_UPDATE",
                        service="PRODUCTS"
                    ),
                    data=saga_data
                ),
                routing_key="products.service.routing.key",
                exchange_name="products.service.exchange",
                headers={
                    "reply_key": "purchase.producer.routing.key",
                    "reply_exchange": "purchase.producer.exchange",
                    "reply_entity_name": "create_return",
                    "reply_service_name": "PURCHASES_RETURN",
                    "service_name": "PRODUCTS",
                    "entity_name": "update_bulk_prodinv",
                    "body": products_toupdate
                }
            )

            return True
        except Exception as e:
            try:
                from helpers.emit_notification import emit_notification
                import asyncio
                asyncio.create_task(emit_notification(
                    title="Purchase Return Process Failed",
                    message=f"Failed to initiate purchase return process: {str(e.detail) if hasattr(e, 'detail') else str(e)}",
                    type="error",
                    user_id=executing_user_id or data.shop_id
                ))
            except Exception as notification_error:
                ic(f"Notification error: {notification_error}")
            raise e
