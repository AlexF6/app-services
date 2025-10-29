from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine
from app.core.config import settings
from app.api.v1 import auth
from app.api.v1 import users
from app.api.v1 import subscriptions
from app.api.v1 import me_subscriptions
from app.api.v1 import payments
from app.api.v1 import me_payments
from app.api.v1 import plans
from app.api.v1 import me_plans
from app.api.v1 import contents
from app.api.v1 import me_contents
from app.api.v1 import profiles
from app.api.v1 import me_profiles
from app.api.v1 import watchlist
from app.api.v1 import me_watchlist
from app.api.v1 import playbacks
from app.api.v1 import me_playbacks
from app.api.v1 import episodes

app = FastAPI()

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(plans.router)
app.include_router(me_plans.router)
app.include_router(subscriptions.router)
app.include_router(me_subscriptions.router)
app.include_router(payments.router)
app.include_router(me_payments.router)
app.include_router(profiles.router)
app.include_router(me_profiles.router)
app.include_router(contents.router)
app.include_router(me_contents.router)
app.include_router(watchlist.router)
app.include_router(me_watchlist.router)
app.include_router(episodes.router)
app.include_router(playbacks.router)
app.include_router(me_playbacks.router)


origins = [
    "http://localhost:4200",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
