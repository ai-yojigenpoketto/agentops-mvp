from sqlmodel import create_engine, Session, SQLModel
from app.core.settings import settings

# Create engine
engine = create_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
)


def init_db() -> None:
    """Create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Get a database session."""
    with Session(engine) as session:
        yield session
