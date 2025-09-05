from fastapi import APIRouter, HTTPException, status
from schemas.users import User

router = APIRouter(prefix="/users", tags=["Users"])

users = [
    {"id": 1, "nombre": "Alex", "email": "alex@example.com", "activo": True},
    {"id": 2, "nombre": "Maria", "email": "maria@example.com", "activo": False},
    {"id": 3, "nombre": "Carlos", "email": "carlos@example.com", "activo": True}
]

# Read
# users index
@router.get("/", response_model=list[User])
def list_all_users(activo: bool | None = None):
    if activo is None:
        return users
    return [u for u in users if u["activo"] == activo]

# Show
@router.get("/{user_id}", response_model=User)
def get_user(user_id: int):
    for user in users:
        if user["id"] == user_id:
            return user
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

# Create
@router.post("/", status_code=201, response_model=User)
async def create_user(user: User):
    return {"message": "Usuario creado", "user": user}

# Update
@router.put("/{user_id}", response_model=User)
def update_user(user_id: int, updated_user: User):
    for index, user in enumerate(users):
        if user["id"] == user_id:
            users[index].update(updated_user.model_dump())
            return users[index]
    
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

# Delete
@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int):
    for index, user in enumerate(users):
        if user["id"] == user_id:
            users.pop(index)
            return 
    
    raise HTTPException(status_code=404)

