from fastapi import APIRouter, HTTPException
from app.schemas.series import Serie

router = APIRouter(prefix="/series", tags=["Series"])

series = [
    {"id": 1, "name": "Breaking Bad", "seasons": 5, "active": True},
    {"id": 2, "name": "Stranger Things", "seasons": 4, "active": True},
    {"id": 3, "name": "The Office", "seasons": 9, "active": False},
    {"id": 4, "name": "Game of Thrones", "seasons": 8, "active": False},
    {"id": 5, "name": "The Witcher", "seasons": 3, "active": True},
]


# Show
@router.get("/{serie_id}", response_model=Serie)
def get_serie(serie_id: int):
    for serie in series:
        if serie["id"] == serie_id:
            return serie
    raise HTTPException(status_code=404, detail="Serie not found")


# Read
# users index
@router.get("/", response_model=list[Serie])
def list_all_series(active: bool | None = None):
    if active is None:
        return series
    return [u for u in series if u["active"] == active]


# Update
@router.put("/{serie_id}", response_model=Serie)
def update_serie(serie_id: int, updated_serie: Serie):
    for index, serie in enumerate(series):
        if serie["id"] == serie_id:
            series[index].update(updated_serie.model_dump())
            return series[index]

    raise HTTPException(status_code=404, detail="Serie not found")


# Create
@router.post("/", status_code=201)
async def create_serie(serie: Serie):
    return {"message": "Serie Created", "serie": serie}


# Delete
@router.delete("/{serie_id}", status_code=204)
def delete_serie(serie_id: int):
    for index, user in enumerate(series):
        if user["id"] == serie_id:
            series.pop(index)
            return

    raise HTTPException(status_code=404)
