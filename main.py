from fastapi import FastAPI
from api.v1.users import router as users_router

app = FastAPI(title="API")
app.include_router(users_router)