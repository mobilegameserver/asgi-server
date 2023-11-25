import anyio
from broadcaster import Broadcast
from conf.conf import get_conf


conf = get_conf()
broadcast = Broadcast(conf.redis_url)


async def channel(websocket):
    await websocket.accept()

    async with anyio.create_task_group() as task_group:
        # run until first is complete
        async def run_channel_receiver():
            await channel_receiver(websocket=websocket)
            task_group.cancel_scope.cancel()

        task_group.start_soon(run_channel_receiver)
        await channel_sender(websocket)


async def channel_receiver(websocket):
    async for message in websocket.iter_text():
        await broadcast.publish(channel='channel', message=message)


async def channel_sender(websocket):
    async with broadcast.subscribe(channel='channel') as subscriber:
        async for event in subscriber:
            await websocket.send_text(event.message)
