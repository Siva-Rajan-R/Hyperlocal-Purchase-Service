from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class InventoryVariantReadModel(BaseModel):
    id: str
    inventory_id: str
    sku: str
    name: Optional[str] = None
    stocks: float
    buy_price: float
    sell_price: float
    reorder_point: int
    datas: Optional[Dict[str, Any]] = None
    batches: List['InventoryBatchReadModel'] = []
    serial_numbers: Optional['InventorySerialReadModel'] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class InventoryBatchReadModel(BaseModel):
    id: str
    inventory_id: str
    variant_id: Optional[str] = None
    name: Optional[str] = None
    stocks: float
    expiry_date: Optional[datetime] = None
    manufacturing_date: Optional[datetime] = None
    datas: Optional[Dict[str, Any]] = None
    serial_numbers: Optional['InventorySerialReadModel'] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class InventorySerialReadModel(BaseModel):
    id: str
    inventory_id: str
    variant_id: Optional[str] = None
    batch_id: Optional[str] = None
    serial_numbers: List[str] = []
    created_at: Optional[datetime] = None

class InventoryReadModel(BaseModel):
    id: str
    ui_id: Optional[str] = None
    sequence_id: Optional[int] = None
    shop_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    category: str
    stocks: float
    reorder_point: int
    buy_price: float
    sell_price: float
    sku: str
    barcode: Optional[str] = None
    has_variant: bool
    has_batch: bool
    has_serialno: bool
    is_active: bool
    datas: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    variants: List[InventoryVariantReadModel] = []
    batches: List[InventoryBatchReadModel] = []
    serials: Optional[InventorySerialReadModel] = None
