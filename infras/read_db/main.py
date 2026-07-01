from motor.motor_asyncio import AsyncIOMotorClient
from core.configs.settings_config import SETTINGS
import asyncio
from icecream import ic


READ_DB_URL=SETTINGS.READ_DB_URL

CLIENT=None
READ_DATABASE=None

async def init_read_db():
    global CLIENT,READ_DATABASE
    CLIENT=AsyncIOMotorClient(READ_DB_URL)
    READ_DATABASE=CLIENT['PurchaseServiceReadDb']

async def close_read_db():
    global CLIENT
    if CLIENT:
        CLIENT.close()

MONGO_CLIENT=AsyncIOMotorClient(SETTINGS.READ_DB_URL)


DB=MONGO_CLIENT["PurchaseServiceReadDb"]

PURCHAESE_COLLECTION=DB['PurchaseCollections']
PURCHASE_STATS_COLLECTION=DB['PurchaseStatsCollections']



