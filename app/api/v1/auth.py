from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from app.core.utils import OAuth2PasswordBearerWithCookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token, verify_password
from app.models.user import User
from app.schemas.token import MessageResponse
from app.schemas.user import UserResponse, UserCreate
from app.core.config import settings
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="/auth/token")

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


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user in the system.

    Checks if the email is already registered. Hashes the password and
    creates a new user record in the database, assigning the same ID
    to the 'created_by' field.

    Args:
        user_create: Data for the new user (name, email, password).
        db: Dependency providing the database session.

    Raises:
        HTTPException: 400 Bad Request if the email is already registered.

    Returns:
        The newly created and persisted User object.
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

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=MessageResponse)
def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    Authenticates a user and issues a JWT access token.

    Verifies credentials (email and password) and the user's status (active, not deleted).
    If authentication is successful, it generates an access token with a defined expiration.

    Args:
        response: FastAPI Response object to set cookies
        form_data: Request data (username as email and password).
        db: Dependency providing the database session.

    Raises:
        HTTPException: 401 Unauthorized if credentials are incorrect.
        HTTPException: 403 Forbidden if the user is inactive or deleted.

    Returns:
        A success message. The access token is set as an HTTP-only cookie.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.active:
        raise HTTPException(status_code=403, detail="User is inactive")
    if user.deleted_at is not None:
        raise HTTPException(status_code=403, detail="User is deleted")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )
    
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {"message": "Login successful"}


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    """
    Logs out the user by deleting the access token cookie.
    
    Args:
        response: FastAPI Response object to delete the cookie
        
    Returns:
        A message indicating successful logout
    """
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dependency function to get the authenticated user from the JWT token.
    Supports both Authorization header and HTTP-only cookies.

    Decodes the token, validates the payload, fetches the user ID from the database,
    and returns the corresponding User object. Also checks if user is active and not deleted.

    Args:
        request: FastAPI Request object to access cookies directly
        token: The JWT token extracted from 'Authorization' header or cookie via oauth2_scheme
        db: Dependency providing the database session.

    Raises:
        HTTPException: 401 Unauthorized if the token is invalid, expired, or the user doesn't exist.
        HTTPException: 403 Forbidden if the user is inactive or deleted.

    Returns:
        The User object associated with the token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token or token.lower() in ("undefined", "null"):
        auth_cookie = request.cookies.get("access_token")
        if not auth_cookie:
            raise credentials_exception
        token = auth_cookie[7:] if auth_cookie.startswith("Bearer ") else auth_cookie

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception

    try:
        user_id = UUID(sub)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is deleted"
        )

    return user


@router.get("/me", response_model=UserResponse)
def read_own_profile(current_user: User = Depends(get_current_user)):
    """
    Retrieves the profile information for the currently authenticated user.

    This route uses the get_current_user dependency to ensure that only
    authenticated users can access it.

    Args:
        current_user: User object injected by the get_current_user dependency.

    Returns:
        The UserResponse object with the user's information.
    """
    return current_user