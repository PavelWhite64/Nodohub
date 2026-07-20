import os

SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key-change-me")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://nodohub:devpassword@db:5432/nodohubdb")