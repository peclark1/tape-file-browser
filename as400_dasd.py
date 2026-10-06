#!/usr/bin/env python3

"""Read-only exploratory parser for CISC AS/400 520-byte DASD images.

The physical facts are deliberately kept separate from interpretations that are
still being validated. A CISC sector is 520 bytes: an eight-byte storage-
management header followed by a 512-byte page. Real 9404/B10 data shows that
those headers are sufficient to recover a surprisingly large portion of the
physical/virtual extent map.

Nothing in this module writes to a DASD image.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

SECTOR_SIZE = 520
HEADER_SIZE = 8
PAGE_SIZE = 512
ZERO_HEADER = b"\x00" * HEADER_SIZE
FF_HEADER = b"\xff" * HEADER_SIZE
KNOWN_B10_SHADOW_LOG_VADDR = 0x000083000000


@dataclass(frozen=True)
class SectorHeader:
    """Decoded view of an eight-byte CISC storage-management header.

    IBM documentation describes a 39-bit virtual page identity in the header.
    The real B10 image strongly supports the first 40 bits being that 39-bit
    value plus one low-order status bit. The low-nibble extent-order decoding
    is likewise supported by aligned 1..32768-page extents in the real image.

    The semantics of the status bit and several flag bits remain intentionally
    unnamed until we have firmer documentation or another independent image.
    """

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != HEADER_SIZE:
            raise ValueError("sector header must be exactly 8 bytes")

    @property
    def is_zero(self) -> bool:
        return self.raw == ZERO_HEADER

    @property
    def is_ff(self) -> bool:
        return self.raw == FF_HEADER

    @property
    def page_word(self) -> int:
        return int.from_bytes(self.raw[0:5], "big")

    @property
    def virtual_page_number(self) -> int:
        # 40 stored bits -> 39 page-address bits + one low status bit.
        return self.page_word >> 1

    @property
    def page_word_low_flag(self) -> int:
        return self.page_word & 1

    @property
    def virtual_address(self) -> int:
        # CISC pages are 512 bytes, so restore the nine byte-offset bits.
        return self.virtual_page_number << 9

    @property
    def extent_order(self) -> int:
        return self.raw[5] & 0x0F

    @property
    def extent_pages(self) -> int:
        return 1 << self.extent_order

    @property
    def extent_flag_bits(self) -> int:
        return self.raw[5] & 0xF0

    @property
    def reserved_byte(self) -> int:
        return self.raw[6]

    @property
    def pointer_control(self) -> int:
        return self.raw[7]

    @property
    def pointer_field_c(self) -> int:
        # IBM VMC documentation identifies the final five header bits as
        # field C when the pointer indicator is active.
        return self.raw[7] & 0x1F


@dataclass(frozen=True)
class Sector:
    lba: int
    header: SectorHeader
    data: bytes

    @property
    def offset(self) -> int:
        return self.lba * SECTOR_SIZE


@dataclass(frozen=True)
class OriginCandidate:
    lba: int
    header: bytes
    extent_order: int
    extent_pages: int
    repeats: int

    @property
    def confidence(self) -> str:
        if self.repeats >= 5 and self.extent_order >= 12:
            return "VERY HIGH"
        if self.repeats >= 3:
            return "HIGH"
        return "MEDIUM"


@dataclass(frozen=True)
class Extent:
    start_lba: int
    pages: int
    kind: str
    header: bytes
    virtual_address: int | None = None

    @property
    def end_lba(self) -> int:
        return self.start_lba + self.pages - 1

    @property
    def byte_length(self) -> int:
        return self.pages * PAGE_SIZE

    @property
    def virtual_end(self) -> int | None:
        if self.virtual_address is None:
            return None
        return self.virtual_address + self.byte_length - 1


@dataclass(frozen=True)
class Region:
    kind: str
    start_lba: int
    end_lba: int
    virtual_address: int | None = None

    @property
    def sector_count(self) -> int:
        return self.end_lba - self.start_lba + 1


@dataclass(frozen=True)
class VirtualChain:
    extents: tuple[Extent, ...]

    @property
    def virtual_address(self) -> int:
        return self.extents[0].virtual_address or 0

    @property
    def pages(self) -> int:
        return sum(extent.pages for extent in self.extents)

    @property
    def byte_length(self) -> int:
        return self.pages * PAGE_SIZE

    @property
    def virtual_end(self) -> int:
        return self.virtual_address + self.byte_length - 1


@dataclass
class ScanResult:
    path: str
    sector_count: int
    zero_headers: int
    ff_headers: int
    other_headers: int
    zero_payloads: int | None
    reserved_nonzero_headers: int
    origin: OriginCandidate | None
    free_extents: list[Extent] = field(default_factory=list)
    allocated_extents: list[Extent] = field(default_factory=list)
    gaps: list[Region] = field(default_factory=list)
    virtual_chains: list[VirtualChain] = field(default_factory=list)

    @property
    def managed_sectors(self) -> int:
        if self.origin is None:
            return 0
        return self.sector_count - self.origin.lba

    @property
    def free_pages(self) -> int:
        return sum(extent.pages for extent in self.free_extents)

    @property
    def allocated_pages(self) -> int:
        return sum(extent.pages for extent in self.allocated_extents)

    @property
    def recognized_pages(self) -> int:
        return self.free_pages + self.allocated_pages

    @property
    def unresolved_pages(self) -> int:
        return sum(region.sector_count for region in self.gaps)

    @property
    def recognized_ratio(self) -> float:
        if not self.managed_sectors:
            return 0.0
        return self.recognized_pages / self.managed_sectors

    @property
    def extent_size_histogram(self) -> Counter:
        return Counter(extent.pages for extent in self.allocated_extents)

    def resolve_virtual(self, address: int) -> Extent | None:
        for extent in self.allocated_extents:
            if extent.virtual_address is None:
                continue
            if extent.virtual_address <= address <= extent.virtual_end:
                return extent
        return None


class HeaderSnapshot:
    """Analyze an 8-bytes-per-sector metadata snapshot without page payloads."""

    def __init__(self, header_bytes: bytes, *, name: str = "header snapshot"):
        if len(header_bytes) % HEADER_SIZE:
            raise ValueError("header snapshot size is not divisible by 8")
        self.name = name
        self._headers = header_bytes
        self.sector_count = len(header_bytes) // HEADER_SIZE

    def header_bytes(self, lba: int) -> bytes:
        if lba < 0 or lba >= self.sector_count:
            raise ValueError(f"LBA {lba} outside 0..{self.sector_count - 1}")
        offset = lba * HEADER_SIZE
        return self._headers[offset : offset + HEADER_SIZE]

    def iter_header_bytes(self) -> Iterator[bytes]:
        for offset in range(0, len(self._headers), HEADER_SIZE):
            yield self._headers[offset : offset + HEADER_SIZE]

    def scan(self) -> ScanResult:
        return analyze_headers(
            self._headers,
            path=self.name,
            zero_payloads=None,
        )


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
        return Sector(
            lba=lba,
            header=SectorHeader(raw[:HEADER_SIZE]),
            data=raw[HEADER_SIZE:],
        )

    def iter_sectors(self) -> Iterator[Sector]:
        with open(self.path, "rb") as handle:
            for lba in range(self.sector_count):
                raw = handle.read(SECTOR_SIZE)
                if len(raw) != SECTOR_SIZE:
                    raise ValueError(f"Short read at LBA {lba}")
                yield Sector(
                    lba=lba,
                    header=SectorHeader(raw[:HEADER_SIZE]),
                    data=raw[HEADER_SIZE:],
                )

    def scan(self) -> ScanResult:
        headers = bytearray(self.sector_count * HEADER_SIZE)
        zero_payloads = 0
        with open(self.path, "rb") as handle:
            for lba in range(self.sector_count):
                raw = handle.read(SECTOR_SIZE)
                if len(raw) != SECTOR_SIZE:
                    raise ValueError(f"Short read at LBA {lba}")
                start = lba * HEADER_SIZE
                headers[start : start + HEADER_SIZE] = raw[:HEADER_SIZE]
                if raw[HEADER_SIZE:] == b"\x00" * PAGE_SIZE:
                    zero_payloads += 1
        return analyze_headers(
            bytes(headers),
            path=self.path,
            zero_payloads=zero_payloads,
        )


def _header_at(header_bytes: bytes, lba: int) -> bytes:
    start = lba * HEADER_SIZE
    return header_bytes[start : start + HEADER_SIZE]


def detect_storage_origin(header_bytes: bytes) -> OriginCandidate | None:
    """Find the strongest repeated, power-of-two-aligned delimiter pattern.

    The System/38 recovery description says large free extents are represented by
    a preassigned virtual-address delimiter. On the real B10 disk a distinctive
    order-15 header repeats every 32768 sectors seven times. We search for the
    same architectural pattern instead of hard-coding that LBA or byte string.
    """

    count = len(header_bytes) // HEADER_SIZE
    candidates: list[OriginCandidate] = []

    for lba in range(count):
        raw = _header_at(header_bytes, lba)
        if raw in (ZERO_HEADER, FF_HEADER):
            continue
        header = SectorHeader(raw)
        if header.extent_order < 8:
            continue
        span = header.extent_pages
        if lba + 2 * span >= count:
            continue
        if _header_at(header_bytes, lba + span) != raw:
            continue
        if _header_at(header_bytes, lba + 2 * span) != raw:
            continue
        repeats = 3
        while lba + repeats * span < count:
            if _header_at(header_bytes, lba + repeats * span) != raw:
                break
            repeats += 1
        candidates.append(
            OriginCandidate(
                lba=lba,
                header=raw,
                extent_order=header.extent_order,
                extent_pages=span,
                repeats=repeats,
            )
        )

    if not candidates:
        return None
    return max(
        candidates,
        key=lambda candidate: (
            candidate.repeats,
            candidate.extent_order,
            -candidate.lba,
        ),
    )


def _valid_extent_start(
    header_bytes: bytes,
    *,
    lba: int,
    origin: int,
    sector_count: int,
) -> Extent | None:
    raw = _header_at(header_bytes, lba)
    if raw in (ZERO_HEADER, FF_HEADER):
        return None
    header = SectorHeader(raw)
    pages = header.extent_pages
    if lba + pages > sector_count:
        return None
    if (lba - origin) % pages:
        return None

    address = header.virtual_address
    if pages > 1:
        second_raw = _header_at(header_bytes, lba + 1)
        if second_raw in (ZERO_HEADER, FF_HEADER):
            return None
        second = SectorHeader(second_raw)
        if second.extent_order != header.extent_order:
            return None
        if second.virtual_address != address + PAGE_SIZE:
            return None

    return Extent(
        start_lba=lba,
        pages=pages,
        kind="allocated-candidate",
        header=raw,
        virtual_address=address,
    )


def _build_virtual_chains(extents: list[Extent]) -> list[VirtualChain]:
    """Group extents with directly adjoining virtual address ranges.

    These are deliberately called candidate chains rather than object segments:
    duplicate/overlapping address metadata may need a more sophisticated second
    pass once permanent-directory formats are decoded.
    """

    ordered = sorted(
        (extent for extent in extents if extent.virtual_address is not None),
        key=lambda extent: (extent.virtual_address, extent.start_lba),
    )
    chains: list[VirtualChain] = []
    current: list[Extent] = []
    expected: int | None = None

    for extent in ordered:
        if current and extent.virtual_address == expected:
            current.append(extent)
        else:
            if current:
                chains.append(VirtualChain(tuple(current)))
            current = [extent]
        expected = extent.virtual_address + extent.byte_length

    if current:
        chains.append(VirtualChain(tuple(current)))
    return chains


def analyze_headers(
    header_bytes: bytes,
    *,
    path: str = "header snapshot",
    zero_payloads: int | None = None,
) -> ScanResult:
    if len(header_bytes) % HEADER_SIZE:
        raise ValueError("header data size is not divisible by 8")

    sector_count = len(header_bytes) // HEADER_SIZE
    zero_headers = ff_headers = other_headers = reserved_nonzero = 0
    for lba in range(sector_count):
        raw = _header_at(header_bytes, lba)
        if raw == ZERO_HEADER:
            zero_headers += 1
        elif raw == FF_HEADER:
            ff_headers += 1
        else:
            other_headers += 1
        if raw[6] != 0:
            reserved_nonzero += 1

    origin = detect_storage_origin(header_bytes)
    result = ScanResult(
        path=path,
        sector_count=sector_count,
        zero_headers=zero_headers,
        ff_headers=ff_headers,
        other_headers=other_headers,
        zero_payloads=zero_payloads,
        reserved_nonzero_headers=reserved_nonzero,
        origin=origin,
    )
    if origin is None:
        return result

    free_extents: list[Extent] = []
    allocated_extents: list[Extent] = []
    lba = origin.lba

    while lba < sector_count:
        raw = _header_at(header_bytes, lba)
        header = SectorHeader(raw)

        if raw == origin.header:
            pages = header.extent_pages
            if (lba - origin.lba) % pages == 0 and lba + pages <= sector_count:
                free_extents.append(
                    Extent(
                        start_lba=lba,
                        pages=pages,
                        kind="free-delimiter",
                        header=raw,
                        virtual_address=None,
                    )
                )
                lba += pages
                continue

        candidate = _valid_extent_start(
            header_bytes,
            lba=lba,
            origin=origin.lba,
            sector_count=sector_count,
        )
        if candidate is not None:
            allocated_extents.append(candidate)
            lba += candidate.pages
            continue
        lba += 1

    recognized = sorted(
        [*free_extents, *allocated_extents], key=lambda extent: extent.start_lba
    )
    gaps: list[Region] = []
    cursor = origin.lba
    for extent in recognized:
        if extent.start_lba > cursor:
            gaps.append(Region("unresolved", cursor, extent.start_lba - 1))
        cursor = max(cursor, extent.end_lba + 1)
    if cursor < sector_count:
        gaps.append(Region("unresolved", cursor, sector_count - 1))

    result.free_extents = free_extents
    result.allocated_extents = allocated_extents
    result.gaps = gaps
    result.virtual_chains = _build_virtual_chains(allocated_extents)
    return result


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
