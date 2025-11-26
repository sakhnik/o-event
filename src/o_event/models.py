from datetime import date
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON
)
from sqlalchemy.orm import declarative_base, relationship, object_session
import enum

Base = declarative_base()


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
    type = Column(String, nullable=False)  # "str", "int", "date"

    KEY_NAME = "name"
    KEY_DATE = "date"
    KEY_CURRENT_DAY = "current_day"
    KEY_JUDGE = "judge"
    KEY_SECRETARY = "secretary"
    KEY_PLACE = "place"

    @staticmethod
    def set(db, key, value):
        if isinstance(value, int):
            typ = "int"
            val_str = str(value)
        elif isinstance(value, date):
            typ = "date"
            val_str = value.isoformat()
        else:
            typ = "str"
            val_str = str(value)

        # Check if key exists
        c = db.query(Config).filter_by(key=key).first()
        if c:
            # Update existing
            c.value = val_str
            c.type = typ
        else:
            # Insert new
            c = Config(key=key, value=val_str, type=typ)
            db.add(c)
        db.commit()

    @staticmethod
    def get(db, key, default=None):
        c = db.query(Config).filter_by(key=key).first()
        if not c:
            return default

        if c.type == "int":
            return int(c.value)
        elif c.type == "date":
            return date.fromisoformat(c.value)
        else:
            return c.value

    @staticmethod
    def create(db, name: str, start_date: date, judge: str, secretary: str, place: str):
        Config.set(db, Config.KEY_NAME, name)
        Config.set(db, Config.KEY_DATE, start_date)
        Config.set(db, Config.KEY_JUDGE, judge)
        Config.set(db, Config.KEY_SECRETARY, secretary)
        Config.set(db, Config.KEY_PLACE, place)


class Stage(Base):
    __tablename__ = "stages"

    id = Column(Integer, primary_key=True)
    day = Column(Integer)            # 1-based: stage number
    name = Column(String)         # Optional (e.g. "Sprint")
    date = Column(DateTime, nullable=True)

    map = relationship("MapInfo", uselist=False, back_populates="stage",
                       cascade="all, delete-orphan")
    controls = relationship("Control", back_populates="stage",
                            cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="stage",
                           cascade="all, delete-orphan")


class MapInfo(Base):
    __tablename__ = "maps"

    id = Column(Integer, primary_key=True)
    stage_id = Column(Integer, ForeignKey("stages.id"))
    scale = Column(Integer)
    top_left_x = Column(Float)
    top_left_y = Column(Float)
    bottom_right_x = Column(Float)
    bottom_right_y = Column(Float)

    stage = relationship("Stage", back_populates="map")


class Control(Base):
    __tablename__ = "controls"

    id = Column(Integer, primary_key=True)
    code = Column(String)
    type = Column(String)
    modify_time = Column(String)
    stage_id = Column(Integer, ForeignKey("stages.id"))

    lng = Column(Float)
    lat = Column(Float)
    map_x = Column(Float)
    map_y = Column(Float)

    stage = relationship("Stage", back_populates="controls")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)
    stage_id = Column(Integer, ForeignKey("stages.id"))
    name = Column(String)
    length = Column(Integer)
    climb = Column(Integer)
    modify_time = Column(String)

    stage = relationship("Stage", back_populates="courses")
    controls = relationship(
        "CourseControl",
        order_by="CourseControl.seq",
        cascade="all, delete-orphan"
    )


class CourseControl(Base):
    __tablename__ = "course_controls"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    seq = Column(Integer)
    type = Column(String)
    control_code = Column(String)
    leg_length = Column(Integer)


class Status(enum.Enum):
    OK = "OK"
    DNS = "DNS"
    MP = "MP"
    OVT = "OVT"


class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True)
    reg = Column(String(20))
    group = Column(String(50))
    sid = Column(Integer)
    first_name = Column(String(100))
    last_name = Column(String(100))
    notes = Column(String(500))
    money = Column(Integer)
    #registered = Column(DateTime, nullable=True)

    declared_days = Column(JSON)   # e.g. [1,2]

    runs = relationship("Run", back_populates="competitor")

    @property
    def club_name(self):
        c = object_session(self).get(Club, self.reg)
        return c.name if c else ""


class Club(Base):
    __tablename__ = "clubs"

    reg = Column(String(20), primary_key=True)
    name = Column(String(200), nullable=False)


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"))
    day = Column(Integer)

    start_slot = Column(Integer, nullable=True)
    start = Column(Integer, nullable=True)
    finish = Column(Integer, nullable=True)
    result = Column(Integer, nullable=True)
    status = Column(Enum(Status), default=Status.DNS)

    competitor = relationship("Competitor", back_populates="runs")


class RunSplit(Base):
    __tablename__ = "run_splits"

    id = Column(Integer, primary_key=True)

    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)

    seq = Column(Integer, nullable=False)           # leg/control sequence in course
    control_code = Column(String, nullable=False)  # the control code
    leg_time = Column(Integer, nullable=True)      # time between previous and this control
    cum_time = Column(Integer, nullable=True)      # cumulative from start

    run = relationship("Run", backref="splits")
    course = relationship("Course")


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True)
    card_number = Column(Integer, nullable=False)

    run_id = Column(Integer, ForeignKey("runs.id"), nullable=True)

    start_time = Column(Integer)
    finish_time = Column(Integer)
    check_time = Column(Integer)

    readout_datetime = Column(DateTime)

    raw_json = Column(JSON)
