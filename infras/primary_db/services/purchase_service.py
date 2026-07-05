from models.service_models.base_service_model import BaseServiceModel
from ..repos.purchase_repo import PurchaseRepo

from core.data_formats.enums.stock_adj_enums import StockAdjustmentMovementType,StockAdjustmentTypesEnum
from typing import Optional,List
from ..models.purchase_model import Purchase,PurchaseItems,PurchaseItemsPricing,PurchaseItemsStoragelocation
from sqlalchemy.ext.asyncio import AsyncSession
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from schemas.v1.purchase_schemas.db_schemas import CreatePurchaseDbSchema,CreatePurchaseItemsDbSchema,CreatePurchasePricingDbSchema,CreateStorageLocationDbSchema,UpdatePurchaseDbSchema,UpdatePurchaseItemsDbSchema,UpdatePurchasePricingDbSchema,UpdateStorageLocationDbSchema,DeletePurchaseDbSchema
from schemas.v1.purchase_schemas.request_schema import CreatePurchaseItemsSchema,CreatePurchasePricingSchema,CreatePurchaseSchema,CreateStorageLocationSchema,UpdatePurchaseItemsSchema,UpdatePurchasePricingSchema,UpdatePurchaseSchema,UpdateStorageLocationSchema,DeletePurchaseSchema,PurchaseItemInfos,GetPurchaseByIdSchema,GetAllPurchaseSchemas,GetPurchaseByShopIdSchema
from core.errors.messaging_errors import BussinessError,FatalError,RetryableError
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums,PurchaseViewsEnums
from icecream import ic
from typing import Union,List,Dict
from datetime import date
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
from infras.read_db.models.purchase_model import PurchaseReadModel,SupplierInfo
import httpx
from messaging.saga_producer import SagaProducer,CreateSagaStateSchema,SagaStatusEnum
from hyperlocal_platform.core.enums.saga_state_enum import SagaStepsValueEnum
from hyperlocal_platform.core.typed_dicts.saga_status_typ_dict import SagaStateExecutionTypDict

from integrations.utility_service import get_ui_id

ACTIVITY_LOG_URL = "http://127.0.0.1:8001/activity-logs"

async def _send_activity_log(shop_id: str, action: str, entity_id: str, description: str, changes: list = None):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(ACTIVITY_LOG_URL, json={
                "shop_id": shop_id,
                "user_name": "siva",
                "service": "Purchase",
                "action": action,
                "entity_type": "Purchase",
                "entity_id": entity_id,
                "description": description,
                "changes": changes or []
            })
    except Exception as e:
        ic(f"Failed to log activity: {e}")


class PurchaseService:
    def __init__(self, session:AsyncSession):
        self.session=session
        self.purchase_repo_obj=PurchaseRepo(session=session)


    async def create(self,data:CreatePurchaseSchema):

        invoice_exists=await self.purchase_repo_obj.verify_invoice_exists(invoice_no=data.invoice_no,shop_id=data.shop_id)
        if invoice_exists:
            ic("invoice number already exists")
            return False
        

        saga_id:str=generate_uuid()
        steps={
            "SUPPLIER_VERIFY":SagaStepsValueEnum.PENDING,
            "PRODUCT_VERIFY_UPDATE":SagaStepsValueEnum.PENDING,
            "FETCHING_PRODUCTS":SagaStepsValueEnum.PENDING
        }

        saga_data={"purchase":data.model_dump(mode="json")}
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
                "reply_key":"purchase.producer.routing.key",
                "reply_exchange":"purchase.producer.exchange",
                "reply_entity_name":"create_purchase",
                "reply_service_name":"PURCHASE",
                "service_name":"SUPPLIERS",
                "entity_name":"get_supplier_by_id",
                "body":{
                    "shop_id":data.shop_id,
                    "id":data.supplier_id
                }

            }
        )

        return True


        



    async def update(self,data:UpdatePurchaseSchema):
        purchase_repo_obj=PurchaseRepo(session=self.session)
        items_toupdate=[]
        pricing_toupdate=[]
        stl_toadd=[]
        stl_toupdate=[]

        stl_to_verify={}

        total_items_stocks=0
        total_items_amount=0
        total_items_gst=0
        total_items_count=len(data.items)

        pur_get_res=await purchase_repo_obj.get_purchase_by_id(data=GetPurchaseByIdSchema(id=data.id,shop_id=data.shop_id))

        if not pur_get_res:
            ic("The give purchase was not found")
            return False
        
        if data.items and len(pur_get_res.items)!=len(data.items):
            ic("The purchase items doesn't matched")
            return False
        
        for item in data.items:
            pur_item_id=item.id
            items_toupdate.append(
                UpdatePurchaseItemsDbSchema(
                    id=pur_item_id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    batch_id=item.batch_id,
                    serialno_id=item.serialno_id,
                    gst=item.gst,
                    stocks=item.stocks,
                    stocks_before=0,
                    stocks_after=item.stocks,
                    serial_numbers=item.serial_numbers
                )
            )

            pricing_id=item.pricing_infos.id
            pricing_toupdate.append(
                UpdatePurchasePricingSchema(
                    pricing_id=pricing_id,
                    purchase_id=data.id,
                    purchase_item_id=pur_item_id,
                    buy_price=item.pricing_infos.buy_price,
                    sell_price=item.pricing_infos.sell_price

                )
            )

            stl_id=item.storage_location_infos.id
            if stl_id:
                stl_toupdate.append(
                    UpdateStorageLocationDbSchema(
                        storage_location_id=stl_id,
                        purchase_item_id=pur_item_id,
                        purchase_id=data.id,
                        name=item.storage_location_infos.name
                    )
                )
            else:
                stl_id=generate_uuid()
                stl_to_verify[item.id]=PurchaseItemsStoragelocation(
                    storage_location_id=stl_id,
                    purchase_item_id=pur_item_id,
                    purchase_id=data.id,
                    name=item.storage_location_infos.name
                )

            total_items_stocks+=item.stocks
            total_items_amount+=1
            total_items_gst+=int(item.gst.split("%")[0]) if item.gst else 0

        

        purchase_toadd=UpdatePurchaseDbSchema(
            date=data.purchase_date,
            **data.model_dump(mode="json",exclude=['purchase_date'])
        )

        if stl_to_verify:
            for itm in pur_get_res.items:
                ic(itm)
                ic(itm.storage_locations)
                ic(stl_to_verify)
                if not itm.storage_locations:
                    stl_toadd.append(stl_to_verify[itm.id])
            
        if len(stl_toadd)!=len(stl_to_verify):
            ic("Invalid Storage location data, storage location already exist for this purchase")
            return False

        
        pur_add_res=await purchase_repo_obj.update_bulk_purchase(data=[purchase_toadd])
        ic(pur_add_res)
        if pur_add_res:
            await purchase_repo_obj.update_bulk_item(data=items_toupdate)
            await purchase_repo_obj.update_bulk_pricing(data=pricing_toupdate)
            if stl_toadd:
                await purchase_repo_obj.create_bulk_stl(data=stl_toadd)

            await purchase_repo_obj.update_bulk_stl(data=stl_toupdate)
            
            from hyperlocal_platform.core.utils.activity_logger import ActivityLogger
            pur_get_res_dict = {col.name: getattr(pur_get_res, col.name) for col in pur_get_res.__table__.columns} if pur_get_res else {}
            changes_list = ActivityLogger.compute_changes(pur_get_res_dict, data.model_dump(mode='json', exclude_none=True, exclude_unset=True))
            if changes_list:
                desc_changes = [f"{c['field']} prv({c['before']}) after ({c['after']})" for c in changes_list]
                desc = f"updated purchase {', '.join(desc_changes)}"
                try:
                    from messaging.main import RabbitMQMessagingConfig
                    rabbitmq_msg_obj = RabbitMQMessagingConfig()
                    await rabbitmq_msg_obj.publish_event(
                        routing_key="activity_logs.routing.key",
                        exchange_name="activity_logs.exchange",
                        payload={
                            "shop_id": data.shop_id,
                            "user_name": "siva",
                            "service": "Purchase",
                            "action": "UPDATE",
                            "entity_type": "Purchase",
                            "entity_id": data.id,
                            "description": desc,
                            "changes": changes_list
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
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                await rabbitmq_msg_obj.publish_event(
                    routing_key="activity_logs.routing.key",
                    exchange_name="activity_logs.exchange",
                    payload={
                        "shop_id": data.shop_id,
                        "user_name": "siva",
                        "service": "Purchase",
                        "action": "DELETE",
                        "entity_type": "Purchase",
                        "entity_id": data.id,
                        "description": f"Deleted purchase {data.id}",
                        "changes": [{"field": "id", "before": str(data.id), "after": "DELETED"}]
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
                    
            


        
        

            

            




        

    
    