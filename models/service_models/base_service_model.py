from hyperlocal_platform.core.models.service_repo_base_models import CommonBaseServiceModel
from sqlalchemy.ext.asyncio import AsyncSession


class BaseServiceModel(CommonBaseServiceModel):
    def __init__(self,session:AsyncSession):
        self.session=session