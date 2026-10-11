#!/usr/bin/env python3
"""One-scan read-only acceptance for 18 recent CISC Guided workflow types.

Unlike per-family validators, this recovers original disk objects *once*,
reuses the same image/model, and computes SHA256 before and after the run.
Emits counts/status only: never object names, retrieved bytes or profiles.
Synthetic CI calls assess(); run on original extracted .hda on your own rig.
"""
import argparse
from collections import Counter
from types import SimpleNamespace as NS
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_wscst import WorkstationTransformExplorer
from as400_gss import SavedSymbolExplorer
from as400_journals import JournalReceiverExplorer
from as400_alert_tables import AlertTableExplorer
from as400_messages import MessageExplorer
from as400_printer_queues import PrinterQueueExplorer
from as400_outq import OutputQueueExplorer
from as400_internal_profiles import InternalProfileExplorer
from as400_subsystems import SubsystemExplorer
from as400_archival_indexes import ArchivalIndexExplorer
from as400_local_data import LocalDataExplorer
from as400_spool_controls import SpoolControlExplorer
from as400_jmq import JobMessageQueueExplorer
from as400_panel_groups import PanelGroupExplorer
from as400_edit_descriptions import EditDescriptionExplorer
from as400_jobs import JobExplorer
from tools.validate_command_exploration import digest


# Type, Guided command, required named argument.
# These are the audited *partial* types added after the 29-type checkpoint.
WORKFLOWS = (
    ("0E/02", "WRKOUTQ", "OUTQ"),
    ("0E/01", "WRKJOBQ", "JOBQ"),
    ("0E/C4", "DSPINTPRF", "INTPRF"),
    ("19/09", "DSPSBSD", "SBSD"),
    ("19/04", "DSPCLS", "CLS"),
    ("0E/07", "DSPSCHIDX", "SCHIDX"),
    ("0E/91", "DSPMSRVI", "MSRVI"),
    ("19/CE", "DSPLDA", "LDA"),
    ("19/C2", "DSPSPLCB", "SPLCB"),
    ("18/A0", "DSPJMQ", "JMQ"),
    ("19/15", "DSPPNLGRP", "PNLGRP"),
    ("19/08", "DSPEDTD", "EDTD"),
    ("0E/C7", "DSPPRTQ", "PRTQ"),
    ("0E/09", "DSPALRTBL", "ALRTBL"),
    ("09/01", "DSPJRN", "JRN"),
    ("07/01", "DSPJRNRCV", "JRNRCV"),
    ("19/0C", "DSPGSS", "GSS"),
    ("19/38", "DSPWSCST", "WSCST"),
)
TYPE_CODES = {t[0] for t in WORKFLOWS}
DETAIL_ACTIONS = {
    "outq_action", "printer_queue_action", "alert_index_action", "archival_index_action", "jmq_action",
    "panel_symbol_action", "gss_symbol_action", "lda_action", "subsystem_action",
}


def make_model(image, inventory, segments=None):
    """Use the same capability service routing as the production TUI."""
    wscst = WorkstationTransformExplorer(image,inventory)
    gss = SavedSymbolExplorer(image)
    journals = JournalReceiverExplorer(image, inventory)
    messages = MessageExplorer(image, inventory, segments or NS(segments=[]))
    alerts = AlertTableExplorer(image, inventory, message_explorer=messages)
    messages.alert_explorer = alerts
    printer_queues = PrinterQueueExplorer(image, inventory)
    outq = OutputQueueExplorer(image)
    profiles = InternalProfileExplorer(inventory)
    subsystems = SubsystemExplorer(image, inventory)
    indexes = ArchivalIndexExplorer(image)
    lda = LocalDataExplorer(image)
    spool = SpoolControlExplorer(image, inventory, printer_queue_explorer=printer_queues)
    jmq = JobMessageQueueExplorer(image)
    panels = PanelGroupExplorer(image, inventory)
    edits = EditDescriptionExplorer(image, inventory)
    jobs = JobExplorer(image, inventory)
    services = {
        "19/38": wscst,
        "19/0C": gss,
        "09/01": journals,
        "07/01": journals,
        "0E/09": alerts,
        "0E/C7": printer_queues,
        "0E/02": outq,
        "0E/01": jobs,
        "0E/C4": profiles,
        "19/09": subsystems,
        "19/04": subsystems,
        "0E/07": indexes,
        "0E/91": indexes,
        "19/CE": lda,
        "19/C2": spool,
        "18/A0": jmq,
        "19/15": panels,
        "19/08": edits,
    }
    model = Guided5250(
        inventory,
        capability_loader=lambda obj, sample=None: services[obj.type_code].rows(obj),
        gss_loader=gss.rows,
        alert_loader=alerts.rows,
        message_loader=messages.rows,
        printer_queue_loader=printer_queues.rows,
        outq_loader=outq.rows,
        subsystem_loader=subsystems.rows,
        archival_index_loader=indexes.rows,
        lda_loader=lda.rows,
        jmq_loader=jmq.rows,
        panel_group_loader=panels.rows,
    )
    return services, model


def _candidate_detail(row):
    request = row.get("request", {})
    if row.get("kind") in DETAIL_ACTIONS:
        return (request.get("entry") is not None or
                request.get("symbol") is not None or
                request.get("slot") is not None or
                row.get("name") == "Saved queue-index keys")
    # A recovered same-name related object must retain an exact origin.
    return row.get("object") is not None


def _run_ui_walkthrough(model, obj, command, arg):
    """Exercise command search, exact selected origin, detail and Back."""
    model.run_command(f"{command} {arg}(*ALL/*)")
    if model.screen == "type_objects":
        found = next((i for i, row in enumerate(model.rows())
                      if row.get("object") is obj), None)
        if found is None:
            return "selection_missing"
        model.selected = found
        model.open_row(found)
    if model.screen != "capabilities":
        return "view_not_open"
    rows = model.rows()
    if not rows or rows[0]["name"] in ("Unavailable", "Identity unavailable"):
        return "withheld"
    detail = next((i for i, row in enumerate(rows) if
                   _candidate_detail(row)), None)
    if detail is not None:
        model.selected = detail
        if not model.open_row(detail):
            return "detail_not_open"
        if model.screen not in ("capabilities", "config_info", "details"):
            return "detail_not_open"
        model.back()
        if model.selected != detail:
            return "back_selection_lost"
        return "detail_back_ok"
    return "summary_ok"


def assess(image, inventory, segments=None):
    """Summarize all family origins with one reusable recovered-image model."""
    services, model = make_model(image, inventory, segments)
    by_type = {}
    for type_code, command, argument in WORKFLOWS:
        objects = [o for o in inventory.objects if o.type_code == type_code]
        stats = Counter()
        stats["recovered_primaries"] = len(objects)
        first_supported = None
        for obj in objects:
            try:
                rows = services[type_code].rows(obj)
            except (OSError, ValueError):
                stats["withheld_or_unavailable"] += 1
                continue
            if not rows or rows[0]["name"] == "Unavailable":
                stats["withheld_or_unavailable"] += 1
                continue
            stats["bounded_views"] += 1
            if any(_candidate_detail(r) for r in rows):
                stats["views_with_navigable_candidates"] += 1
            if first_supported is None:
                first_supported = obj
        if first_supported is None:
            stats["ui_walkthroughs_not_possible"] += 1
        else:
            outcome = _run_ui_walkthrough(
                model, first_supported, command, argument)
            stats["ui_" + outcome] += 1
            if outcome not in ("summary_ok", "detail_back_ok"):
                # Fail the acceptance run on actual navigation breakage, but
                # not on legitimately unsupported original-image structures.
                raise ValueError(f"{type_code}: Guided navigation failed ({outcome})")
        by_type[type_code] = {
            "command": command,
            "counts": dict(sorted(stats.items())),
        }
    return by_type


def validate(path):
    before = digest(path)
    image = DASDImage(path)
    scan = image.scan()
    segments = image.recover_segments(scan)
    inventory = image.recover_objects(scan, segments)
    families = assess(image, inventory, segments)
    after = digest(path)
    if before != after:
        raise ValueError("Archived image SHA256 changed during read-only audit")
    return {
        "image_bytes": Path(path).stat().st_size,
        "sha256_unchanged": True,
        "sha256": after,
        "workflows": families,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Extracted original .hda, not ZIP")
    parser.add_argument("--output", type=Path, help="Optional aggregate-only JSON report")
    args = parser.parse_args()
    result = validate(args.image)
    report = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print("Read-only recent-workflow acceptance report written.")
    else:
        print(report, end="")
