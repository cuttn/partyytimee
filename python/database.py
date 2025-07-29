from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager

# Create the engine once and share it
engine = create_engine("sqlite:///database.db")

def get_db_session():
    # Create a new session for each call
    return Session(engine)