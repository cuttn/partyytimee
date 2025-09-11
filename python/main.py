import firebase_admin
from firebase_admin import credentials, auth
from fastapi import FastAPI, Depends, HTTPException
from database import engine, SQLModel, get_db_session
from sqlmodel import Session, select, or_, and_
import models
from models import get_attendee_ids, add_attendee, remove_attendee, get_saved_party_ids, add_saved_party, remove_saved_party, Host
import IDVerification
from http import HTTPStatus
from datetime import datetime
from typing import List
from pydantic import BaseModel

SQLModel.metadata.create_all(engine)

me = credentials.Certificate("houseparty-26abf-firebase-adminsdk-fbsvc-529fbe0b54.json")
firebase_admin.initialize_app(me)
app  = FastAPI()

@app.post("/create-custom-token")
async def create_custom_token(user_id: str):
    try:
        custom_token = auth.create_custom_token(user_id)
        return {"custom_token": custom_token.decode('utf-8')}
    except Exception as e:
        return {"error": str(e)}

@app.post("/register")
async def register(userdata : models.newUser, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    with get_db_session() as Sesh:
        existing_user = await IDVerification.get_user_by_firebase_uid(Sesh, token_data['user_id'])
        if existing_user:
            raise HTTPException(status_code=409, detail="User already exists")
        
        # Create new user in database
        new_user = models.User(
            firebase_uid=token_data['user_id'],
            email=userdata.email,
            username=userdata.username,
            phone=userdata.phone,
            bio=userdata.bio,
            isHost=False
        )
        Sesh.add(new_user)
        Sesh.commit()
        
        return {"message": "User registered successfully", "id" : new_user.id}

@app.post("/login")
async def login(token : dict = Depends(IDVerification.verify_firebase_token)):
    with get_db_session() as sesh:
        user = await IDVerification.get_user_by_firebase_uid(sesh, token["user_id"])
        if user:
            return {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "bio": user.bio,
                }
            }
        else:
            raise HTTPException(status_code=404, detail="User not found")

# Party endpoints
class CreatePartyRequest(BaseModel):
    name: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    max_attendees: int | None = None
    hashtags: str | None = None

class PartyFilters(BaseModel):
    hashtags: list[str] | None = None
    location_radius: dict | None = None  # {"lat": 40.7128, "lng": -74.0060, "radius_km": 10}
    date_range: dict | None = None  # {"start": "2024-01-01", "end": "2024-12-31"}
    host_id: int | None = None
    ticketsLeft: int | None = None  # {"min": 5, "max": 50}

@app.post("/parties/create")
async def create_party(party_data: CreatePartyRequest, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    with get_db_session() as sesh:
        # Get the current user
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.isHost:
            raise HTTPException(status_code=403, detail="Only hosts can create parties")
        
        host = sesh.exec(select(Host).where(Host.user_id == user.id)).first()
        # Create new party
        new_party = models.Party(
            name=party_data.name,
            description=party_data.description,
            host_id=host.id,
            latitude=party_data.latitude,
            longitude=party_data.longitude,
            address=party_data.address,
            start_time=party_data.start_time,
            end_time=party_data.end_time,
            max_attendees=party_data.max_attendees,
            hashtags=party_data.hashtags
        )
        
        sesh.add(new_party)
        sesh.commit()
        sesh.refresh(new_party)
        
        return {"message": "Party created successfully", "id": new_party.id}

@app.post("/parties/{party_id}/join")
async def join_party(party_id: int, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    with get_db_session() as sesh:
        # Get the current user
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get the party
        party = sesh.exec(select(models.Party).where(models.Party.id == party_id)).first()
        if not party:
            raise HTTPException(status_code=404, detail="Party not found")
        
        # Check if user is already attending
        attendee_ids = get_attendee_ids(party)
        if user.id in attendee_ids:
            raise HTTPException(status_code=400, detail="Already attending this party")
        
        # Add user to attendees
        if add_attendee(party, user.id):
            sesh.commit()
            return {"message": "Successfully joined party", "id": party_id}
        else:
            raise HTTPException(status_code=400, detail="Failed to join party")

@app.post("/parties/{party_id}/leave")
async def leave_party(party_id: int, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    with get_db_session() as sesh:
        # Get the current user
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get the party
        party = sesh.exec(select(models.Party).where(models.Party.id == party_id)).first()
        if not party:
            raise HTTPException(status_code=404, detail="Party not found")
        
        # Remove user from attendees
        if remove_attendee(party, user.id):
            sesh.commit()
            return {"message": "Successfully left party"}
        else:
            raise HTTPException(status_code=400, detail="Not attending this party")

@app.get("/parties")
async def get_parties(token_data: dict = Depends(IDVerification.verify_firebase_token)):
    with get_db_session() as sesh:
        # Get all parties (you might want to add filtering/pagination)
        parties = sesh.exec(select(models.Party)).all()
        
        party_list = []
        for party in parties:
            # Get host info
            host = sesh.exec(select(models.User).where(models.User.id == party.host_id)).first()
            
            party_data = {
                "id": party.id,
                "name": party.name,
                "description": party.description,
                "host": {
                    "id": host.id,
                    "username": host.username
                } if host else None,
                "attendee_count": len(get_attendee_ids(party)),
                "location": {
                    "latitude": party.latitude,
                    "longitude": party.longitude,
                    "address": party.address
                },
                "start_time": party.start_time,
                "end_time": party.end_time,
                "max_attendees": party.max_attendees,
                "created_at": party.created_at
            }
            party_list.append(party_data)
        
        return {"parties": party_list}

@app.get("/parties/{party_id}")
async def get_party(party_id: int, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    with get_db_session() as sesh:
        party = sesh.exec(select(models.Party).where(models.Party.id == party_id)).first()
        if not party:
            raise HTTPException(status_code=404, detail="Party not found")
        
        # Get host info
        host = sesh.exec(select(models.User).where(models.User.id == party.host_id)).first()
        
        # Get attendee info
        attendee_ids = get_attendee_ids(party)
        attendees = []
        for user_id in attendee_ids:
            user = sesh.exec(select(models.User).where(models.User.id == user_id)).first()
            if user:
                attendees.append({
                    "id": user.id,
                    "username": user.username,
                    "pfpURL": user.pfpURL
                })
        
        return {
            "id": party.id,
            "name": party.name,
            "description": party.description,
            "host": {
                "id": host.id,
                "username": host.username
            } if host else None,
            "attendees": attendees,
            "location": {
                "latitude": party.latitude,
                "longitude": party.longitude,
                "address": party.address
            },
            "start_time": party.start_time,
            "end_time": party.end_time,
            "max_attendees": party.max_attendees,
            "created_at": party.created_at
        }

@app.post("/parties/filter")
async def filter_parties(
    filters: PartyFilters,
    token_data: dict = Depends(IDVerification.verify_firebase_token)
):
    with get_db_session() as sesh:
        query = select(models.Party)
        
        # Hashtag filtering
        if filters.hashtags:
            hashtag_conditions = []
            for hashtag in filters.hashtags:
                # Ensure hashtag starts with #
                if not hashtag.startswith("#"):
                    hashtag = "#" + hashtag
                hashtag_conditions.append(models.Party.hashtags.contains(hashtag))
            if hashtag_conditions:
                query = query.where(or_(*hashtag_conditions))
        
        # Location radius filtering
        if filters.location_radius:
            lat = filters.location_radius.get("lat")
            lng = filters.location_radius.get("lng")
            radius_km = filters.location_radius.get("radius_km", 10)
            
            if lat is not None and lng is not None:
                # Simple distance calculation (you might want to use PostGIS for better performance)
                # This is a rough approximation - for production, use proper spatial queries
                query = query.where(
                    and_(
                        models.Party.latitude.is_not(None),
                        models.Party.longitude.is_not(None)
                    )
                )
        
        # Date range filtering
        if filters.date_range:
            if filters.date_range.get("start"):
                start_date = datetime.fromisoformat(filters.date_range["start"].replace('Z', '+00:00'))
                query = query.where(models.Party.start_time >= start_date)
            if filters.date_range.get("end"):
                end_date = datetime.fromisoformat(filters.date_range["end"].replace('Z', '+00:00'))
                query = query.where(models.Party.start_time <= end_date)
        
        # Host filtering
        if filters.host_id:
            query = query.where(models.Party.host_id == filters.host_id)
        
        # Max attendees filtering
        if filters.ticketsLeft:
            query = query.where(models.Party.max_attendees <= filters.ticketsLeft)
        distances = {}
        parties = sesh.exec(query).all()
        # Post-process location filtering (since SQLite doesn't have spatial functions)
        if filters.location_radius:
            lat = filters.location_radius.get("lat")
            lng = filters.location_radius.get("lng")
            radius_km = filters.location_radius.get("radius_km", 10)
            
            if lat is not None and lng is not None:
                import math
                
                def calculate_distance(lat1, lng1, lat2, lng2):
                    """Calculate distance between two points in km"""
                    R = 6371  # Earth's radius in km
                    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
                    dlat = lat2 - lat1
                    dlng = lng2 - lng1
                    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
                    c = 2 * math.asin(math.sqrt(a))
                    return R * c
                
                # Filter parties within radius
                # parties = [
                #     party for party in parties 
                #     if party.latitude and party.longitude and 
                #     calculate_distance(lat, lng, party.latitude, party.longitude) <= radius_km
                # ]
                closeparties = []
                for party in parties:
                    if party.latitude and party.longitude:
                        distance = calculate_distance(lat, lng, party.latitude, party.longitude)
                        if distance <= radius_km:
                            closeparties.append(party)
                            distances[party.id] = distance
                parties = closeparties
        # Build response
        party_list = []
        for party in parties:
            # Get host info
            party_data = {
                "id": party.id,
                "name": party.name,
                "description": party.description,
                "hashtags": party.hashtags,
                "distance" : distances.get(party.id, 0),
                "attendee_count": len(get_attendee_ids(party)),
                # "location": {
                #     "latitude": party.latitude,
                #     "longitude": party.longitude,
                #     "address": party.address
                # },
                "start_time": party.start_time,
                "end_time": party.end_time,
                "max_attendees": party.max_attendees,
                "created_at": party.created_at
            }
            party_list.append(party_data)
        
        return {"parties": party_list}

@app.post("/parties/{party_id}/end")
async def end_party(party_id: int, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    """End a party abruptly by setting end_time to now"""
    with get_db_session() as sesh:
        # Get the current user
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get the party
        party = sesh.exec(select(models.Party).where(models.Party.id == party_id)).first()
        if not party:
            raise HTTPException(status_code=404, detail="Party not found")
        
        # Check if user is the host
        if party.host_id != user.id:
            raise HTTPException(status_code=403, detail="Only the host can end the party")
        
        # End the party by setting end_time to now
        party.end_time = datetime.now(datetime.UTC)
        sesh.commit()
        
        return {"message": "Party ended successfully"}

@app.post("/parties/{party_id}/cancel")
async def cancel_party(party_id: int, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    """Cancel a party by setting start_time equal to end_time"""
    with get_db_session() as sesh:
        # Get the current user
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get the party
        party = sesh.exec(select(models.Party).where(models.Party.id == party_id)).first()
        if not party:
            raise HTTPException(status_code=404, detail="Party not found")
        
        # Check if user is the host
        if party.host_id != user.id:
            raise HTTPException(status_code=403, detail="Only the host can cancel the party")
        
        # Cancel the party by setting start_time equal to end_time
        party.end_time = party.start_time
        sesh.commit()
        
        return {"message": "Party cancelled successfully"}

# Saved parties endpoints
@app.post("/users/saved-parties/{party_id}")
async def save_party(party_id: int, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    """Save a party to user's saved parties"""
    with get_db_session() as sesh:
        # Get the current user
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get the party
        party = sesh.exec(select(models.Party).where(models.Party.id == party_id)).first()
        if not party:
            raise HTTPException(status_code=404, detail="Party not found")
        
        # Add party to saved parties
        if add_saved_party(user, party_id):
            sesh.commit()
            return {"message": "Party saved successfully"}
        else:
            raise HTTPException(status_code=400, detail="Party already saved")

@app.delete("/users/saved-parties/{party_id}")
async def remove_saved_party_endpoint(party_id: int, token_data: dict = Depends(IDVerification.verify_firebase_token)):
    """Remove a party from user's saved parties"""
    with get_db_session() as sesh:
        # Get the current user
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Remove party from saved parties
        if remove_saved_party(user, party_id):
            sesh.commit()
            return {"message": "Party removed from saved parties"}
        else:
            raise HTTPException(status_code=400, detail="Party not in saved parties")

@app.get("/users/saved-parties")
async def get_saved_parties(token_data: dict = Depends(IDVerification.verify_firebase_token)):
    """Get user's saved parties"""
    with get_db_session() as sesh:
        # Get the current user
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get saved party IDs
        saved_party_ids = get_saved_party_ids(user)
        
        # Get party details
        saved_parties = []
        for party_id in saved_party_ids:
            party = sesh.exec(select(models.Party).where(models.Party.id == party_id)).first()
            if party:
                # Get host info
                host = sesh.exec(select(models.User).where(models.User.id == party.host_id)).first()
                
                party_data = {
                    "id": party.id,
                    "name": party.name,
                    "description": party.description,
                    "host": {
                        "id": host.id,
                        "username": host.username
                    } if host else None,
                    "attendee_count": len(get_attendee_ids(party)),
                    "location": {
                        "latitude": party.latitude,
                        "longitude": party.longitude,
                        "address": party.address
                    },
                    "start_time": party.start_time,
                    "end_time": party.end_time,
                    "max_attendees": party.max_attendees,
                    "created_at": party.created_at
                }
                saved_parties.append(party_data)
        
        return {"saved_parties": saved_parties}
    
@app.post("/users/become-host")
async def become_host(token_data: dict = Depends(IDVerification.verify_firebase_token)):
    """
    Instantly upgrades the current user to a host (for development/testing only).
    TODO: In production, require Stripe onboarding and card verification here!
    """
    with get_db_session() as sesh:
        user = await IDVerification.get_user_by_firebase_uid(sesh, token_data['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.isHost:
            return {"message": "User is already a host"}
        user.isHost = True
        # Create Host record if not exists
        existing_host = sesh.exec(select(Host).where(Host.user_id == user.id)).first()
        if not existing_host:
            new_host = Host(user_id=user.id)
            sesh.add(new_host)
        sesh.commit()
        return {"message": "User upgraded to host (dev only, add Stripe in prod)", "user_id": user.id}
    
