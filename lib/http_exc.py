from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import PlainTextResponse


async def not_found(_req, _exc):
    return PlainTextResponse('Not Found')


async def internal_server_error(_req, _exc):
    return PlainTextResponse('Internal Server Error')


exception_handlers = {
    404: not_found,
    500: internal_server_error
}
