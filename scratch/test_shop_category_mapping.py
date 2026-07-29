import asyncio
import sys
import os

# Add Utility_Service directory to sys.path
sys.path.insert(0, r"d:\projects\airport-marketplace\Services\HyperLocal_Services\Utility_Service")

from core.constants import SHOP_CATEGORIES_MAPPING, DEFAULT_CATEGORIES
from infras.primary_db.main import AsyncUtilisLocalSession, init_utilis_pg_db
from infras.primary_db.services.shop_categories_service import ShopCategoryService
from schemas.v1.request_schemas.shop_category_schema import GetShopCategorySchema
from icecream import ic

async def run_test():
    print("=======================================================")
    print("1. VERIFYING PREDEFINED SHOP CATEGORIES MAPPING")
    print("=======================================================")
    ic("Shop Categories Keys =>", list(SHOP_CATEGORIES_MAPPING.keys()))
    assert "GROCERY" in SHOP_CATEGORIES_MAPPING
    assert "ELECTRONICS" in SHOP_CATEGORIES_MAPPING
    assert "CLOTHING" in SHOP_CATEGORIES_MAPPING
    assert "PHARMACY" in SHOP_CATEGORIES_MAPPING
    assert "RESTAURANT" in SHOP_CATEGORIES_MAPPING

    # Initialize DB tables
    await init_utilis_pg_db()

    print("\n=======================================================")
    print("2. TESTING DYNAMIC INIT_CATEGORIES FOR ELECTRONICS SHOP")
    print("=======================================================")
    shop_id_1 = "shop-electronics-test-01"
    async with AsyncUtilisLocalSession() as session:
        service = ShopCategoryService(session=session)
        await service.init_categories(shop_id=shop_id_1, categories=["ELECTRONICS"])
        await session.commit()

    async with AsyncUtilisLocalSession() as session:
        service = ShopCategoryService(session=session)
        cats_res = await service.get(GetShopCategorySchema(shop_id=shop_id_1, limit=100))
        cat_names = [c["name"] for c in cats_res]
        ic("Electronics Shop Product Categories =>", cat_names)
        assert "ELECTRONICS" in cat_names
        assert "HOME APPLIANCES" in cat_names
        assert "STATIONERY" in cat_names
        assert "GENERAL" in cat_names
        assert "OTHERS" in cat_names

    print("\n=======================================================")
    print("3. TESTING DYNAMIC INIT_CATEGORIES FOR MULTIPLE SHOP CATEGORIES (ELECTRONICS + CLOTHING)")
    print("=======================================================")
    shop_id_2 = "shop-multi-test-02"
    async with AsyncUtilisLocalSession() as session:
        service = ShopCategoryService(session=session)
        await service.init_categories(shop_id=shop_id_2, categories=["ELECTRONICS", "CLOTHING"])
        await session.commit()

    async with AsyncUtilisLocalSession() as session:
        service = ShopCategoryService(session=session)
        cats_res = await service.get(GetShopCategorySchema(shop_id=shop_id_2, limit=100))
        cat_names = [c["name"] for c in cats_res]
        ic("Multi Shop Product Categories =>", cat_names)
        assert "ELECTRONICS" in cat_names
        assert "CLOTHING" in cat_names
        assert "HOME APPLIANCES" in cat_names
        assert "PERSONAL CARE" in cat_names
        # Check no duplicates
        assert len(cat_names) == len(set(cat_names))

    print("\n=======================================================")
    print("ALL SHOP CATEGORY MAPPING TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_test())
