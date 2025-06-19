from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from ..database import get_db
from ..models import User, Session as SessionModel, Rating
from ..schemas import UserCreate
from ..auth import require_role, get_password_hash

router = APIRouter()


@router.post("/users")
def create_user(
        request: UserCreate,
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    # Check if phone already exists in this learning center
    existing_user = db.query(User).filter(
        User.phone == request.phone,
        User.learning_center_id == current_user.learning_center_id
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu telefon raqam allaqachon ro'yxatdan o'tgan"
        )

    if request.role not in ["assistant", "student"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat yordamchi yoki talaba hisobi yaratish mumkin"
        )

    user = User(
        fullname=request.fullname,
        phone=request.phone,
        password=get_password_hash(request.password),
        role=request.role,
        learning_center_id=current_user.learning_center_id,
        subject_field=request.subject_field
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "success": True,
        "message": f"{request.role.title()} hisobi muvaffaqiyatli yaratildi"
    }


@router.get("/users")
def get_users(
        role: str = Query(..., description="assistant yoki student"),
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    if role not in ["assistant", "student"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat assistant yoki student roli mumkin"
        )

    users = db.query(User).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.role == role
    ).all()

    result = []
    for user in users:
        result.append({
            "id": user.id,
            "fullname": user.fullname,
            "phone": user.phone,
            "subject_field": user.subject_field,
            "photo_url": user.photo_url,
            "active_status": "faol"
        })

    return result


@router.get("/stats")
def get_stats(
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    # Get assistants with their ratings
    assistants = db.query(User).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.role == "assistant"
    ).all()

    assistant_stats = []
    for assistant in assistants:
        # Get average rating
        avg_rating_query = db.query(
            func.avg((Rating.knowledge + Rating.communication + Rating.patience +
                      Rating.engagement + Rating.problem_solving) / 5.0)
        ).join(SessionModel).filter(SessionModel.assistant_id == assistant.id)

        avg_rating = avg_rating_query.scalar() or 0

        # Get total sessions
        total_sessions = db.query(func.count(SessionModel.id)).filter(
            SessionModel.assistant_id == assistant.id
        ).scalar()

        assistant_stats.append({
            "fullname": assistant.fullname,
            "avg_rating": round(avg_rating, 2),
            "total_sessions": total_sessions,
            "subject": assistant.subject_field,
            "photo_url": assistant.photo_url
        })

    # Popular subjects
    subject_stats = db.query(
        User.subject_field,
        func.count(SessionModel.id).label("booking_count")
    ).join(SessionModel, SessionModel.assistant_id == User.id).filter(
        User.learning_center_id == current_user.learning_center_id
    ).group_by(User.subject_field).all()

    popular_subjects = [{"subject": stat[0], "booking_count": stat[1]} for stat in subject_stats]

    # Peak hours
    peak_hours = db.query(
        extract('hour', SessionModel.datetime).label('hour'),
        func.count(SessionModel.id).label('session_count')
    ).join(User, SessionModel.assistant_id == User.id).filter(
        User.learning_center_id == current_user.learning_center_id
    ).group_by('hour').all()

    peak_hours_list = [{"hour": f"{int(stat[0])}:00", "session_count": stat[1]} for stat in peak_hours]

    # Center totals
    current_month = datetime.now().month
    sessions_this_month = db.query(func.count(SessionModel.id)).join(
        User, SessionModel.assistant_id == User.id
    ).filter(
        User.learning_center_id == current_user.learning_center_id,
        extract('month', SessionModel.datetime) == current_month
    ).scalar()

    active_students = db.query(func.count(User.id)).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.role == "student"
    ).scalar()

    active_assistants = db.query(func.count(User.id)).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.role == "assistant"
    ).scalar()

    return {
        "assistants": assistant_stats,
        "popular_subjects": popular_subjects,
        "peak_hours": peak_hours_list,
        "center_totals": {
            "sessions_this_month": sessions_this_month,
            "active_students": active_students,
            "active_assistants": active_assistants
        }
    }