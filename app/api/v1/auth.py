from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security, status
from fastapi.security import APIKeyCookie, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token, verify_password
from app.models.user import User
from app.models.profile import Profile
from app.schemas.token import MessageResponse
from app.schemas.user import UserResponse, UserCreate
from app.core.config import settings
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Auth"])

cookie_scheme = APIKeyCookie(name="access_token", auto_error=False)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
    auto_error=False
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Generates a secure hash for a given password using the bcrypt scheme.

    Args:
        password: The plaintext password to hash.

    Returns:
        The password hash as a string.
    """
    return pwd_context.hash(password)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user in the system and creates a default profile.

    Checks if the email is already registered. Hashes the password and
    creates a new user record in the database, assigning the same ID
    to the 'created_by' field. Additionally, creates a default Profile
    linked to the new user within the same transaction.
    """
    if db.query(User).filter(User.email == user_create.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_id = uuid4()

    user = User(
        id=new_id,
        name=user_create.name,
        email=user_create.email,
        password=get_password_hash(user_create.password),
        active=True,
        created_by=new_id,
    )

    default_profile_name = (user_create.name.split()[0] or "Main").strip()

    profile = Profile(
        user_id=new_id,
        name=default_profile_name,
        avatar=None,
        maturity_rating=None,
        created_by=new_id,
    )

    try:
        db.add_all([user, profile])
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(user)
    return user


@router.post("/token", response_model=MessageResponse)
def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    if not user.active:
        raise HTTPException(status_code=403, detail="User is inactive")
    if user.deleted_at is not None:
        raise HTTPException(status_code=403, detail="User is deleted")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)

    attrs = _cookie_attrs()
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=int(access_token_expires.total_seconds()),
        expires=int(access_token_expires.total_seconds()),
        **attrs
    )
    return {"message": "Login successful"}


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    attrs = _cookie_attrs()
    response.delete_cookie(key="access_token", path=attrs.get("path", "/"), domain=attrs.get("domain"))
    return {"message": "Successfully logged out"}


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    bearer_token: str | None = Security(oauth2_scheme),
    _cookie_present: str | None = Security(cookie_scheme),
):
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token: str | None = None

    if bearer_token and bearer_token.strip().lower() not in ("undefined", "null", ""):
        token = bearer_token.strip()

    if not token:
        cookie_val = request.cookies.get("access_token")
        if not cookie_val:
            raise credentials_exc
        token = cookie_val[7:] if cookie_val.startswith("Bearer ") else cookie_val

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exc

    sub = payload.get("sub")
    if not sub:
        raise credentials_exc

    try:
        user_id = UUID(sub)
    except Exception:
        raise credentials_exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise credentials_exc
    if not user.active:
        raise HTTPException(status_code=403, detail="User is inactive")
    if user.deleted_at is not None:
        raise HTTPException(status_code=403, detail="User is deleted")

    return user


@router.get("/me", response_model=UserResponse)
def read_own_profile(current_user: User = Depends(get_current_user)):
    """
    Retrieves the profile information for the currently authenticated user.

    This route uses the get_current_user dependency to ensure that only
    authenticated users can access it.
    """
    return current_user


def _cookie_attrs():
    is_prod = getattr(settings, "ENV", "dev").lower() in ("prod", "production")
    attrs = {
        "httponly": True,
        "path": "/",
        "samesite": "lax",
        "secure": False,
    }
    if is_prod:
        attrs["samesite"] = "none"
        attrs["secure"] = True
    return attrs


def _hash(password: str) -> str:
    return pwd_context.hash(password)
