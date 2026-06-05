from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.services.system_settings import seed_default_settings


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.username == "admin"))
        if existing:
            print("admin user already exists")
            seed_default_settings(db)
            return
        db.add(
            User(
                username="admin",
                password_hash=hash_password("admin123456"),
                name="系统管理员",
                roles=["admin", "hr", "verifier", "auditor"],
            )
        )
        db.commit()
        seed_default_settings(db)
        print("created admin user: admin / admin123456")
    finally:
        db.close()


if __name__ == "__main__":
    main()
