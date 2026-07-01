from hyperlocal_platform.core.utils.settings_initializer import init_settings
from ..settings import InventorySettings,ENV_PREFIX


SETTINGS:InventorySettings=init_settings(settings=InventorySettings,service_name="Inventory",env_prefix=ENV_PREFIX)