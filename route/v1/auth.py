from starlette.responses import PlainTextResponse


async def token(_req):
    return PlainTextResponse('OK')
