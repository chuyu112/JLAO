from fastapi import APIRouter, HTTPException

from app.schemas import LoginRequest, LoginResponse, UserProfile

router = APIRouter()

DEMO_USERS = {
    "operator": {
        "password": "jlao123",
        "profile": UserProfile(id="user-operator", username="operator", display_name="场控小玉", role="场控"),
    },
    "anchor": {
        "password": "jlao123",
        "profile": UserProfile(id="user-anchor", username="anchor", display_name="主播号", role="主播"),
    },
    "admin": {
        "password": "jlao123",
        "profile": UserProfile(id="user-admin", username="admin", display_name="直播负责人", role="管理员"),
    },
}


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    record = DEMO_USERS.get(payload.username)
    if not record or record["password"] != payload.password:
        raise HTTPException(status_code=401, detail="账号或密码不正确")

    profile = record["profile"]
    return LoginResponse(token=f"demo-token-{profile.username}", user=profile)
