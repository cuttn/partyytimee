from sqlmodel import Field, SQLModel, create_engine
from pydantic import EmailStr, BaseModel
from datetime import datetime
from typing import List, Optional
import json

class User(SQLModel, table=True):
    id : int | None = Field(default=None, primary_key=True)
    username : str
    display_name : str
    email : EmailStr | None
    pfpURL : str | None
    firebase_uid: str | None = Field(default=None, index=True, unique=True, description="Firebase UID")
    email_verified: bool = Field(default=False, description="Is the email verified?")
    phone: str | None = Field(default=None, description="User's phone number")
    custom_claims: str | None = Field(default=None, description="Custom claims as JSON string")
    first_name: str
    last_name: str
    isHost: bool | None = Field(default=False)
    bio: str | None = Field(default=None, description="User's bio")
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(datetime.UTC))
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(datetime.UTC))

class Party(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(description="Party name")
    description: str | None = Field(default=None, description="Party description")
    
    # Host relationship
    host_id: int = Field(foreign_key="user.id", description="Host user ID")
    
    # Attendees as JSON list of user IDs (lighter than full User objects)
    attendee_ids: str = Field(default="[]", description="JSON array of user IDs")
    
    # Location with PostGIS support
    latitude: float | None = Field(default=None, description="Latitude")
    longitude: float | None = Field(default=None, description="Longitude")
    address: str | None = Field(default=None, description="Human readable address")
    
    # Party details
    start_time: datetime | None = Field(default=None, description="Party start time")
    end_time: datetime | None = Field(default=None, description="Party end time")
    max_attendees: int | None = Field(default=None, description="Maximum number of attendees")
    hashtags: str | None = Field(default=None, description="Comma-separated hashtags")
    
    # Timestamps
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(datetime.UTC))
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(datetime.UTC))

class newUser(BaseModel):
    email: EmailStr
    username : str
    display_name: str
    first_name: str
    last_name: str
    phone: str = None
    bio: str = None

# Helper functions for Party model
def get_attendee_ids(party: Party) -> List[int]:
    """Get list of attendee user IDs from JSON string"""
    try:
        return json.loads(party.attendee_ids)
    except (json.JSONDecodeError, TypeError):
        return []

def set_attendee_ids(party: Party, attendee_ids: List[int]) -> None:
    """Set attendee user IDs as JSON string"""
    party.attendee_ids = json.dumps(attendee_ids)

def add_attendee(party: Party, user_id: int) -> bool:
    """Add a user to the party attendees"""
    attendee_ids = get_attendee_ids(party)
    if user_id not in attendee_ids:
        attendee_ids.append(user_id)
        set_attendee_ids(party, attendee_ids)
        return True
    return False

def remove_attendee(party: Party, user_id: int) -> bool:
    """Remove a user from the party attendees"""
    attendee_ids = get_attendee_ids(party)
    if user_id in attendee_ids:
        attendee_ids.remove(user_id)
        set_attendee_ids(party, attendee_ids)
        return True
    return False