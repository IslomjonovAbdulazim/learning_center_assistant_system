from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models import User, Availability, Session as SessionModel
from ..schemas import AvailabilityCreate
from ..auth import require_role

router = APIRouter()


@router.post("/availability")
def set_availability(
        request: AvailabilityCreate,
        current_user: User = Depends(require_role(["assistant"])),
        db: Session = Depends(get_db)
):
    # Delete existing availability for this date
    db.query(Availability).filter(
        Availability.assistant_id == current_user.id,
        Availability.date == request.date
    ).delete()

    # Add new time slots
    for time_slot in request.time_slots:
        availability = Availability(
            assistant_id=current_user.id,
            date=request.date,
            time_slot=time_slot,
            is_available="available"
        )
        db.add(availability)

    db.commit()

    return {
        "success": True,
        "message": f"{request.date} sanasi uchun jadval muvaffaqiyatli saqlandi"
    }


@router.get("/availability")
def get_availability(
        current_user: User = Depends(require_role(["assistant"])),
        db: Session = Depends(get_db)
):
    availability = db.query(Availability).filter(
        Availability.assistant_id == current_user.id
    ).all()

    # Group by date
    dates = {}
    for slot in availability:
        if slot.date not in dates:
            dates[slot.date] = {"available_slots": [], "booked_slots": []}

        if slot.is_available == "available":
            dates[slot.date]["available_slots"].append(slot.time_slot)
        else:
            dates[slot.date]["booked_slots"].append(slot.time_slot)

    result = []
    for date, slots in dates.items():
        result.append({
            "date": date,
            "available_slots": slots["available_slots"],
            "booked_slots": slots["booked_slots"]
        })

    return result


@router.get("/sessions/{date}/{time}")
def get_sessions_by_time(
        date: str = Path(...),
        time: str = Path(...),
        current_user: User = Depends(require_role(["assistant"])),
        db: Session = Depends(get_db)
):
    # Parse datetime
    try:
        session_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Noto'g'ri sana yoki vaqt formati. Format: YYYY-MM-DD HH:MM"
        )

    sessions = db.query(SessionModel).filter(
        SessionModel.assistant_id == current_user.id,
        SessionModel.datetime == session_datetime
    ).all()

    result = []
    for session in sessions:
        student = db.query(User).filter(User.id == session.student_id).first()
        result.append({
            "student_id": student.id,
            "student_name": student.fullname,
            "student_phone": student.phone,
            "student_photo": student.photo_url,
            "attendance_status": session.attendance or "kutilmoqda"
        })

    return result


@router.put("/sessions/{session_id}/attendance")
def mark_attendance(
        session_id: int,
        attendance_data: dict,
        current_user: User = Depends(require_role(["assistant"])),
        db: Session = Depends(get_db)
):
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.assistant_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dars topilmadi"
        )

    attendance = attendance_data.get("attendance")
    if attendance not in ["present", "absent"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Davomat 'present' yoki 'absent' bo'lishi kerak"
        )

    session.attendance = attendance
    session.status = "completed"
    db.commit()

    return {
        "success": True,
        "message": "Davomat muvaffaqiyatli belgilandi"
    }


@router.get("/sessions")
def get_sessions(
        status: str = Query("upcoming", description="upcoming yoki past"),
        current_user: User = Depends(require_role(["assistant"])),
        db: Session = Depends(get_db)
):
    now = datetime.now()

    if status == "upcoming":
        sessions = db.query(SessionModel).filter(
            SessionModel.assistant_id == current_user.id,
            SessionModel.datetime >= now
        ).all()
    else:
        sessions = db.query(SessionModel).filter(
            SessionModel.assistant_id == current_user.id,
            SessionModel.datetime < now
        ).all()

    result = []
    for session in sessions:
        student = db.query(User).filter(User.id == session.student_id).first()
        result.append({
            "id": session.id,
            "date": session.datetime.strftime("%Y-%m-%d"),
            "time": session.datetime.strftime("%H:%M"),
            "students": [{
                "name": student.fullname,
                "phone": student.phone,
                "photo": student.photo_url,
                "attendance": session.attendance or "kutilmoqda"
            }]
        })

    return result