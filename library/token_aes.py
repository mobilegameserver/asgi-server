import json
import secrets
from datetime import datetime
from base64 import urlsafe_b64encode, urlsafe_b64decode
from binascii import Error

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from conf.conf import get_conf


class Aes:
    def __init__(self, key):
        self.key = key

    def encrypt(self, plain_text):
        iv = secrets.token_bytes(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_GCM, iv)

        encrypted = cipher.encrypt(pad(plain_text.encode('utf-8'), AES.block_size))
        urlsafe_b64encoded = urlsafe_b64encode(iv + encrypted).decode('utf-8')

        return urlsafe_b64encoded

    def decrypt(self, b64encoded):
        try:
            encrypted = urlsafe_b64decode(b64encoded)
            cipher = AES.new(self.key, AES.MODE_GCM, encrypted[:AES.block_size])

            result = unpad(cipher.decrypt(encrypted[AES.block_size:]), AES.block_size).decode('utf-8')
        except ValueError as val_err:
            result = val_err

        return result


class Token:
    def __init__(self):
        self.conf = get_conf()

        self.data = {
            'access': int(datetime.now().timestamp()) + self.conf.token_access_lifetime_minutes * 60,
            'refresh': int(datetime.now().timestamp()) + self.conf.token_refresh_lifetime_minutes * 60,
        }

    def load(self, s):
        if s == '':
            return False

        aes = Aes(self.conf.aes_key)
        decrypted = aes.decrypt(s)
        if isinstance(decrypted, Error) or decrypted == '':
            return False

        json_loaded = json.loads(decrypted)
        if isinstance(json_loaded, ValueError):
            return False

        if int(json_loaded.get('access', 0)) < int(datetime.now().timestamp()):
            return False

        self.data = json_loaded
        return True

    def __str__(self):
        aes = Aes(self.conf.aes_key)
        return aes.encrypt(json.dumps(self.data))
