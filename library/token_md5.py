from datetime import datetime
from hashlib import md5
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from conf.conf import conf


class TokenMd5:
    def __init__(self):
        self.exp = {
            'access': int(datetime.now().timestamp()) + conf.token_access_lifetime_minutes * 60,
            'refresh': int(datetime.now().timestamp()) + conf.token_refresh_lifetime_minutes * 60,
        }
        self.data = {}

    def load(self, s):
        if len(s) < 32:
            return False

        b64_encoded = s[:-32]
        md5_hex_digest = s[-32:]

        if md5_hex_digest != md5((b64_encoded + conf.secret_key).encode('utf-8')).hexdigest():
            return False

        json_loaded = json.loads(urlsafe_b64decode(b64_encoded))
        self.exp = json_loaded.get('exp', {})

        if int(self.exp.get('access', 0)) < int(datetime.now().timestamp()):
            return False

        self.data = json_loaded.get('data', {})
        return True

    def __str__(self):
        json_dumped = json.dumps({
            'exp': self.exp,
            'data': self.data,
        }).encode('utf-8')

        b64_encoded = urlsafe_b64encode(json_dumped).decode('utf-8')
        md5_hex_digest = md5((b64_encoded + conf.secret_key).encode('utf-8')).hexdigest()

        return b64_encoded + md5_hex_digest
