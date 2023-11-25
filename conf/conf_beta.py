from conf.conf_base import ConfBase


class Conf(ConfBase):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfBase, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__()

        self.phase = 'beta'
        if self.phase != self.env('PHASE'):
            raise RuntimeError('phase not matched')

        self.server_host = '0.0.0.0'
        self.server_port = 9871

        self.redis_url = 'redis://localhost:6379'
        self.allow_origins = ['http://127.0.0.1:8000']
