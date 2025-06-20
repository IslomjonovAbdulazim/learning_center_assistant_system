from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import User, LearningCenter
from ..schemas import LearningCenterCreate, UserCreate
from ..auth import require_role, get_password_hash

router = APIRouter()


@router.post("/users", response_model=dict)
def create_manager(
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

    if request.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat menejer yaratish mumkin"
        )

    # Verify learning center exists
    if not request.learning_center_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Menejer uchun o'quv markaz ID kerak"
        )

    center = db.query(LearningCenter).filter(LearningCenter.id == request.learning_center_id).first()
    if not center:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O'quv markaz topilmadi"
        )

    # Managers don't have subjects - only assistants and students do
    user = User(
        fullname=request.fullname,
        phone=request.phone,
        password=get_password_hash(request.password),
        role=request.role,
        learning_center_id=request.learning_center_id,
        subject_id=None  # Managers don't have subjects
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "success": True,
        "message": "Menejer muvaffaqiyatli yaratildi"
    }


@router.get("/users")
def get_managers(
        current_user: User = Depends(require_role(["admin"])),
        db: Session = Depends(get_db)
):
    managers = db.query(User).filter(User.role == "manager").all()

    result = []
    for manager in managers:
        center = db.query(LearningCenter).filter(LearningCenter.id == manager.learning_center_id).first()
        result.append({
            "id": manager.id,
            "fullname": manager.fullname,
            "phone": manager.phone,
            "learning_center_id": manager.learning_center_id,
            "learning_center_name": center.name if center else "N/A",
            "created_at": manager.created_at
        })

    return result


@router.put("/users/{user_id}")
def update_manager(
        user_id: int,
        request: dict,
        current_user: User = Depends(require_role(["admin"])),
        db: Session = Depends(get_db)
):
    manager = db.query(User).filter(User.id == user_id, User.role == "manager").first()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menejer topilmadi"
        )

    # Update fields
    if "fullname" in request:
        manager.fullname = request["fullname"]
    if "phone" in request:
        manager.phone = request["phone"]
    if "learning_center_id" in request:
        manager.learning_center_id = request["learning_center_id"]

    db.commit()
    db.refresh(manager)

    return {
        "success": True,
        "message": "Menejer muvaffaqiyatli yangilandi"
    }


@router.delete("/users/{user_id}")
def delete_manager(
        user_id: int,
        current_user: User = Depends(require_role(["admin"])),
        db: Session = Depends(get_db)
):
    manager = db.query(User).filter(User.id == user_id, User.role == "manager").first()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menejer topilmadi"
        )

    db.delete(manager)
    db.commit()

    return {
        "success": True,
        "message": "Menejer muvaffaqiyatli o'chirildi"
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
        name=request.name
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
            "created_date": center.created_at.strftime("%d.%m.%Y") if center.created_at else "N/A"
        })

    return result


@router.put("/learning-centers/{center_id}")
def update_learning_center(
        center_id: int,
        request: dict,
        current_user: User = Depends(require_role(["admin"])),
        db: Session = Depends(get_db)
):
    center = db.query(LearningCenter).filter(LearningCenter.id == center_id).first()
    if not center:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O'quv markaz topilmadi"
        )

    if "name" in request:
        center.name = request["name"]

    db.commit()
    db.refresh(center)

    return {
        "success": True,
        "message": "O'quv markaz muvaffaqiyatli yangilandi"
    }


@router.delete("/learning-centers/{center_id}")
def delete_learning_center(
        center_id: int,
        current_user: User = Depends(require_role(["admin"])),
        db: Session = Depends(get_db)
):
    center = db.query(LearningCenter).filter(LearningCenter.id == center_id).first()
    if not center:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O'quv markaz topilmadi"
        )

    # Check if center has users
    users_count = db.query(func.count(User.id)).filter(User.learning_center_id == center_id).scalar()
    if users_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu markazda foydalanuvchilar mavjud. Avval ularni o'chiring."
        )

    db.delete(center)
    db.commit()

    return {
        "success": True,
        "message": "O'quv markaz muvaffaqiyatli o'chirildi"
    }