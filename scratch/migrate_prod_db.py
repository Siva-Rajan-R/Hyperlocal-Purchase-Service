import asyncio
import sys
import os

path_pur = r"d:\projects\airport-marketplace\Services\HyperLocal_Services\purchase_service"
path_root = r"d:\projects\airport-marketplace\Services\HyperLocal_Services"
if path_pur not in sys.path:
    sys.path.insert(0, path_pur)
if path_root not in sys.path:
    sys.path.insert(0, path_root)

from icecream import ic

async def run_prod_migration():
    print("=======================================================")
    print("RUNNING DATABASE MIGRATION ON PRODUCTION PURCHASE DB")
    print("=======================================================")

    from core.configs.settings_config import SETTINGS
    print(f"Target Database URL: {SETTINGS.PG_DATABASE_URL}")

    from infras.primary_db.main import init_inventory_pg_db, ENGINE
    
    # Run the init / schema migration script
    await init_inventory_pg_db()

    # Verify tables & columns created on production DB
    from sqlalchemy import text
    async with ENGINE.connect() as conn:
        res_cols = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'purchase' OR table_name = 'purchase_items'
            ORDER BY table_name, column_name;
        """))
        columns = res_cols.fetchall()
        print("\nProduction DB Table Schema Verification:")
        for col in columns:
            print(f"  - Table Column: {col[0]} ({col[1]})")

    print("\n=======================================================")
    print("PRODUCTION PURCHASE SERVICE DB MIGRATION COMPLETED!")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_prod_migration())
