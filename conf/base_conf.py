from hashlib import md5
from starlette.config import Config


class _BaseConf:
    def __init__(self):
        self.env = Config('.env')
        self.aes_key = md5(self.env('AES_KEY').encode('utf-8')).digest()

        self.phase = ''

        self.server_host = ''
        self.server_port = 0

        self.redis_url = ''
        self.allow_origins = []

        self.token_access_lifetime_minutes = 14 * 24 * 60  # 14 days * 24 hours * 60 minutes
        self.token_refresh_lifetime_minutes = 28 * 24 * 60  # 28 days * 24 hours * 60 minutes
