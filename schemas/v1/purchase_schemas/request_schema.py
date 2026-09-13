from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional,List,Literal,Union
from datetime import date
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods,PurchaseTypeEnums
from .custom_types import PurchaseCalculationInfos,PurchaseChargeInfos,PurchaseItemInfos,PurchasePaymentInfos,PurchasePaymentMethods,PurchaseStorageLocationInfos,PurchasePricingInfos,PurchaseBatchInfosType,PurchaseSerialnoInfosType,PurchaseReorderPointInfosType,PurchaseStocksInfosType




# PURCHASE ITMES
class CreatePurchaseItemsSchema(BaseModel):
    product_id:str
    variant_id:Optional[str]=None
    batch_infos:Optional[PurchaseBatchInfosType]=None
    serialno_numbers:Optional[List[Union[str, PurchaseSerialnoInfosType, dict]]]=None
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
    serialno_numbers:Optional[List[Union[str, PurchaseSerialnoInfosType, dict]]]=None
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
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[str] = None
    shop_id: str
    supplier_id: str
    type: PurchaseTypeEnums
    status: Optional[str] = "COMPLETED"
    calculation_infos: PurchaseCalculationInfos
    gst_infos: PurchaseGstInfos
    charges_infos: PurchaseChargeInfos
    payment_infos: List[PurchasePaymentInfos]
    
    purchase_date: date
    items: List[CreatePurchaseItemsSchema]
    invoice_no: Optional[str] = None
    notes: Optional[str] = None
    max_updates: Optional[int] = Field(default=1, alias="update_limit")
    custom_fields: Optional[dict] = {}


class UpdatePurchaseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[str] = None
    shop_id: str
    supplier_id: Optional[str] = None
    status: Optional[str] = None
    invoice_no: Optional[str] = None
    notes: Optional[str] = None
    calculation_infos: Optional[PurchaseCalculationInfos] = None

    charges_infos: Optional[PurchaseChargeInfos] = None
    payment_infos: Optional[List[PurchasePaymentInfos]] = None
    purchase_date: Optional[date] = None
    items: Optional[List[UpdatePurchaseItemsSchema]] = None
    max_updates: Optional[int] = Field(default=None, alias="update_limit")
    custom_fields: Optional[dict] = {}


class DeletePurchaseSchema(BaseModel):
    id: str
    shop_id: str


class CancelPurchaseSchema(BaseModel):
    id: str
    shop_id: str




class GetAllPurchaseSchemas(BaseModel):
    limit: int = 10
    offset: int = 1
    query: Optional[str] = Field(default=None, alias='q')
    q: Optional[str] = None
    status: Optional[str] = None
    outstanding: Optional[bool] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    exclude_cancle: Optional[bool] = None
    exclude_cancel: Optional[bool] = None
    exclude_canceled: Optional[bool] = None
    exclude_cancelled: Optional[bool] = None
    exclude_canceled_purchase: Optional[bool] = None
    exclude_canceled_purchases: Optional[bool] = None
    exclude_cancelled_purchases: Optional[bool] = None
    exclude_draft: Optional[bool] = None
    exclude_drafts: Optional[bool] = None
    exclude_draft_purchase: Optional[bool] = None
    exclude_draft_purchases: Optional[bool] = None
    exclude_not_paid: Optional[bool] = None
    exclude_unpaid: Optional[bool] = None
    exclude_notpaid: Optional[bool] = None
    exclude_unpaid_purchase: Optional[bool] = None
    exclude_unpaid_purchases: Optional[bool] = None
    exclude_not_paid_purchase: Optional[bool] = None
    exclude_not_paid_purchases: Optional[bool] = None
    exclude_paid: Optional[bool] = None
    exclude_completed_payment: Optional[bool] = None
    exclude_paid_purchase: Optional[bool] = None
    exclude_paid_purchases: Optional[bool] = None
    exclude_completed_purchase: Optional[bool] = None
    exclude_partial_paid: Optional[bool] = None
    exclude_partially_paid: Optional[bool] = None
    exclude_partial: Optional[bool] = None
    exclude_partially: Optional[bool] = None
    exclude_partial_paid_purchase: Optional[bool] = None
    exclude_partially_paid_purchases: Optional[bool] = None
    exclude_outstanding: Optional[bool] = None
    exclude_outstading: Optional[bool] = None
    exclude_outstaitng: Optional[bool] = None
    exclude_outstanding_purchases: Optional[bool] = None
    exclude_with_outstanding: Optional[bool] = None
    exclude_non_outstanding: Optional[bool] = None
    exclude_non_outstating: Optional[bool] = None
    exclude_no_outstanding: Optional[bool] = None
    exclude_without_outstanding: Optional[bool] = None
    exclude_zero_outstanding: Optional[bool] = None
    exclude_return: Optional[bool] = None
    exclude_returns: Optional[bool] = None
    exclude_returned: Optional[bool] = None
    exclude_has_return: Optional[bool] = None
    exclude_has_returns: Optional[bool] = None
    exclude_with_return: Optional[bool] = None
    exclude_with_returns: Optional[bool] = None
    exclude_non_return: Optional[bool] = None
    exclude_non_returns: Optional[bool] = None
    exclude_no_return: Optional[bool] = None
    exclude_no_returns: Optional[bool] = None
    exclude_without_return: Optional[bool] = None
    exclude_without_returns: Optional[bool] = None

class GetPurchaseByShopIdSchema(BaseModel):
    limit: int = 10
    offset: int = 1
    query: Optional[str] = Field(default=None, alias='q')
    q: Optional[str] = None
    shop_id: str
    supplier_id: Optional[str] = None
    status: Optional[str] = None
    outstanding: Optional[bool] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    exclude_cancle: Optional[bool] = None
    exclude_cancel: Optional[bool] = None
    exclude_canceled: Optional[bool] = None
    exclude_cancelled: Optional[bool] = None
    exclude_canceled_purchase: Optional[bool] = None
    exclude_canceled_purchases: Optional[bool] = None
    exclude_cancelled_purchases: Optional[bool] = None
    exclude_draft: Optional[bool] = None
    exclude_drafts: Optional[bool] = None
    exclude_draft_purchase: Optional[bool] = None
    exclude_draft_purchases: Optional[bool] = None
    exclude_not_paid: Optional[bool] = None
    exclude_unpaid: Optional[bool] = None
    exclude_notpaid: Optional[bool] = None
    exclude_unpaid_purchase: Optional[bool] = None
    exclude_unpaid_purchases: Optional[bool] = None
    exclude_not_paid_purchase: Optional[bool] = None
    exclude_not_paid_purchases: Optional[bool] = None
    exclude_paid: Optional[bool] = None
    exclude_completed_payment: Optional[bool] = None
    exclude_paid_purchase: Optional[bool] = None
    exclude_paid_purchases: Optional[bool] = None
    exclude_completed_purchase: Optional[bool] = None
    exclude_partial_paid: Optional[bool] = None
    exclude_partially_paid: Optional[bool] = None
    exclude_partial: Optional[bool] = None
    exclude_partially: Optional[bool] = None
    exclude_partial_paid_purchase: Optional[bool] = None
    exclude_partially_paid_purchases: Optional[bool] = None
    exclude_outstanding: Optional[bool] = None
    exclude_outstading: Optional[bool] = None
    exclude_outstaitng: Optional[bool] = None
    exclude_outstanding_purchases: Optional[bool] = None
    exclude_with_outstanding: Optional[bool] = None
    exclude_non_outstanding: Optional[bool] = None
    exclude_non_outstating: Optional[bool] = None
    exclude_no_outstanding: Optional[bool] = None
    exclude_without_outstanding: Optional[bool] = None
    exclude_zero_outstanding: Optional[bool] = None
    exclude_return: Optional[bool] = None
    exclude_returns: Optional[bool] = None
    exclude_returned: Optional[bool] = None
    exclude_has_return: Optional[bool] = None
    exclude_has_returns: Optional[bool] = None
    exclude_with_return: Optional[bool] = None
    exclude_with_returns: Optional[bool] = None
    exclude_non_return: Optional[bool] = None
    exclude_non_returns: Optional[bool] = None
    exclude_no_return: Optional[bool] = None
    exclude_no_returns: Optional[bool] = None
    exclude_without_return: Optional[bool] = None
    exclude_without_returns: Optional[bool] = None

class GetPurchaseByIdSchema(BaseModel):
    id:str
    shop_id:str

class GetPurchaseByProductIdSchema(BaseModel):
    limit:int=10
    offset:int=1
    shop_id:str
    product_id:str
    outstanding: Optional[bool] = None
    exclude_cancle: Optional[bool] = None
    exclude_cancel: Optional[bool] = None
    exclude_canceled: Optional[bool] = None
    exclude_cancelled: Optional[bool] = None
    exclude_canceled_purchase: Optional[bool] = None
    exclude_canceled_purchases: Optional[bool] = None
    exclude_cancelled_purchases: Optional[bool] = None
    exclude_draft: Optional[bool] = None
    exclude_drafts: Optional[bool] = None
    exclude_draft_purchase: Optional[bool] = None
    exclude_draft_purchases: Optional[bool] = None
    exclude_not_paid: Optional[bool] = None
    exclude_unpaid: Optional[bool] = None
    exclude_notpaid: Optional[bool] = None
    exclude_unpaid_purchase: Optional[bool] = None
    exclude_unpaid_purchases: Optional[bool] = None
    exclude_not_paid_purchase: Optional[bool] = None
    exclude_not_paid_purchases: Optional[bool] = None
    exclude_paid: Optional[bool] = None
    exclude_completed_payment: Optional[bool] = None
    exclude_paid_purchase: Optional[bool] = None
    exclude_paid_purchases: Optional[bool] = None
    exclude_completed_purchase: Optional[bool] = None
    exclude_partial_paid: Optional[bool] = None
    exclude_partially_paid: Optional[bool] = None
    exclude_partial: Optional[bool] = None
    exclude_partially: Optional[bool] = None
    exclude_partial_paid_purchase: Optional[bool] = None
    exclude_partially_paid_purchases: Optional[bool] = None
    exclude_outstanding: Optional[bool] = None
    exclude_outstading: Optional[bool] = None
    exclude_outstaitng: Optional[bool] = None
    exclude_outstanding_purchases: Optional[bool] = None
    exclude_with_outstanding: Optional[bool] = None
    exclude_non_outstanding: Optional[bool] = None
    exclude_non_outstating: Optional[bool] = None
    exclude_no_outstanding: Optional[bool] = None
    exclude_without_outstanding: Optional[bool] = None
    exclude_zero_outstanding: Optional[bool] = None
    exclude_return: Optional[bool] = None
    exclude_returns: Optional[bool] = None
    exclude_returned: Optional[bool] = None
    exclude_has_return: Optional[bool] = None
    exclude_has_returns: Optional[bool] = None
    exclude_with_return: Optional[bool] = None
    exclude_with_returns: Optional[bool] = None
    exclude_non_return: Optional[bool] = None
    exclude_non_returns: Optional[bool] = None
    exclude_no_return: Optional[bool] = None
    exclude_no_returns: Optional[bool] = None
    exclude_without_return: Optional[bool] = None
    exclude_without_returns: Optional[bool] = None

class GetPurchaseBySupplierIdSchema(BaseModel):
    limit:int=10
    offset:int=1
    shop_id:str
    supplier_id:str
    status: Optional[str] = None
    outstanding: Optional[bool] = None
    exclude_cancle: Optional[bool] = None
    exclude_cancel: Optional[bool] = None
    exclude_canceled: Optional[bool] = None
    exclude_cancelled: Optional[bool] = None
    exclude_canceled_purchase: Optional[bool] = None
    exclude_canceled_purchases: Optional[bool] = None
    exclude_cancelled_purchases: Optional[bool] = None
    exclude_draft: Optional[bool] = None
    exclude_drafts: Optional[bool] = None
    exclude_draft_purchase: Optional[bool] = None
    exclude_draft_purchases: Optional[bool] = None
    exclude_not_paid: Optional[bool] = None
    exclude_unpaid: Optional[bool] = None
    exclude_notpaid: Optional[bool] = None
    exclude_unpaid_purchase: Optional[bool] = None
    exclude_unpaid_purchases: Optional[bool] = None
    exclude_not_paid_purchase: Optional[bool] = None
    exclude_not_paid_purchases: Optional[bool] = None
    exclude_paid: Optional[bool] = None
    exclude_completed_payment: Optional[bool] = None
    exclude_paid_purchase: Optional[bool] = None
    exclude_paid_purchases: Optional[bool] = None
    exclude_completed_purchase: Optional[bool] = None
    exclude_partial_paid: Optional[bool] = None
    exclude_partially_paid: Optional[bool] = None
    exclude_partial: Optional[bool] = None
    exclude_partially: Optional[bool] = None
    exclude_partial_paid_purchase: Optional[bool] = None
    exclude_partially_paid_purchases: Optional[bool] = None
    exclude_outstanding: Optional[bool] = None
    exclude_outstading: Optional[bool] = None
    exclude_outstaitng: Optional[bool] = None
    exclude_outstanding_purchases: Optional[bool] = None
    exclude_with_outstanding: Optional[bool] = None
    exclude_non_outstanding: Optional[bool] = None
    exclude_non_outstating: Optional[bool] = None
    exclude_no_outstanding: Optional[bool] = None
    exclude_without_outstanding: Optional[bool] = None
    exclude_zero_outstanding: Optional[bool] = None
    exclude_return: Optional[bool] = None
    exclude_returns: Optional[bool] = None
    exclude_returned: Optional[bool] = None
    exclude_has_return: Optional[bool] = None
    exclude_has_returns: Optional[bool] = None
    exclude_with_return: Optional[bool] = None
    exclude_with_returns: Optional[bool] = None
    exclude_non_return: Optional[bool] = None
    exclude_non_returns: Optional[bool] = None
    exclude_no_return: Optional[bool] = None
    exclude_no_returns: Optional[bool] = None
    exclude_without_return: Optional[bool] = None
    exclude_without_returns: Optional[bool] = None

class ClearPurchaseOutstandingSchema(BaseModel):
    purchase_id: str
    shop_id: str
    amount: float
    payment_method: str
    notes: Optional[str] = None

class RecordPurchasePaymentSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    purchase_id: Optional[str] = Field(default=None, alias="id")
    id: Optional[str] = None
    shop_id: str
    amount: float
    payment_method: Optional[str] = Field(default="CASH", alias="method")
    reference_no: Optional[str] = None
    notes: Optional[str] = None
    supplier_id: Optional[str] = None
    invoice_no: Optional[str] = None
    date: Optional[Union[str, date]] = None
    from_supplier_service: Optional[bool] = False
