from firebase_admin import auth
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import User
from sqlmodel import Session, select
security = HTTPBearer()

async def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        # Verify the ID token
        decoded_token = auth.verify_id_token(credentials.credentials)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=401, 
            detail=f"Invalid authentication token: {str(e)}"
        )

async def get_user_by_firebase_uid(db: Session, uid : str):
    statement = select(User).where(User.firebase_uid == uid)
    return db.exec(statement).first()