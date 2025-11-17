
import xml.etree.ElementTree as ET
from models import Race, Stage, MapInfo, Control, Course, CourseControl


class IOFImporter:
    def __init__(self, session):
        self.session = session

    def import_stage(self, filename, race_id, stage_number, stage_name=None):
        tree = ET.parse(filename)
        root = tree.getroot()

        ns = {"iof": "http://www.orienteering.org/datastandard/3.0"}

        race = self.session.get(Race, race_id)
        if race is None:
            raise ValueError(f"Race {race_id} does not exist")

        # Create a new Stage
        stage = Stage(
            race=race,
            number=stage_number,
            name=stage_name,
            iof_file=filename
        )
        self.session.add(stage)

        # Extract date from Event/Name
        event_name = root.find("iof:Event/iof:Name", ns)
        if event_name is not None:
            stage.date = event_name.text.strip()

        # Map
        map_elem = root.find("iof:RaceCourseData/iof:Map", ns)
        if map_elem is not None:
            stage.map = MapInfo(
                scale=int(map_elem.find("iof:Scale", ns).text),
                top_left_x=float(map_elem.find("iof:MapPositionTopLeft", ns).get("x")),
                top_left_y=float(map_elem.find("iof:MapPositionTopLeft", ns).get("y")),
                bottom_right_x=float(map_elem.find("iof:MapPositionBottomRight", ns).get("x")),
                bottom_right_y=float(map_elem.find("iof:MapPositionBottomRight", ns).get("y")),
            )

        # Controls
        for ctrl in root.findall("iof:RaceCourseData/iof:Control", ns):
            c = Control(
                code=ctrl.find("iof:Id", ns).text.strip(),
                type=ctrl.get("type"),
                modify_time=ctrl.get("modifyTime"),
                stage=stage
            )

            pos = ctrl.find("iof:Position", ns)
            if pos is not None:
                c.lng = float(pos.get("lng"))
                c.lat = float(pos.get("lat"))

            mpos = ctrl.find("iof:MapPosition", ns)
            if mpos is not None:
                c.map_x = float(mpos.get("x"))
                c.map_y = float(mpos.get("y"))

            stage.controls.append(c)

        # Courses
        for course_elem in root.findall("iof:RaceCourseData/iof:Course", ns):
            course = Course(
                name=course_elem.find("iof:Name", ns).text.strip(),
                length=int(course_elem.find("iof:Length", ns).text),
                climb=int(course_elem.find("iof:Climb", ns).text),
                modify_time=course_elem.get("modifyTime"),
                stage=stage
            )
            self.session.add(course)

            # Sequence course controls
            seq = 0
            for cc in course_elem.findall("iof:CourseControl", ns):
                control_code = cc.find("iof:Control", ns).text.strip()
                leg = cc.find("iof:LegLength", ns)
                leg_length = int(leg.text) if leg is not None else None

                course.controls.append(
                    CourseControl(
                        seq=seq,
                        type=cc.get("type"),
                        control_code=control_code,
                        leg_length=leg_length,
                    )
                )
                seq += 1

        self.session.commit()
        return stage
