from pydantic import BaseModel
from typing import Optional,List,Literal
from datetime import date
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods,PurchaseTypeEnums
from .custom_types import PurchaseCalculationInfos,PurchaseChargeInfos,PurchaseItemInfos,PurchasePaymentInfos,PurchasePaymentMethods,PurchaseStorageLocationInfos,PurchasePricingInfos,PurchaseBatchInfosType,PurchaseSerialnoInfosType,PurchaseReorderPointInfosType,PurchaseStocksInfosType




# PURCHASE ITMES
class CreatePurchaseItemsSchema(BaseModel):
    product_id:str
    variant_id:Optional[str]=None
    batch_infos:Optional[PurchaseBatchInfosType]=None
    serialno_numbers:Optional[List[str]]=None
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
    serialno_numbers:Optional[List[str]]=None
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

class PurchaseGstInfos(BaseModel):
    type:Literal['EXCLUSIVE','INCLUSIVE']

# PURCHASES
class CreatePurchaseSchema(BaseModel):
    shop_id:str
    supplier_id:str
    type:PurchaseTypeEnums
    calculation_infos:PurchaseCalculationInfos
    gst_infos:PurchaseGstInfos
    charges_infos:PurchaseChargeInfos
    payment_infos:List[PurchasePaymentInfos]
    
    purchase_date:date
    items:List[CreatePurchaseItemsSchema]
    invoice_no:str

    custom_fields:Optional[dict]={}



class UpdatePurchaseSchema(BaseModel):
    id:Optional[str]=None
    shop_id:str
    calculation_infos:Optional[PurchaseCalculationInfos]=None

    charges_infos:Optional[PurchaseChargeInfos]=None
    payment_infos:Optional[List[PurchasePaymentInfos]]=None
    purchase_date:Optional[date]=None
    items:Optional[List[UpdatePurchaseItemsSchema]]=None
    custom_fields:Optional[dict]={}



class DeletePurchaseSchema(BaseModel):
    id:str
    shop_id:str



class GetAllPurchaseSchemas(BaseModel):
    limit:int=10
    offset:int=1
    q:Optional[str]=None
    outstanding: Optional[bool] = None

class GetPurchaseByShopIdSchema(BaseModel):
    limit:int=10
    offset:int=1
    q:Optional[str]=None
    shop_id:str
    outstanding: Optional[bool] = None

class GetPurchaseByIdSchema(BaseModel):
    id:str
    shop_id:str

class GetPurchaseByProductIdSchema(BaseModel):
    limit:int=10
    offset:int=1
    shop_id:str
    product_id:str
    outstanding: Optional[bool] = None

class GetPurchaseBySupplierIdSchema(BaseModel):
    limit:int=10
    offset:int=1
    shop_id:str
    supplier_id:str
    outstanding: Optional[bool] = None

class ClearPurchaseOutstandingSchema(BaseModel):
    purchase_id: str
    shop_id: str
    amount: float
    payment_method: str
    notes: Optional[str] = None