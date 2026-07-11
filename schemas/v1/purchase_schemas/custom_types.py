from pydantic import BaseModel
from typing import Optional,List
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods
from datetime import date


class PurchaseCalculationInfos(BaseModel):
    ...

class PurchaseBatchInfosType(BaseModel):
    id:Optional[str]=None
    name:Optional[str]=None
    expiry_date:Optional[date]=None
    manufacturing_date:Optional[date]=None

class PurchaseChargeInfos(BaseModel):
    transport_charge:float
    other_charge:float

class PurchaseReorderPointInfosType(BaseModel):
    reorder_point:float

class PurchaseItemInfos(BaseModel):
    total_items:float
    total_stocks:float
    total_amounts:float
    total_gst:str

class PurchasePaymentInfos(BaseModel):
    method:PurchasePaymentMethods
    amount:float

class PurchaseStorageLocationInfos(BaseModel):
    name:str

class PurchasePricingInfos(BaseModel):
    buy_price:float
    sell_price:float

class PurchaseSerialnoInfosType(BaseModel):
    name:str


class PurchaseStocksInfosType(BaseModel):
    stocks:float    