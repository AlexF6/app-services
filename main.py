from fastapi import FastAPI
from api.v1.users import router as users_router
from api.v1.series import router as series_router
from api.v1.subscriptions import router as subscriptions_router


app = FastAPI(title="API")
app.include_router(users_router)
app.include_router(series_router)
app.include_router(subscriptions_router)