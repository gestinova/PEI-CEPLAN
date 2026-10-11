"""Persistence and password primitives for the authenticated PEI application."""

import base64
import os
from datetime import datetime, timezone

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    generations: Mapped[list["Generation"]] = relationship(back_populates="user")


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generation_request_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    output_name: Mapped[str] = mapped_column(String(255), unique=True)
    municipality: Mapped[str] = mapped_column(String(120))
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    user: Mapped[User] = relationship(back_populates="generations")


def create_database(database_url):
    engine = create_engine(database_url, pool_pre_ping=not database_url.startswith("sqlite"))
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def hash_password(password):
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres.")
    salt = os.urandom(16)
    key = Argon2id(salt=salt, length=32, iterations=3, lanes=4, memory_cost=64 * 1024).derive(
        password.encode("utf-8")
    )
    return "argon2id$v=19$m=65536,t=3,p=4$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(key).decode("ascii"),
    )


def verify_password(password, encoded):
    try:
        _, _, _, salt_text, key_text = encoded.split("$", 4)
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(key_text)
        Argon2id(
            salt=salt, length=len(expected), iterations=3, lanes=4, memory_cost=64 * 1024
        ).verify(password.encode("utf-8"), expected)
        return True
    except (ValueError, InvalidKey):
        return False
