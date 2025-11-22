from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


DB_PATH = "race.db"
ENGINE = create_engine(f"sqlite:///{DB_PATH}", future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)
