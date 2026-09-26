#!/usr/bin/env python3

"""Tape-image parsers and converters used by Tape File Browser.

The module intentionally has no GTK dependency so its parsing/conversion logic
can be tested and used from command-line tools independently of the GUI.
"""

from __future__ import annotations

import hashlib
import os
import struct
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# SIMH .tap framing.
TMK = 0x00000000
EOM = 0xFFFFFFFF
GAP = 0xFFFFFFFE
ERR = 0x80000000
SIMH_MAX_RECORD = 0x00FFFFFF

# AWS/Hercules 6-byte block header flags.
AWS_NEWREC = 0x80
AWS_TAPEMARK = 0x40
AWS_ENDREC = 0x20
AWS_KNOWN_FLAGS = AWS_NEWREC | AWS_TAPEMARK | AWS_ENDREC
AWS_MAX_CHUNK = 0xFFFF


@dataclass
class TapeRecord:
    number: int
    image_offset: int
    data_offset: int
    length: int
    error: bool = False
    segments: tuple[tuple[int, int], ...] = field(default_factory=tuple, repr=False)


@dataclass
class TapeFile:
    number: int
    records: list[TapeRecord] = field(default_factory=list)
    total_bytes: int = 0
    errors: int = 0
    sizes: Counter = field(default_factory=Counter)


@dataclass(frozen=True)
class ConversionReport:
    source_path: str
    output_path: str
    source_format: str
    output_format: str
    files: int
    tape_marks: int
    records: int
    payload_bytes: int
    logical_sha256: str
    warnings: tuple[str, ...]
    verified: bool = True

    def summary(self) -> str:
        lines = [
            f"{self.source_format} -> {self.output_format}",
            f"{self.files:,} logical files, {self.tape_marks:,} tape marks, "
            f"{self.records:,} records, {self.payload_bytes:,} payload bytes",
            "Record structure verified; every record payload SHA-256 matched.",
            f"Logical tape SHA-256: {self.logical_sha256}",
        ]
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines)


class TapeImage:
    """Read-only logical view of a tape image."""

    format_name = "unknown"

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.files: list[TapeFile] = []
        self.tape_mark_count = 0
        self.eom_found = False
        self.gaps: list[int] = []
        self._scan()

    @property
    def total_records(self) -> int:
        return sum(len(tape_file.records) for tape_file in self.files)

    @property
    def total_errors(self) -> int:
        return sum(tape_file.errors for tape_file in self.files)

    @property
    def total_bytes(self) -> int:
        return sum(tape_file.total_bytes for tape_file in self.files)

    def _scan(self) -> None:
        raise NotImplementedError

    def read_record(self, record: TapeRecord) -> bytes:
        segments = record.segments or ((record.data_offset, record.length),)
        parts: list[bytes] = []
        total = 0
        with open(self.path, "rb") as handle:
            for data_offset, length in segments:
                handle.seek(data_offset)
                data = handle.read(length)
                if len(data) != length:
                    raise ValueError(
                        f"Could not read all {length} bytes of record {record.number}"
                    )
                parts.append(data)
                total += length

        if total != record.length:
            raise ValueError(
                f"Record {record.number} segment lengths total {total}, "
                f"expected {record.length}"
            )
        return b"".join(parts)

    def iter_events(self) -> Iterator[tuple[str, TapeRecord | None]]:
        """Yield logical records and tape marks in physical order."""
        for index, tape_file in enumerate(self.files):
            for record in tape_file.records:
                yield "record", record
            if index < self.tape_mark_count:
                yield "tapemark", None


class SimhTapeImage(TapeImage):
    """Read-only index of a SIMH .tap image."""

    format_name = "SIMH"

    def _scan(self) -> None:
        current = TapeFile(0)
        file_no = 0
        record_no = 0

        with open(self.path, "rb") as handle:
            while True:
                image_offset = handle.tell()
                raw = handle.read(4)

                if not raw:
                    if current.records:
                        self.files.append(current)
                    break

                if len(raw) != 4:
                    raise ValueError(
                        f"Truncated SIMH record header at image offset {image_offset}"
                    )

                word = struct.unpack("<I", raw)[0]

                if word == TMK:
                    self.files.append(current)
                    self.tape_mark_count += 1
                    file_no += 1
                    record_no = 0
                    current = TapeFile(file_no)
                    continue

                if word == EOM:
                    self.eom_found = True
                    if current.records:
                        self.files.append(current)
                    break

                if word == GAP:
                    self.gaps.append(image_offset)
                    continue

                error = bool(word & ERR)
                length = word & ~ERR
                if length > SIMH_MAX_RECORD:
                    raise ValueError(
                        f"Invalid SIMH record length {length} at image offset "
                        f"{image_offset}"
                    )

                data_offset = handle.tell()
                handle.seek(length, os.SEEK_CUR)
                if length & 1:
                    handle.seek(1, os.SEEK_CUR)

                trailer_offset = handle.tell()
                trailer_raw = handle.read(4)
                if len(trailer_raw) != 4:
                    raise ValueError(
                        f"Missing SIMH record trailer at image offset {trailer_offset}"
                    )

                trailer = struct.unpack("<I", trailer_raw)[0]
                if trailer != word:
                    raise ValueError(
                        "SIMH header/trailer mismatch at image offset "
                        f"{image_offset}: {word:08X} != {trailer:08X}"
                    )

                record_no += 1
                record = TapeRecord(
                    number=record_no,
                    image_offset=image_offset,
                    data_offset=data_offset,
                    length=length,
                    error=error,
                    segments=((data_offset, length),),
                )
                current.records.append(record)
                current.total_bytes += length
                current.sizes[length] += 1
                if error:
                    current.errors += 1


class AwsTapeImage(TapeImage):
    """Read-only index of AWS/Hercules tape images.

    AWS stores a six-byte little-endian header before every data chunk. The
    first and last chunks of a logical record are identified by NEWREC and
    ENDREC flags. Most tape images use one chunk per record, but this parser
    also accepts standard multi-chunk records.
    """

    format_name = "AWS"

    def _scan(self) -> None:
        current = TapeFile(0)
        file_no = 0
        record_no = 0
        expected_previous_length = 0

        pending_segments: list[tuple[int, int]] = []
        pending_length = 0
        pending_image_offset: int | None = None
        pending_data_offset: int | None = None

        with open(self.path, "rb") as handle:
            while True:
                image_offset = handle.tell()
                raw = handle.read(6)

                if not raw:
                    if pending_segments:
                        raise ValueError(
                            "AWS image ended in the middle of a multi-chunk record"
                        )
                    if current.records:
                        self.files.append(current)
                    break

                if len(raw) != 6:
                    raise ValueError(
                        f"Truncated AWS block header at image offset {image_offset}"
                    )

                current_length, previous_length, flags1, flags2 = struct.unpack(
                    "<HHBB", raw
                )

                if previous_length != expected_previous_length:
                    raise ValueError(
                        "AWS previous-block length mismatch at image offset "
                        f"{image_offset}: header says {previous_length}, "
                        f"expected {expected_previous_length}"
                    )

                if flags2 != 0:
                    raise ValueError(
                        f"Unsupported AWS flags2 value 0x{flags2:02X} at image "
                        f"offset {image_offset}"
                    )

                if flags1 & ~AWS_KNOWN_FLAGS:
                    raise ValueError(
                        f"Unsupported AWS flags1 value 0x{flags1:02X} at image "
                        f"offset {image_offset}"
                    )

                if flags1 & AWS_TAPEMARK:
                    if flags1 != AWS_TAPEMARK or current_length != 0:
                        raise ValueError(
                            f"Invalid AWS tape-mark header at image offset {image_offset}"
                        )
                    if pending_segments:
                        raise ValueError(
                            f"AWS tape mark interrupted a record at image offset "
                            f"{image_offset}"
                        )

                    self.files.append(current)
                    self.tape_mark_count += 1
                    file_no += 1
                    record_no = 0
                    current = TapeFile(file_no)
                    expected_previous_length = 0
                    continue

                is_new = bool(flags1 & AWS_NEWREC)
                is_end = bool(flags1 & AWS_ENDREC)

                if not pending_segments and not is_new:
                    raise ValueError(
                        f"AWS continuation chunk without NEWREC at image offset "
                        f"{image_offset}"
                    )
                if pending_segments and is_new:
                    raise ValueError(
                        f"AWS NEWREC encountered before ENDREC at image offset "
                        f"{image_offset}"
                    )

                data_offset = handle.tell()
                payload = handle.read(current_length)
                if len(payload) != current_length:
                    raise ValueError(
                        f"Truncated AWS data chunk at image offset {data_offset}: "
                        f"expected {current_length} bytes"
                    )

                if not pending_segments:
                    pending_image_offset = image_offset
                    pending_data_offset = data_offset

                pending_segments.append((data_offset, current_length))
                pending_length += current_length
                expected_previous_length = current_length

                if is_end:
                    record_no += 1
                    record = TapeRecord(
                        number=record_no,
                        image_offset=pending_image_offset
                        if pending_image_offset is not None
                        else image_offset,
                        data_offset=pending_data_offset
                        if pending_data_offset is not None
                        else data_offset,
                        length=pending_length,
                        error=False,
                        segments=tuple(pending_segments),
                    )
                    current.records.append(record)
                    current.total_bytes += pending_length
                    current.sizes[pending_length] += 1

                    pending_segments = []
                    pending_length = 0
                    pending_image_offset = None
                    pending_data_offset = None


def open_tape_image(path: str, format_hint: str | None = None) -> TapeImage:
    """Open a tape image by explicit hint, extension, or conservative probing."""
    path = str(Path(path).expanduser())
    hint = (format_hint or "").strip().lower()
    suffix = Path(path).suffix.lower()

    if hint in {"simh", "tap"} or (not hint and suffix == ".tap"):
        return SimhTapeImage(path)
    if hint in {"aws", "awstape"} or (
        not hint and suffix in {".aws", ".awstape"}
    ):
        return AwsTapeImage(path)
    if hint:
        raise ValueError(f"Unknown tape format hint: {format_hint}")

    errors = []
    for image_type in (SimhTapeImage, AwsTapeImage):
        try:
            return image_type(path)
        except Exception as exc:
            errors.append(f"{image_type.format_name}: {exc}")
    raise ValueError("Could not identify tape image format. " + " | ".join(errors))


def _target_format_from_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".tap":
        return "simh"
    if suffix in {".aws", ".awstape"}:
        return "aws"
    raise ValueError("Output filename must end in .tap, .aws, or .awstape")


def _atomic_output_path(output_path: str):
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    )
    return destination, temp


def _write_simh(source: TapeImage, output_path: str) -> list[str]:
    warnings: list[str] = []
    destination, temp = _atomic_output_path(output_path)
    try:
        with temp as handle:
            for event_type, record in source.iter_events():
                if event_type == "tapemark":
                    handle.write(struct.pack("<I", TMK))
                    continue

                assert record is not None
                data = source.read_record(record)
                if len(data) > SIMH_MAX_RECORD:
                    raise ValueError(
                        f"Record {record.number} is {len(data):,} bytes; SIMH .tap "
                        f"supports at most {SIMH_MAX_RECORD:,} bytes per record"
                    )
                if len(data) == 0:
                    raise ValueError(
                        "A zero-length AWS data record cannot be represented distinctly "
                        "from a SIMH tape mark"
                    )

                word = len(data) | (ERR if record.error else 0)
                handle.write(struct.pack("<I", word))
                handle.write(data)
                if len(data) & 1:
                    handle.write(b"\x00")
                handle.write(struct.pack("<I", word))

            if source.eom_found:
                handle.write(struct.pack("<I", EOM))

        os.replace(temp.name, destination)
    except Exception:
        try:
            os.unlink(temp.name)
        except FileNotFoundError:
            pass
        raise

    return warnings


def _write_aws(source: TapeImage, output_path: str) -> list[str]:
    warnings: list[str] = []
    if source.total_errors:
        warnings.append(
            f"{source.total_errors} SIMH error-record flag(s) cannot be represented "
            "in AWS metadata; payload bytes were preserved."
        )
    if source.gaps:
        warnings.append(
            f"{len(source.gaps)} SIMH gap marker(s) cannot be represented in AWS "
            "and were omitted."
        )

    large_records = sum(
        1
        for tape_file in source.files
        for record in tape_file.records
        if record.length > AWS_MAX_CHUNK
    )
    if large_records:
        warnings.append(
            f"{large_records} record(s) exceed 65,535 bytes and were written as "
            "standard multi-chunk AWS records."
        )

    destination, temp = _atomic_output_path(output_path)
    try:
        previous_chunk_length = 0
        with temp as handle:
            for event_type, record in source.iter_events():
                if event_type == "tapemark":
                    handle.write(
                        struct.pack(
                            "<HHBB",
                            0,
                            previous_chunk_length,
                            AWS_TAPEMARK,
                            0,
                        )
                    )
                    previous_chunk_length = 0
                    continue

                assert record is not None
                data = source.read_record(record)
                chunks = [
                    data[offset : offset + AWS_MAX_CHUNK]
                    for offset in range(0, len(data), AWS_MAX_CHUNK)
                ] or [b""]

                for index, chunk in enumerate(chunks):
                    flags = 0
                    if index == 0:
                        flags |= AWS_NEWREC
                    if index == len(chunks) - 1:
                        flags |= AWS_ENDREC
                    handle.write(
                        struct.pack(
                            "<HHBB",
                            len(chunk),
                            previous_chunk_length,
                            flags,
                            0,
                        )
                    )
                    handle.write(chunk)
                    previous_chunk_length = len(chunk)

        os.replace(temp.name, destination)
    except Exception:
        try:
            os.unlink(temp.name)
        except FileNotFoundError:
            pass
        raise

    return warnings


def _record_hash(image: TapeImage, record: TapeRecord) -> bytes:
    return hashlib.sha256(image.read_record(record)).digest()


def logical_sha256(image: TapeImage) -> str:
    """Hash logical records and tape marks, independent of container framing."""
    digest = hashlib.sha256()
    for event_type, record in image.iter_events():
        if event_type == "tapemark":
            digest.update(b"M")
            continue
        assert record is not None
        data = image.read_record(record)
        digest.update(b"R")
        digest.update(struct.pack("<Q", len(data)))
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def verify_logical_tapes(source: TapeImage, converted: TapeImage) -> None:
    """Verify structure, record lengths, and every record payload SHA-256."""
    if source.tape_mark_count != converted.tape_mark_count:
        raise ValueError(
            "Verification failed: tape-mark count differs "
            f"({source.tape_mark_count} != {converted.tape_mark_count})"
        )
    if len(source.files) != len(converted.files):
        raise ValueError(
            "Verification failed: logical file count differs "
            f"({len(source.files)} != {len(converted.files)})"
        )

    for file_index, (source_file, converted_file) in enumerate(
        zip(source.files, converted.files)
    ):
        if len(source_file.records) != len(converted_file.records):
            raise ValueError(
                f"Verification failed in file {file_index}: record count differs "
                f"({len(source_file.records)} != {len(converted_file.records)})"
            )

        for record_index, (source_record, converted_record) in enumerate(
            zip(source_file.records, converted_file.records), start=1
        ):
            if source_record.length != converted_record.length:
                raise ValueError(
                    f"Verification failed in file {file_index}, record {record_index}: "
                    f"length differs ({source_record.length} != "
                    f"{converted_record.length})"
                )
            if _record_hash(source, source_record) != _record_hash(
                converted, converted_record
            ):
                raise ValueError(
                    f"Verification failed in file {file_index}, record {record_index}: "
                    "payload SHA-256 differs"
                )


def convert_tape(
    source_path: str,
    output_path: str,
    target_format: str | None = None,
) -> ConversionReport:
    """Convert between SIMH and AWS and verify the logical result."""
    source_path = str(Path(source_path).expanduser())
    output_path = str(Path(output_path).expanduser())

    if os.path.abspath(source_path) == os.path.abspath(output_path):
        raise ValueError("Source and output paths must be different")

    source = open_tape_image(source_path)
    target = (target_format or _target_format_from_path(output_path)).lower()
    if target in {"tap", "simh"}:
        target = "simh"
        output_format_name = "SIMH"
    elif target in {"aws", "awstape"}:
        target = "aws"
        output_format_name = "AWS"
    else:
        raise ValueError(f"Unsupported target tape format: {target_format}")

    if source.format_name.lower() == output_format_name.lower():
        raise ValueError(
            f"Source is already {source.format_name}; choose the other output format"
        )

    if target == "simh":
        warnings = _write_simh(source, output_path)
    else:
        warnings = _write_aws(source, output_path)

    converted = open_tape_image(output_path, target)
    verify_logical_tapes(source, converted)

    return ConversionReport(
        source_path=os.path.abspath(source_path),
        output_path=os.path.abspath(output_path),
        source_format=source.format_name,
        output_format=converted.format_name,
        files=len(source.files),
        tape_marks=source.tape_mark_count,
        records=source.total_records,
        payload_bytes=source.total_bytes,
        logical_sha256=logical_sha256(source),
        warnings=tuple(warnings),
        verified=True,
    )
