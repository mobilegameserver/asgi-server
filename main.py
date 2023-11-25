from starlette.applications import Starlette
import uvicorn
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware

from library.auth import BasicAuthBackend
from library.http_exc import exception_handlers
from library.routes import routes
from conf.conf import conf
from library.lifespan import lifespan
from library.util import check_all_conns_synchronously


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
    check_all_conns_synchronously()
    uvicorn.run(app, host=conf.server_host, port=conf.server_port)
