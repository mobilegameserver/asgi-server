import contextlib

from library.database import users_db, services_db, statistics_db
from library.channel import broadcast


@contextlib.asynccontextmanager
async def lifespan(_app):
    await users_db.connect()
    await services_db.connect()
    await statistics_db.connect()
    await broadcast.connect()

    yield

    await users_db.disconnect()
    await services_db.disconnect()
    await statistics_db.disconnect()
    await broadcast.disconnect()
