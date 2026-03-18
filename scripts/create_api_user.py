import asyncio
import uuid
from app.database import AsyncSessionLocal
from app.models import UserModel
from app.services.auth_service import get_password_hash
from sqlalchemy import select
import sys

async def create_user(phone: str, password: str, api_key: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserModel).where(UserModel.phone == phone))
        user = result.scalar_one_or_none()
        
        if user:
            print(f"User with phone {phone} already exists. Updating API Key.")
            user.api_key = api_key
            await db.commit()
            print(f"API Key updated for user {phone}")
            return

        hashed_pwd = get_password_hash(password)
        user = UserModel(
            id=str(uuid.uuid4()),
            phone=phone,
            password_hash=hashed_pwd,
            role="admin",
            api_key=api_key
        )
        db.add(user)
        await db.commit()
        print(f"User {phone} created with API Key: {api_key}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m scripts.create_api_user <phone> <password> <api_key>")
        sys.exit(1)
    
    phone = sys.argv[1]
    password = sys.argv[2]
    api_key = sys.argv[3]
    asyncio.run(create_user(phone, password, api_key))
