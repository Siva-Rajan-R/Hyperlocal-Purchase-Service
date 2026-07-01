from pydantic import BaseModel
from typing import Optional,List
from datetime import date
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods,PurchaseTypeEnums
from .custom_types import PurchaseCalculationInfos,PurchaseChargeInfos,PurchaseItemInfos,PurchasePaymentInfos,PurchasePaymentMethods,PurchaseStorageLocationInfos,PurchasePricingInfos,PurchaseBatchInfosType,PurchaseSerialnoInfosType,PurchaseReorderPointInfosType,PurchaseStocksInfosType




# PURCHASE ITMES
class CreatePurchaseItemsSchema(BaseModel):
    product_id:str
    variant_id:Optional[str]=None
    batch_infos:Optional[PurchaseBatchInfosType]=None
    serialno_infos:Optional[List[PurchaseSerialnoInfosType]]=None
    storage_location_infos:Optional[PurchaseStorageLocationInfos]=None
    reorder_point_infos:Optional[PurchaseReorderPointInfosType]=None
    pricing_infos:PurchasePricingInfos
    gst:str
    stock_infos:PurchaseStocksInfosType

class UpdatePurchaseItemsSchema(BaseModel):
    id:str
    product_id:str
    variant_id:Optional[str]=None
    batch_infos:Optional[PurchaseBatchInfosType]=None
    serialno_infos:Optional[List[PurchaseSerialnoInfosType]]=None
    storage_location_infos:Optional[PurchaseStorageLocationInfos]=None
    reorder_point_infos:Optional[PurchaseReorderPointInfosType]=None
    pricing_infos:Optional[PurchasePricingInfos]=None
    gst:Optional[str]=None
    stock_infos:PurchaseStocksInfosType


# PURCHAASE PRICING
class CreatePurchasePricingSchema(BaseModel):
    pricing_id:str
    purchase_id:str
    purchase_item_id:str
    buy_price:float
    sell_price:float


class UpdatePurchasePricingSchema(BaseModel):
    pricing_id:str
    purchase_id:str
    purchase_item_id:str
    buy_price:Optional[float]=None
    sell_price:Optional[float]=None



# PURCHASE STORAGE LOCATION
class CreateStorageLocationSchema(BaseModel):
    storage_location_id:str
    purchase_id:str
    purchase_item_id:str
    name:str


class UpdateStorageLocationSchema(BaseModel):
    storage_location_id:str
    purchase_id:str
    purchase_item_id:str
    name:Optional[str]=None


# PURCHASE REORDER POINT
class CreateReorderPointSchema(BaseModel):
    reorder_point_id:str
    purchase_id:str
    purchase_item_id:str
    reorder_point:float


class UpdateReorderPointSchema(BaseModel):
    reorder_point_id:str
    purchase_id:str
    purchase_item_id:str
    reorder_point:Optional[float]=None


# PURCHASES
class CreatePurchaseSchema(BaseModel):
    shop_id:str
    supplier_id:str
    type:PurchaseTypeEnums
    calculation_infos:PurchaseCalculationInfos
    gst_infos:dict
    charges_infos:PurchaseChargeInfos
    payment_infos:List[PurchasePaymentInfos]
    
    purchase_date:date
    items:List[CreatePurchaseItemsSchema]
    invoice_no:str



class UpdatePurchaseSchema(BaseModel):
    id:str
    shop_id:str
    calculation_infos:Optional[PurchaseCalculationInfos]=None

    charges_infos:Optional[PurchaseChargeInfos]=None
    payment_infos:Optional[List[PurchasePaymentInfos]]=None
    purchase_date:Optional[date]=None
    items:Optional[List[UpdatePurchaseItemsSchema]]=None



class DeletePurchaseSchema(BaseModel):
    id:str
    shop_id:str



class GetAllPurchaseSchemas(BaseModel):
    limit:int=10
    offset:int=1
    q:Optional[str]=None

class GetPurchaseByShopIdSchema(BaseModel):
    limit:int=10
    offset:int=1
    q:Optional[str]=None
    shop_id:str


class GetPurchaseByIdSchema(BaseModel):
    id:str
    shop_id:str