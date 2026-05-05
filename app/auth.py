# import os
# from datetime import datetime, timedelta

# import bcrypt
# import jwt
# from fastapi import APIRouter, HTTPException, Depends
# from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
# from pydantic import BaseModel, EmailStr

# from app.db import get_main_db_connection

# router = APIRouter()
# security = HTTPBearer()

# JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret")
# JWT_ALGORITHM = "HS256"


# class LoginRequest(BaseModel):
#     tenant_slug: str
#     email: EmailStr
#     password: str


# def create_token(payload: dict):
#     data = payload.copy()
#     data["exp"] = datetime.utcnow() + timedelta(days=7)
#     return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


# def get_tenant_by_slug(slug: str):
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 "SELECT * FROM tenants WHERE slug=%s AND status='active'",
#                 (slug,),
#             )
#             return cur.fetchone()
#     finally:
#         conn.close()


# @router.post("/auth/login")
# def login(req: LoginRequest):
#     tenant = get_tenant_by_slug(req.tenant_slug)

#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found")

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT * FROM tenant_users
#                 WHERE tenant_id=%s AND email=%s AND status='active'
#                 """,
#                 (tenant["id"], req.email),
#             )
#             user = cur.fetchone()

#             if not user:
#                 raise HTTPException(
#                     status_code=401,
#                     detail="This email is not allowed for this tenant.",
#                 )

#             if not user.get("password_hash"):
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Password is not created for this user. Please contact admin.",
#                 )

#             if not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
#                 raise HTTPException(status_code=401, detail="Invalid email or password")

#             cur.execute(
#                 "UPDATE tenant_users SET last_login_at=NOW() WHERE id=%s",
#                 (user["id"],),
#             )
#         print("Tenant:", tenant)
#         print("User:", user)
#     finally:
#         conn.close()

#     token = create_token({
#         "user_id": user["id"],
#         "tenant_id": tenant["id"],
#         "tenant_slug": tenant["slug"],
#         "email": user["email"],
#         "role": user["role"],
#     })

#     return {
#         "success": True,
#         "token": token,
#         "tenant": {
#             "id": tenant["id"],
#             "slug": tenant["slug"],
#             "tenant_name": tenant["tenant_name"],
#         },
#         "user": {
#             "id": user["id"],
#             "name": user["name"],
#             "email": user["email"],
#             "role": user["role"],
#         },
#     }


# def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
#     try:
#         token = credentials.credentials
#         payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
#         return payload
#     except Exception:
#         raise HTTPException(status_code=401, detail="Invalid or expired token")


# @router.get("/auth/me")
# def me(current_user: dict = Depends(get_current_user)):
#     return {
#         "success": True,
#         "user": current_user,
#     } 

import os
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.db import get_main_db_connection

router = APIRouter()
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret")
JWT_ALGORITHM = "HS256"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def create_token(payload: dict):
    data = payload.copy()
    data["exp"] = datetime.utcnow() + timedelta(days=7)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/auth/login")
def login(req: LoginRequest):
    conn = get_main_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    tu.id,
                    tu.tenant_id,
                    tu.name,
                    tu.email,
                    tu.password_hash,
                    tu.role,
                    tu.status,
                    t.slug,
                    t.tenant_name
                FROM tenant_users tu
                JOIN tenants t ON tu.tenant_id = t.id
                WHERE tu.email=%s
                  AND tu.status='active'
                  AND t.status='active'
                """,
                (req.email,),
            )

            user = cur.fetchone()

            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="This email is not registered with any active tenant.",
                )

            if not user.get("password_hash"):
                raise HTTPException(
                    status_code=401,
                    detail="Password is not created for this user. Please contact admin.",
                )

            if not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid email or password",
                )

            cur.execute(
                "UPDATE tenant_users SET last_login_at=NOW() WHERE id=%s",
                (user["id"],),
            )

    finally:
        conn.close()

    token = create_token(
        {
            "user_id": user["id"],
            "tenant_id": user["tenant_id"],
            "tenant_slug": user["slug"],
            "email": user["email"],
            "role": user.get("role") or "member",
        }
    )

    return {
        "success": True,
        "token": token,
        "tenant": {
            "id": user["tenant_id"],
            "slug": user["slug"],
            "tenant_name": user["tenant_name"],
        },
        "user": {
            "id": user["id"],
            "name": user.get("name"),
            "email": user["email"],
            "role": user.get("role") or "member",
        },
    }


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "user": current_user,
    }