import xml.etree.ElementTree as ET
from o_event.models import Stage, MapInfo, Control, Course, CourseControl


class IOFImporter:
    def __init__(self, session):
        self.session = session
        self.ns = {"iof": "http://www.orienteering.org/datastandard/3.0"}

    def import_stage(self, filename, day, stage_name=None):
        tree = ET.parse(filename)
        root = tree.getroot()

        stage = Stage(
            day=day,
            name=stage_name
        )
        self.session.add(stage)

        # Stage date from <Event>/<Name>
        # event_name = root.find("iof:Event/iof:Name", self.ns)
        # if event_name is not None:
        #    stage.date = event_name.text.strip()

        # ----- Map -----
        map_elem = root.find("iof:RaceCourseData/iof:Map", self.ns)
        if map_elem is not None:
            stage.map = MapInfo(
                scale=int(map_elem.find("iof:Scale", self.ns).text),
                top_left_x=float(map_elem.find(
                    "iof:MapPositionTopLeft", self.ns).get("x")),
                top_left_y=float(map_elem.find(
                    "iof:MapPositionTopLeft", self.ns).get("y")),
                bottom_right_x=float(map_elem.find(
                    "iof:MapPositionBottomRight", self.ns).get("x")),
                bottom_right_y=float(map_elem.find(
                    "iof:MapPositionBottomRight", self.ns).get("y")),
            )

        # ----- Controls -----
        for ctrl in root.findall("iof:RaceCourseData/iof:Control", self.ns):
            c = Control(
                code=ctrl.find("iof:Id", self.ns).text.strip(),
                type=ctrl.get("type"),
                modify_time=ctrl.get("modifyTime"),
                stage=stage
            )

            pos = ctrl.find("iof:Position", self.ns)
            if pos is not None:
                c.lng = float(pos.get("lng"))
                c.lat = float(pos.get("lat"))

            mpos = ctrl.find("iof:MapPosition", self.ns)
            if mpos is not None:
                c.map_x = float(mpos.get("x"))
                c.map_y = float(mpos.get("y"))

            stage.controls.append(c)

        # ----- Courses -----
        for course_elem in root.findall("iof:RaceCourseData/iof:Course", self.ns):
            course = Course(
                name=course_elem.find("iof:Name", self.ns).text.strip().replace(' ', ''),
                length=int(course_elem.find("iof:Length", self.ns).text),
                climb=int(course_elem.find("iof:Climb", self.ns).text),
                modify_time=course_elem.get("modifyTime"),
                stage=stage
            )
            self.session.add(course)

            seq = 0
            for cc in course_elem.findall("iof:CourseControl", self.ns):
                control_code = cc.find("iof:Control", self.ns).text.strip()
                leg = cc.find("iof:LegLength", self.ns)
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
