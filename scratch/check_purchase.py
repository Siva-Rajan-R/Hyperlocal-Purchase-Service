import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motor.motor_asyncio import AsyncIOMotorClient
from core.configs.settings_config import SETTINGS

async def fetch_purchase():
    client = AsyncIOMotorClient(SETTINGS.READ_DB_URL)
    db = client['PurchaseServiceReadDb']
    try:
        res = await db["PurchaseCollections"].find_one({"ui_id": "PUR-100026"})
        if res:
            res["_id"] = str(res["_id"])
            for r in res.get("returns", []):
                if "_id" in r:
                    r["_id"] = str(r["_id"])
            with open("scratch/purchase_dump.json", "w") as f:
                json.dump(res, f, indent=4)
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(fetch_purchase())
