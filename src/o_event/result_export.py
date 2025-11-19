#!/usr/bin/env python3

from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional
import xml.etree.ElementTree as ET
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Competitor, Run, Card, Stage


# --- DTOs ---
@dataclass
class SplitTimeDTO:
    control_code: str
    time: Optional[int] = None
    status: Optional[str] = None


@dataclass
class ResultDTO:
    bib_number: int
    start_time: datetime
    finish_time: Optional[datetime] = None
    time: Optional[int] = None
    time_behind: Optional[int] = None
    position: Optional[int] = None
    status: str = "DNS"
    split_times: List[SplitTimeDTO] = field(default_factory=list)
    control_card: Optional[str] = None


@dataclass
class PersonResultDTO:
    first_name: str
    last_name: str
    competitor_id: str
    org_name: str
    org_short: str
    result: ResultDTO


@dataclass
class CourseResultDTO:
    name: str
    length: int
    climb: int
    person_results: List[PersonResultDTO] = field(default_factory=list)


@dataclass
class ClassResultDTO:
    name: str
    course: CourseResultDTO


@dataclass
class EventDTO:
    id: str
    name: str
    date: datetime
    start_time: datetime
    officials: List[dict] = field(default_factory=list)
    class_results: List[ClassResultDTO] = field(default_factory=list)


# --- Build DTOs from ORM ---
def build_person_result(competitor, run, card) -> PersonResultDTO:
    if card and card.punches:
        # Sort punches by punch_time
        sorted_punches = sorted(card.punches, key=lambda x: x.punch_time)

        # SplitTimes
        split_times = [
            SplitTimeDTO(control_code=str(p.code), time=(p.punch_time - card.start_time))
            for p in sorted_punches
        ]

        # Start and finish from card
        start_time = datetime.fromtimestamp(card.start_time) if card.start_time else None
        finish_time = datetime.fromtimestamp(card.finish_time) if card.finish_time else None

        # Total time = finish - start (in seconds)
        total_time = finish_time.timestamp() - start_time.timestamp() if start_time and finish_time else None

        control_card = str(card.card_number)
    else:
        split_times = []
        start_time = None
        finish_time = None
        total_time = None
        control_card = None

    result = ResultDTO(
        bib_number=competitor.sid,
        start_time=start_time,
        finish_time=finish_time,
        time=int(total_time) if total_time else None,
        time_behind=0,  # compute later
        position=None,  # compute later
        status=run.status.value,
        split_times=split_times,
        control_card=control_card
    )

    return PersonResultDTO(
        first_name=competitor.first_name,
        last_name=competitor.last_name,
        competitor_id=competitor.reg,
        org_name=competitor.group,
        org_short=competitor.group[:3] if competitor.group else "",
        result=result
    )


def build_class_results(db: Session, stage) -> List[ClassResultDTO]:
    class_results = []
    for course in stage.courses:
        person_results = []
        for run in db.query(Run).join(Competitor).filter(
            Run.day == stage.day,
            Run.competitor_id == Competitor.id
        ):
            card = db.query(Card).filter(Card.run_id == run.id).first()
            pr = build_person_result(run.competitor, run, card)
            person_results.append(pr)

        course_result = CourseResultDTO(
            name=course.name,
            length=course.length,
            climb=course.climb,
            person_results=person_results
        )
        class_results.append(ClassResultDTO(name=course.name, course=course_result))
    return class_results


# --- Serialize DTOs to XML ---
def dto_to_xml(event_dto: EventDTO) -> ET.Element:
    ns = "http://www.orienteering.org/datastandard/3.0"
    ET.register_namespace("", ns)
    root = ET.Element("ResultList", {
        "createTime": datetime.now().isoformat(),
        "creator": "QuickEvent 3.4.13",
        "iofVersion": "3.0",
        "status": "Complete",
        "xmlns": ns
    })

    # Event
    event_el = ET.SubElement(root, "Event")
    ET.SubElement(event_el, "Id", {"type": "ORIS"}).text = event_dto.id
    ET.SubElement(event_el, "Name").text = event_dto.name

    start_time_el = ET.SubElement(event_el, "StartTime")
    ET.SubElement(start_time_el, "Date").text = event_dto.date.date().isoformat()
    ET.SubElement(start_time_el, "Time").text = event_dto.start_time.time().isoformat()

    for official in event_dto.officials:
        off_el = ET.SubElement(event_el, "Official", {"type": official["role"]})
        person_el = ET.SubElement(off_el, "Person")
        name_el = ET.SubElement(person_el, "Name")
        ET.SubElement(name_el, "Family").text = official.get("family", "")
        ET.SubElement(name_el, "Given").text = official.get("given", "")

    # ClassResults
    for cr in event_dto.class_results:
        cr_el = ET.SubElement(root, "ClassResult")
        cls_el = ET.SubElement(cr_el, "Class")
        ET.SubElement(cls_el, "Id").text = "1"
        ET.SubElement(cls_el, "Name").text = cr.name

        course_el = ET.SubElement(cr_el, "Course")
        ET.SubElement(course_el, "Length").text = str(cr.course.length)
        ET.SubElement(course_el, "Climb").text = str(cr.course.climb)

        for pr in cr.course.person_results:
            pr_el = ET.SubElement(cr_el, "PersonResult")
            person_el = ET.SubElement(pr_el, "Person")
            ET.SubElement(person_el, "Id", {"type": "QuickEvent"}).text = pr.competitor_id
            name_el = ET.SubElement(person_el, "Name")
            ET.SubElement(name_el, "Family").text = pr.last_name
            ET.SubElement(name_el, "Given").text = pr.first_name

            org_el = ET.SubElement(pr_el, "Organisation")
            ET.SubElement(org_el, "Name").text = pr.org_name
            ET.SubElement(org_el, "ShortName").text = pr.org_short

            result = pr.result
            res_el = ET.SubElement(pr_el, "Result")
            ET.SubElement(res_el, "BibNumber").text = str(result.bib_number)
            if result.start_time:
                ET.SubElement(res_el, "StartTime").text = result.start_time.isoformat()
            if result.finish_time:
                ET.SubElement(res_el, "FinishTime").text = result.finish_time.isoformat()
            if result.time is not None:
                ET.SubElement(res_el, "Time").text = str(result.time)
            ET.SubElement(res_el, "Status").text = result.status

            for st in result.split_times:
                attrs = {}
                if st.status:
                    attrs["status"] = st.status
                st_el = ET.SubElement(res_el, "SplitTime", attrs)
                ET.SubElement(st_el, "ControlCode").text = st.control_code
                if st.time is not None:
                    ET.SubElement(st_el, "Time").text = str(st.time)

            if result.control_card:
                ET.SubElement(res_el, "ControlCard").text = result.control_card

    return root


def indent(elem, level=0):
    """Recursively add indentation to an ElementTree element."""
    i = "\n" + level * "    "  # 4 spaces per level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


# --- Example usage ---
def export_iof(db: Session, stage_id: int, filename):
    stage = db.query(Stage).filter(Stage.id == stage_id).first()
    if not stage:
        raise ValueError("Stage not found")

    event_dto = EventDTO(
        id="0",
        name="O-Halloween",
        date=datetime.now(),
        start_time=datetime.now(),
        officials=[{"role": "MainReferee", "family": "В.М.", "given": "Білошицький"}],
        class_results=build_class_results(db, stage)
    )

    xml_root = dto_to_xml(event_dto)
    indent(xml_root)
    tree = ET.ElementTree(xml_root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    engine = create_engine("sqlite:///race.db")
    Session = sessionmaker(bind=engine)
    session = Session()
    export_iof(session, stage_id=1, filename="/tmp/1.xml")
