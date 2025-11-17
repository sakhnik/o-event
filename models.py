
from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, DateTime
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Race(Base):
    __tablename__ = "races"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)

    stages = relationship("Stage", back_populates="race",
                          cascade="all, delete-orphan")


class Stage(Base):
    __tablename__ = "stages"

    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"))
    number = Column(Integer)    # 1,2,3…
    date = Column(String)       # stored as ISO date
    name = Column(String)       # optional (e.g. "Sprint", "Middle")
    iof_file = Column(String)   # original XML filename for traceability

    race = relationship("Race", back_populates="stages")
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
    code = Column(String)       # “31”, “S”, “F”
    type = Column(String)
    stage_id = Column(Integer, ForeignKey("stages.id"))
    modify_time = Column(String)

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
    controls = relationship("CourseControl",
                            order_by="CourseControl.seq",
                            cascade="all, delete-orphan")


class CourseControl(Base):
    __tablename__ = "course_controls"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    seq = Column(Integer)
    type = Column(String)
    control_code = Column(String, ForeignKey("controls.code"))
    leg_length = Column(Integer)

    control = relationship("Control", foreign_keys=[control_code])
