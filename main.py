from starlette.applications import Starlette
import uvicorn
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware

from lib.auth import BasicAuthBackend
from lib.http_exc import exception_handlers
from lib.routes import routes
from conf.conf import Conf
from lib.lifespan import lifespan


conf = Conf()
app = Starlette(
    debug=(conf.phase == 'dev'),
    routes=routes,
    middleware=[
        Middleware(CORSMiddleware, allow_origins=conf.allow_origins),
        Middleware(AuthenticationMiddleware, backend=BasicAuthBackend()),
    ],
    exception_handlers=exception_handlers,
    lifespan=lifespan,
)


if __name__ == '__main__':
    uvicorn.run(app, host=conf.server_host, port=conf.server_port)
