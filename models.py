from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, Enum, JSON
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class Stage(Base):
    __tablename__ = "stages"

    id = Column(Integer, primary_key=True)
    number = Column(Integer)      # 1, 2, …
    date = Column(String)         # "2025-11-15"
    name = Column(String)         # Optional (e.g. "Sprint")
    iof_file = Column(String)     # Original filename

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

    declared_days = Column(JSON)   # e.g. [1,2]

    runs = relationship("Run", back_populates="competitor")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"))
    day = Column(Integer)

    start = Column(Integer, nullable=True)
    finish = Column(Integer, nullable=True)
    result = Column(Integer, nullable=True)
    status = Column(Enum(Status), default=Status.DNS)

    competitor = relationship("Competitor", back_populates="runs")
