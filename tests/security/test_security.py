from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token

def test_password_hashing():
    password = "secret_password"
    hashed = get_password_hash(password)
    
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_jwt_token_creation_and_decoding():
    data = {"sub": "user_id_123"}
    token = create_access_token(data=data)
    
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user_id_123"