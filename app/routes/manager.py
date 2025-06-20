from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, desc
from datetime import datetime, timedelta
from ..database import get_db
from ..models import User, Session as SessionModel, Rating, Subject, Availability
from ..schemas import UserCreate, ChangePasswordRequest
from ..auth import require_role, get_password_hash

router = APIRouter()


# =============== USERS MANAGEMENT ===============

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
        # Calculate stats based on role
        if role == "assistant":
            # Average rating received
            avg_rating = db.query(
                func.avg((Rating.knowledge + Rating.communication + Rating.patience +
                          Rating.engagement + Rating.problem_solving) / 5.0)
            ).join(SessionModel).filter(SessionModel.assistant_id == user.id).scalar() or 0

            # Total sessions given
            total_sessions = db.query(func.count(SessionModel.id)).filter(
                SessionModel.assistant_id == user.id
            ).scalar()

        else:  # student
            # Average rating given by student
            avg_rating = db.query(
                func.avg((Rating.knowledge + Rating.communication + Rating.patience +
                          Rating.engagement + Rating.problem_solving) / 5.0)
            ).join(SessionModel).filter(SessionModel.student_id == user.id).scalar() or 0

            # Total sessions attended
            total_sessions = db.query(func.count(SessionModel.id)).filter(
                SessionModel.student_id == user.id
            ).scalar()

        result.append({
            "id": user.id,
            "fullname": user.fullname,
            "phone": user.phone,
            "subject_field": user.subject_field,
            "photo_url": user.photo_url,
            "avg_rating": round(avg_rating, 2),
            "total_sessions": total_sessions,
            "created_at": user.created_at.strftime("%d.%m.%Y") if user.created_at else "N/A",
            "active_status": "faol"
        })

    return result


@router.get("/users/{user_id}")
def get_user_detail(
        user_id: int,
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.id == user_id,
        User.learning_center_id == current_user.learning_center_id,
        User.role.in_(["assistant", "student"])
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )

    # Get sessions based on role
    if user.role == "assistant":
        sessions = db.query(SessionModel).filter(SessionModel.assistant_id == user.id).all()
    else:
        sessions = db.query(SessionModel).filter(SessionModel.student_id == user.id).all()

    # Format sessions
    session_list = []
    total_rating = 0
    rating_count = 0

    for session in sessions:
        # Get related user (student if user is assistant, assistant if user is student)
        if user.role == "assistant":
            related_user = db.query(User).filter(User.id == session.student_id).first()
        else:
            related_user = db.query(User).filter(User.id == session.assistant_id).first()

        # Get rating
        rating = db.query(Rating).filter(Rating.session_id == session.id).first()
        session_rating = None
        if rating:
            avg_rating = (rating.knowledge + rating.communication + rating.patience +
                          rating.engagement + rating.problem_solving) / 5.0
            session_rating = round(avg_rating, 2)
            total_rating += avg_rating
            rating_count += 1

        session_list.append({
            "id": session.id,
            "datetime": session.datetime.strftime("%d.%m.%Y %H:%M"),
            "related_user_name": related_user.fullname if related_user else "N/A",
            "attendance": session.attendance or "kutilmoqda",
            "status": session.status,
            "rating": session_rating,
            "rating_details": {
                "knowledge": rating.knowledge,
                "communication": rating.communication,
                "patience": rating.patience,
                "engagement": rating.engagement,
                "problem_solving": rating.problem_solving,
                "comments": rating.comments
            } if rating else None
        })

    # Calculate overall stats
    avg_rating = round(total_rating / rating_count, 2) if rating_count > 0 else 0

    return {
        "id": user.id,
        "fullname": user.fullname,
        "phone": user.phone,
        "role": user.role,
        "subject_field": user.subject_field,
        "photo_url": user.photo_url,
        "created_at": user.created_at.strftime("%d.%m.%Y") if user.created_at else "N/A",
        "avg_rating": avg_rating,
        "total_sessions": len(sessions),
        "completed_sessions": len([s for s in sessions if s.status == "completed"]),
        "sessions": sorted(session_list, key=lambda x: datetime.strptime(x["datetime"], "%d.%m.%Y %H:%M"), reverse=True)
    }


@router.put("/users/{user_id}")
def update_user(
        user_id: int,
        request: dict,
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.id == user_id,
        User.learning_center_id == current_user.learning_center_id,
        User.role.in_(["assistant", "student"])
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )

    # Update allowed fields
    if "fullname" in request:
        user.fullname = request["fullname"]
    if "phone" in request:
        # Check if phone is already taken
        existing = db.query(User).filter(
            User.phone == request["phone"],
            User.id != user_id,
            User.learning_center_id == current_user.learning_center_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu telefon raqam boshqa foydalanuvchi tomonidan ishlatilmoqda"
            )
        user.phone = request["phone"]
    if "subject_field" in request:
        user.subject_field = request["subject_field"]

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": "Foydalanuvchi ma'lumotlari muvaffaqiyatli yangilandi"
    }


@router.delete("/users/{user_id}")
def delete_user(
        user_id: int,
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.id == user_id,
        User.learning_center_id == current_user.learning_center_id,
        User.role.in_(["assistant", "student"])
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )

    # Check if user has sessions
    session_count = db.query(func.count(SessionModel.id)).filter(
        (SessionModel.assistant_id == user_id) | (SessionModel.student_id == user_id)
    ).scalar()

    if session_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu foydalanuvchining darslari mavjud. Avval darslarni tugatish kerak."
        )

    db.delete(user)
    db.commit()

    return {
        "success": True,
        "message": f"{user.role.title()} hisobi muvaffaqiyatli o'chirildi"
    }


@router.put("/users/{user_id}/change-password")
def change_user_password(
        user_id: int,
        request: dict,
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.id == user_id,
        User.learning_center_id == current_user.learning_center_id,
        User.role.in_(["assistant", "student"])
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )

    if "new_password" not in request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yangi parol talab qilinadi"
        )

    user.password = get_password_hash(request["new_password"])
    db.commit()

    return {
        "success": True,
        "message": "Parol muvaffaqiyatli o'zgartirildi"
    }


# =============== SUBJECTS MANAGEMENT ===============

@router.post("/subjects")
def create_subject(
        request: dict,
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    if "name" not in request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fan nomi talab qilinadi"
        )

    # Check if subject already exists in this center
    existing = db.query(Subject).filter(
        Subject.name == request["name"],
        Subject.learning_center_id == current_user.learning_center_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu fan allaqachon mavjud"
        )

    subject = Subject(
        name=request["name"],
        learning_center_id=current_user.learning_center_id
    )

    db.add(subject)
    db.commit()
    db.refresh(subject)

    return {
        "subject_id": subject.id,
        "success": True,
        "message": "Fan muvaffaqiyatli qo'shildi"
    }


@router.get("/subjects")
def get_subjects(
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    subjects = db.query(Subject).filter(
        Subject.learning_center_id == current_user.learning_center_id
    ).all()

    result = []
    for subject in subjects:
        # Count assistants and students for this subject
        assistant_count = db.query(func.count(User.id)).filter(
            User.learning_center_id == current_user.learning_center_id,
            User.role == "assistant",
            User.subject_field == subject.name
        ).scalar()

        student_count = db.query(func.count(User.id)).filter(
            User.learning_center_id == current_user.learning_center_id,
            User.role == "student",
            User.subject_field == subject.name
        ).scalar()

        result.append({
            "id": subject.id,
            "name": subject.name,
            "assistant_count": assistant_count,
            "student_count": student_count,
            "created_at": subject.created_at.strftime("%d.%m.%Y") if subject.created_at else "N/A"
        })

    return result


@router.put("/subjects/{subject_id}")
def update_subject(
        subject_id: int,
        request: dict,
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.learning_center_id == current_user.learning_center_id
    ).first()

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fan topilmadi"
        )

    if "name" in request:
        # Check if new name already exists
        existing = db.query(Subject).filter(
            Subject.name == request["name"],
            Subject.learning_center_id == current_user.learning_center_id,
            Subject.id != subject_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu fan nomi allaqachon mavjud"
            )

        old_name = subject.name
        subject.name = request["name"]

        # Update all users with this subject
        db.query(User).filter(
            User.learning_center_id == current_user.learning_center_id,
            User.subject_field == old_name
        ).update({"subject_field": request["name"]})

    db.commit()
    db.refresh(subject)

    return {
        "success": True,
        "message": "Fan muvaffaqiyatli yangilandi"
    }


@router.delete("/subjects/{subject_id}")
def delete_subject(
        subject_id: int,
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.learning_center_id == current_user.learning_center_id
    ).first()

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fan topilmadi"
        )

    # Check if any users are assigned to this subject
    user_count = db.query(func.count(User.id)).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.subject_field == subject.name
    ).scalar()

    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu fanga tayinlangan foydalanuvchilar mavjud. Avval ularni boshqa fanga o'tkazing."
        )

    db.delete(subject)
    db.commit()

    return {
        "success": True,
        "message": "Fan muvaffaqiyatli o'chirildi"
    }


# =============== ENHANCED STATS ===============

@router.get("/stats")
def get_stats(
        current_user: User = Depends(require_role(["manager"])),
        db: Session = Depends(get_db)
):
    # Basic counts
    total_assistants = db.query(func.count(User.id)).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.role == "assistant"
    ).scalar()

    total_students = db.query(func.count(User.id)).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.role == "student"
    ).scalar()

    total_subjects = db.query(func.count(Subject.id)).filter(
        Subject.learning_center_id == current_user.learning_center_id
    ).scalar()

    # Session stats
    current_month = datetime.now().month
    current_year = datetime.now().year

    sessions_this_month = db.query(func.count(SessionModel.id)).join(
        User, SessionModel.assistant_id == User.id
    ).filter(
        User.learning_center_id == current_user.learning_center_id,
        extract('month', SessionModel.datetime) == current_month,
        extract('year', SessionModel.datetime) == current_year
    ).scalar()

    total_sessions = db.query(func.count(SessionModel.id)).join(
        User, SessionModel.assistant_id == User.id
    ).filter(
        User.learning_center_id == current_user.learning_center_id
    ).scalar()

    # Average rating across all sessions
    avg_rating = db.query(
        func.avg((Rating.knowledge + Rating.communication + Rating.patience +
                  Rating.engagement + Rating.problem_solving) / 5.0)
    ).join(SessionModel).join(User, SessionModel.assistant_id == User.id).filter(
        User.learning_center_id == current_user.learning_center_id
    ).scalar() or 0

    # Monthly session trends (last 6 months)
    monthly_trends = []
    for i in range(6):
        target_date = datetime.now() - timedelta(days=30 * i)
        month_sessions = db.query(func.count(SessionModel.id)).join(
            User, SessionModel.assistant_id == User.id
        ).filter(
            User.learning_center_id == current_user.learning_center_id,
            extract('month', SessionModel.datetime) == target_date.month,
            extract('year', SessionModel.datetime) == target_date.year
        ).scalar()

        monthly_trends.append({
            "month": target_date.strftime("%B"),
            "sessions": month_sessions
        })

    # Subject popularity
    subject_stats = db.query(
        User.subject_field,
        func.count(SessionModel.id).label("session_count")
    ).join(SessionModel, SessionModel.assistant_id == User.id).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.subject_field.isnot(None)
    ).group_by(User.subject_field).all()

    subject_popularity = [
        {"subject": stat[0], "sessions": stat[1]}
        for stat in subject_stats
    ]

    # Top assistants by rating
    top_assistants = db.query(
        User.fullname,
        func.avg((Rating.knowledge + Rating.communication + Rating.patience +
                  Rating.engagement + Rating.problem_solving) / 5.0).label("avg_rating"),
        func.count(SessionModel.id).label("session_count")
    ).join(SessionModel, SessionModel.assistant_id == User.id).join(
        Rating, Rating.session_id == SessionModel.id
    ).filter(
        User.learning_center_id == current_user.learning_center_id,
        User.role == "assistant"
    ).group_by(User.id).having(func.count(SessionModel.id) >= 3).order_by(
        desc("avg_rating")
    ).limit(5).all()

    top_assistants_list = [
        {
            "name": assistant[0],
            "rating": round(assistant[1], 2),
            "sessions": assistant[2]
        }
        for assistant in top_assistants
    ]

    # Peak hours analysis
    peak_hours = db.query(
        extract('hour', SessionModel.datetime).label('hour'),
        func.count(SessionModel.id).label('session_count')
    ).join(User, SessionModel.assistant_id == User.id).filter(
        User.learning_center_id == current_user.learning_center_id
    ).group_by('hour').order_by('hour').all()

    peak_hours_list = [
        {"hour": f"{int(stat[0])}:00", "sessions": stat[1]}
        for stat in peak_hours
    ]

    # Attendance rate
    completed_sessions = db.query(func.count(SessionModel.id)).join(
        User, SessionModel.assistant_id == User.id
    ).filter(
        User.learning_center_id == current_user.learning_center_id,
        SessionModel.attendance == "present"
    ).scalar()

    attendance_rate = round((completed_sessions / total_sessions * 100), 2) if total_sessions > 0 else 0

    return {
        "overview": {
            "total_assistants": total_assistants,
            "total_students": total_students,
            "total_subjects": total_subjects,
            "sessions_this_month": sessions_this_month,
            "total_sessions": total_sessions,
            "avg_rating": round(avg_rating, 2),
            "attendance_rate": attendance_rate
        },
        "monthly_trends": list(reversed(monthly_trends)),
        "subject_popularity": subject_popularity,
        "top_assistants": top_assistants_list,
        "peak_hours": peak_hours_list
    }