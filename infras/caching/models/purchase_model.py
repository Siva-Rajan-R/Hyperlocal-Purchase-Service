from icecream import ic
from hyperlocal_platform.infras.redis.repo import RedisRepo,redis_client
from schemas.v1.caching_schemas.purchase_schema import PurchaseProductCachingSchema,PurchaseSupplierCachingSchema
from typing import Optional



class PurchaseProductCacheModel:
    def __init__(self,shop_id:str,user_id:str):
        self.shop_id=shop_id
        self.user_id=user_id
        self.cache_key=f"PURCHASE-PRODUCT-CACHE-{shop_id}-{user_id}"

    async def set(self,data:PurchaseProductCachingSchema,expiry:Optional[int]=10000):
        final_data={}
        existing_data=self.get()
        if existing_data:
            existing_data['barcodes'].extend(data.barcodes)
            final_data['barcodes']=existing_data
        else:
            final_data['barcodes']=data.barcodes
        
        return RedisRepo.set(key=self.cache_key,value=final_data,expire=expiry)

    async def get(self):
        return await RedisRepo.get(key=self.cache_key)

    async def delete(self):
        return await RedisRepo.unlink(keys=[self.cache_key])
    

class PurchaseSupplierCacheModel:
    def __init__(self,shop_id:str,user_id:str):
        self.shop_id=shop_id
        self.user_id=user_id
        self.cache_key=f"PURCHASE-PRODUCT-CACHE-{shop_id}-{user_id}"

    async def set(self,data:PurchaseSupplierCachingSchema,expiry:Optional[int]=10000):
        final_data={}
        existing_data=self.get()
        if existing_data:
            existing_data['mobile_numbers'].extend(data.mobile_numbers)
            final_data['mobile_numbers']=existing_data
        else:
            final_data['mobile_numbers']=data.mobile_numbers
        
        return RedisRepo.set(key=self.cache_key,value=final_data,expire=expiry)

    async def get(self):
        return await RedisRepo.get(key=self.cache_key)

    async def delete(self):
        return await RedisRepo.unlink(keys=[self.cache_key])
    