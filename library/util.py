from urllib.parse import urlparse
import pymysql
from conf.conf import conf
from pymysql.cursors import DictCursor
import redis


def check_all_conns_synchronously():
    for k in ['USERS_DB_URL', 'SERVICES_DB_URL', 'STATISTICS_DB_URL']:
        dcs = urlparse(conf.env(k))

        try:
            db_conn = pymysql.connect(
                host=dcs.hostname,
                user=dcs.username,
                password=dcs.password,
                database=dcs.path.lstrip('/'),
                port=dcs.port,
                charset='utf8mb4',
                cursorclass=DictCursor,
                autocommit=True,
            )
            db_conn.query('SELECT 1')
            db_conn.close()
        except pymysql.Error as err:
            raise RuntimeError(str(err))

    rcs = urlparse(conf.redis_url)
    try:
        rds_conn = redis.Redis(host=rcs.hostname, port=rcs.port)
        rds_conn.get('one')
        rds_conn.close()
    except redis.RedisError as err:
        raise RuntimeError(str(err))
