import base64

import binascii
from starlette.authentication import AuthenticationBackend, AuthCredentials, SimpleUser, AuthenticationError


class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if 'Authorization' not in conn.headers:
            return

        auth = conn.headers['Authorization']
        try:
            scheme, credentials = auth.split()
            if scheme.lower() != 'basic':
                return
            decoded = base64.b64decode(credentials).decode('ascii')
        except (ValueError, UnicodeDecodeError, binascii.Error) as _exc:
            raise AuthenticationError('Invalid basic auth credentials')

        username, _, password = decoded.partition(':')
        # TODO: You'd want to verify the username and password here.
        return AuthCredentials(['authenticated']), SimpleUser(username)
