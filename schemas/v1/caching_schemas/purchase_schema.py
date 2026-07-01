from pydantic import BaseModel


class PurchaseProductCachingSchema(BaseModel):
    barcodes:list=[]

class PurchaseSupplierCachingSchema(BaseModel):
    mobile_numbers:list=[]