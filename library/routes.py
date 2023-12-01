from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles

from route.home import home, cors_test, auth_test
from library.channel import channel
from route import v1
from route.v1 import user
from route.v1 import auth
from route.v1.api import notes

routes = [
    Route('/', endpoint=home, methods=['GET']),

    WebSocketRoute('/channel', endpoint=channel),
    Mount('/web', app=StaticFiles(directory='web'), name='web'),

    Route('/cors_test', endpoint=cors_test, methods=['GET']),
    Route('/auth_test', endpoint=auth_test, methods=['GET']),

    Route('/v1/user/signup', endpoint=v1.user.signup, methods=['POST']),
    Route('/v1/auth/token', endpoint=v1.auth.token, methods=['GET']),

    Route('/v1/api/notes/list', endpoint=v1.api.notes.list, methods=['GET']),
    Route('/v1/api/notes/add', endpoint=v1.api.notes.add, methods=['POST']),
]
