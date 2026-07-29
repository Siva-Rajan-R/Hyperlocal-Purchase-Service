from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from core.configs.settings_config import SETTINGS
from icecream import ic


ENGINE=create_async_engine(SETTINGS.PG_DATABASE_URL,echo=False, pool_size=1, max_overflow=2, pool_recycle=1800, pool_pre_ping=True)

BASE=declarative_base()


from sqlalchemy import text

AsyncInventoryLocalSession=async_sessionmaker(ENGINE)

async def init_inventory_pg_db():
    try:
        ic("initializing pg db...")
        async with ENGINE.connect() as conn:
            # await conn.run_sync(BASE.metadata.drop_all)
            await conn.run_sync(BASE.metadata.create_all)
            await conn.execute(text("ALTER TABLE purchase ADD COLUMN IF NOT EXISTS version VARCHAR DEFAULT 'v1';"))
            await conn.execute(text("ALTER TABLE purchase ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'COMPLETED';"))
            await conn.execute(text("ALTER TABLE purchase_items DROP COLUMN IF EXISTS serialno_id;"))
            await conn.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='purchase_items' AND column_name='serial_numbers' AND data_type != 'ARRAY'
                    ) THEN
                        ALTER TABLE purchase_items ALTER COLUMN serial_numbers TYPE jsonb[] USING serial_numbers::jsonb[];
                    END IF;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END $$;
            """))
            await conn.commit()
        ic("...Databse initialized successfully...")
    except Exception as e:
        ic(f"Error : initializing pg db => {e}")


async def get_pg_async_session():
    Session=AsyncInventoryLocalSession()
    try:
        yield Session
    finally:
        await Session.close()