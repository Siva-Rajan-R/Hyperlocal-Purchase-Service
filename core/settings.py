from pydantic_settings import BaseSettings
from hyperlocal_platform.core.enums.environment_enum import EnvironmentEnum
from .constants import ENV_PREFIX
from dotenv import load_dotenv
load_dotenv()

class InventorySettings(BaseSettings):
    PG_DATABASE_URL:str
    ENVIRONMENT:EnvironmentEnum
    READ_DB_URL:str
    
    model_config={
        'case_sensitive':False,
        'env_prefix':ENV_PREFIX
    }