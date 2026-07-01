from .main import RabbitMQMessagingConfig,ExchangeType
from .controllers.service_controller import service_main_controller
from .controllers.producer_controller import producer_main_controller
from .msgqueue_consumers.shopconfig_msgqueue_consumer import ShopConfigMsgQueueConsumer
import asyncio

async def worker():
    rabbitmq_conn=await RabbitMQMessagingConfig.get_rabbitmq_connection()
    rabbitmq_msg_obj=RabbitMQMessagingConfig(rabbitMQ_connection=rabbitmq_conn)

    # Exchanges
    exchanges=[
        {'name':'purchase.service.exchange','exc_type':ExchangeType.DIRECT},
        {'name':'purchase.producer.exchange','exc_type':ExchangeType.DIRECT},
        {'name':'hyperlocal_domain_events','exc_type':ExchangeType.DIRECT}
    ]

    for exchange in exchanges:
        await rabbitmq_msg_obj.create_exchange(name=exchange['name'],exchange_type=exchange['exc_type'])

    # Queues
    queues=[
        {'exc_name':'purchase.service.exchange','q_name':'purchase.service.queue','r_key':'purchase.service.routing.key'},
        {'exc_name':'purchase.producer.exchange','q_name':'purchase.producer.queue','r_key':'purchase.producer.routing.key'},
        {'exc_name':'hyperlocal_domain_events','q_name':'supplier_service_shopconfig_q','r_key':'hyperlocal.shopconfig.updated'}
    ]

    for queue in queues:
        queue=await rabbitmq_msg_obj.create_queue(
            exchange_name=queue['exc_name'],
            queue_name=queue['q_name'],
            routing_key=queue['r_key']
        )

    # Consumers
    consumers=[
        {'q_name':'purchase.service.queue','handler':service_main_controller},
        {'q_name':'purchase.producer.queue','handler':producer_main_controller}
    ]

    for consumer in consumers:

        await rabbitmq_msg_obj.consume_event(queue_name=consumer['q_name'],handler=consumer['handler'])

    # Start ShopConfig Consumer
    shop_config_consumer = ShopConfigMsgQueueConsumer()
    await shop_config_consumer.consume()

    await asyncio.Event().wait()
