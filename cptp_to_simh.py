#!/usr/bin/env python3
"""Convert COPYTAPE CPTP images to SIMH .tap format.

The old copytape utility stores whatever byte count the host tape driver
returns as one CPTP:BLK record. For the AS/400 QIC archives this can combine
many original 512-byte physical tape blocks into a single large CPTP block.
This converter splits each CPTP block back into fixed-size records (512 bytes
by default), preserves tape marks, and maps CPTP:EOT to the second terminal
tape mark that COPYTAPE consumed from the original tape.

Input files are never modified. Output files are created separately and are
not overwritten unless --force is specified.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


CPTP_PREFIX = b"CPTP:"
SIMH_TAPE_MARK = struct.pack("<I", 0)


@dataclass
class Stats:
    cptp_blocks: int = 0
    output_records: int = 0
    tape_marks: int = 0
    input_data_bytes: int = 0
    output_data_bytes: int = 0
    eot_seen: bool = False


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_exact(f, length: int, what: str) -> bytes:
    data = f.read(length)
    if len(data) != length:
        raise ValueError(
            f"Unexpected EOF while reading {what}: expected {length} bytes, "
            f"got {len(data)}"
        )
    return data


def write_simh_record(out, data: bytes) -> None:
    """Write one standard SIMH record, including odd-length padding."""
    length = len(data)
    header = struct.pack("<I", length)
    out.write(header)
    out.write(data)
    if length & 1:
        out.write(b"\x00")
    out.write(header)


def convert_cptp_to_simh(
    src: Path,
    dst: Path,
    block_size: int = 512,
    force: bool = False,
) -> Stats:
    if block_size <= 0:
        raise ValueError("block size must be greater than zero")
    if src.resolve() == dst.resolve():
        raise ValueError("input and output paths must be different")
    if dst.exists() and not force:
        raise FileExistsError(f"output already exists: {dst}")

    stats = Stats()
    mode = "wb" if force else "xb"

    try:
        with src.open("rb") as inp, dst.open(mode) as out:
            while True:
                offset = inp.tell()
                prefix = inp.read(5)

                if not prefix:
                    if not stats.eot_seen:
                        raise ValueError(
                            f"Unexpected EOF at input offset {offset}: "
                            "CPTP:EOT was not found"
                        )
                    break

                if prefix != CPTP_PREFIX:
                    raise ValueError(
                        f"Invalid CPTP header at input offset {offset}: "
                        f"expected {CPTP_PREFIX!r}, got {prefix!r}"
                    )

                kind = read_exact(inp, 4, "CPTP record type")

                if kind == b"BLK ":
                    digits = read_exact(inp, 7, "CPTP block length")
                    if digits[-1:] != b"\n" or not digits[:6].isdigit():
                        raise ValueError(
                            f"Malformed CPTP block header at input offset {offset}"
                        )
                    length = int(digits[:6])
                    payload = read_exact(inp, length, "CPTP block payload")
                    newline = read_exact(inp, 1, "CPTP block trailing newline")
                    if newline != b"\n":
                        raise ValueError(
                            f"Missing CPTP payload newline after block at input "
                            f"offset {offset}"
                        )
                    if length % block_size:
                        raise ValueError(
                            f"CPTP block at input offset {offset} has length "
                            f"{length}, which is not divisible by block size "
                            f"{block_size}"
                        )

                    stats.cptp_blocks += 1
                    stats.input_data_bytes += length

                    for pos in range(0, length, block_size):
                        record = payload[pos : pos + block_size]
                        write_simh_record(out, record)
                        stats.output_records += 1
                        stats.output_data_bytes += len(record)

                elif kind == b"MRK\n":
                    out.write(SIMH_TAPE_MARK)
                    stats.tape_marks += 1

                elif kind == b"EOT\n":
                    # COPYTAPE returns EOT when it reads the second consecutive
                    # physical tape mark. The first was already emitted as MRK,
                    # so one more SIMH tape mark reconstructs the original pair.
                    out.write(SIMH_TAPE_MARK)
                    stats.tape_marks += 1
                    stats.eot_seen = True

                    if inp.read(1):
                        raise ValueError(
                            f"Unexpected data after CPTP:EOT at input offset "
                            f"{inp.tell() - 1}"
                        )
                    break

                else:
                    raise ValueError(
                        f"Unknown CPTP record type {kind!r} at input offset {offset}"
                    )

    except Exception:
        # Never leave a misleading partial conversion behind.
        try:
            if dst.exists():
                dst.unlink()
        except OSError:
            pass
        raise

    return stats


def default_output_path(src: Path) -> Path:
    return src.with_name(src.stem + "-fixed.tap")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert COPYTAPE CPTP images to SIMH .tap, restoring fixed-size "
            "tape record boundaries. Input files are never modified."
        )
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="CPTP .img file(s)")
    parser.add_argument(
        "-o", "--output-dir", type=Path,
        help="directory for converted files (default: alongside each input)",
    )
    parser.add_argument(
        "-b", "--block-size", type=int, default=512,
        help="original physical tape block size (default: 512)",
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite existing output files",
    )
    parser.add_argument(
        "--no-hash", action="store_true", help="skip SHA-256 calculation",
    )
    args = parser.parse_args()

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    failed = False

    for src in args.inputs:
        if not src.is_file():
            print(f"ERROR: input file not found: {src}", file=sys.stderr)
            failed = True
            continue

        dst = (
            args.output_dir / (src.stem + "-fixed.tap")
            if args.output_dir
            else default_output_path(src)
        )

        print(f"Input : {src}")
        print(f"Output: {dst}")

        try:
            input_hash = None if args.no_hash else sha256_file(src)
            stats = convert_cptp_to_simh(
                src, dst, block_size=args.block_size, force=args.force
            )
            output_hash = None if args.no_hash else sha256_file(dst)

            print(f"  CPTP blocks:    {stats.cptp_blocks:,}")
            print(f"  SIMH records:   {stats.output_records:,}")
            print(f"  Tape marks:     {stats.tape_marks:,}")
            print(f"  Data bytes:     {stats.output_data_bytes:,}")
            print(f"  CPTP EOT found: {'yes' if stats.eot_seen else 'no'}")

            if input_hash:
                print(f"  Input SHA-256:  {input_hash}")
                print(f"  Output SHA-256: {output_hash}")
            print()

        except Exception as exc:
            print(f"ERROR: {exc}\n", file=sys.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
