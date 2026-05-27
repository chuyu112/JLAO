import os

from fastapi import APIRouter, HTTPException

from app.auth_utils import create_access_token, verify_password
from app.schemas import LoginRequest, LoginResponse, UserProfile

router = APIRouter()

# 预哈希的默认密码（原 jlao123），生产环境务必通过环境变量覆盖
_DEFAULT_HASH = "$2b$12$p5JL2N7AuSlV5BFozTqzaekqA7ECgfGScZMlO1Tbxa5LxSEuZTjw."

_USERS = {
    "operator": {
        "password_hash": os.getenv("OPERATOR_PASSWORD_HASH", _DEFAULT_HASH),
        "profile": UserProfile(id="user-operator", username="operator", display_name="场控小玉", role="场控"),
    },
    "anchor": {
        "password_hash": os.getenv("ANCHOR_PASSWORD_HASH", _DEFAULT_HASH),
        "profile": UserProfile(id="user-anchor", username="anchor", display_name="主播号", role="主播"),
    },
    "admin": {
        "password_hash": os.getenv("ADMIN_PASSWORD_HASH", _DEFAULT_HASH),
        "profile": UserProfile(id="user-admin", username="admin", display_name="直播负责人", role="管理员"),
    },
}


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    record = _USERS.get(payload.username)
    if not record or not verify_password(payload.password, record["password_hash"]):
        raise HTTPException(status_code=401, detail="账号或密码不正确")

    profile = record["profile"]
    token = create_access_token(data={"sub": profile.username, "role": profile.role})
    return LoginResponse(token=token, user=profile)
