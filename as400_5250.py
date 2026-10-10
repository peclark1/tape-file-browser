"""Guided, read-only 5250-style navigation for archived CISC AS/400 DASD.

This is a screen/command *browser*, not a 5250 protocol emulator or OS/400.
The object inventory and member contents always come from the recovery backend.
"""
from __future__ import annotations

import fnmatch
import re
import textwrap
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
    CommandSpec("DSPCTLD", "DSPCTLD CTLD(*ALL/*)", "Inspect controller address-occurrence links to devices and lines."),
    CommandSpec("DSPLIND", "DSPLIND LIND(*ALL/*)", "Inspect line reverse address-occurrence links."),
    CommandSpec("DSPMODD", "DSPMODD MODD(QPCSUPP)", "Display recovered communications mode-description evidence."),
    CommandSpec("WRKCMD", "WRKCMD CMD(*ALL/CPY*)", "Find recovered commands, including unassigned primaries."),
    CommandSpec("DSPCMD", "DSPCMD CMD(QIWS/CPYTOPCD)", "Explore a recovered command definition; never execute it."),
    CommandSpec("DSPAFP", "DSPAFP OBJ(*ALL/*)", "Browse embedded print-resource fields and coded-font dependencies."),
    CommandSpec("WRKOUTQ", "WRKOUTQ OUTQ(*ALL/QPRINT) FORM(*STD)", "Inspect saved output-queue index keys and tentative form tokens; no live spool state."),
    CommandSpec("DSPRCT", "DSPRCT RCT(*ALL/*) KEYHEX(E2)", "Browse reference-code keys and corroborated opaque records."),
    CommandSpec("DSPPGM", "DSPPGM PGM(*ALL/*)", "Explore command/menu program-name references; no instruction decoding."),
    CommandSpec("DSPMSG", "DSPMSG MSGQ(*ALL/*)", "Inspect saved message-definition references, not live queue messages."),
    CommandSpec("DSPINTPRF", "DSPINTPRF INTPRF(*ALL/*)", "Match saved internal-profile identities to recovered user-profile names without inspecting credentials."),
    CommandSpec("DSPJOBD", "DSPJOBD JOBD(*ALL/*)", "Follow saved job-description queue-name candidates."),
    CommandSpec("WRKJOBQ", "WRKJOBQ JOBQ(*ALL/*)", "Browse saved job-queue identities and referring descriptions, not live jobs."),
    CommandSpec("DSPMNU", "DSPMNU MENU(*ALL/*)", "Inspect supported menu variants and name-qualified target candidates."),
    CommandSpec("DSPMSGD", "DSPMSGD MSGF(*ALL/QIWSMSG) MSGID(IWN*)", "Browse recovered message IDs and validated message records."),
    CommandSpec("WRKFLR", "WRKFLR FLR(*ALL/*)", "Explore recovered folder anchor relationships."),
    CommandSpec("WRKTYP", "WRKTYP TYPE(*)", "Explorer extension: browse all MI types and recovered counts."),
    CommandSpec("DSPDTAARA", "DSPDTAARA DTAARA(*ALL/*)", "Display bounded recovered character data-area values."),
    CommandSpec("DSPFD", "DSPFD FILE(*ALL/*)", "Inspect recovered file/format candidates and field layouts."),
    CommandSpec("DSPTBL", "DSPTBL TBL(*ALL/QASCII) HEX(C1C2C3)", "Inspect a byte map; HEX is an offline sample extension."),
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
        "WRKOBJ": {"LIB", "OBJ", "OBJTYPE"},
        "WRKMBRPDM": {"FILE"},
        "DSPPFM": {"FILE", "MBR"},
        "DSPUSRPRF": {"USRPRF"},
        "DSPDEVD": {"DEVD"},
        "DSPCTLD": {"CTLD"},
        "DSPLIND": {"LIND"},
        "DSPMODD": {"MODD"},
        "WRKCMD": {"CMD"},
        "DSPCMD": {"CMD"},
        "WRKTYP": {"TYPE"},
        "WRKFLR": {"FLR"},
        "DSPMSGD": {"MSGF", "MSGID"},
        "DSPMNU": {"MENU"},
        "DSPINTPRF": {"INTPRF"},
        "DSPJOBD": {"JOBD"},
        "DSPMSG": {"MSGQ"},
        "DSPPGM": {"PGM"},
        "WRKOUTQ": {"OUTQ", "KEYHEX", "FORM"},
        "DSPRCT": {"RCT", "KEYHEX"},
        "DSPAFP": {"OBJ"},
        "WRKJOBQ": {"JOBQ"},
        "DSPFD": {"FILE"},
        "DSPDTAARA": {"DTAARA"},
        "DSPTBL": {"TBL", "HEX"},
        "HELP": set(),
    }[name]
    extra = set(parameters) - allowed
    if extra:
        raise ValueError("Unsupported parameter(s): " + ", ".join(sorted(extra)))
    return name, parameters


class Guided5250:
    """Testable navigation model shared by the curses frontend and unit tests."""

    def __init__(self, inventory, *, member_info=None, member_loader=None,
                 command_info_loader=None, config_info_loader=None,
                 command_definition_loader=None, capability_loader=None, record_loader=None, anchor_loader=None, message_loader=None, index_loader=None, directory_loader=None, queue_loader=None, library_loader=None, reference_loader=None, afp_loader=None, outq_loader=None):
        self.outq_loader = outq_loader
        self.afp_loader = afp_loader
        self.reference_loader = reference_loader
        self.library_loader = library_loader
        self.anchor_loader = anchor_loader
        self.queue_loader = queue_loader
        self.directory_loader = directory_loader
        self.message_loader = message_loader
        self.index_loader = index_loader
        self.record_loader = record_loader
        self.capability_loader = capability_loader
        self.command_definition_loader = command_definition_loader
        self.view_rows = []
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
                self.library_filter, self.selected, self.scroll, list(self.detail), list(self.view_rows))

    def _goto(self, screen, *, library="", file="", member="", detail=None, library_filter="*", view_rows=None):
        self.history.append(self._snapshot())
        self.screen, self.library, self.file, self.member = screen, library, file, member
        self.detail = list(detail or [])
        self.view_rows = list(view_rows or [])
        self.library_filter = library_filter
        self.selected = self.scroll = 0

    def back(self):
        if not self.history:
            self.status = "Already at the top level."
            return False
        (self.screen, self.library, self.file, self.member,
         self.library_filter, self.selected, self.scroll, self.detail, self.view_rows) = self.history.pop()
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
        if self.screen in ("commands", "command_definition", "command_prompts", "related_programs",
                           "mi_types", "type_objects", "capabilities"):
            return self.view_rows
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
                if not self.library and obj.library_name:
                    continue
                info = self.member_info(obj)
                result.append(dict(
                    kind="member", name=obj.member_name.upper(),
                    type=getattr(info, "member_type", "") or "member",
                    note=getattr(info, "text", "") or "", object=obj))
            return result
        return []

    def title(self):
        return {
            "mi_types": "MI Types — Recovered Primaries (Not Live Counts)",
            "type_objects": "Search Recovered Objects",
            "capabilities": "Explore Recovered Object Capability",
            "libraries": "Work with Libraries Using PDM",
            "objects": "Work with Objects Using PDM",
            "members": "Work with Members Using PDM",
            "contents": "Display Physical File Member (Recovered)",
            "commands": "Work with Recovered Commands",
            "command_definition": "Explore Command Definition (Read-only)",
            "command_prompts": "Recovered Command Prompts (Read-only)",
            "related_programs": "Candidate Program Name Matches (Unverified Link)",
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

    def command_rows(self, pattern="*ALL/*"):
        """Search identities only; do not read every primary or hide duplicates."""
        parts = pattern.split("/")
        if len(parts) == 1:
            parts = ["*ALL", parts[0]]
        if len(parts) != 2 or not all(parts):
            raise ValueError("Use CMD(name), CMD(library/name), or CMD(*ALL/pattern).")
        lib, name = parts
        if not all(re.fullmatch(r"[A-Z0-9#$@_*?]+", value) for value in parts):
            raise ValueError("Command search accepts names and * or ? wildcards only.")
        name = "*" if name == "*ALL" else name
        result = []
        for obj in self.inventory.objects:
            if (obj.object_type, obj.object_subtype) != (0x19, 0x05):
                continue
            library = obj.library_name or "*UNASSIGNED"
            lib_match = (lib == "*ALL" or
                         (lib == "*ORPHAN" and not obj.library_name) or
                         (obj.library_name and fnmatch.fnmatchcase(library.upper(), lib)))
            if lib_match and fnmatch.fnmatchcase(obj.name.upper(), name):
                result.append(dict(kind="command", name=obj.name, type=library,
                                   note=f"LBA {obj.segment.start_lba}", object=obj))
        return sorted(result, key=lambda r: (r["name"], r["type"], r["object"].segment.start_lba))

    def explore_command(self, obj):
        if self.command_definition_loader is None:
            self.show_command_info(obj)
            return
        from as400_cmd import parameter_information_lines, prompt_form_lines
        try:
            view = self.command_definition_loader(obj)
        except (OSError, ValueError) as exc:
            self._goto("command_info", library=obj.library_name or "<unassigned>",
                       file=obj.name, detail=[f"Command recovery unavailable: {exc}"])
            return
        rows = [dict(kind="command_section", name="Summary", type="Origin",
                     note=view.recovery.reason, lines=view.summary),
                dict(kind="command_section", name="Evidence", type="Tentative",
                     note="Whole-command strings and offsets", lines=view.evidence)]
        definitions = {p.keyword.ordinal: p for p in view.definition.parameters}
        prompt_rows = []
        for ordinal in view.definition.prompt_order:
            item = definitions[ordinal]
            label = (item.prompt.text or "[stored prompt blank]" if item.prompt
                     else "[prompt unavailable]")
            prompt_rows.append(dict(kind="command_section", name=item.keyword.keyword,
                type=f"#{ordinal}", note=label,
                hint=item.hint.text if item.hint else "unavailable",
                default=repr(item.default_candidate.text) if item.default_candidate else "unknown",
                values=", ".join(repr(v.text) for v in item.value_candidates) or "unknown",
                lines=parameter_information_lines(obj, item.keyword, item)))
        rows.append(dict(kind="prompt_form", name="Prompt form", type="Read only",
                         note="Linked labels, hints and candidate values", rows=prompt_rows,
                         lines=prompt_form_lines(obj, view.definition)))
        if view.processor:
            pgm, lib = view.processor
            matches = [o for o in self.inventory.objects
                       if (o.object_type, o.object_subtype) == (2, 1)
                       and o.name.upper() == pgm
                       and (o.library_name or "").upper() == lib]
            related = [dict(kind="object", name=o.name, type="*PGM", object=o,
                            note=f"{lib} LBA {o.segment.start_lba}; name match only")
                       for o in sorted(matches, key=lambda o: o.segment.start_lba)]
            rows.append(dict(kind="related", name="PGM matches", type="Unverified",
                             note=f"{lib}/{pgm}: {len(matches)} name matches", rows=related))
        for parameter in view.recovery.parameters:
            definition = definitions.get(parameter.ordinal)
            prompt = definition.prompt if definition else None
            note = (prompt.text or "[stored prompt blank]" if prompt is not None
                    else "[prompt unavailable]")
            rows.append(dict(kind="command_section", name=parameter.keyword,
                             type=f"#{parameter.ordinal}", note=note,
                             lines=parameter_information_lines(obj, parameter, definition)))
        self._goto("command_definition", library=obj.library_name or "<unassigned>",
                   file=obj.name, view_rows=rows)
        self.status = (f"{len(view.recovery.parameters)} keywords; stored order, not F4 order."
                       if view.recovery.parameters else view.recovery.reason)

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

    def explore_object(self, obj, sample=None):
        try:
            rows = list(self.capability_loader(obj, sample) if self.capability_loader else [])
        except (OSError, ValueError) as exc:
            rows = [dict(kind="capability_section", name="Unavailable", type="Diagnostic",
                         note=str(exc), lines=[str(exc), "No substitute layout or bytes were guessed."])]
        if not rows:
            return False
        self._goto("capabilities", library=obj.library_name or "<unassigned>",
                   file=obj.name, view_rows=rows)
        self.status = "Read-only. Enter=Inspect; 8=Origin; Back restores selection."
        return True

    def show_records(self, request):
        try:
            rows = list(self.record_loader(**request)) if self.record_loader else []
        except (OSError, ValueError) as exc:
            rows = [dict(kind="capability_section", name="Unavailable", type="Diagnostic",
                         note=str(exc), lines=[str(exc), "No data/schema substitute was selected."])]
        member = request["member"]
        self._goto("capabilities", library=member.library_name or "<unassigned>",
                   file=member.member_file_name, member=member.member_name, view_rows=rows)
        self.status = "Explicit format; recovered ordinals. Enter=Inspect; Next/Previous=50-entry window."
        return True

    def show_evidence(self, request, loader):
        if loader is None:
            self.status = "Evidence service is unavailable."
            return False
        try:
            rows = list(loader(**request))
        except (OSError, ValueError) as exc:
            from as400_capabilities import section
            rows = [section("Unavailable", [str(exc)])]
        obj = request["obj"]
        self._goto("capabilities", library=obj.library_name or "<unassigned>",
                   file=obj.name, view_rows=rows)
        return True

    def open_row(self, index, option=None):
        rows = self.rows()
        if index < 0 or index >= len(rows):
            self.status = "No entry selected."
            return False
        row = rows[index]
        default = "12" if row["kind"] in ("library", "file") else "5"
        option = str(option or default)
        if row["kind"] == "outq_action" and option == "5":
            return self.show_evidence(row["request"], self.outq_loader)
        elif self.outq_loader and row.get("object") is not None and row["object"].type_code == "0E/02" and option == "5":
            return self.show_evidence(dict(obj=row["object"], keyhex=row.get("outq_keyhex", ""), form=row.get("outq_form", "")), self.outq_loader)
        elif row["kind"] == "afp_action" and option == "5":
            return self.show_evidence(row["request"], self.afp_loader)
        elif self.afp_loader and row.get("object") is not None and row["object"].type_code in ("19/26", "19/28", "19/36") and option == "5":
            return self.show_evidence(dict(obj=row["object"]), self.afp_loader)
        elif row["kind"] == "reference_action" and option == "5":
            return self.show_evidence(row["request"], self.reference_loader)
        elif self.reference_loader and row.get("object") is not None and row["object"].type_code == "0E/08" and option == "5":
            return self.show_evidence(dict(obj=row["object"], keyhex=row.get("reference_keyhex", "")), self.reference_loader)
        elif row["kind"] == "library_action" and option == "5":
            return self.show_evidence(row["request"], self.library_loader)
        elif self.library_loader and row.get("object") is not None and row["object"].type_code == "04/01" and option == "5":
            return self.show_evidence(dict(obj=row["object"]), self.library_loader)
        elif row["kind"] == "queue_action" and option == "5":
            return self.show_evidence(row["request"], self.queue_loader)
        elif self.queue_loader and row.get("object") is not None and row["object"].type_code == "19/02" and option == "5":
            return self.show_evidence(dict(obj=row["object"]), self.queue_loader)
        elif row["kind"] == "directory_action" and option == "5":
            return self.show_evidence(row["request"], self.directory_loader)
        elif self.directory_loader and row.get("object") is not None and row["object"].type_code in ("0E/90","19/52") and option == "5":
            return self.show_evidence(dict(obj=row["object"]), self.directory_loader)
        elif row["kind"] in ("message_action", "index_action") and option == "5":
            return self.show_evidence(row["request"], self.message_loader if row["kind"] == "message_action" else self.index_loader)
        elif self.message_loader and row.get("object") is not None and row["object"].type_code == "0E/03" and option == "5":
            return self.show_evidence(dict(obj=row["object"], pattern=row.get("message_pattern", "*")), self.message_loader)
        elif row["kind"] == "anchor_action" and option == "5" and self.anchor_loader:
            try:
                links = list(self.anchor_loader(**row["request"]))
            except (OSError, ValueError) as exc:
                links = [dict(kind="capability_section", name="Unavailable", type="Diagnostic",
                              note=str(exc), lines=[str(exc)])]
            self._goto("capabilities", library=self.library, file=self.file, view_rows=links)
            self.status = "Anchor key evidence; parent/child paths are not certified QDLS paths."
            return True
        elif row["kind"] == "record_action" and option == "5":
            return self.show_records(row["request"])
        elif row["kind"] == "record_entry" and option == "5":
            from as400_records import record_rows
            self._goto("capabilities", library=self.library, file=self.file, member=self.member,
                       view_rows=record_rows(row["record"], row["fields"], row["origin"]))
            return True
        elif row["kind"] == "record_members" and option == "5":
            from as400_records import action, section
            file = row["file_object"]
            members = [m for m in self.inventory.members(file_name=file.name)
                       if (m.library_name or "").upper() == (file.library_name or "").upper()]
            links = [action(m.member_name, m, row["format_object"],
                            note=f"Cursor LBA {m.segment.start_lba}; explicit selected format") for m in members]
            if not links:
                links = [section("Unavailable", ["No recovered member cursor matches this file name/namespace."])]
            self._goto("capabilities", library=file.library_name or "<unassigned>", file=file.name, view_rows=links)
            return True
        elif row["kind"] == "member" and option == "6" and self.record_loader:
            return self.show_records(dict(member=row["object"], mode="choose"))
        elif row["kind"] == "mi_type" and option in ("5", "12"):
            from as400_capabilities import select_objects
            self._goto("type_objects", file=row["type"], view_rows=select_objects(
                self.inventory, object_type=row["code"]))
            self.status = "Recovered primaries only; zero matches does not prove absence."
            return True
        elif row["kind"] == "capability_section" and option in ("5", "8"):
            self._goto("details", library=self.library, file=self.file, detail=row["lines"])
            return True
        elif (row.get("object") is not None and self.capability_loader and
              ((option == "5" and row["object"].type_code in
                ("02/01", "19/03", "0E/01", "0E/C4", "19/16", "10/01", "12/01", "11/01", "19/01", "19/51", "19/06", "19/0A", "19/0E", "19/12", "06/C1", "0B/90", "0C/90")) or
               (option == "9" and row["object"].is_member_cursor))):
            if self.explore_object(row["object"], row.get("sample")):
                if row.get("source_file") is not None and self.record_loader:
                    self.view_rows.insert(1, dict(kind="record_members", name="Records", type="Members",
                        note="Use this explicitly selected format", file_object=row["source_file"], format_object=row["object"]))
                return True
            self.status = "No object-specific view is available. Use 8 for identity."
            return False
        elif row["kind"] == "command" and option == "5":
            self.explore_command(row["object"])
            return True
        elif row["kind"] == "prompt_form" and option == "5":
            if row["rows"]:
                self._goto("command_prompts", library=self.library, file=self.file,
                           view_rows=row["rows"])
            else:
                self._goto("command_info", library=self.library, file=self.file, detail=row["lines"])
            self.status = "Linked order is empirical. Enter=field evidence; no execution."
            return True
        elif row["kind"] == "command_section" and option in ("5", "8"):
            self._goto("command_info", library=self.library, file=self.file,
                       member=row["name"], detail=row["lines"])
        elif row["kind"] == "related" and option == "5":
            self._goto("related_programs", library=self.library, file=self.file,
                       view_rows=row["rows"])
            self.status = "Name matches only; CPP pointer unverified. Empty is not proof of absence."
            return True
        elif row["kind"] == "library" and option == "12":
            self._goto("objects", library=row["name"])
        elif row["kind"] == "file" and option == "12":
            self._goto("members", library=(getattr(row.get("object"), "library_name", None)
                                              or ("" if row.get("object") else self.library)), file=row["name"])
        elif row["kind"] == "member" and option == "5":
            obj = row["object"]
            self.show_contents(obj, library=obj.library_name or "", file=obj.member_file_name)
        elif (row["kind"] == "object" and row["type"] == "*CMD"
              and option == "5"):
            self.explore_command(row["object"])
            return True
        elif (row["kind"] == "object"
              and row["type"] in ("*USRPRF", "*DEVD", "*MODD")
              and option == "5"):
            self.show_config_info(row["object"])
        elif option in ("5", "8") and row["kind"] in ("library", "file", "object", "directory", "command"):
            obj = row.get("object")
            origin_library = (getattr(obj, "library_name", None) or "<unassigned>"
                              if obj is not None else self.library or row["name"])
            lines = [
                "Recovered object details (read-only)",
                f"Name:    {row['name']}",
                f"Type:    {getattr(obj, 'external_type_hint', None) or row['type']}",
                f"Library: {origin_library}",
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
            if obj is not None and hasattr(obj, "segment"):
                lines.extend([f"Primary LBA: {obj.segment.start_lba}",
                              f"Virtual address: {obj.segment.virtual_address:012X}"])
            if self.screen == "related_programs":
                lines.append("Candidate processor name match only; not a verified CPP link.")
            self._goto("details", library=getattr(obj, "library_name", None) or self.library,
                       file=self.file, detail=lines)
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
            elif name in ("DSPCTLD", "DSPLIND") or (name == "DSPDEVD" and self.capability_loader):
                from as400_capabilities import select_objects
                arg,kind = {"DSPDEVD":("DEVD","*DEVD"),"DSPCTLD":("CTLD","*CTLD"),"DSPLIND":("LIND","*LIND")}[name]
                rows=select_objects(self.inventory,params.get(arg,"*ALL/*"),kind)
                if len(rows)==1:self.explore_object(rows[0]["object"])
                else:self._goto("type_objects",view_rows=rows)
            elif name == "DSPAFP":
                from as400_capabilities import select_objects
                rows=[r for r in select_objects(self.inventory,params.get("OBJ","*ALL/*")) if r["object"].type_code in ("19/26","19/28","19/36")]
                if len(rows)==1:self.show_evidence(dict(obj=rows[0]["object"]),self.afp_loader)
                else:self._goto("type_objects",view_rows=rows)
            elif name == "WRKOUTQ":
                from as400_capabilities import select_objects
                keyhex = params.get("KEYHEX", "")
                prefix = bytes.fromhex(keyhex)
                if len(prefix) > 48:
                    raise ValueError("KEYHEX exceeds 48 bytes")
                form = params.get("FORM", "")
                rows = select_objects(self.inventory, params.get("OUTQ", "*ALL/*"), "*OUTQ")
                for row in rows:
                    row["outq_keyhex"], row["outq_form"] = keyhex, form
                if len(rows) == 1:
                    self.show_evidence(dict(obj=rows[0]["object"], keyhex=keyhex, form=form), self.outq_loader)
                else:
                    self._goto("type_objects", view_rows=rows)
            elif name == "DSPRCT":
                from as400_capabilities import select_objects
                keyhex=params.get("KEYHEX", "")
                prefix=bytes.fromhex(keyhex)
                if len(prefix)>8:raise ValueError("KEYHEX exceeds eight bytes")
                rows=select_objects(self.inventory,params.get("RCT","*ALL/*"),"*RCT")
                for row in rows:row["reference_keyhex"]=keyhex
                if len(rows)==1:self.show_evidence(dict(obj=rows[0]["object"],keyhex=keyhex),self.reference_loader)
                else:self._goto("type_objects",view_rows=rows)
            elif name == "DSPMSG":
                from as400_capabilities import select_objects
                rows=select_objects(self.inventory,params.get("MSGQ","*ALL/*"),"*MSGQ")
                if len(rows)==1:self.show_evidence(dict(obj=rows[0]["object"]),self.queue_loader)
                else:self._goto("type_objects",view_rows=rows)
            elif name == "DSPMSGD":
                from as400_capabilities import select_objects
                rows = select_objects(self.inventory, params.get("MSGF", "*ALL/*"), "*MSGF")
                pattern = params.get("MSGID", "*")
                for row in rows: row["message_pattern"] = pattern
                if len(rows) == 1:
                    self.show_evidence(dict(obj=rows[0]["object"], pattern=pattern), self.message_loader)
                else:
                    self._goto("type_objects", view_rows=rows)
            elif name == "WRKTYP":
                from as400_capabilities import type_rows
                self._goto("mi_types", view_rows=type_rows(self.inventory, params.get("TYPE", "*")))
                self.status = "Later catalog names; not proof of CISC presence or decoder support."
            elif name in ("DSPFD", "DSPTBL", "DSPDTAARA", "WRKFLR", "DSPMNU", "DSPJOBD", "WRKJOBQ", "DSPPGM", "DSPINTPRF") or (name == "WRKOBJ" and ("OBJ" in params or "OBJTYPE" in params)):
                from as400_capabilities import select_objects, hex_sample
                if name == "WRKOBJ" and "LIB" in params and "OBJ" in params:
                    raise ValueError("Use OBJ(library/name) or LIB(name), not both.")
                arg = {"DSPFD": "FILE", "DSPTBL": "TBL", "DSPDTAARA": "DTAARA", "WRKFLR": "FLR", "DSPMNU": "MENU", "DSPJOBD": "JOBD", "WRKJOBQ": "JOBQ", "DSPPGM": "PGM", "DSPINTPRF": "INTPRF"}.get(name, "OBJ")
                pattern = params.get(arg, params.get("LIB", "*ALL") + "/*")
                objtype = {"DSPFD": "*FILE", "DSPTBL": "*TBL", "DSPDTAARA": "*DTAARA", "WRKFLR": "*FLR", "DSPMNU": "*MENU", "DSPJOBD": "*JOBD", "WRKJOBQ": "*JOBQ", "DSPPGM": "*PGM", "DSPINTPRF": "*INTPRF"}.get(name, params.get("OBJTYPE", "*ALL"))
                sample = hex_sample(params["HEX"]) if "HEX" in params else None
                rows = select_objects(self.inventory, pattern, objtype)
                for row in rows:
                    row["sample"] = sample
                if name != "WRKOBJ" and len(rows) == 1 and self.explore_object(rows[0]["object"], sample):
                    pass
                else:
                    self._goto("type_objects", file=pattern, view_rows=rows)
                    self.status = "Select a primary; duplicate names retain library/LBA. 5=Inspect; 8=Origin."
            elif name in ("WRKCMD", "DSPCMD"):
                pattern = params.get("CMD", "*ALL/*" if name == "WRKCMD" else "")
                if not pattern:
                    raise ValueError("Specify CMD(library/name) or CMD(name).")
                rows = self.command_rows(pattern)
                if name == "DSPCMD" and len(rows) == 1:
                    self.explore_command(rows[0]["object"])
                else:
                    self._goto("commands", file=pattern, view_rows=rows)
                    self.status = ("Select an individual primary; library and LBA distinguish duplicates."
                                   if rows else "No recovered command matches. Try WRKCMD CMD(*ALL/*).")
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
            "5/Enter on *CMD: Explore definition, keywords, origin and evidence",
            "WRKTYP: browse every catalog type plus unidentified recovered codes",
            "DSPMSGD MSGF(library/file) MSGID(pattern): IDs -> validated text/opaque records",
            "WRKFLR FLR(*ALL/*): folder -> anchor source -> parents/children/objects",
            "WRKOBJ OBJ(*ORPHAN/*) OBJTYPE(*TBL): search all/unassigned primaries",
            "WRKOBJ OBJ(QDOC/*) OBJTYPE(*DOC): companion candidates -> byte stream",
            "DSPDTAARA DTAARA(library/name): character value by position",
            "DSPFD FILE(library/file): format candidates -> fields -> descriptor",
            "5 on *FILE: formats; 12: members; 9 on member: direct storage links",
            "6 on member: choose format/raw -> paged records -> field values",
            "DSPFD -> select format -> Records: preserve that exact format",
            "DSPTBL TBL(library/table) HEX(C1C2C3): byte map and offline sample",
            "WRKTYP and HEX are explorer extensions, not executed CL commands.",
            "WRKCMD CMD(*ALL/CPY*): find commands across recovered namespaces",
            "WRKCMD CMD(*ORPHAN/*): include commands with no recovered library",
            "DSPCMD CMD(QIWS/CPYTOPCD): open definition (duplicates stay separate)",
            "Definition: Enter Prompt form for labels/hints/candidate values",
            "Enter a keyword for linked attributes, origin and unknowns",
            "All command views are offline; no commands or parameters execute.",
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


def _detail_lines(model, width):
    """Wrap evidence so ordinary terminals do not silently hide qualifiers."""
    return [part for line in model.detail
            for part in (textwrap.wrap(_safe_display_text(line), max(1, width - 4),
                                        replace_whitespace=False) or [" "])]


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
    if model.screen == "command_definition":
        put(2, 2, "Enter=Inspect  Prompt form=Labels/hints  Values=Candidates")
    elif model.screen == "command_prompts":
        put(2, 2, "Labels/hints: linked. Default?/Values?: tentative meanings.")
    elif model.screen in ("capabilities", "members"):
        put(2, 2, "Enter=Inspect  Member: 5=Content  6=Records  9=Storage")
    elif model.screen == "commands":
        put(2, 2, "Enter=Explore  8=Origin  Unassigned=unknown library")
    else:
        put(2, 2, "Type options, press Enter.  12=Work with  5=Display  8=Details")
    body_height = max(1, height - 10)
    if model.screen in ("contents", "details", "help", "command_info", "config_info"):
        lines = _detail_lines(model, width)
        for i, line in enumerate(lines[model.scroll: model.scroll + body_height]):
            put(4 + i, 2, line)
    elif model.screen == "command_prompts":
        rows = model.rows()
        visible = max(1, body_height // 3)
        model.selected = min(model.selected, max(0, len(rows) - 1))
        start = min(max(0, model.selected - visible // 2), max(0, len(rows) - visible))
        for i, row in enumerate(rows[start:start + visible]):
            y = 4 + i * 3
            attr = curses.A_REVERSE if start + i == model.selected else 0
            put(y, 2, f"{row['type']} {row['name']} — {row['note']}", attr)
            put(y + 1, 4, f"Hint: {row['hint']}")
            put(y + 2, 4, f"Default?: {row['default']}  Values?: {row['values']}")
        put(height - 6, 2, f"{len(rows)} parameters  Selected: {model.selected + 1}")
    else:
        heading = ("Opt  Command      Library     Primary origin" if model.screen == "commands"
                   else "Opt  Keyword      Ordinal     Recovered prompt" if model.screen == "command_definition"
                   else "Opt  Name         Type        Information")
        put(3, 2, heading, curses.A_BOLD)
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
            page_size = max(1, stdscr.getmaxyx()[0] - 10)
            if model.screen == "command_prompts":
                page_size = max(1, page_size // 3)
            delta = {curses.KEY_UP: -1, curses.KEY_DOWN: 1,
                     curses.KEY_PPAGE: -page_size,
                     curses.KEY_NPAGE: page_size}[key]
            if model.screen in ("contents", "details", "help", "command_info", "config_info"):
                model.scroll = max(0, min(max(0, len(_detail_lines(model, stdscr.getmaxyx()[1])) - 1), model.scroll + delta))
            else:
                model.selected = max(0, min(max(0, len(model.rows()) - 1),
                                            model.selected + delta))
            option = ""
        elif key in (ord("5"), ord("6"), ord("8"), ord("9"), ord("1"), ord("2")):
            option += chr(key)
            option = option[-2:]
        elif key in (10, 13, curses.KEY_ENTER):
            if model.screen not in ("contents", "details", "help", "command_info", "config_info"):
                model.open_row(model.selected, option or None)
            option = ""
        elif key in (curses.KEY_BACKSPACE, 8, 127):
            option = _back_or_edit_option(model, option)
