#!/usr/bin/env python3

import os
import yaml
import tempfile
import subprocess
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from rapidfuzz import fuzz
from sqlalchemy.inspection import inspect

from db import SessionLocal
from models import Competitor, Run, Status, Config

db = SessionLocal()

# Commands
commands = ['ls', 'edit', 'add', 'day', 'quit']
cmd_completer = WordCompleter(commands, ignore_case=True)


def resolve_command(cmd, commands):
    """
    Resolve a possibly abbreviated command to full command.
    If multiple matches exist, return None (ambiguous).
    """
    matches = [c for c in commands if c.startswith(cmd)]
    if len(matches) == 1:
        return matches[0]
    elif cmd in commands:
        return cmd  # exact match
    else:
        return None  # ambiguous or unknown


def get_columns(model):
    return [c.key for c in inspect(model).mapper.column_attrs]


# ---------- Utilities ----------
def competitor_to_dict(c: Competitor):
    comp_dict = {col: getattr(c, col) for col in get_columns(Competitor)}
    comp_dict["runs"] = [
        {col: getattr(r, col) if col != "status" else (r.status.value if r.status else None)
         for col in get_columns(Run)}
        for r in c.runs
    ]
    return comp_dict


def update_competitor_from_dict(d: dict):
    comp_columns = get_columns(Competitor)
    run_columns = get_columns(Run)

    # Create or fetch competitor
    if "id" not in d or d["id"] is None:
        comp = Competitor()
        db.add(comp)
        db.flush()
    else:
        comp = db.get(Competitor, d["id"])
        if comp is None:
            raise ValueError(f"Competitor id {d['id']} not found")

    # Update competitor fields dynamically
    for col in comp_columns:
        if col in d and col != "id":  # don't overwrite primary key
            setattr(comp, col, d[col])

    # Update runs
    existing_by_id = {r.id: r for r in comp.runs if r.id is not None}
    seen_existing_ids = set()

    for rd in d.get("runs", []):
        if "id" in rd and rd["id"] in existing_by_id:
            r = existing_by_id[rd["id"]]
            seen_existing_ids.add(rd["id"])
        else:
            r = Run()
            r.competitor = comp
            db.add(r)

        for col in run_columns:
            if col in rd and col != "id":  # don't overwrite primary key
                setattr(r, col, rd[col])

        # Handle enum status separately
        st = rd.get("status")
        if hasattr(Run, "status"):
            if st is None:
                r.status = None
            else:
                r.status = Status(st) if st in Status._value2member_map_ else None

    # Remove deleted runs
    for r in list(comp.runs):
        if r.id is not None and r.id not in seen_existing_ids:
            db.delete(r)

    db.flush()
    return comp


def edit_competitor_in_editor(comp_dict: dict):
    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".yaml", delete=False) as tf:
        path = tf.name
        yaml.safe_dump(comp_dict, tf, sort_keys=False, allow_unicode=True)
        tf.flush()
    try:
        # Save original text
        original_text = yaml.safe_dump(comp_dict, sort_keys=False, allow_unicode=True)

        # Launch editor
        subprocess.call([editor, path])

        # Read edited text
        with open(path, "r", encoding="utf-8") as f:
            edited_text = f.read()

        # If nothing changed, return None
        if edited_text.strip() == original_text.strip():
            return None

        # Otherwise parse YAML and return
        edited = yaml.safe_load(edited_text)
        return edited

    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ---------- Commands ----------
def ls_competitors(query: str = None):
    comps = db.query(Competitor).all()
    results = []

    for c in comps:
        name = f"{c.last_name or ''} {c.first_name or ''}"
        group = c.group or ""
        notes = c.notes or ""
        reg = c.reg or ""
        declared = c.declared_days or []

        # If no query, include everything
        if not query:
            results.append((100, c))  # 100 score to keep original order
            continue

        # Compute fuzzy score across multiple fields
        score = max(
            fuzz.partial_ratio(query.lower(), name.lower()),
            fuzz.partial_ratio(query.lower(), group.lower()),
            fuzz.partial_ratio(query.lower(), notes.lower()),
            fuzz.partial_ratio(query.lower(), reg.lower()),
        )

        if score >= 75:  # threshold for matching
            results.append((score, c))

    results.sort(key=lambda x: x[0])

    for score, c in results:
        name = f"{c.last_name or ''} {c.first_name or ''}"
        group = c.group or ""
        declared = c.declared_days or []
        notes = c.notes or ''
        print(f"{c.id:3} | {c.reg or '':6} | {name:20} | {group:6} | {declared} | {notes}")


def add_competitor():
    skeleton = {
        "id": None,
        "reg": "",
        "group": "",
        "sid": None,
        "first_name": "",
        "last_name": "",
        "notes": "",
        "money": None,
        "declared_days": [],
        "runs": [],
    }
    edited = edit_competitor_in_editor(skeleton)
    if edited:  # only update DB if user actually changed something
        update_competitor_from_dict(edited)
        db.commit()
        print("Added new competitor.")
    else:
        print("No changes made. Aborted.")


def edit_competitor(cid: int):
    comp = db.get(Competitor, cid)
    if not comp:
        print(f"No competitor with ID {cid}")
        return
    comp_dict = competitor_to_dict(comp)
    edited = edit_competitor_in_editor(comp_dict)
    if edited:
        update_competitor_from_dict(edited)
        db.commit()
        print(f"Competitor {cid} updated.")


def get_current_day():
    return Config.get(db, Config.KEY_CURRENT_DAY)


def set_current_day(arg):
    try:
        Config.set(db, Config.KEY_CURRENT_DAY, int(arg))
    except Exception:
        ...


# ---------- Main CLI Loop ----------
def main():
    print("Orienteering CLI (type 'help' for commands)")
    session = PromptSession()
    while True:
        try:
            current_day = get_current_day()
            text = session.prompt(HTML(f'<ansiblue>E{current_day}> </ansiblue>'), completer=cmd_completer)
            if not text.strip():
                continue
            parts = text.strip().split()
            cmd_input = parts[0].lower()
            cmd = resolve_command(cmd_input, commands)
            args = parts[1:]

            if cmd == 'quit':
                break
            elif cmd == 'day':
                set_current_day(parts[1])
            elif cmd == 'ls':
                query = " ".join(args) if args else None
                ls_competitors(query)
            elif cmd == 'add':
                add_competitor()
            elif cmd == 'edit' and args:
                try:
                    cid = int(args[0])
                    edit_competitor(cid)
                except ValueError:
                    print("Usage: edit <competitor_id>")
            elif cmd == 'help':
                print("Commands: ls <query>, add, edit <id>, quit")
            else:
                print("Unknown command, type 'help'")
        except KeyboardInterrupt:
            print("Use 'quit' to exit")
        except EOFError:
            break

    db.close()


if __name__ == "__main__":
    main()
