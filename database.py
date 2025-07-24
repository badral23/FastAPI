import os
import logging

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Improved engine configuration for NeonDB
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,                    # Number of connections to maintain
    max_overflow=10,                # Additional connections beyond pool_size
    pool_pre_ping=True,            # Validate connections before use
    pool_recycle=3600,             # Recycle connections every hour
    connect_args={
        "connect_timeout": 30,      # Connection timeout
        "sslmode": "require"        # Ensure SSL connection
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

logger = logging.getLogger(__name__)


def get_db():
    """
    Get database session with proper error handling.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()