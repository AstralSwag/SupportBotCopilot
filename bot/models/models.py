from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    company = Column(String, nullable=False)
    shop = Column(String, nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    tickets = relationship("Ticket", back_populates="user")

class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    plane_ticket_id = Column(String, nullable=True)
    mattermost_post_id = Column(String, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="tickets")
    messages = relationship("Message", back_populates="ticket")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    sender_type = Column(String, nullable=False)  # "user" или "support"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ticket = relationship("Ticket", back_populates="messages")
