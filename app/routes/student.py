from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from ..database import get_db
from ..models import User, Session as SessionModel, Rating, Availability
from ..schemas import SessionCreate, RatingCreate
from ..auth import require_role

router = APIRouter()


@router.get("/assistants")
def get_assistants(
        current_user: User = Depends(require_role(["student"])),
        db: Session = Depends(get_db)
):
    # Get assistants in same subject and learning center
    assistants = db.query(User).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.role == "assistant",
        User.subject_field == current_user.subject_field
    ).all()

    result = []
    for assistant in assistants:
        # Calculate average rating
        avg_rating_query = db.query(
            func.avg((Rating.knowledge + Rating.communication + Rating.patience +
                      Rating.engagement + Rating.problem_solving) / 5.0)
        ).join(SessionModel).filter(SessionModel.assistant_id == assistant.id)

        avg_rating = avg_rating_query.scalar() or 0

        # Get available slots for next 7 days
        available_slots = db.query(Availability).filter(
            Availability.assistant_id == assistant.id,
            Availability.is_available == "available"
        ).limit(10).all()

        slots_list = []
        for slot in available_slots:
            slots_list.append(f"{slot.date} {slot.time_slot}")

        result.append({
            "id": assistant.id,
            "fullname": assistant.fullname,
            "subject": assistant.subject_field,
            "avg_rating": round(avg_rating, 2),
            "photo_url": assistant.photo_url,
            "available_slots": slots_list
        })

    return result


@router.post("/sessions")
def book_session(
        request: SessionCreate,
        current_user: User = Depends(require_role(["student"])),
        db: Session = Depends(get_db)
):
    # Check if assistant exists and is in same learning center
    assistant = db.query(User).filter(
        User.id == request.assistant_id,
        User.learning_center_id == current_user.learning_center_id,
        User.role == "assistant"
    ).first()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Yordamchi topilmadi"
        )

    # Check if subjects match
    if assistant.subject_field != current_user.subject_field:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat o'z yo'nalishingiz bo'yicha yordamchi tanlashingiz mumkin"
        )

    # Check if time slot is available
    date_str = request.datetime.strftime("%Y-%m-%d")
    time_str = request.datetime.strftime("%H:%M")

    availability = db.query(Availability).filter(
        Availability.assistant_id == request.assistant_id,
        Availability.date == date_str,
        Availability.time_slot == time_str,
        Availability.is_available == "available"
    ).first()

    if not availability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu vaqt band yoki mavjud emas"
        )

    # Check if student already has a session at this time
    existing_session = db.query(SessionModel).filter(
        SessionModel.student_id == current_user.id,
        SessionModel.datetime == request.datetime
    ).first()

    if existing_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu vaqtda sizda allaqachon dars bor"
        )

    # Create session
    session = SessionModel(
        student_id=current_user.id,
        assistant_id=request.assistant_id,
        datetime=request.datetime,
        status="booked"
    )

    db.add(session)

    # Mark availability as booked
    availability.is_available = "booked"

    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "success": True,
        "message": "Dars muvaffaqiyatli band qilindi"
    }


@router.get("/sessions")
def get_sessions(
        status: str = Query("upcoming", description="upcoming yoki past"),
        current_user: User = Depends(require_role(["student"])),
        db: Session = Depends(get_db)
):
    now = datetime.now()

    if status == "upcoming":
        sessions = db.query(SessionModel).filter(
            SessionModel.student_id == current_user.id,
            SessionModel.datetime >= now
        ).all()
    else:
        sessions = db.query(SessionModel).filter(
            SessionModel.student_id == current_user.id,
            SessionModel.datetime < now
        ).all()

    result = []
    for session in sessions:
        assistant = db.query(User).filter(User.id == session.assistant_id).first()

        # Check if student has rated this session
        my_rating = db.query(Rating).filter(Rating.session_id == session.id).first()

        result.append({
            "id": session.id,
            "assistant_name": assistant.fullname,
            "assistant_photo": assistant.photo_url,
            "datetime": session.datetime.strftime("%d.%m.%Y %H:%M"),
            "attendance": session.attendance or "kutilmoqda",
            "my_rating": {
                "knowledge": my_rating.knowledge,
                "communication": my_rating.communication,
                "patience": my_rating.patience,
                "engagement": my_rating.engagement,
                "problem_solving": my_rating.problem_solving,
                "comments": my_rating.comments
            } if my_rating else None
        })

    return result


@router.post("/ratings")
def create_rating(
        request: RatingCreate,
        current_user: User = Depends(require_role(["student"])),
        db: Session = Depends(get_db)
):
    # Check if session exists and belongs to student
    session = db.query(SessionModel).filter(
        SessionModel.id == request.session_id,
        SessionModel.student_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dars topilmadi"
        )

    # Check if session is completed
    if session.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat tugallangan darslarni baholash mumkin"
        )

    # Check if already rated
    existing_rating = db.query(Rating).filter(Rating.session_id == request.session_id).first()
    if existing_rating:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu dars allaqachon baholangan"
        )

    # Validate rating values
    ratings = [request.knowledge, request.communication, request.patience,
               request.engagement, request.problem_solving]
    if any(rating < 1 or rating > 5 for rating in ratings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcha baholar 1 dan 5 gacha bo'lishi kerak"
        )

    # Create rating
    rating = Rating(
        session_id=request.session_id,
        knowledge=request.knowledge,
        communication=request.communication,
        patience=request.patience,
        engagement=request.engagement,
        problem_solving=request.problem_solving,
        comments=request.comments
    )

    db.add(rating)
    db.commit()

    return {
        "success": True,
        "message": "Baholash muvaffaqiyatli saqlandi"
    }