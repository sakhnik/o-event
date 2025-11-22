#!/usr/bin/env python3

from o_event.models import Competitor, Run, RunSplit, Stage, Course, Status, Config
from datetime import datetime, time
from dataclasses import dataclass
from typing import List, Optional
import xml.etree.ElementTree as ET
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, selectinload


# --- DTOs ---
@dataclass
class SplitDTO:
    code: int
    time: Optional[int] = None       # None → missing punch
    status: Optional[str] = None     # "Missing" or None


@dataclass
class ResultDTO:
    bib: Optional[int]
    start: datetime
    finish: datetime
    time: int
    timeBehind: int
    position: int
    status: str      # "OK", "MissingPunch", etc.
    splits: List[SplitDTO]
    controlCard: Optional[int]


@dataclass
class PersonDTO:
    ids: dict          # { "CZE": "XYZ", "QuickEvent": "...", ... }
    family: str
    given: str
    clubShort: str
    clubName: str


@dataclass
class PersonResultDTO:
    person: PersonDTO
    result: ResultDTO


@dataclass
class CourseDTO:
    length: int
    climb: int
    controls: List[int]


@dataclass
class ClassResultDTO:
    classId: int
    className: str
    course: CourseDTO
    persons: List[PersonResultDTO]


@dataclass
class EventDTO:
    eventId: str
    name: str
    startDate: str
    startTime: str
    directorFamily: str = ""
    directorGiven: str = ""
    refereeFamily: str = ""
    refereeGiven: str = ""


@dataclass
class ResultListDTO:
    createTime: datetime
    event: EventDTO
    classes: List[ClassResultDTO]


class IOFExporter:

    def seconds_to_time(self, sec: int) -> time:
        return time(sec // 3600, (sec % 3600) // 60, sec % 60)

    def export_iof(self, dto: ResultListDTO) -> str:
        NS = "http://www.orienteering.org/datastandard/3.0"
        ET.register_namespace("", NS)

        root = ET.Element(
            "ResultList",
            {
                "createTime": dto.createTime.isoformat(),
                "creator": "O-Event",
                "iofVersion": "3.0",
                "status": "Complete",
            },
        )

        # ---- Event ----
        ev = ET.SubElement(root, "Event")
        ET.SubElement(ev, "Id", {"type": "O-Event"}).text = dto.event.eventId
        ET.SubElement(ev, "Name").text = dto.event.name

        st = ET.SubElement(ev, "StartTime")
        ET.SubElement(st, "Date").text = dto.event.startDate
        ET.SubElement(st, "Time").text = dto.event.startTime

        # Officials
        def mk_official(type_, fam, giv):
            off = ET.SubElement(ev, "Official", {"type": type_})
            person = ET.SubElement(off, "Person")
            nm = ET.SubElement(person, "Name")
            ET.SubElement(nm, "Family").text = fam
            ET.SubElement(nm, "Given").text = giv

        mk_official("Director", dto.event.directorFamily, dto.event.directorGiven)
        mk_official("MainReferee", dto.event.refereeFamily, dto.event.refereeGiven)

        # ---- Class results ----
        for cls in dto.classes:
            cr = ET.SubElement(root, "ClassResult")

            cl = ET.SubElement(cr, "Class")
            ET.SubElement(cl, "Id").text = str(cls.classId)
            ET.SubElement(cl, "Name").text = cls.className

            course = ET.SubElement(cr, "Course")
            ET.SubElement(course, "Length").text = str(cls.course.length)
            ET.SubElement(course, "Climb").text = str(cls.course.climb)

            # ---- Persons ----
            for pr in cls.persons:
                pr_el = ET.SubElement(cr, "PersonResult")

                # Person
                p = ET.SubElement(pr_el, "Person")
                for id_type, id_value in pr.person.ids.items():
                    ET.SubElement(p, "Id", {"type": id_type}).text = id_value

                name_el = ET.SubElement(p, "Name")
                ET.SubElement(name_el, "Family").text = pr.person.family
                ET.SubElement(name_el, "Given").text = pr.person.given

                org = ET.SubElement(pr_el, "Organisation")
                ET.SubElement(org, "Name").text = pr.person.clubName
                ET.SubElement(org, "ShortName").text = pr.person.clubShort

                # Result
                r = pr.result
                res = ET.SubElement(pr_el, "Result")

                ET.SubElement(res, "StartTime").text = self.seconds_to_time(r.start).isoformat()
                ET.SubElement(res, "FinishTime").text = self.seconds_to_time(r.finish).isoformat()
                ET.SubElement(res, "Time").text = str(r.time)
                if r.status == 'OK':
                    ET.SubElement(res, "TimeBehind").text = str(r.timeBehind)
                if r.position is not None:
                    ET.SubElement(res, "Position").text = str(r.position)
                ET.SubElement(res, "Status").text = r.status

                for sp in r.splits:
                    if sp.time is None:
                        st_el = ET.SubElement(res, "SplitTime", {"status": "Missing"})
                    else:
                        st_el = ET.SubElement(res, "SplitTime")
                    ET.SubElement(st_el, "ControlCode").text = str(sp.code)
                    if sp.time is not None:
                        ET.SubElement(st_el, "Time").text = str(sp.time)

                if r.controlCard is not None:
                    ET.SubElement(res, "ControlCard").text = str(r.controlCard)

        # ---- Pretty print ----
        xml_bytes = ET.tostring(root, encoding="utf-8")
        import xml.dom.minidom
        parsed = xml.dom.minidom.parseString(xml_bytes)
        return parsed.toprettyxml(indent="\t", encoding="utf-8").decode("utf-8")

    def load_result_data(self, db, day: int):
        """
        Load all data for a given stage/day for result export.
        """
        stage = (
            db.query(Stage)
            .options(
                selectinload(Stage.courses).selectinload(Course.controls),
                selectinload(Stage.controls),
            )
            .filter(Stage.day == day)
            .first()
        )
        if not stage:
            return None

        # All competitors that declared this day
        competitors = (
            db.query(Competitor)
            .options(
                selectinload(Competitor.runs)
                .selectinload(Run.splits)
                .selectinload(RunSplit.course),
            )
            .all()
        )

        # Filter competitors who actually have runs on this day
        competitors = [
            c for c in competitors if any(r.day == day and r.result is not None for r in c.runs)
        ]

        return stage, competitors

    def map_event(self, config: dict, stage: Stage) -> EventDTO:
        """
        config = {
            "name": "...",
            "date": date(),
            "judge": "...",
            "secretary": "...",
            "place": "..."
        }
        """
        return EventDTO(
            # name=config["name"],
            eventId=0,
            name=config["name"],
            startDate=stage.date.date().isoformat(),
            startTime=stage.date.time().isoformat(),
            # place=config["place"],
            directorFamily=config["judge"].split()[1:],
            directorGiven=" ".join(config["judge"].split()[0]),
            refereeFamily=config["secretary"].split()[1:],
            refereeGiven=" ".join(config["secretary"].split()[0]),
        )

    def map_split(self, s: RunSplit) -> SplitDTO:
        return SplitDTO(
            code=s.control_code,
            time=s.cum_time,
            status=None if s.leg_time is not None else "Missing",
        )

    def map_person(self, c: Competitor) -> PersonDTO:
        return PersonDTO(
            ids={"O-Event": str(c.id)},
            family=c.last_name,
            given=c.first_name,
            clubShort=c.reg,
            clubName=None,       # add clubs later
        )

    def map_status_string(self, status: Status):
        if status == Status.OK:
            return 'OK'
        if status == Status.MP:
            return 'MissingPunch'
        return status.value

    def map_result(self, run: Run, position: int, time_behind: int) -> ResultDTO:
        return ResultDTO(
            bib=run.competitor.sid,
            start=run.start,
            finish=run.finish,
            time=run.result,
            timeBehind=time_behind,
            position=position,
            status=self.map_status_string(run.status),
            splits=[self.map_split(s) for s in sorted(run.splits, key=lambda x: x.seq) if s.control_code.isdigit()],
            controlCard=run.competitor.sid,
        )

    def map_class(self, group_name: str, course: Course, runs: list[Run]) -> ClassResultDTO:

        # Ranking: OK runners only, sorted by result
        ok_runs = [r for r in runs if r.status == Status.OK]
        ok_runs_sorted = sorted(ok_runs, key=lambda r: r.result)
        dsq_runs = [r for r in runs if r.status != Status.OK]
        dsq_runs_sorted = sorted(dsq_runs, key=lambda r: r.result)

        best_time = ok_runs_sorted[0].result if ok_runs_sorted else None

        persons = []

        for i, run in enumerate(ok_runs_sorted, 1):
            position = i
            time_behind = run.result - best_time

            persons.append(
                PersonResultDTO(
                    person=self.map_person(run.competitor),
                    result=self.map_result(run, position, time_behind),
                )
            )

        for run in dsq_runs_sorted:
            persons.append(
                PersonResultDTO(
                    person=self.map_person(run.competitor),
                    result=self.map_result(run, None, None),
                )
            )

        return ClassResultDTO(
            classId=course.id,
            className=group_name,
            course=CourseDTO(
                length=course.length,
                climb=course.climb,
                controls=[cc.control_code for cc in course.controls],
            ),
            persons=persons,
        )

    def map_result_list(self, db, day: int) -> ResultListDTO:

        stage, competitors = self.load_result_data(db, day)

        # Load Config into a dict
        config = {
            "name": Config.get(db, Config.KEY_NAME),
            "date": Config.get(db, Config.KEY_DATE),
            "judge": Config.get(db, Config.KEY_JUDGE),
            "secretary": Config.get(db, Config.KEY_SECRETARY),
            "place": Config.get(db, Config.KEY_PLACE),
        }

        event = self.map_event(config, stage)

        # Build classes based on group names
        group_to_runs = {}

        for c in competitors:
            for run in c.runs:
                if run.day == day:
                    group_to_runs.setdefault(c.group, []).append(run)

        classes = []

        for group, runs in group_to_runs.items():
            # Find course for this group
            # Your data implies course name == group
            course = next((co for co in stage.courses if co.name == group), None)
            if not course:
                continue  # competitor in group without a course (skip)

            classes.append(self.map_class(group, course, runs))

        return ResultListDTO(
            createTime=datetime.now(),
            event=event,
            classes=classes,
        )


if __name__ == "__main__":
    engine = create_engine("sqlite:///race.db")
    Session = sessionmaker(bind=engine)
    session = Session()
    iof_exporter = IOFExporter()
    result = iof_exporter.map_result_list(session, 1)
    xml = iof_exporter.export_iof(result)
    print(xml)
