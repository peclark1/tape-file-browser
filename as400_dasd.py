#!/usr/bin/env python3

"""Read-only exploratory parser for CISC AS/400 520-byte DASD images.

The initial milestone deliberately separates facts from hypotheses.  IBM CISC
AS/400 DASD sectors are modeled as an 8-byte storage-management header followed
by a 512-byte storage page.  The exact field packing inside the eight-byte
header is not assumed here; instead, the scanner evaluates a small set of
candidate six-byte virtual-address layouts and reports the strongest monotonic
pattern it finds.

Nothing in this module writes to a DASD image.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

SECTOR_SIZE = 520
HEADER_SIZE = 8
PAGE_SIZE = 512
KNOWN_B10_SHADOW_LOG_VADDR = 0x000083000000


@dataclass(frozen=True)
class Sector:
    lba: int
    header: bytes
    data: bytes

    @property
    def offset(self) -> int:
        return self.lba * SECTOR_SIZE


@dataclass(frozen=True)
class AddressLayout:
    """One candidate interpretation of a virtual address inside the header."""

    offset: int
    width: int
    byteorder: str
    stride: int

    def decode(self, header: bytes) -> int | None:
        end = self.offset + self.width
        if len(header) < end:
            return None
        raw = header[self.offset:end]
        if raw == b"\x00" * self.width or raw == b"\xff" * self.width:
            return None
        return int.from_bytes(raw, self.byteorder)

    @property
    def name(self) -> str:
        return (
            f"header[{self.offset}:{self.offset + self.width}] "
            f"{self.byteorder}-endian, stride 0x{self.stride:X}"
        )


@dataclass
class LayoutScore:
    layout: AddressLayout
    comparisons: int = 0
    matches: int = 0
    backwards: int = 0
    large_jumps: int = 0

    @property
    def ratio(self) -> float:
        if not self.comparisons:
            return 0.0
        return self.matches / self.comparisons

    @property
    def confidence(self) -> str:
        ratio = self.ratio
        if self.comparisons < 16:
            return "INSUFFICIENT"
        if ratio >= 0.90:
            return "VERY HIGH"
        if ratio >= 0.75:
            return "HIGH"
        if ratio >= 0.50:
            return "MEDIUM"
        if ratio >= 0.25:
            return "LOW"
        return "WEAK"


@dataclass(frozen=True)
class Region:
    kind: str
    start_lba: int
    end_lba: int
    address_start: int | None = None
    address_end: int | None = None

    @property
    def sector_count(self) -> int:
        return self.end_lba - self.start_lba + 1


@dataclass
class ScanResult:
    path: str
    sector_count: int
    scanned_sectors: int
    zero_headers: int
    ff_headers: int
    other_headers: int
    zero_payloads: int
    layout_scores: list[LayoutScore] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)

    @property
    def best_layout(self) -> LayoutScore | None:
        usable = [score for score in self.layout_scores if score.comparisons]
        if not usable:
            return None
        return max(usable, key=lambda score: (score.ratio, score.matches))

    @property
    def sequential_regions(self) -> list[Region]:
        return [region for region in self.regions if region.kind == "address-run"]

    @property
    def sectors_in_sequential_regions(self) -> int:
        return sum(region.sector_count for region in self.sequential_regions)


class DASDImage:
    """Read-only view of one raw 520-byte CISC AS/400 DASD image."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = os.path.abspath(os.fspath(Path(path).expanduser()))
        self.size = os.path.getsize(self.path)
        if self.size % SECTOR_SIZE:
            raise ValueError(
                f"{self.path}: size {self.size:,} is not divisible by "
                f"{SECTOR_SIZE}; not a raw 520-byte-sector image"
            )
        self.sector_count = self.size // SECTOR_SIZE

    def read_sector(self, lba: int) -> Sector:
        if lba < 0 or lba >= self.sector_count:
            raise ValueError(
                f"LBA {lba} is outside image range 0..{self.sector_count - 1}"
            )
        with open(self.path, "rb") as handle:
            handle.seek(lba * SECTOR_SIZE)
            raw = handle.read(SECTOR_SIZE)
        if len(raw) != SECTOR_SIZE:
            raise ValueError(f"Short read at LBA {lba}")
        return Sector(lba=lba, header=raw[:HEADER_SIZE], data=raw[HEADER_SIZE:])

    def iter_sectors(self, limit: int | None = None) -> Iterator[Sector]:
        count = self.sector_count if limit is None else min(limit, self.sector_count)
        with open(self.path, "rb") as handle:
            for lba in range(count):
                raw = handle.read(SECTOR_SIZE)
                if len(raw) != SECTOR_SIZE:
                    raise ValueError(f"Short read at LBA {lba}")
                yield Sector(lba=lba, header=raw[:HEADER_SIZE], data=raw[HEADER_SIZE:])

    @staticmethod
    def candidate_layouts() -> list[AddressLayout]:
        layouts: list[AddressLayout] = []
        # Direct 9404 documentation describes a six-byte virtual storage
        # address.  We do not yet know its exact placement in the eight-byte
        # sector header, so test all possible six-byte windows and both byte
        # orders.  CISC pages are 512 bytes, so test both page-number and
        # byte-address strides.
        for offset in (0, 1, 2):
            for byteorder in ("big", "little"):
                for stride in (1, PAGE_SIZE):
                    layouts.append(
                        AddressLayout(
                            offset=offset,
                            width=6,
                            byteorder=byteorder,
                            stride=stride,
                        )
                    )
        return layouts

    def scan(
        self,
        *,
        limit: int | None = None,
        min_run: int = 4,
    ) -> ScanResult:
        layouts = self.candidate_layouts()
        scores = [LayoutScore(layout=layout) for layout in layouts]
        previous: list[int | None] = [None] * len(layouts)

        zero_headers = 0
        ff_headers = 0
        other_headers = 0
        zero_payloads = 0
        scanned = 0

        for sector in self.iter_sectors(limit=limit):
            scanned += 1
            if sector.header == b"\x00" * HEADER_SIZE:
                zero_headers += 1
            elif sector.header == b"\xff" * HEADER_SIZE:
                ff_headers += 1
            else:
                other_headers += 1

            if sector.data == b"\x00" * PAGE_SIZE:
                zero_payloads += 1

            for index, score in enumerate(scores):
                value = score.layout.decode(sector.header)
                prev = previous[index]
                if value is not None and prev is not None:
                    score.comparisons += 1
                    delta = value - prev
                    if delta == score.layout.stride:
                        score.matches += 1
                    elif delta < 0:
                        score.backwards += 1
                    elif delta > score.layout.stride * 1024:
                        score.large_jumps += 1
                previous[index] = value

        result = ScanResult(
            path=self.path,
            sector_count=self.sector_count,
            scanned_sectors=scanned,
            zero_headers=zero_headers,
            ff_headers=ff_headers,
            other_headers=other_headers,
            zero_payloads=zero_payloads,
            layout_scores=scores,
        )

        best = result.best_layout
        if best is not None:
            result.regions = self._build_regions(
                best.layout, limit=limit, min_run=min_run
            )
        else:
            result.regions = self._special_regions(limit=limit)

        return result

    def _special_regions(self, *, limit: int | None = None) -> list[Region]:
        regions: list[Region] = []
        current_kind: str | None = None
        start = 0
        last = -1

        for sector in self.iter_sectors(limit=limit):
            if sector.header == b"\x00" * HEADER_SIZE:
                kind = "zero-header"
            elif sector.header == b"\xff" * HEADER_SIZE:
                kind = "ff-header"
            else:
                kind = "unclassified"

            if current_kind is None:
                current_kind = kind
                start = sector.lba
            elif kind != current_kind:
                regions.append(Region(current_kind, start, last))
                current_kind = kind
                start = sector.lba
            last = sector.lba

        if current_kind is not None:
            regions.append(Region(current_kind, start, last))
        return regions

    def _build_regions(
        self,
        layout: AddressLayout,
        *,
        limit: int | None,
        min_run: int,
    ) -> list[Region]:
        """Build physical regions using the strongest address hypothesis.

        A region is classified as an address-run only when at least min_run
        consecutive physical sectors have address values advancing by the
        selected stride.  Short or irregular stretches remain unclassified.
        """

        sectors = []
        for sector in self.iter_sectors(limit=limit):
            if sector.header == b"\x00" * HEADER_SIZE:
                kind = "zero-header"
                value = None
            elif sector.header == b"\xff" * HEADER_SIZE:
                kind = "ff-header"
                value = None
            else:
                kind = "other"
                value = layout.decode(sector.header)
            sectors.append((sector.lba, kind, value))

        if not sectors:
            return []

        provisional: list[Region] = []
        i = 0
        n = len(sectors)
        while i < n:
            lba, kind, value = sectors[i]
            if kind in ("zero-header", "ff-header"):
                j = i + 1
                while j < n and sectors[j][1] == kind:
                    j += 1
                provisional.append(Region(kind, lba, sectors[j - 1][0]))
                i = j
                continue

            # Measure a physical run whose decoded value advances by the
            # candidate stride one sector at a time.
            j = i + 1
            prev_value = value
            while j < n:
                next_lba, next_kind, next_value = sectors[j]
                if (
                    next_kind != "other"
                    or prev_value is None
                    or next_value is None
                    or next_value - prev_value != layout.stride
                ):
                    break
                prev_value = next_value
                j += 1

            run_length = j - i
            if run_length >= min_run and value is not None:
                provisional.append(
                    Region(
                        "address-run",
                        lba,
                        sectors[j - 1][0],
                        address_start=value,
                        address_end=sectors[j - 1][2],
                    )
                )
                i = j
            else:
                provisional.append(Region("unclassified", lba, lba))
                i += 1

        # Coalesce neighboring non-address regions of the same kind.  This
        # keeps reports manageable even when the address model is incomplete.
        merged: list[Region] = []
        for region in provisional:
            if (
                merged
                and region.kind != "address-run"
                and merged[-1].kind == region.kind
                and merged[-1].end_lba + 1 == region.start_lba
            ):
                prior = merged[-1]
                merged[-1] = Region(
                    kind=prior.kind,
                    start_lba=prior.start_lba,
                    end_lba=region.end_lba,
                )
            else:
                merged.append(region)
        return merged

    def find_virtual(
        self,
        address: int,
        layout: AddressLayout,
        *,
        limit: int | None = None,
    ) -> list[int]:
        matches: list[int] = []
        for sector in self.iter_sectors(limit=limit):
            if layout.decode(sector.header) == address:
                matches.append(sector.lba)
        return matches


def format_hex(data: bytes, *, width: int = 16, start_offset: int = 0) -> str:
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_part = " ".join(f"{byte:02X}" for byte in chunk)
        lines.append(f"{start_offset + offset:08X}  {hex_part}")
    return "\n".join(lines)


def ebcdic_preview(data: bytes, *, limit: int = 128) -> str:
    sample = data[:limit].decode("cp037", errors="replace")
    return "".join(ch if ch.isprintable() else "." for ch in sample)
