from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import User, LearningCenter
from ..schemas import LearningCenterCreate, LearningCenterResponse, UserCreate
from ..auth import require_role, get_password_hash

router = APIRouter()


@router.post("/users", response_model=dict)
def create_admin_user(
        request: UserCreate,
        current_user: User = Depends(require_role(["admin"])),
        db: Session = Depends(get_db)
):
    # Check if phone already exists
    existing_user = db.query(User).filter(User.phone == request.phone).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu telefon raqam allaqachon ro'yxatdan o'tgan"
        )

    if request.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat admin yoki menejer yaratish mumkin"
        )

    user = User(
        fullname=request.fullname,
        phone=request.phone,
        password=get_password_hash(request.password),
        role=request.role,
        learning_center_id=request.learning_center_id if request.role == "manager" else None,
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


@router.post("/learning-centers", response_model=dict)
def create_learning_center(
        request: LearningCenterCreate,
        current_user: User = Depends(require_role(["admin"])),
        db: Session = Depends(get_db)
):
    # Check if learning center name already exists
    existing_center = db.query(LearningCenter).filter(LearningCenter.name == request.name).first()
    if existing_center:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu nomdagi o'quv markaz allaqachon mavjud"
        )

    learning_center = LearningCenter(
        name=request.name,
        created_by_admin_id=current_user.id
    )
    db.add(learning_center)
    db.commit()
    db.refresh(learning_center)

    return {
        "center_id": learning_center.id,
        "name": learning_center.name,
        "message": "O'quv markaz muvaffaqiyatli yaratildi"
    }


@router.get("/learning-centers")
def get_learning_centers(
        current_user: User = Depends(require_role(["admin"])),
        db: Session = Depends(get_db)
):
    centers = db.query(LearningCenter).all()
    result = []

    for center in centers:
        total_users = db.query(func.count(User.id)).filter(User.learning_center_id == center.id).scalar()
        result.append({
            "id": center.id,
            "name": center.name,
            "total_users": total_users,
            "created_date": center.created_at.strftime("%d.%m.%Y")
        })

    return result