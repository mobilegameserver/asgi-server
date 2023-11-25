from conf.base_conf import _BaseConf


class _Conf(_BaseConf):
    def __init__(self):
        super().__init__()

        self.phase = 'beta'
        if self.phase != self.env('PHASE'):
            raise RuntimeError('phase not matched')

        self.server_host = '0.0.0.0'
        self.server_port = 9871

        self.redis_url = 'redis://localhost:6379'
        self.allow_origins = ['http://127.0.0.1:8000']


conf = _Conf()
