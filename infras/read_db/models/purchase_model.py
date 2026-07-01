from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, Field


class ReadVariantInfos(BaseModel):
    id: str
    name: str

class ReadBatchInfos(BaseModel):
    id: str
    name: str
    mfg_date: Optional[datetime] = None
    exp_date: Optional[datetime] = None

class ReadStocksInfos(BaseModel):
    stocks: float
    stocks_before: float
    stocks_after: float

class ReadReorderPointInfos(BaseModel):
    id: Optional[str] = None
    reorder_point: float

class ReadStorageLocationInfos(BaseModel):
    id: Optional[str] = None
    name: str

class PurchaseItemReadModel(BaseModel):
    id: str
    product_id: str
    ui_id: str
    name: str
    
    category_name: Optional[str] = None
    unit_name: Optional[str] = None
    
    variant_infos: Optional[ReadVariantInfos] = None
    batch_infos: Optional[ReadBatchInfos] = None
    stocks_infos: ReadStocksInfos
    reorder_point_infos: Optional[ReadReorderPointInfos] = None
    storage_location_infos: Optional[ReadStorageLocationInfos] = None
    
    serial_numbers: List[str] = []
    
    sell_price: float = 0
    buy_price: float = 0
    total_amount: float = 0
    
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

    supplier: SupplierInfo

    
    total_cost: float = 0.0
    total_items: int = 0
    total_quantity: int = 0

    paid_amount: float = 0.0
    payment_status: str = "completed"
    transport_charge: float = 0.0
    other_charges: float = 0.0
    calculations: dict = {}
    payment_status:str

    items: List[PurchaseItemReadModel] = []
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
