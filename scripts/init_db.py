"""Create database tables."""

from app.database import Base, engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database schema ready.")


if __name__ == "__main__":
    main()
