import functools

import typing
import anyio
from broadcaster import Broadcast


broadcast = Broadcast('redis://localhost:6379')


async def run_until_first_complete(*args: typing.Tuple[typing.Callable, dict]) -> None:  # type: ignore[type-arg]  # noqa: E501
    async with anyio.create_task_group() as task_group:

        async def run(func: typing.Callable[[], typing.Coroutine]) -> None:  # type: ignore[type-arg]  # noqa: E501
            await func()
            task_group.cancel_scope.cancel()

        for func, kwargs in args:
            task_group.start_soon(run, functools.partial(func, **kwargs))


async def channel(websocket):
    await websocket.accept()
    await run_until_first_complete(
        (channel_receiver, {'websocket': websocket}),
        (channel_sender, {'websocket': websocket}),
    )


async def channel_receiver(websocket):
    async for message in websocket.iter_text():
        await broadcast.publish(channel='channel', message=message)


async def channel_sender(websocket):
    async with broadcast.subscribe(channel='channel') as subscriber:
        async for event in subscriber:
            await websocket.send_text(event.message)
