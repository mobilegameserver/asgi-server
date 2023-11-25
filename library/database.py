import databases
from conf.conf import get_conf


conf = get_conf()

USERS_DB_URL = conf.env('USERS_DB_URL')
SERVICES_DB_URL = conf.env('SERVICES_DB_URL')
STATISTICS_DB_URL = conf.env('STATISTICS_DB_URL')

users_db = databases.Database(USERS_DB_URL)
services_db = databases.Database(SERVICES_DB_URL)
statistics_db = databases.Database(STATISTICS_DB_URL)
