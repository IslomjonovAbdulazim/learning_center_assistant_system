from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# Auth Schemas
class LoginRequest(BaseModel):
    phone: str
    password: str
    learning_center_id: Optional[int] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    fullname: Optional[str] = None
    subject_field: Optional[str] = None


# User Schemas
class UserCreate(BaseModel):
    fullname: str
    phone: str
    password: str
    role: str
    subject_field: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    fullname: str
    phone: str
    role: str
    subject_field: Optional[str] = None
    photo_url: Optional[str] = None

    class Config:
        from_attributes = True


# Learning Center Schemas
class LearningCenterCreate(BaseModel):
    name: str


class LearningCenterResponse(BaseModel):
    id: int
    name: str
    total_users: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True


# Session Schemas
class SessionCreate(BaseModel):
    assistant_id: int
    datetime: datetime


class SessionResponse(BaseModel):
    id: int
    student_name: Optional[str] = None
    assistant_name: Optional[str] = None
    datetime: datetime
    status: str
    attendance: Optional[str] = None

    class Config:
        from_attributes = True


# Rating Schemas
class RatingCreate(BaseModel):
    session_id: int
    knowledge: int
    communication: int
    patience: int
    engagement: int
    problem_solving: int
    comments: Optional[str] = None


# Availability Schemas
class AvailabilityCreate(BaseModel):
    date: str
    time_slots: List[str]


class AvailabilityResponse(BaseModel):
    date: str
    available_slots: List[str]
    booked_slots: List[str]


# Response Schemas
class SuccessResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None