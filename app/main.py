from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine
from app.core.config import settings
from app.api.v1 import auth
from app.api.v1 import users


app = FastAPI()

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/config")
def read_config():
    return {"foo": settings.DATABASE_URL}

origins = [
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
