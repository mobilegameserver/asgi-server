from starlette.responses import JSONResponse

from lib.database import services_db
from model.notes import notes


async def list_notes(_request):
    query = notes.select()
    results = await services_db.fetch_all(query)
    content = [
        {
            'text': result['text'],
            'completed': result['completed']
        }
        for result in results
    ]
    return JSONResponse(content)


async def add_note(request):
    data = await request.json()
    query = notes.insert().values(
       text=data['text'],
       completed=data['completed']
    )
    await database.execute(query)
    return JSONResponse({
        'text': data['text'],
        'completed': data['completed']
    })
