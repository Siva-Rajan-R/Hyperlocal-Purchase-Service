import datetime
from typing import Any, Dict, List
from icecream import ic
from ..main import RabbitMQMessagingConfig
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid

from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.models.purchase_model import PurchaseReturns, PurchaseReturnItems
from infras.primary_db.repos.return_repo import ReturnRepo
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
from infras.read_db.main import PURCHAESE_COLLECTION
from schemas.v1.purchase_schemas.request_schema import GetPurchaseByIdSchema

class MessagingQueuePurchaseReturnProducer:
    def __init__(self, headers: dict, payload: dict, saga_datas: dict):
        self.headers = headers
        self.payload = payload
        self.saga_datas = saga_datas

    async def create_return(self):
        ic(self.headers, self.payload, self.saga_datas)

        execution = self.saga_datas.get('execution', {})
        current_step = execution.get('step')
        datas = self.saga_datas.get("data", {})
        purchase_return_payload = datas.get("purchase_return")

        rabbitmq_msg_obj = RabbitMQMessagingConfig()

        if not purchase_return_payload:
            ic("Missing 'purchase_return' in saga data context.")
            return {"success": False, "reason": "Missing required payload data"}

        return_toadd = purchase_return_payload.get("return_toadd")
        return_items_toadd = purchase_return_payload.get("return_items_toadd")
        ic(return_toadd, return_items_toadd)

        if current_step == "PRODUCT_VERIFY_UPDATE":
            try:
                async with AsyncInventoryLocalSession() as session:
                    return_repo_obj = ReturnRepo(session=session)

                    await return_repo_obj.create_return_with_items(
                        return_obj=PurchaseReturns(**return_toadd),
                        return_items=[PurchaseReturnItems(**{k: v for k, v in itm.items() if k not in ('serialno_infos',)}) for itm in return_items_toadd]
                    )

                    ic("Purchase Return Process Completed in Primary DB")

                    purchase_id = return_toadd.get("purchase_id")
                    shop_id = return_toadd.get("shop_id")

                    if purchase_id and shop_id:
                        existing_purchase = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id))
                        if existing_purchase:
                            if "returns" not in existing_purchase or existing_purchase["returns"] is None:
                                existing_purchase["returns"] = []

                            return_items_formatted = []
                            for itm in return_items_toadd:
                                formatted_item = {
                                    "id": itm.get("id"),
                                    "purchase_item_id": itm.get("purchase_item_id"),
                                    "product_id": itm.get("product_id"),
                                    "quantity": itm.get("quantity", 0),
                                    "entered_qty": itm.get("entered_qty"),
                                    "entered_unit": itm.get("entered_unit"),
                                    "refund_amount": itm.get("refund_amount", 0.0),
                                    "reason": itm.get("reason", "")
                                }

                                original_item = next((orig for orig in existing_purchase.get("items", []) if orig.get("id") == itm.get("purchase_item_id")), None)
                                if original_item:
                                    formatted_item.update({
                                        "name": original_item.get("name"),
                                        "ui_id": original_item.get("ui_id"),
                                        "category_infos": original_item.get("category_infos"),
                                        "unit_infos": original_item.get("unit_infos"),
                                        "variant_infos": original_item.get("variant_infos"),
                                        "batch_infos": original_item.get("batch_infos"),
                                        "serialno_infos": itm.get("serialno_infos") or [],
                                        "buy_price": original_item.get("buy_price"),
                                        "sell_price": original_item.get("sell_price"),
                                        "gst": original_item.get("gst")
                                    })

                                return_items_formatted.append(formatted_item)

                                # Update root items in MongoDB document
                                for existing_item in existing_purchase.get("items", []):
                                    if existing_item.get("id") == itm.get("purchase_item_id"):
                                        curr_returned = existing_item.get("returned_quantity") or 0.0
                                        existing_item["returned_quantity"] = curr_returned + float(itm.get("quantity", 0))

                                        if "returns" not in existing_item or existing_item["returns"] is None:
                                            existing_item["returns"] = []

                                        existing_item["returns"].append({
                                            "id": return_toadd.get("id"),
                                            "purchase_item_id": itm.get("purchase_item_id"),
                                            "quantity": itm.get("quantity", 0),
                                            "entered_qty": itm.get("entered_qty"),
                                            "entered_unit": itm.get("entered_unit"),
                                            "serialno_infos": itm.get("serialno_infos") or [],
                                            "refund_amount": itm.get("refund_amount", 0.0),
                                            "reason": itm.get("reason", ""),
                                            "created_at": return_toadd.get("created_at")
                                        })
                                        break

                            new_return = {
                                "id": return_toadd.get("id"),
                                "ui_id": return_toadd.get("ui_id"),
                                "sequence_id": return_toadd.get("sequence_id"),
                                "status": return_toadd.get("status", "COMPLETED"),
                                "total_refund_amount": return_toadd.get("total_refund_amount", 0.0),
                                "total_refund_qty": return_toadd.get("total_refund_qty", 0.0),
                                "payment_infos": return_toadd.get("payment_infos", {}),
                                "created_at": return_toadd.get("created_at"),
                                "updated_at": return_toadd.get("updated_at"),
                                "items": return_items_formatted
                            }
                            existing_purchase["returns"].append(new_return)

                            await PURCHAESE_COLLECTION.update_one(
                                {"shop_id": shop_id, "$or": [{"purchase_id": purchase_id}, {"id": purchase_id}]},
                                {"$set": existing_purchase}
                            )

                        try:
                            rabbitmq_msg_obj = RabbitMQMessagingConfig()
                            await rabbitmq_msg_obj.publish_event(
                                routing_key="activity_logs.routing.key",
                                exchange_name="activity_logs.exchange",
                                payload={
                                    "shop_id": shop_id,
                                    "user_name": "Hyperlocal-User",
                                    "service": "Purchase-Order",
                                    "action": "RETURN",
                                    "entity_type": "PURCHASE-RETURN",
                                    "entity_id": purchase_id,
                                    "description": f"Returned purchase {purchase_id}",
                                    "changes": [{"field": "id", "before": str(purchase_id), "after": "RETURN"}]
                                },
                                headers={}
                            )
                        except Exception as e:
                            ic(f"Failed to publish activity log: {e}")

                try:
                    from helpers.emit_notification import emit_notification
                    import asyncio
                    executing_user_id = datas.get("executing_user_id")
                    asyncio.create_task(emit_notification(
                        title="Purchase Return Processed",
                        message=f"Purchase return for purchase '{purchase_id}' has been successfully processed.",
                        type="info",
                        user_id=executing_user_id or shop_id,
                        additional_metadata={"purchase_id": purchase_id}
                    ))
                except Exception as notification_error:
                    ic(f"Notification error: {notification_error}")

                return {
                    "success": True,
                    "execution": None
                }
            except Exception as e:
                try:
                    from helpers.emit_notification import emit_notification
                    import asyncio
                    executing_user_id = datas.get("executing_user_id")
                    asyncio.create_task(emit_notification(
                        title="Purchase Return Failed",
                        message=f"Failed to process return for purchase '{return_toadd.get('purchase_id')}': {str(e)}",
                        type="error",
                        user_id=executing_user_id or return_toadd.get("shop_id")
                    ))
                except Exception as notification_error:
                    ic(f"Notification error: {notification_error}")
                raise e
