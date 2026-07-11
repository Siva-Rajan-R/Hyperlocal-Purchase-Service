from pydantic import BaseModel
from typing import Optional,List
from datetime import date
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods,PurchaseTypeEnums
from .custom_types import PurchaseCalculationInfos,PurchaseChargeInfos,PurchaseItemInfos,PurchasePaymentInfos,PurchasePaymentMethods,PurchaseStorageLocationInfos,PurchasePricingInfos,PurchaseReorderPointInfosType,PurchaseBatchInfosType,PurchaseSerialnoInfosType,PurchaseStocksInfosType



# PURCHASE ITEMS
class CreatePurchaseItemsDbSchema(BaseModel):
    id:str
    product_id:str
    variant_id:Optional[str]=None
    batch_id:Optional[str]=None
    serialno_id:Optional[str]=None
    storage_location_infos:Optional[PurchaseStorageLocationInfos]=None
    pricing_infos:PurchasePricingInfos
    reorder_point_infos:Optional[PurchaseReorderPointInfosType]=None
    gst:str
    serial_numbers:Optional[List]=None
    stocks:float
    stocks_after:float
    stocks_before:float


class UpdatePurchaseItemsDbSchema(BaseModel):
    id:str
    product_id:str
    gst:Optional[str]=None
    stocks:Optional[float]=None
    stocks_before:Optional[float]=None
    stocks_after:Optional[float]=None
    serial_numbers:Optional[List[str]]=None


# PURCHAASE PRICING
class CreatePurchasePricingDbSchema(BaseModel):
    pricing_id:str
    purchase_id:str
    purchase_item_id:str
    buy_price:float
    sell_price:float


class UpdatePurchasePricingDbSchema(BaseModel):
    pricing_id:str
    purchase_id:str
    purchase_item_id:str
    buy_price:Optional[float]=None
    sell_price:Optional[float]=None



# PURCHASE STORAGE LOCATION
class CreateStorageLocationDbSchema(BaseModel):
    storage_location_id:int
    purchase_id:str
    purchase_item_id:str
    name:str


class UpdateStorageLocationDbSchema(BaseModel):
    storage_location_id:int
    purchase_id:str
    purchase_item_id:str
    name:Optional[str]=None


# PURCHASE REORDER POINT
class CreateReorderPointDbSchema(BaseModel):
    reorder_point_id:int
    purchase_id:str
    purchase_item_id:str
    reorder_point:float


class UpdateReorderPointDbSchema(BaseModel):
    reorder_point_id:int
    purchase_id:str
    purchase_item_id:str
    reorder_point:Optional[float]=None

# PURCHASE
class CreatePurchaseDbSchema(BaseModel):
    shop_id:str
    supplier_id:str
    type:PurchaseTypeEnums
    calculation_infos:PurchaseCalculationInfos
    charges_infos:PurchaseChargeInfos
    payment_infos:List[PurchasePaymentInfos]
    
    purchase_date:date
    invoice_no:str



class UpdatePurchaseDbSchema(BaseModel):
    id:str
    shop_id:str
    calculation_infos:Optional[PurchaseCalculationInfos]=None
    charges_infos:Optional[PurchaseChargeInfos]=None
    payment_infos:Optional[List[PurchasePaymentInfos]]=None
    item_infos:Optional[dict]=None
    purchase_date:Optional[date]=None
    



class DeletePurchaseDbSchema(BaseModel):
    id:str
    shop_id:str
