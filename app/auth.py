import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
RESET_OTP_MINUTES = int(os.getenv("RESET_OTP_MINUTES", "10"))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


def create_token(payload: dict):
    data = payload.copy()
    data["exp"] = datetime.utcnow() + timedelta(days=7)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _generate_otp() -> str:
    return str(random.randint(100000, 999999))


def _send_reset_otp_email(to_email: str, otp: str) -> None:
    """
    Sends OTP using SMTP env vars. If SMTP is not configured, the OTP is printed
    in Railway logs so local/dev testing does not fail.

    Railway env vars needed for real email:
      SMTP_HOST=smtp.gmail.com
      SMTP_PORT=587
      SMTP_USER=your-email@gmail.com
      SMTP_PASSWORD=your-app-password
      SMTP_FROM=your-email@gmail.com
      SMTP_FROM_NAME=Agentic Bot
    """
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user).strip()
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "Agentic Bot").strip()

    subject = "Your password reset OTP"
    body = f"""Hello,

Your password reset OTP is: {otp}

This OTP will expire in {RESET_OTP_MINUTES} minutes.

If you did not request this, you can ignore this email.
"""

    if not smtp_host or not smtp_user or not smtp_password or not smtp_from:
        print("[PASSWORD RESET OTP] SMTP is not configured. Email:", to_email, "OTP:", otp)
        return

    message = MIMEMultipart()
    message["From"] = f"{smtp_from_name} <{smtp_from}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, [to_email], message.as_string())


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
                LIMIT 1
                """,
                (req.email.strip().lower(),),
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

            if not bcrypt.checkpw(req.password.encode("utf-8"), user["password_hash"].encode("utf-8")):
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


@router.post("/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    email = req.email.strip().lower()
    otp = _generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=RESET_OTP_MINUTES)

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tu.id, tu.email
                FROM tenant_users tu
                JOIN tenants t ON tu.tenant_id = t.id
                WHERE tu.email=%s
                  AND tu.status='active'
                  AND t.status='active'
                LIMIT 1
                """,
                (email,),
            )
            user = cur.fetchone()

            if not user:
                raise HTTPException(status_code=404, detail="This email is not registered with any active tenant.")

            cur.execute(
                """
                UPDATE tenant_users
                SET reset_otp=%s,
                    reset_otp_expiry=%s,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (otp, expiry.strftime("%Y-%m-%d %H:%M:%S"), user["id"]),
            )
    finally:
        conn.close()

    try:
        _send_reset_otp_email(email, otp)
    except Exception as exc:
        print("[PASSWORD RESET EMAIL ERROR]", repr(exc))
        raise HTTPException(status_code=500, detail="OTP created but email could not be sent. Check SMTP settings.")

    return {
        "success": True,
        "message": "OTP sent to your registered email.",
        "email": email,
    }


@router.post("/auth/reset-password")
def reset_password(req: ResetPasswordRequest):
    email = req.email.strip().lower()
    otp = (req.otp or "").strip()
    new_password = req.new_password or ""

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    if not otp:
        raise HTTPException(status_code=400, detail="OTP is required.")

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, reset_otp, reset_otp_expiry
                FROM tenant_users
                WHERE email=%s
                  AND status='active'
                LIMIT 1
                """,
                (email,),
            )
            user = cur.fetchone()

            if not user:
                raise HTTPException(status_code=404, detail="This email is not registered.")

            if not user.get("reset_otp") or str(user.get("reset_otp")) != otp:
                raise HTTPException(status_code=400, detail="Invalid OTP.")

            expiry = user.get("reset_otp_expiry")
            if not expiry:
                raise HTTPException(status_code=400, detail="OTP expired. Please request a new OTP.")

            if isinstance(expiry, str):
                expiry_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            else:
                expiry_dt = expiry

            if expiry_dt < datetime.utcnow():
                cur.execute(
                    """
                    UPDATE tenant_users
                    SET reset_otp=NULL,
                        reset_otp_expiry=NULL,
                        updated_at=NOW()
                    WHERE id=%s
                    """,
                    (user["id"],),
                )
                raise HTTPException(status_code=400, detail="OTP expired. Please request a new OTP.")

            password_hash = _hash_password(new_password)

            cur.execute(
                """
                UPDATE tenant_users
                SET password_hash=%s,
                    reset_otp=NULL,
                    reset_otp_expiry=NULL,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (password_hash, user["id"]),
            )
    finally:
        conn.close()

    return {
        "success": True,
        "message": "Password reset successfully. Please sign in with your new password.",
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
