#!/usr/bin/env python

import xml.etree.ElementTree as ET
from copy import deepcopy
import argparse

NS = {"iof": "http://www.orienteering.org/datastandard/3.0"}
ET.register_namespace("", NS["iof"])
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")


def find_controls(tree):
    return tree.findall(".//iof:RaceCourseData/iof:Control", NS)


def find_courses(tree):
    return tree.findall(".//iof:RaceCourseData/iof:Course", NS)


def control_id(ctrl):
    return ctrl.find("iof:Id", NS).text


def merge_controls(tree_a, tree_b, rcdata_a):
    controls_a = find_controls(tree_a)
    controls_b = find_controls(tree_b)

    start_a = [c for c in controls_a if control_id(c) == "S"][0]
    finish_b = [c for c in controls_b if control_id(c) == "F"][0]

    middle_a = [c for c in controls_a
                if control_id(c) not in ("S", "F")]

    middle_b = [c for c in controls_b
                if control_id(c) not in ("S", "F")]

    merged = [start_a] + middle_a + middle_b + [finish_b]

    for old in controls_a:
        rcdata_a.remove(old)

    for c in merged:
        rcdata_a.append(deepcopy(c))


def get_course_name(course):
    return course.find("iof:Name", NS).text


def course_controls(course):
    return course.findall("iof:CourseControl", NS)


def merge_course(one_a, one_b):
    name = get_course_name(one_a)

    controls_a = course_controls(one_a)
    controls_b = course_controls(one_b)

    start_idx_a = 0
    finish_idx_a = next(i for i,c in enumerate(controls_a)
                        if c.get("type") == "Finish")

    start_idx_b = next(i for i,c in enumerate(controls_b)
                       if c.get("type") == "Start")
    finish_idx_b = next(i for i,c in enumerate(controls_b)
                        if c.get("type") == "Finish")

    merged_list = []
    merged_list.extend(controls_a[start_idx_a : finish_idx_a])
    merged_list.extend(controls_b[start_idx_b+1 : finish_idx_b+1])

    new_course = deepcopy(one_a)
    for c in course_controls(new_course):
        new_course.remove(c)
    for c in merged_list:
        new_course.append(deepcopy(c))

    return new_course


def merge_xml(file_a, file_b, out_file):
    tree_a = ET.parse(file_a)
    tree_b = ET.parse(file_b)

    root_a = tree_a.getroot()
    rcdata_a = root_a.find("iof:RaceCourseData", NS)

    merge_controls(tree_a, tree_b, rcdata_a)

    courses_a = find_courses(tree_a)
    courses_b = find_courses(tree_b)

    map_b = {get_course_name(c): c for c in courses_b}

    for old in courses_a:
        rcdata_a.remove(old)

    for ca in courses_a:
        name = get_course_name(ca)
        if name in map_b:
            merged = merge_course(ca, map_b[name])
        else:
            merged = deepcopy(ca)
        rcdata_a.append(merged)

    tree_a.write(out_file, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(
        description="Merge two IOF XML course files: start & early controls from first, "
                    "finish & late controls from second, merging per-class courses."
    )
    parser.add_argument("file_a", help="First XML file (start comes from here)")
    parser.add_argument("file_b", help="Second XML file (finish comes from here)")
    parser.add_argument("output", help="Output merged XML file")

    args = parser.parse_args()

    merge_xml(args.file_a, args.file_b, args.output)
    print(f"Merged into {args.output}")


if __name__ == "__main__":
    main()
