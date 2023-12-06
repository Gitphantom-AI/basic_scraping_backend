from fastapi import APIRouter, Depends, HTTPException, Query
from server.database import SessionLocal
from server.models import Users
from typing import Annotated
from sqlalchemy.orm import Session
from server.models import APIKeys
from fastapi.security.api_key import APIKeyHeader
from starlette import status
from datetime import datetime
from dateutil.relativedelta import relativedelta


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

# Validate key
async def validate_key(db: db_dependency, key: str):
    try:
        api_key = db.query(APIKeys).filter(APIKeys.key == key).first()
        if not api_key:
            return {"success": False, "error": "Provided key is invalid."}
        if not api_key.charge > 0:
            return {"success": False, "error": "API key charge is expired. Please renew key."}
        else:
            return {"success": True }
    except:
        return {"error": "Failed to validate key."}


# Consume Key
async def consume_key(db: db_dependency, key: str):
    try:
        response = await validate_key(db, key)
        key_is_valid = response["success"]
        if not key_is_valid:
            return {"error": "Provided key is invalid."}
        
        api_key = db.query(APIKeys).filter(APIKeys.key == key).first()
        if api_key.charge <= 0:
            return {"success": False, "error": "This key is expired, please renew key."}
        
        api_key.charge = api_key.charge - 1
        db.add(api_key)
        db.commit()

        return {"success": True, "charge": api_key.charge}
    except Exception as e:
        print(e)
        return {"success": False, "error": "Failed to use key."}
        


# Save Key
async def save_api_key(db: db_dependency, key: str, charge: int, user: Users):
    try:
        create_api_Key_model = APIKeys(
            key=key,
            owner_id=user.id,
            charge=charge,
            key_renewal_date=datetime.utcnow() + relativedelta(months=+1),
        )
        db.add(create_api_Key_model)
        db.commit()
        return {"success": True, "charge": create_api_Key_model.charge}
    except Exception as e:
        print(e)
        return {"success": False,"error": "Failed to save key."}
# Renew Key


# header dependency
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
async def get_api_key_header(db: db_dependency, api_key: Annotated[str, Depends(api_key_header)]):
    response = await validate_key(db, api_key)
    print(response)
    if not response["success"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=response["error"])
    return api_key
    