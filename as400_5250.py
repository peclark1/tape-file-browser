"""Guided, read-only 5250-style navigation for archived CISC AS/400 DASD.

This is a screen/command *browser*, not a 5250 protocol emulator or OS/400.
The object inventory and member contents always come from the recovery backend.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from as400_object_types import lookup as lookup_object_type


@dataclass(frozen=True)
class CommandSpec:
    name: str
    usage: str
    description: str


# Only commands implemented by this offline browser appear as runnable.
COMMANDS = (
    CommandSpec("WRKLIBPDM", "WRKLIBPDM LIB(Q*)", "Browse recovered libraries using PDM-style options."),
    CommandSpec("WRKLIB", "WRKLIB LIB(Q*)", "List recovered libraries."),
    CommandSpec("WRKOBJPDM", "WRKOBJPDM LIB(QGPL)", "Browse recovered objects in a specified library."),
    CommandSpec("WRKOBJ", "WRKOBJ LIB(QGPL)", "List recovered objects in a specified library."),
    CommandSpec("WRKMBRPDM", "WRKMBRPDM FILE(QGPL/QCLSRC)", "Browse members of a recovered file."),
    CommandSpec("DSPPFM", "DSPPFM FILE(QGPL/QCLSRC) MBR(MEMBER)", "Display recovered physical-file member contents."),
    CommandSpec("DSPUSRPRF", "DSPUSRPRF USRPRF(QSYSOPR)", "Display recovered user-profile identity and relationships (no credentials)."),
    CommandSpec("DSPDEVD", "DSPDEVD DEVD(QCONSOLE)", "Display recovered device-description evidence."),
    CommandSpec("DSPMODD", "DSPMODD MODD(QPCSUPP)", "Display recovered communications mode-description evidence."),
    CommandSpec("HELP", "HELP", "Show guided navigation and supported commands."),
)
_COMMAND_MAP = {item.name: item for item in COMMANDS}
_PARAMS = re.compile(r"([A-Z][A-Z0-9]*)\s*\(([^()]*)\)", re.I)
_HEAD = re.compile(r"^\s*([A-Z][A-Z0-9]*)(?:\s+(.*))?$", re.I | re.S)


def command_matches(query="", screen="libraries"):
    """Searchable supported command catalog; relevant commands first."""
    needle = query.strip().upper()
    matching = [
        item for item in COMMANDS
        if not needle or needle in item.name or needle in item.description.upper()
    ]
    priority = {
        "libraries": {"WRKLIBPDM", "WRKLIB"},
        "objects": {"WRKOBJPDM", "WRKOBJ", "WRKMBRPDM"},
        "members": {"WRKMBRPDM", "DSPPFM"},
        "contents": {"DSPPFM"},
        "config_info": {"DSPUSRPRF", "DSPDEVD", "DSPMODD"},
    }.get(screen, set())
    return sorted(matching, key=lambda item: (item.name not in priority, item.name))


def parse_command(text):
    """Parse a documented-style named parameter subset, without executing CL."""
    match = _HEAD.fullmatch(text.strip())
    if not match:
        raise ValueError("Use COMMAND PARAM(value), e.g. WRKOBJPDM LIB(QGPL).")
    name, args = match.group(1).upper(), (match.group(2) or "").strip()
    if name not in _COMMAND_MAP:
        raise ValueError(
            f"{name} is not supported by this read-only explorer. "
            "Press F4 to browse implemented commands."
        )
    parameters = {}
    consumed = []
    for param in _PARAMS.finditer(args):
        key, value = param.group(1).upper(), param.group(2).strip().upper()
        if not value or key in parameters:
            raise ValueError(f"Invalid or duplicate parameter {key}.")
        parameters[key] = value
        consumed.append((param.start(), param.end()))
    remainder = list(args)
    for start, end in consumed:
        remainder[start:end] = " " * (end - start)
    if "".join(remainder).strip():
        raise ValueError("Use named parameters such as LIB(QGPL) or FILE(QGPL/QCLSRC).")
    allowed = {
        "WRKLIBPDM": {"LIB"},
        "WRKLIB": {"LIB"},
        "WRKOBJPDM": {"LIB"},
        "WRKOBJ": {"LIB"},
        "WRKMBRPDM": {"FILE"},
        "DSPPFM": {"FILE", "MBR"},
        "DSPUSRPRF": {"USRPRF"},
        "DSPDEVD": {"DEVD"},
        "DSPMODD": {"MODD"},
        "HELP": set(),
    }[name]
    extra = set(parameters) - allowed
    if extra:
        raise ValueError("Unsupported parameter(s): " + ", ".join(sorted(extra)))
    return name, parameters


class Guided5250:
    """Testable navigation model shared by the curses frontend and unit tests."""

    def __init__(self, inventory, *, member_info=None, member_loader=None,
                 command_info_loader=None, config_info_loader=None):
        self.inventory = inventory
        self.member_info = member_info or (lambda obj: None)
        self.member_loader = member_loader or (lambda lib, file, obj: [])
        self.command_info_loader = command_info_loader or (lambda obj: [])
        self.config_info_loader = config_info_loader or (lambda obj: [])
        self.screen = "libraries"
        self.library = ""
        self.file = ""
        self.member = ""
        self.library_filter = "*"
        self.selected = 0
        self.scroll = 0
        self.detail = []
        self.status = "Read-only recovered image. F4 lists available commands."
        self.history = []
        self.command_history = []

    def _snapshot(self):
        return (self.screen, self.library, self.file, self.member,
                self.library_filter, self.selected, self.scroll, list(self.detail))

    def _goto(self, screen, *, library="", file="", member="", detail=None, library_filter="*"):
        self.history.append(self._snapshot())
        self.screen, self.library, self.file, self.member = screen, library, file, member
        self.detail = list(detail or [])
        self.library_filter = library_filter
        self.selected = self.scroll = 0

    def back(self):
        if not self.history:
            self.status = "Already at the top level."
            return False
        (self.screen, self.library, self.file, self.member,
         self.library_filter, self.selected, self.scroll, self.detail) = self.history.pop()
        self.status = ""
        return True

    def _libraries(self):
        names = {obj.name.upper() for obj in self.inventory.libraries if obj.name}
        names.update((obj.library_name or "").upper()
                     for obj in self.inventory.objects if obj.library_name)
        names.update(entry.library_name.upper() for entry in
                     getattr(self.inventory, "context_entries", ()) if entry.library_name)
        return sorted(name for name in names
                      if fnmatch.fnmatchcase(name, self.library_filter.upper()))

    def rows(self):
        if self.screen == "libraries":
            return [dict(kind="library", name=name, type="*LIB", note="Recovered namespace")
                    for name in self._libraries()]
        if self.screen == "objects":
            result = []
            seen_files = set()
            for obj in self.inventory.in_library(self.library):
                if obj.is_member_cursor:
                    continue
                is_file = (obj.object_type, obj.object_subtype) == (0x19, 0x01)
                if is_file:
                    seen_files.add(obj.name.upper())
                type_info = lookup_object_type(obj.object_type, obj.object_subtype)
                result.append(dict(
                    kind="file" if is_file else "object", name=obj.name.upper(),
                    type="*FILE" if is_file else (obj.external_type_hint or obj.type_code),
                    note="[internal]" if type_info and type_info.category == "internal" else "",
                    object=obj, catalog_info=type_info))
            for member in self.inventory.members(library=self.library):
                name = member.member_file_name.upper()
                if name not in seen_files:
                    seen_files.add(name)
                    result.append(dict(kind="file", name=name, type="*FILE",
                                       note="[member-only]", object=None))
            for entry in self.inventory.unresolved_context_entries(self.library):
                if entry.is_member_cursor:
                    continue
                type_info = lookup_object_type(entry.type_code)
                result.append(dict(
                    kind="directory", name=entry.display_name_hint or "<unknown>",
                    type=type_info.name if type_info else entry.type_code,
                    note="[dir] primary absent", entry=entry, catalog_info=type_info))
            return sorted(result, key=lambda r: (r["name"], r["type"], r["kind"]))
        if self.screen == "members":
            result = []
            for obj in self.inventory.members(library=self.library, file_name=self.file):
                info = self.member_info(obj)
                result.append(dict(
                    kind="member", name=obj.member_name.upper(),
                    type=getattr(info, "member_type", "") or "member",
                    note=getattr(info, "text", "") or "", object=obj))
            return result
        return []

    def title(self):
        return {
            "libraries": "Work with Libraries Using PDM",
            "objects": "Work with Objects Using PDM",
            "members": "Work with Members Using PDM",
            "contents": "Display Physical File Member (Recovered)",
            "command_info": "Display Command Information (Recovered)",
            "config_info": "Display OS/400 Configuration (Recovered)",
            "details": "Display Recovered Object Information",
            "help": "Guided 5250 Help",
        }[self.screen]

    def location(self):
        return "/".join(x for x in (self.library, self.file, self.member) if x) or "All recovered libraries"

    def show_contents(self, member, *, library=None, file=None):
        library = self.library if library is None else library
        file = self.file if file is None else file
        try:
            lines = list(self.member_loader(library, file, member))
        except (OSError, ValueError) as exc:
            lines = [f"Recovery error: {exc}"]
        if not lines:
            lines = ["No recoverable member contents in this image."]
        self._goto("contents", library=library, file=file,
                   member=member.member_name.upper(), detail=lines)
        self.status = "Recovered content; this is not a live OS/400 display."

    def show_command_info(self, command_object):
        """Use recovered primary metadata/evidence; never execute a command."""
        try:
            lines = list(self.command_info_loader(command_object))
        except (OSError, ValueError) as exc:
            lines = [f"Command information unavailable: {exc}"]
        if not lines:
            lines = [
                "Display Command Information — recovered image",
                "",
                f"Command: {command_object.name}",
                "No verified compiled-command definition fields are available.",
            ]
        self._goto("command_info", library=self.library, detail=lines)
        self.status = "Read-only command metadata/evidence; no command execution."

    def show_config_info(self, obj):
        """Navigate to a read-only, evidence-labeled object-specific view."""
        try:
            lines = list(self.config_info_loader(obj))
        except (OSError, ValueError) as exc:
            lines = [f"Configuration metadata unavailable: {exc}"]
        if not lines:
            lines = [
                "Display Configuration Information — recovered image",
                f"Object: {obj.name}",
                "Object-specific CISC fields not yet decoded.",
            ]
        self._goto("config_info", library=obj.library_name or self.library, detail=lines)
        self.status = "Read-only recovered configuration evidence; no commands executed."

    def open_row(self, index, option=None):
        rows = self.rows()
        if index < 0 or index >= len(rows):
            self.status = "No entry selected."
            return False
        row = rows[index]
        default = "12" if row["kind"] in ("library", "file") else "5"
        option = str(option or default)
        if row["kind"] == "library" and option == "12":
            self._goto("objects", library=row["name"])
        elif row["kind"] == "file" and option == "12":
            self._goto("members", library=self.library, file=row["name"])
        elif row["kind"] == "member" and option == "5":
            self.show_contents(row["object"])
        elif (row["kind"] == "object" and row["type"] == "*CMD"
              and option == "5"):
            self.show_command_info(row["object"])
        elif (row["kind"] == "object"
              and row["type"] in ("*USRPRF", "*DEVD", "*MODD")
              and option == "5"):
            self.show_config_info(row["object"])
        elif option in ("5", "8") and row["kind"] in ("library", "file", "object", "directory"):
            lines = [
                "Recovered object details (read-only)",
                f"Name:    {row['name']}",
                f"Type:    {row['type']}",
                f"Library: {self.library or row['name']}",
                f"Status:  {row.get('note') or 'Primary object recovered'}",
            ]
            info = row.get("catalog_info")
            obj = row.get("object")
            entry = row.get("entry")
            mi_code = (getattr(obj, "type_code", "")
                       if obj is not None else
                       getattr(entry, "type_code", "") if entry is not None else "")
            if mi_code:
                lines.append(f"MI type: {mi_code}")
            if info is not None:
                lines.extend([
                    f"IBM object class: {info.category}",
                    f"IBM description: {info.description}",
                    "Catalog: modern IBM i documentation (V2R3 presence unverified)",
                    f"Reference: {info.source}",
                ])
            self._goto("details", library=self.library, file=self.file, detail=lines)
        else:
            self.status = f"Option {option} is not available for this selection."
            return False
        self.status = ""
        return True

    def run_command(self, text):
        try:
            name, params = parse_command(text)
            if name == "HELP":
                self._goto("help", detail=self.help_lines())
            elif name in ("DSPUSRPRF", "DSPDEVD", "DSPMODD"):
                specs = {
                    "DSPUSRPRF": ("USRPRF", (0x08, 0x01)),
                    "DSPDEVD": ("DEVD", (0x10, 0x01)),
                    "DSPMODD": ("MODD", (0x15, 0x01)),
                }
                arg, pair = specs[name]
                wanted = params.get(arg)
                if not wanted or "/" in wanted:
                    raise ValueError(f"Specify {arg}(name).")
                matches = [
                    obj for obj in self.inventory.objects
                    if obj.name.upper() == wanted
                    and (obj.object_type, obj.object_subtype) == pair
                ]
                if not matches:
                    raise ValueError(
                        f"{wanted} {name} target not recovered on this image.")
                if len(matches) != 1:
                    raise ValueError(
                        f"{len(matches)} matching {wanted} objects recovered; "
                        "select an individual object in the library list.")
                self.show_config_info(matches[0])
            elif name in ("WRKLIB", "WRKLIBPDM"):
                pattern = params.get("LIB", "*ALL")
                self._goto("libraries", library_filter="*" if pattern == "*ALL" else pattern)
            elif name in ("WRKOBJ", "WRKOBJPDM"):
                library = params.get("LIB") or self.library
                if not library or library not in self._all_libraries():
                    raise ValueError("Specify an existing recovered library with LIB(name).")
                self._goto("objects", library=library)
            elif name in ("WRKMBRPDM", "DSPPFM"):
                path = params.get("FILE") or (
                    f"{self.library}/{self.file}" if self.library and self.file else ""
                )
                if "/" not in path or len(path.split("/")) != 2:
                    raise ValueError("Specify FILE(LIBRARY/FILE).")
                lib, file = path.split("/")
                if lib not in self._all_libraries():
                    raise ValueError(f"Library {lib} is not recovered.")
                if file not in {
                    item["name"] for item in self._object_rows_for(lib)
                    if item["kind"] == "file"
                }:
                    raise ValueError(f"File {lib}/{file} is not recovered.")
                if name == "WRKMBRPDM":
                    self._goto("members", library=lib, file=file)
                else:
                    members = self.inventory.members(library=lib, file_name=file)
                    wanted = params.get("MBR")
                    if not wanted:
                        raise ValueError("Specify MBR(name) to display a recovered member.")
                    found = next((m for m in members if m.member_name.upper() == wanted), None)
                    if found is None:
                        raise ValueError(f"Member {lib}/{file}({wanted}) is not recovered.")
                    self.show_contents(found, library=lib, file=file)
            self.command_history.append(text.strip())
            return True
        except ValueError as exc:
            self.status = str(exc)
            return False

    def _all_libraries(self):
        previous = self.library_filter
        try:
            self.library_filter = "*"
            return set(self._libraries())
        finally:
            self.library_filter = previous

    def _object_rows_for(self, lib):
        previous = self.library
        try:
            self.library = lib
            return self.rows() if self.screen == "objects" else self._rows_for_objects()
        finally:
            self.library = previous

    def _rows_for_objects(self):
        old = self.screen
        try:
            self.screen = "objects"
            return self.rows()
        finally:
            self.screen = old

    def help_lines(self):
        return [
            "GUIDED 5250 EXPLORER — read-only disk-image browsing",
            "",
            "F4: Search supported commands and descriptions",
            "F1: This help screen       F12 or Backspace: Previous screen",
            "Ctrl+B: Previous screen (terminal-safe alternative)",
            "Up/Down: Select row       Enter: Open selected row",
            "12 + Enter: Work with objects or members",
            "5 + Enter: Display selected member/object",
            "5/Enter on *CMD: Recover command information (evidence-only)",
            "5/Enter on *USRPRF, *DEVD, *MODD: read-only configuration evidence",
            "DSPUSRPRF/DSPDEVD/DSPMODD NAME(value): inspect recovered identity",
            "Type a command directly, or press ':' to edit the command field.",
            "",
            "Only recovered image contents are displayed.",
            "[dir] identifies an entry whose primary was not recovered.",
            "[member-only] identifies a file inferred from surviving member cursors.",
            "[internal] marks an IBM internal object, not a PDM-editable user object.",
            "IBM type names come from a modern catalog; V2R3 release support is unproven.",
            "Commands requiring a running AS/400 are not emulated.",
            "",
            "Implemented commands:",
            *[f"{c.usage}: {c.description}" for c in command_matches(screen=self.screen)],
        ]


def _safe_display_text(value):
    """Escape nonprintable characters from recovered data before curses output.

    Some legitimate damaged/partially recovered AS/400 objects contain NUL
    bytes. curses.addnstr() rejects embedded U+0000 with ValueError, which
    previously escaped the UI and ended the entire browser. Preserve original
    bytes in the parser/model; only escape the on-screen representation.
    Escaping all C0/C1 controls also prevents control/escape sequences from
    altering the terminal's display.
    """
    return re.sub(
        r"[\x00-\x1f\x7f-\x9f]",
        lambda match: f"\\x{ord(match.group(0)):02X}",
        str(value),
    )


def _draw(screen, model, option="", command="", suggestions=None, active=False, suggestion_index=0):
    import curses

    height, width = screen.getmaxyx()
    screen.erase()
    if height < 16 or width < 64:
        screen.addnstr(0, 0, "Resize terminal to at least 64x16. F3 exits.", max(1, width - 1))
        screen.refresh()
        return
    put = lambda y, x, text, attr=0: screen.addnstr(
        y, x, _safe_display_text(text), max(0, width - x - 1), attr)
    put(0, 1, f" {model.title()} ", curses.A_BOLD | curses.A_REVERSE)
    put(1, 2, f"Location: {model.location()}")
    put(2, 2, "Type options, press Enter.  12=Work with  5=Display  8=Details")
    body_height = max(1, height - 10)
    if model.screen in ("contents", "details", "help", "command_info", "config_info"):
        lines = model.detail
        for i, line in enumerate(lines[model.scroll: model.scroll + body_height]):
            put(4 + i, 2, line)
    else:
        put(3, 2, "Opt  Name         Type        Information", curses.A_BOLD)
        rows = model.rows()
        model.selected = min(model.selected, max(0, len(rows) - 1))
        start = min(max(0, model.selected - body_height // 2),
                    max(0, len(rows) - body_height))
        for i, row in enumerate(rows[start:start + body_height]):
            index = i + start
            marker = option if index == model.selected else ""
            label = f"{marker:<3}  {row['name']:<12.12} {row['type']:<11.11} {row.get('note', '')}"
            put(4 + i, 2, label, curses.A_REVERSE if index == model.selected else 0)
        if not rows:
            put(4, 2, "(No recovered entries for this selection)")
        put(height - 6, 2, f"{len(rows)} entries   Position: {model.selected + 1 if rows else 0}")
    put(height - 5, 2, model.status, curses.A_DIM)
    put(height - 4, 2, f"Command ===> {command if active else ''}",
        curses.A_BOLD if active else 0)
    if active:
        choices = list(suggestions or [])
        visible = max(1, height - 10)
        first = max(0, min(suggestion_index - visible + 1,
                            max(0, len(choices) - visible)))
        put(3, 2, "Matching commands (Up/Down=Select, Tab=Insert, Enter=Run)", curses.A_BOLD)
        for i, item in enumerate(choices[first:first + visible]):
            index = first + i
            put(4 + i, 2, f"{'>' if index == suggestion_index else ' '} {item.usage} — {item.description}",
                curses.A_REVERSE if index == suggestion_index else curses.A_DIM)
        put(height - 2, 2, "Esc=Cancel  F4/Tab=Insert selected  Enter=Run",
            curses.A_REVERSE)
    else:
        put(height - 2, 2, "F12/BS=Back  F4=Commands  F1=Help  F3=Exit  /=Command  PgUp/Dn=Page",
            curses.A_REVERSE)
    screen.refresh()


def _command_input(stdscr, model, seed=""):
    import curses

    value, selected = seed, 0
    while True:
        matches = command_matches(value, model.screen)
        _draw(stdscr, model, command=value, suggestions=matches, active=True,
              suggestion_index=selected)
        key = stdscr.getch()
        if key in (27, curses.KEY_F3, curses.KEY_F12):
            return None
        if key in (10, 13, curses.KEY_ENTER):
            if matches and (
                not value.strip() or
                (value.strip().upper() not in _COMMAND_MAP and " " not in value.strip())
            ):
                return matches[selected].name
            return value
        if key in (curses.KEY_DOWN, curses.KEY_UP) and matches:
            selected = (selected + (1 if key == curses.KEY_DOWN else -1)) % len(matches)
        elif key in (curses.KEY_F4, 9) and matches:
            value = matches[selected].usage
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            value = value[:-1]
            selected = 0
        elif 32 <= key < 127 and len(value) < 160:
            value += chr(key)
            selected = 0


def _back_or_edit_option(model, option):
    """Backspace erases a pending numeric option, else navigates back."""
    if option:
        return option[:-1]
    model.back()
    return ""


def run_curses(stdscr, model):
    import curses

    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    option = ""
    while True:
        _draw(stdscr, model, option)
        key = stdscr.getch()
        if key in (curses.KEY_F3, 27):
            return
        if key in (curses.KEY_F1, ord("?")):
            model._goto("help", detail=model.help_lines())
            option = ""
        elif key in (curses.KEY_F12, 2):  # F12 or Ctrl+B
            model.back()
            option = ""
        elif key in (curses.KEY_F4, ord("/")) or (65 <= key <= 90) or (97 <= key <= 122):
            seed = chr(key) if key not in (curses.KEY_F4, ord("/")) else ""
            entered = _command_input(stdscr, model, seed)
            if entered:
                model.run_command(entered)
            option = ""
        elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_NPAGE, curses.KEY_PPAGE):
            delta = {curses.KEY_UP: -1, curses.KEY_DOWN: 1,
                     curses.KEY_PPAGE: -max(1, stdscr.getmaxyx()[0] - 10),
                     curses.KEY_NPAGE: max(1, stdscr.getmaxyx()[0] - 10)}[key]
            if model.screen in ("contents", "details", "help", "command_info", "config_info"):
                model.scroll = max(0, min(max(0, len(model.detail) - 1), model.scroll + delta))
            else:
                model.selected = max(0, min(max(0, len(model.rows()) - 1),
                                            model.selected + delta))
            option = ""
        elif key in (ord("5"), ord("8"), ord("1"), ord("2")):
            option += chr(key)
            option = option[-2:]
        elif key in (10, 13, curses.KEY_ENTER):
            if model.screen not in ("contents", "details", "help", "command_info", "config_info"):
                model.open_row(model.selected, option or None)
            option = ""
        elif key in (curses.KEY_BACKSPACE, 8, 127):
            option = _back_or_edit_option(model, option)
