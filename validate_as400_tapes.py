#!/usr/bin/env python3
"""Validate IBM AS/400 Standard Label tape images in SIMH/E11 .tap format.

The report is intentionally structural.  It verifies tape-image framing,
collects IBM VOL1/HDR1/HDR2/EOF1/EOF2/EOV1/EOV2 labels, summarizes datasets,
and checks EOV-to-HDR continuation across a multi-volume set.

No input file is ever modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import struct
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


TMK = 0x00000000
EOM = 0xFFFFFFFF
GAP = 0xFFFFFFFE
ERR = 0x80000000
LEN_MASK = 0x00FFFFFF

LABEL_TYPES = {
    "VOL1",
    "HDR1", "HDR2",
    "EOF1", "EOF2",
    "EOV1", "EOV2",
}


@dataclass
class Section:
    number: int
    records: int = 0
    bytes: int = 0


@dataclass
class Label:
    kind: str
    section: int
    record: int
    image_offset: int
    text: str
    fields: dict = field(default_factory=dict)


@dataclass
class Dataset:
    file_id: str
    header_section: int
    volume_serial: str = ""
    volume_sequence: str = ""
    file_sequence: str = ""
    generation: str = ""
    generation_version: str = ""
    creation_date: str = ""
    expiration_date: str = ""
    system_code: str = ""
    record_format: str = ""
    block_length: Optional[int] = None
    record_length: Optional[int] = None
    end_kind: str = ""
    end_section: Optional[int] = None
    label_block_count: str = ""
    data_records: int = 0
    data_bytes: int = 0


@dataclass
class TapeSummary:
    path: str
    format_name: str = "SIMH/E11 (only even-length records)"
    records: int = 0
    error_records: int = 0
    tape_marks: int = 0
    gap_markers: int = 0
    eom_found: bool = False
    logical_eot_found: bool = False
    first_double_mark_offset: Optional[int] = None
    trailing_bytes_after_eom: int = 0
    volume_serial: str = ""
    sections: list[Section] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    datasets: list[Dataset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def ebcdic_label(prefix: bytes) -> Optional[str]:
    """Return an 80-character CP037 label when this looks like an IBM label."""
    if len(prefix) < 4:
        return None
    text = prefix[:80].decode("cp037", errors="replace")
    if text[:4] not in LABEL_TYPES:
        return None
    return text.ljust(80)


def parse_label_fields(kind: str, text: str) -> dict:
    fields: dict = {}

    if kind == "VOL1":
        fields["volume_serial"] = text[4:10].strip()
        fields["accessibility"] = text[10:11]
        fields["owner"] = text[37:51].strip()
        return fields

    if kind in {"HDR1", "EOF1", "EOV1"}:
        fields.update(
            {
                "file_id": text[4:21].rstrip(),
                "volume_serial": text[21:27].strip(),
                "volume_sequence": text[27:31].strip(),
                "file_sequence": text[31:35].strip(),
                "generation": text[35:39].strip(),
                "generation_version": text[39:41].strip(),
                "creation_date": text[41:47].strip(),
                "expiration_date": text[47:53].strip(),
                "security": text[53:54].strip(),
                "block_count": text[54:60].strip(),
                "system_code": text[60:73].rstrip(),
            }
        )
        return fields

    if kind in {"HDR2", "EOF2", "EOV2"}:
        block_length = text[5:10].strip()
        record_length = text[10:15].strip()
        fields.update(
            {
                "record_format": text[4:5],
                "block_length": int(block_length) if block_length.isdigit() else None,
                "record_length": int(record_length) if record_length.isdigit() else None,
            }
        )
        return fields

    return fields


def scan_tape(path: Path) -> TapeSummary:
    summary = TapeSummary(path=str(path))
    current_section = Section(0)
    summary.sections.append(current_section)

    record_in_section = 0
    previous_was_mark = False
    tape_format: Optional[str] = None
    image_size = path.stat().st_size

    try:
        with path.open("rb") as f:
            while True:
                image_offset = f.tell()
                raw = f.read(4)

                if not raw:
                    break
                if len(raw) != 4:
                    raise ValueError(
                        f"truncated 4-byte header at image offset {image_offset}"
                    )

                word = struct.unpack("<I", raw)[0]

                if word == TMK:
                    summary.tape_marks += 1
                    if previous_was_mark and not summary.logical_eot_found:
                        summary.logical_eot_found = True
                        summary.first_double_mark_offset = image_offset

                    previous_was_mark = True
                    current_section = Section(len(summary.sections))
                    summary.sections.append(current_section)
                    record_in_section = 0
                    continue

                previous_was_mark = False

                if word == EOM:
                    summary.eom_found = True
                    summary.trailing_bytes_after_eom = max(0, image_size - f.tell())
                    break

                if word == GAP:
                    summary.gap_markers += 1
                    continue

                error = bool(word & ERR)
                length = word & LEN_MASK

                if length == 0:
                    raise ValueError(
                        f"invalid zero-length non-tape-mark record at {image_offset}"
                    )

                data_offset = f.tell()
                prefix_len = min(length, 80)
                prefix = f.read(prefix_len)
                if len(prefix) != prefix_len:
                    raise ValueError(
                        f"truncated record payload at image offset {image_offset}"
                    )
                remaining = length - prefix_len
                if remaining:
                    f.seek(remaining, os.SEEK_CUR)

                # SIMH pads odd-length records to an even boundary. E11 does not.
                # Auto-detect at the first odd-length record.
                if length & 1:
                    unpadded_trailer_offset = f.tell()

                    if tape_format == "SIMH":
                        f.seek(1, os.SEEK_CUR)
                        trailer_offset = f.tell()
                        trailer_raw = f.read(4)
                    elif tape_format == "E11":
                        trailer_offset = f.tell()
                        trailer_raw = f.read(4)
                    else:
                        trailer_offset = f.tell()
                        trailer_raw = f.read(4)
                        if len(trailer_raw) == 4 and struct.unpack("<I", trailer_raw)[0] == word:
                            tape_format = "E11"
                            summary.format_name = "E11"
                        else:
                            f.seek(unpadded_trailer_offset + 1)
                            trailer_offset = f.tell()
                            trailer_raw = f.read(4)
                            if (
                                len(trailer_raw) == 4
                                and struct.unpack("<I", trailer_raw)[0] == word
                            ):
                                tape_format = "SIMH"
                                summary.format_name = "SIMH"
                            else:
                                raise ValueError(
                                    "could not identify SIMH/E11 framing for "
                                    f"odd-length record at image offset {image_offset} "
                                    f"(length {length})"
                                )
                else:
                    trailer_offset = f.tell()
                    trailer_raw = f.read(4)

                if len(trailer_raw) != 4:
                    raise ValueError(
                        f"missing record trailer at image offset {trailer_offset}"
                    )

                trailer = struct.unpack("<I", trailer_raw)[0]
                if trailer != word:
                    raise ValueError(
                        f"header/trailer mismatch at image offset {image_offset}: "
                        f"{word:08X} != {trailer:08X}"
                    )

                summary.records += 1
                if error:
                    summary.error_records += 1
                current_section.records += 1
                current_section.bytes += length
                record_in_section += 1

                label_text = ebcdic_label(prefix)
                if label_text is not None:
                    kind = label_text[:4]
                    summary.labels.append(
                        Label(
                            kind=kind,
                            section=current_section.number,
                            record=record_in_section,
                            image_offset=image_offset,
                            text=label_text,
                            fields=parse_label_fields(kind, label_text),
                        )
                    )

    except Exception as exc:
        summary.errors.append(str(exc))

    # Drop a purely artificial final section only when the image ended directly
    # after a tape mark and there was no need to represent it for reporting.
    # Keep empty sections in the middle; they represent consecutive tape marks.
    while (
        len(summary.sections) > 1
        and summary.sections[-1].records == 0
        and not summary.logical_eot_found
    ):
        summary.sections.pop()

    if tape_format is None:
        summary.format_name = "SIMH/E11 (only even-length records)"

    build_datasets(summary)
    validate_label_pairs(summary)
    return summary


def build_datasets(summary: TapeSummary) -> None:
    open_dataset: Optional[Dataset] = None

    for i, label in enumerate(summary.labels):
        fields = label.fields

        if label.kind == "VOL1" and not summary.volume_serial:
            summary.volume_serial = fields.get("volume_serial", "")

        elif label.kind == "HDR1":
            if open_dataset is not None:
                summary.warnings.append(
                    f"HDR1 for {fields.get('file_id', '?')} encountered before "
                    f"{open_dataset.file_id} was closed"
                )

            ds = Dataset(
                file_id=fields.get("file_id", ""),
                header_section=label.section,
                volume_serial=fields.get("volume_serial", ""),
                volume_sequence=fields.get("volume_sequence", ""),
                file_sequence=fields.get("file_sequence", ""),
                generation=fields.get("generation", ""),
                generation_version=fields.get("generation_version", ""),
                creation_date=fields.get("creation_date", ""),
                expiration_date=fields.get("expiration_date", ""),
                system_code=fields.get("system_code", ""),
            )

            if i + 1 < len(summary.labels):
                next_label = summary.labels[i + 1]
                if next_label.kind == "HDR2" and next_label.section == label.section:
                    ds.record_format = next_label.fields.get("record_format", "")
                    ds.block_length = next_label.fields.get("block_length")
                    ds.record_length = next_label.fields.get("record_length")

            summary.datasets.append(ds)
            open_dataset = ds

        elif label.kind in {"EOF1", "EOV1"}:
            file_id = fields.get("file_id", "")
            if open_dataset is None:
                summary.warnings.append(
                    f"{label.kind} for {file_id or '?'} has no open HDR1"
                )
                continue

            if file_id and open_dataset.file_id and file_id != open_dataset.file_id:
                summary.warnings.append(
                    f"{label.kind} file id {file_id} does not match open "
                    f"HDR1 {open_dataset.file_id}"
                )

            open_dataset.end_kind = label.kind[:3]  # EOF or EOV
            open_dataset.end_section = label.section
            open_dataset.label_block_count = fields.get("block_count", "")

            # Data is everything in sections strictly between the header-label
            # section and the EOF/EOV-label section.
            for section in summary.sections:
                if (
                    open_dataset.header_section < section.number < label.section
                ):
                    open_dataset.data_records += section.records
                    open_dataset.data_bytes += section.bytes

            open_dataset = None

    if open_dataset is not None:
        summary.warnings.append(
            f"dataset {open_dataset.file_id} has HDR1 but no EOF1/EOV1"
        )


def validate_label_pairs(summary: TapeSummary) -> None:
    by_section: dict[int, list[Label]] = {}
    for label in summary.labels:
        by_section.setdefault(label.section, []).append(label)

    for section_no, labels in by_section.items():
        kinds = [label.kind for label in labels]

        for first, second in (("HDR1", "HDR2"), ("EOF1", "EOF2"), ("EOV1", "EOV2")):
            if first in kinds and second not in kinds:
                summary.warnings.append(
                    f"section {section_no}: {first} present without {second}"
                )

    if not any(label.kind == "VOL1" for label in summary.labels):
        summary.warnings.append("no VOL1 label found")

    if not summary.logical_eot_found:
        summary.warnings.append("no terminal/consecutive tape marks detected")


def numeric_increment(a: str, b: str) -> Optional[bool]:
    if a.isdigit() and b.isdigit():
        return int(b) == int(a) + 1
    return None


def cross_volume_report(summaries: list[TapeSummary]) -> list[dict]:
    checks: list[dict] = []

    for left, right in zip(summaries, summaries[1:]):
        check = {
            "from": left.path,
            "to": right.path,
            "status": "INFO",
            "message": "",
        }

        if not left.datasets:
            check["status"] = "FAIL"
            check["message"] = "previous volume has no datasets"
            checks.append(check)
            continue

        last = left.datasets[-1]
        if last.end_kind != "EOV":
            check["status"] = "INFO"
            check["message"] = (
                f"{last.file_id or '?'} ends with {last.end_kind or 'no end label'}; "
                "no continuation required"
            )
            checks.append(check)
            continue

        if not right.datasets:
            check["status"] = "FAIL"
            check["message"] = (
                f"{last.file_id} ends EOV, but next volume has no HDR1 dataset"
            )
            checks.append(check)
            continue

        first = right.datasets[0]
        problems = []

        if first.file_id != last.file_id:
            problems.append(f"file id {last.file_id} -> {first.file_id}")

        if (
            last.file_sequence
            and first.file_sequence
            and last.file_sequence != first.file_sequence
        ):
            problems.append(
                f"file sequence {last.file_sequence} -> {first.file_sequence}"
            )

        if (
            last.generation
            and first.generation
            and last.generation != first.generation
        ):
            problems.append(
                f"generation {last.generation} -> {first.generation}"
            )

        if (
            last.generation_version
            and first.generation_version
            and last.generation_version != first.generation_version
        ):
            problems.append(
                "generation version "
                f"{last.generation_version} -> {first.generation_version}"
            )

        inc = numeric_increment(last.volume_sequence, first.volume_sequence)
        if inc is False:
            problems.append(
                f"volume sequence {last.volume_sequence} -> "
                f"{first.volume_sequence} (expected +1)"
            )

        if problems:
            check["status"] = "FAIL"
            check["message"] = "; ".join(problems)
        else:
            check["status"] = "PASS"
            seq_text = ""
            if last.volume_sequence or first.volume_sequence:
                seq_text = (
                    f", volume sequence {last.volume_sequence or '?'}"
                    f"->{first.volume_sequence or '?'}"
                )
            check["message"] = (
                f"{last.file_id} continues correctly{seq_text}"
            )

        checks.append(check)

    if summaries and summaries[-1].datasets:
        last_ds = summaries[-1].datasets[-1]
        checks.append(
            {
                "from": summaries[-1].path,
                "to": "",
                "status": "WARN" if last_ds.end_kind == "EOV" else "PASS",
                "message": (
                    f"final volume still ends EOV for {last_ds.file_id}; "
                    "another volume appears to be required"
                    if last_ds.end_kind == "EOV"
                    else f"final dataset {last_ds.file_id} ends {last_ds.end_kind or 'without end label'}"
                ),
            }
        )

    return checks


def print_summary(summary: TapeSummary) -> None:
    name = Path(summary.path).name
    print(f"\n{name}")
    print("-" * len(name))
    print(
        f"Format: {summary.format_name}  |  Volume: "
        f"{summary.volume_serial or '?'}"
    )
    print(
        f"Records: {summary.records:,}  |  Tape marks: {summary.tape_marks:,}  |  "
        f"Sections: {len(summary.sections):,}  |  Error records: "
        f"{summary.error_records:,}"
    )
    print(
        f"Logical EOT (double mark): "
        f"{'yes' if summary.logical_eot_found else 'NO'}"
        f"  |  EOM marker: {'yes' if summary.eom_found else 'no'}"
    )

    if summary.datasets:
        print("Datasets:")
        for ds in summary.datasets:
            end = ds.end_kind or "OPEN"
            seq = (
                f"volseq={ds.volume_sequence or '?'} "
                f"fileseq={ds.file_sequence or '?'}"
            )
            fmt = ""
            if ds.record_format or ds.block_length is not None:
                fmt = (
                    f"  {ds.record_format or '?'}"
                    f"/{ds.block_length if ds.block_length is not None else '?'}"
                )
            print(
                f"  {ds.file_id:<22} {seq:<24} "
                f"data={ds.data_records:>8,} rec / {ds.data_bytes:>12,} B  "
                f"end={end}{fmt}"
            )
    else:
        print("Datasets: none recognized")

    for warning in summary.warnings:
        print(f"  WARNING: {warning}")
    for error in summary.errors:
        print(f"  ERROR: {error}")


def write_csv(path: Path, summaries: list[TapeSummary]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "image",
                "volume_serial",
                "file_id",
                "volume_sequence",
                "file_sequence",
                "generation",
                "generation_version",
                "record_format",
                "block_length",
                "record_length",
                "data_records",
                "data_bytes",
                "end_kind",
                "label_block_count",
            ]
        )
        for summary in summaries:
            for ds in summary.datasets:
                writer.writerow(
                    [
                        summary.path,
                        summary.volume_serial,
                        ds.file_id,
                        ds.volume_sequence,
                        ds.file_sequence,
                        ds.generation,
                        ds.generation_version,
                        ds.record_format,
                        ds.block_length,
                        ds.record_length,
                        ds.data_records,
                        ds.data_bytes,
                        ds.end_kind,
                        ds.label_block_count,
                    ]
                )


def write_json(
    path: Path, summaries: list[TapeSummary], cross_checks: list[dict]
) -> None:
    payload = {
        "tapes": [asdict(summary) for summary in summaries],
        "cross_volume_checks": cross_checks,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate IBM AS/400 Standard Label structure in SIMH/E11 .tap "
            "images and check multi-volume EOV/HDR continuation."
        )
    )
    parser.add_argument(
        "images",
        nargs="+",
        type=Path,
        help="tape images in volume order",
    )
    parser.add_argument("--csv", type=Path, help="also write dataset summary CSV")
    parser.add_argument("--json", type=Path, help="also write full JSON report")
    args = parser.parse_args()

    summaries = [scan_tape(path) for path in args.images]

    for summary in summaries:
        print_summary(summary)

    checks = cross_volume_report(summaries)
    if checks:
        print("\nCross-volume continuity")
        print("-----------------------")
        for check in checks:
            src = Path(check["from"]).name
            dst = Path(check["to"]).name if check["to"] else ""
            arrow = f" -> {dst}" if dst else ""
            print(
                f"{check['status']:<4}  {src}{arrow}: {check['message']}"
            )

    if args.csv:
        write_csv(args.csv, summaries)
        print(f"\nWrote CSV: {args.csv}")

    if args.json:
        write_json(args.json, summaries, checks)
        print(f"Wrote JSON: {args.json}")

    any_errors = any(summary.errors for summary in summaries)
    any_failed_chain = any(check["status"] == "FAIL" for check in checks)
    return 1 if any_errors or any_failed_chain else 0


if __name__ == "__main__":
    raise SystemExit(main())
