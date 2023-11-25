from starlette.responses import RedirectResponse, PlainTextResponse


async def home(_req):
    return RedirectResponse(url='/web/index.html')


async def cors_test(_req):
    return PlainTextResponse('OK')


async def auth_test(req):
    if req.user.is_authenticated:
        return PlainTextResponse('Hello, ' + req.user.display_name)

    return PlainTextResponse('OK')
