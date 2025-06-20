from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
import shutil
import os
from uuid import uuid4

from .database import get_db, SessionLocal, create_tables
from .models import User, LearningCenter
from .schemas import *
from .auth import *
from .routes import admin, manager, assistant, student

app = FastAPI(title="Learning Center API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://education-center-assistant-system-a.vercel.app/",  # Add your deployed frontend URL here
        "https://*.vercel.app",  # Allow all Vercel apps
        "https://*.netlify.app",  # Allow all Netlify apps
        "*"  # Allow all origins (for development only)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory
os.makedirs("uploads/photos", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routes
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(manager.router, prefix="/manager", tags=["manager"])
app.include_router(assistant.router, prefix="/assistant", tags=["assistant"])
app.include_router(student.router, prefix="/student", tags=["student"])


@app.on_event("startup")
def startup_event():
    # Create tables
    create_tables()

    # Create admin if no admin exists
    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.role == "admin").first()
        if not admin_exists:
            admin_user = User(
                fullname="Admin",
                phone="+998990330919",
                password=get_password_hash("aisha"),
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            print("✅ Admin user created: +998990330919 / aisha")
    except Exception as e:
        print(f"Error creating admin: {e}")
    finally:
        db.close()


# Auth endpoints
@app.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, request.phone, request.password, request.learning_center_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telefon raqam yoki parol noto'g'ri"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return {
        "token": access_token,
        "user_info": {
            "id": user.id,
            "fullname": user.fullname,
            "phone": user.phone,
            "role": user.role,
            "subject_field": user.subject_field,
            "photo_url": user.photo_url
        },
        "role": user.role
    }


@app.put("/auth/change-password")
def change_password(request: ChangePasswordRequest, current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(request.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Joriy parol noto'g'ri"
        )

    current_user.password = get_password_hash(request.new_password)
    db.commit()

    return {"success": True, "message": "Parol muvaffaqiyatli o'zgartirildi"}


@app.put("/auth/update-profile")
def update_profile(request: UpdateProfileRequest, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if request.fullname:
        current_user.fullname = request.fullname
    if request.subject_field:
        current_user.subject_field = request.subject_field

    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "message": "Profil muvaffaqiyatli yangilandi",
        "updated_user": {
            "id": current_user.id,
            "fullname": current_user.fullname,
            "subject_field": current_user.subject_field
        }
    }


@app.post("/auth/upload-photo")
def upload_photo(file: UploadFile = File(...), current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat rasm fayllari qabul qilinadi"
        )

    file_extension = file.filename.split(".")[-1]
    filename = f"{uuid4()}.{file_extension}"
    file_path = f"uploads/photos/{filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    photo_url = f"/uploads/photos/{filename}"
    current_user.photo_url = photo_url
    db.commit()

    return {"photo_url": photo_url}


@app.get("/")
def root():
    return {"message": "Learning Center API ishlamoqda!"}


# Debug endpoint to reset database
@app.post("/debug/reset-db")
def reset_database_endpoint():
    from .database import reset_database
    try:
        reset_database()
        startup_event()  # Recreate admin
        return {"message": "Database reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))