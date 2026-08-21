from datetime import datetime, date
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class ReadVariantInfos(BaseModel):
    id: str
    name: str

class ReadBatchInfos(BaseModel):
    id: str
    name: str
    expiry_date: Optional[str] = None
    manufacturing_date: Optional[str] = None

class ReadStocksInfos(BaseModel):
    stocks: float
    stocks_before: float
    stocks_after: float

class ReadReorderPointInfos(BaseModel):
    id: str
    reorder_point: float

class ReadStorageLocationInfos(BaseModel):
    id: str
    name: str

class PurchaseItemReadModel(BaseModel):
    id: str
    product_id: str
    ui_id: str
    name: str
    category_infos: Optional[dict] = None
    unit_infos: Optional[dict] = None
    
    variant_infos: Optional[ReadVariantInfos] = None
    batch_infos: Optional[ReadBatchInfos] = None
    stocks_infos: ReadStocksInfos
    reorder_point_infos: Optional[ReadReorderPointInfos] = None
    storage_location_infos: Optional[ReadStorageLocationInfos] = None
    
    serial_numbers: List[Union[str, dict]] = []
    
    sell_price: float = 0
    buy_price: float = 0
    total_amount: float = 0
    
    returned_quantity: float = 0.0
    returned_amount: float = 0.0
    exchanged_amount: float = 0.0

    gst: Optional[str] = None

class SupplierInfo(BaseModel):
    supplier_id: str
    supplier_name: str



class PurchaseReadModel(BaseModel):
    purchase_id: str
    ui_id: str
    invoice_no: str
    shop_id: str

    purchase_date: datetime
    status: str = "COMPLETED"

    supplier: SupplierInfo

    
    item_infos:dict={}

    payment_infos: list = []
    payment_status: str = "completed"
    outstanding_amount : float = 0.0 
    paid_amount: float = 0.0
    charges_infos: dict = {}
    calculations: dict = {}
    gst_infos: dict = {}
    custom_fields: Optional[dict] = {}
    items: List[PurchaseItemReadModel] = []
    version: Optional[str] = "v1"
    history: Optional[List[dict]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PurchaseStatsReadModel(BaseModel):
    shop_id: str
    total_purchase_count: int = 0
    total_purchase_value: float = 0.0
    outstanding_counts: int = 0
    outstanding_value: float = 0.0
    complete_counts: int = 0
    completed_value: float = 0.0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
