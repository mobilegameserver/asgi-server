from hashlib import md5
from starlette.config import Config


class ConfBase:
    env = None
    aes_key = ''

    phase = ''
    server_host = ''
    server_port = 0
    redis_url = ''
    allow_origins = []
    token_access_lifetime_minutes = 14 * 24 * 60  # 14 days * 24 hours * 60 minutes
    token_refresh_lifetime_minutes = 28 * 24 * 60  # 28 days * 24 hours * 60 minutes

    def __init__(self):
        self.env = Config('.env')
        self.aes_key = md5(self.env('AES_KEY').encode('utf-8')).digest()
