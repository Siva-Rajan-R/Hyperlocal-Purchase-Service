from .main import RabbitMQMessagingConfig
from sqlalchemy.ext.asyncio import AsyncSession
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from hyperlocal_platform.core.enums.saga_state_enum import SagaStatusEnum
from typing import Optional
from pydantic import BaseModel
from hyperlocal_platform.infras.saga.schemas import CreateSagaStateSchema,UpdateSagaStateSchema
from hyperlocal_platform.infras.saga.repo import SagaStatesRepo
from hyperlocal_platform.infras.saga.main import AsyncInfraDbLocalSession
from hyperlocal_platform.core.typed_dicts.saga_status_typ_dict import SagaStateErrorTypDict,SagaStateExecutionTypDict
from icecream import ic


class SagaProducer:
    @staticmethod
    async def emit(saga_payload:CreateSagaStateSchema,routing_key:str,exchange_name:str,headers:Optional[dict]={},):
        rabbitmq_msg_obj=RabbitMQMessagingConfig()
        ic("Inside Saga Producer")
        async with AsyncInfraDbLocalSession() as session:
            is_saga_created=await SagaStatesRepo(session=session).create(data=saga_payload)

        if is_saga_created:
            await rabbitmq_msg_obj.publish_event(
                routing_key=routing_key,
                exchange_name=exchange_name,
                payload={},
                headers={
                    **headers,
                    'routing_key':routing_key,
                    'exchange_name':exchange_name,
                    'saga_id':saga_payload.id,
                }
            )

            return {'status':SagaStatusEnum.PENDING,'saga_id':saga_payload.id}
        
