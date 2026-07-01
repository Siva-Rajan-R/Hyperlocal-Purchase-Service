from ..repos.base_repo import ReadDbBaseRepo
from ..models.inventory_model import ReadDbInventoryCreateModel,ReadDbInventoryUpdateModel,ReadDbInventoryReadModel
from ..main import INVENTORY_COLLECTION
from typing import Optional,List,Any
from models.infra_models.readdb_model import BaseReadDbModel
from pymongo import UpdateOne
from typing import Optional,List


class ReadDbInventoryService(BaseReadDbModel):
    def __init__(self,payload:Any,conditions:dict):
        self.payload=payload
        self.conditions=conditions
        self.collection=INVENTORY_COLLECTION
        self.base_Repo_obj=ReadDbBaseRepo(collection=self.collection)
        # super.__init__(payload,conditions)

    
    async def create(self):
        if not isinstance(self.payload,ReadDbInventoryCreateModel):
            return False

        data=self.payload.model_dump(mode="json",exclude_unset=True)
        return (await self.base_Repo_obj.create(data=data)).acknowledged
    
    async def update(self):
        if not isinstance(self.payload,ReadDbInventoryUpdateModel):
            return False
        
        data=self.payload.model_dump(mode="json",exclude_unset=True)
        return (await self.base_Repo_obj.update(data=data,conditions=self.conditions))
    
    async def delete(self):
        return (await self.base_Repo_obj.delete(conditions=self.conditions))
    
    async def get(self,query:str,limit:Optional[int]=None,offset:Optional[int]=None):
        query=query.strip()
        queries={
            "$or":[
                {'inventory_id':{'$regex':query,'$options':'i'}},
                {'shop_id':{'$regex':query,'$options':'i'}},
                {'barcode':{'$regex':query,'$options':'i'}},
                {'product_name':{'$regex':query,'$options':'i'}},
                {'product_category':{'$regex':query,'$options':'i'}},
                {'product_description':{'$regex':query,'$options':'i'}},
                {'added_by':{'$regex':query,'$options':'i'}}
            ]
        }

        return await self.base_Repo_obj.get(queries=queries,offset=offset,limit=limit)
    
    async def getby_queries(self,queries:dict,limit:Optional[int]=None,offset:Optional[int]=None):
        return await self.base_Repo_obj.get(queries=queries,limit=limit,offset=offset)
    
    async def get_one(self,queries:dict):
        return await self.base_Repo_obj.get_one(queries=queries)
    
    async def update_qty_bulk(self,data:dict,shop_id:str):
        """
        Docstring for update_qty_bulk
        THe data contains product barcode as a key & the qty to increment as a value
        """
        bulk_update_data=[
            UpdateOne(
                {'barcode':barcode,'shop_id':shop_id},
                {'$inc':{'stocks':qty}}
            )
            for barcode,qty in data.items() 
        ]

        return await self.base_Repo_obj.update_bulk(ops=bulk_update_data)
    
