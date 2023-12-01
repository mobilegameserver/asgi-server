import os
import sys
from types import SimpleNamespace
import json
import ssl
from http.client import HTTPConnection, HTTPSConnection


class Test:
    def __init__(self):
        self.cfg = None
        self.http_conn = None
        self.resp = None

    def create_http_conn(self):
        if self.cfg.http_tls:
            context = ssl.create_default_context()
            return HTTPSConnection(self.cfg.http_host, self.cfg.http_port, self.cfg.http_timeout_sec, context=context)
        else:
            return HTTPConnection(self.cfg.http_host, self.cfg.http_port, self.cfg.http_timeout_sec)

    def initialize(self, cfg):
        self.cfg = cfg
        self.http_conn = self.create_http_conn()

    def run(self, method, path, post_data=None, headers=None, callback=None):
        print('{} {}'.format(method, path))

        if headers is None:
            headers = {}

        self.http_conn.request(method, path, post_data, headers)
        resp = self.http_conn.getresponse()

        print(resp.status)
        callback(resp.read().decode('utf-8'))
        print()

    def finalize(self):
        self.http_conn.close()

    @classmethod
    def callback_v1_api_server_status(cls, body):
        json_loaded = json.loads(body)
        print(json_loaded)


def print_and_exit(message):
    print('\n' + message)
    sys.exit()


def load_cfg():
    envs = ['dev', 'beta', 'prod']

    if len(sys.argv) < 2:
        print_and_exit('USAGE: python3 ./_py_test.py {}'.format(envs))

    arg_env = sys.argv[1]
    if arg_env not in envs:
        print_and_exit('ERROR: invalid env, should be one of {}'.format(envs))

    json_file = '_py_test.json'
    if not os.path.exists(json_file):
        print_and_exit('ERROR: {} not found, copy _py_test.example.json to {}'.format(json_file, json_file))

    with open(json_file, 'r') as f:
        json_loaded = json.loads(f.read(), object_hook=lambda d: SimpleNamespace(**d))

    if not hasattr(json_loaded, arg_env):
        print_and_exit('ERROR: invalid env, not found in {}'.format(json_file))

    return getattr(json_loaded, arg_env)


def main():
    cfg = load_cfg()

    t = Test()
    t.initialize(cfg)
    print('\n\ntest initialized.\n')

    t.run('GET', '/v1/api/server/status', None, None, t.callback_v1_api_server_status)

    t.finalize()


if __name__ == '__main__':
    main()
