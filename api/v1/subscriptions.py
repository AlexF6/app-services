from fastapi import APIRouter, HTTPException
from schemas.subscriptions import Subscription

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

subscriptions = [
    {"id": 1, "user_id": 1, "plan": "Basic", "active": True},
    {"id": 2, "user_id": 2, "plan": "Premium", "active": True},
    {"id": 3, "user_id": 3, "plan": "Free", "active": False},
]

@router.get("/", response_model=list[Subscription])
def list_all_subscriptions(active: bool | None = None):
    if active is None:
        return subscriptions
    return [s for s in subscriptions if s["active"] == active]

@router.get("/{subscription_id}", response_model=Subscription)
def get_subscription(subscription_id: int):
    for s in subscriptions:
        if s["id"] == subscription_id:
            return s
    raise HTTPException(status_code=404, detail="Subscription not found")

@router.post("/", status_code=201)
def create_subscription(subscription: Subscription):
    if any(s["id"] == subscription.id for s in subscriptions):
        raise HTTPException(status_code=400, detail="ID already exists")
    data = subscription.model_dump()
    subscriptions.append(data)
    return data

@router.put("/{subscription_id}", response_model=Subscription)
def update_subscription(subscription_id: int, updated: Subscription):
    for index, s in enumerate(subscriptions):
        if s["id"] == subscription_id:
            subscriptions[index] = updated.model_dump()
            return subscriptions[index]
    raise HTTPException(status_code=404, detail="Subscription not found")

@router.delete("/{subscription_id}", status_code=204)
def delete_subscription(subscription_id: int):
    for index, s in enumerate(subscriptions):
        if s["id"] == subscription_id:
            subscriptions.pop(index)
            return
    raise HTTPException(status_code=404, detail="Subscription not found")
