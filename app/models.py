from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Float, func
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class LearningCenter(Base):
    __tablename__ = "learning_centers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_by_admin_id = Column(Integer, nullable=True)  # Remove FK constraint for now
    created_at = Column(DateTime, default=func.now())

    # Remove the relationship to avoid circular dependency
    # users = relationship("User", back_populates="learning_center")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    fullname = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin, manager, assistant, student
    learning_center_id = Column(Integer, ForeignKey("learning_centers.id"), nullable=True)
    subject_field = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Remove the relationship to avoid circular dependency
    # learning_center = relationship("LearningCenter", back_populates="users")
    assistant_sessions = relationship("Session", foreign_keys="Session.assistant_id", back_populates="assistant")
    student_sessions = relationship("Session", foreign_keys="Session.student_id", back_populates="student")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assistant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    datetime = Column(DateTime, nullable=False)
    status = Column(String, default="booked")  # booked, completed, cancelled
    attendance = Column(String, nullable=True)  # present, absent
    created_at = Column(DateTime, default=func.now())

    student = relationship("User", foreign_keys=[student_id], back_populates="student_sessions")
    assistant = relationship("User", foreign_keys=[assistant_id], back_populates="assistant_sessions")
    rating = relationship("Rating", back_populates="session", uselist=False)


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    knowledge = Column(Integer, nullable=False)  # 1-5
    communication = Column(Integer, nullable=False)  # 1-5
    patience = Column(Integer, nullable=False)  # 1-5
    engagement = Column(Integer, nullable=False)  # 1-5
    problem_solving = Column(Integer, nullable=False)  # 1-5
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    session = relationship("Session", back_populates="rating")


class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)
    assistant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(String, nullable=False)  # YYYY-MM-DD
    time_slot = Column(String, nullable=False)  # HH:MM
    is_available = Column(String, default="available")  # available, booked, busy
    created_at = Column(DateTime, default=func.now())