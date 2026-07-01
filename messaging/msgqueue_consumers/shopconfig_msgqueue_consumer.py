from messaging.main import RabbitMQMessagingConfig
from icecream import ic
import orjson
from aio_pika.abc import AbstractIncomingMessage
from infras.read_db.models.shopidconfig_model import ShopIdConfigReadModel, ModuleConfigSchema
from infras.read_db.repos.shopidconfig_repo import ShopIdConfigReadDbRepo

class ShopConfigMsgQueueConsumer:
    async def process_shopconfig_update(self, message: AbstractIncomingMessage):
        try:
            async with message.process():
                payload = orjson.loads(message.body)
                ic(f"Received shop config update: {payload}")
                
                shop_id = payload.get("shop_id")
                raw_config = payload.get("config", {})
                
                if not shop_id:
                    ic("Missing shop_id in payload")
                    return
                
                parsed_config = {}
                for k, v in raw_config.items():
                    parsed_config[k] = ModuleConfigSchema(**v)
                
                read_model = ShopIdConfigReadModel(
                    shop_id=shop_id,
                    config=parsed_config
                )
                
                await ShopIdConfigReadDbRepo.upsert_config(read_model)
                ic(f"Successfully cached shop config for {shop_id} in MongoDB")
                
        except Exception as e:
            ic(f"Error processing shopconfig update event: {e}")

    async def consume(self):
        try:
            rb_msg = RabbitMQMessagingConfig()
            queue = await rb_msg.create_queue(
                routing_key="hyperlocal.shopconfig.updated",
                exchange_name="hyperlocal_domain_events",
                queue_name="inventory_service_shopconfig_q"
            )
            await rb_msg.consume_event(queue_name=queue.name, handler=self.process_shopconfig_update)
            ic("ShopConfigMsgQueueConsumer started listening on inventory_service_shopconfig_q")
        except Exception as e:
            ic(f"Failed to start ShopConfigMsgQueueConsumer: {e}")
