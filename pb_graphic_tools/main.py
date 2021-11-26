from fastapi import FastAPI
from pb_graphic_tools.api.routes import routes

app = FastAPI(debug=True)

app.include_router(routes)
