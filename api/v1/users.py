from fastapi import APIRouter, HTTPException, status
from schemas.users import User

router = APIRouter(prefix="/users", tags=["Users"])

users = [
    {"id": 1, "name": "Alex", "email": "alex@example.com", "active": True},
    {"id": 2, "name": "Maria", "email": "maria@example.com", "active": False},
    {"id": 3, "name": "Carlos", "email": "carlos@example.com", "active": True}
]

# Read
# users index
@router.get("/", response_model=list[User])
def list_all_users(active: bool | None = None):
    if active is None:
        return users
    return [u for u in users if u["active"] == active]

# Show
@router.get("/{user_id}", response_model=User)
def get_user(user_id: int):
    for user in users:
        if user["id"] == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")

# Create
@router.post("/", status_code=201)
async def create_user(user: User):
    return {"message": "User created", "user": user}

# Update
@router.put("/{user_id}", response_model=User)
def update_user(user_id: int, updated_user: User):
    for index, user in enumerate(users):
        if user["id"] == user_id:
            users[index].update(updated_user.model_dump())
            return users[index]
    
    raise HTTPException(status_code=404, detail="User not found")

# Delete
@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int):
    for index, user in enumerate(users):
        if user["id"] == user_id:
            users.pop(index)
            return 
    
    raise HTTPException(status_code=404)

