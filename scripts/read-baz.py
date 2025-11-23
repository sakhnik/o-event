#!/usr/bin/env python

import xml.etree.ElementTree as ET
import csv
import re


def get_group(g: str):
    return g


reg = 0
clubs = {'': ''}
regs = {'': ''}

cyrillic = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
latin    = "ABVGHDEEZZYIIIKLMNOPRSTUFHCCSS'UA"
wovels = "AOUIEY'"


def get_reg(club: str) -> str:
    reg = clubs.get(club, None)
    if reg or reg == "":
        return reg

    trans = ''
    for c in club.upper():
        if c in latin or c.isdigit():
            trans += c
            continue
        idx = cyrillic.find(c)
        if idx != -1:
            cl = latin[idx]
            if cl not in wovels:
                trans += latin[idx]
    m = re.search("([0-9]+)", trans)
    if m:
        reg = m.group(0)
    else:
        def next_reg():
            for i in range(2, len(trans)):
                yield trans[:2] + trans[i]
            for i in range(10):
                yield trans[:2] + str(i)

        for reg in next_reg():
            if reg not in regs:
                break

    regs[reg] = club
    clubs[club] = reg
    return reg


def calc_payment(group: str, days: int) -> int:
    g = group.replace(" ", "").upper()

    if any(x in g for x in ["10", "12", "14", "65", "70", "75", "ДІТИ"]):
        base = 200 if days == 2 else 110
    elif any(x in g for x in ["ДОРОСЛІ", "СТУДЕНТИ", "18", "16", "55"]):
        base = 300 if days == 2 else 160
    elif any(x in g for x in ["21", "35", "45"]):
        base = 400 if days == 2 else 210
    else:
        base = 0

    chip_fee = 5 * days
    return base + chip_fee


tree = ET.parse('baz3982.xml')
root = tree.getroot()

#######################################
# 1. Collect all runners first
#######################################
runners = []

sid_counter = 0  # will be reassigned later

for s in root:
    if s.tag == "Sportsman":
        sid_counter += 1  # temporary SID (will be sorted later)

        g = get_group(s.find("Group").text)
        name = s.find("FIO").text.split(" ")[0:2]

        prog_event = s.find("ProgEvent").text
        days = len(prog_event.split(','))
        try:
            qual = s.find("Qualification").text
        except Exception:
            qual = ""
        year = s.find("Birthday").text.split(".")[2]

        try:
            club = s.find("DUSSH").text
        except:
            try:
                club = s.find("Club").text
            except:
                club = ""

        region = s.find("Region").text
        try:
            trainer = s.find("Trener").text
        except:
            trainer = ""

        notes = f"{prog_event}: {year}, {qual}, {club}, {region}, {trainer}"

        runners.append({
            "club": club,
            "reg": None,  # will hold assigned SID
            "group": g,
            "name": name,
            "notes": notes,
            "days": prog_event,
            "money": calc_payment(g, days)
        })

#######################################
# 2. Sort runners by club code
#######################################
runners.sort(key=lambda r: get_reg(r["club"]))

#######################################
# 3. Assign sequential SID after sorting
#######################################
for i, r in enumerate(runners, start=1):
    r["sid"] = i
    r["regcode"] = get_reg(r["club"])


#######################################
# 4. Write CSV
#######################################
with open('runners.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile, delimiter=',',
                        quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Reg", "Group", "SID", "Last name", "First name",
                     "License", "Notes", "Days", "Money"])

    for r in runners:
        last, first = r["name"]
        writer.writerow([
            r["regcode"],
            r["group"],
            r["sid"],
            last,
            first,
            "",
            r["notes"],
            r["days"],
            r["money"]
        ])

#######################################
# 5. Save assigned reg codes for logging
#######################################
with open("clubs.csv", "w") as f:
    for reg_code, club in regs.items():
        f.write(f"{reg_code},{club}\n")
