from starlette.responses import PlainTextResponse


async def signup():
    return PlainTextResponse('OK')
