#!/usr/bin/env python3

"""Read-only exploratory parser for CISC AS/400 520-byte DASD images.

The physical facts are deliberately kept separate from interpretations that are
still being validated. A CISC sector is 520 bytes: an eight-byte storage-
management header followed by a 512-byte page.

The current implementation follows IBM's documented System/38 directory-
recovery model: find relative record zero, recognize aligned large-free-space
delimiter extents, collect aligned permanent-extent candidates, and treat all
remaining sectors as reclaimable during directory recovery.

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

# The same preassigned large-free-space delimiter is present in both the B10
# surviving disk and the independent single-disk V2R3 image.  IBM's System/38
# VMC documentation describes exactly this kind of preassigned virtual address
# on the first page of large unallocated extents.
FREE_SPACE_DELIMITER = bytes.fromhex("0000fc00000f0000")

# 9404 Service Guide: 64-KB shadow error log on the load-source disk.
KNOWN_B10_SHADOW_LOG_VADDR = 0x000083000000


@dataclass(frozen=True)
class SectorHeader:
    """Decoded view of an eight-byte CISC storage-management header.

    IBM documents the first five bytes as the virtual page address, followed by
    an indicators byte, one reserved byte, and a byte locating the first
    Machine Interface pointer in the page.

    Real-image evidence from two independent CISC AS/400 images shows:
      * the five-byte virtual-page field is the high five bytes of the
        48-bit page-aligned virtual address, so append one zero byte;
      * the low nibble of the indicators byte is log2(extent pages);
      * byte 6 is zero in every header examined so far.

    Other indicator/control bits remain intentionally unnamed until their
    semantics are independently documented or validated.
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
    def virtual_page_prefix(self) -> int:
        return int.from_bytes(self.raw[0:5], "big")

    @property
    def virtual_address(self) -> int:
        return self.virtual_page_prefix << 8

    @property
    def page_aligned(self) -> bool:
        # A 512-byte CISC page requires bit 8 of the byte address to be zero.
        # Because the low byte is omitted from the five-byte header field, that
        # means the low bit of the stored prefix must be zero.
        return (self.virtual_page_prefix & 1) == 0

    @property
    def extent_order(self) -> int:
        return self.raw[5] & 0x0F

    @property
    def extent_pages(self) -> int:
        return 1 << self.extent_order

    @property
    def indicator_flags(self) -> int:
        return self.raw[5] & 0xF0

    @property
    def reserved_byte(self) -> int:
        return self.raw[6]

    @property
    def pointer_control(self) -> int:
        return self.raw[7]

    @property
    def pointer_field_c(self) -> int:
        # IBM VMC documentation describes the final five bits as field C when
        # the pointer indicator is active.
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
    delimiter_header: bytes
    extent_pages: int
    delimiter_occurrences: tuple[int, ...]
    supporting_large_extents: int

    @property
    def confidence(self) -> str:
        if (
            len(self.delimiter_occurrences) >= 2
            or self.supporting_large_extents >= 4
        ):
            return "VERY HIGH"
        if self.delimiter_occurrences and self.supporting_large_extents >= 1:
            return "HIGH"
        return "MEDIUM"


@dataclass(frozen=True)
class Extent:
    start_lba: int
    pages: int
    kind: str
    header: bytes
    virtual_address: int | None = None
    validation: str = ""

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
    free_delimiter_extents: list[Extent] = field(default_factory=list)
    permanent_candidates: list[Extent] = field(default_factory=list)
    reclaimable_regions: list[Region] = field(default_factory=list)
    virtual_chains: list[VirtualChain] = field(default_factory=list)

    @property
    def managed_sectors(self) -> int:
        if self.origin is None:
            return 0
        return self.sector_count - self.origin.lba

    @property
    def explicit_free_pages(self) -> int:
        return sum(extent.pages for extent in self.free_delimiter_extents)

    @property
    def permanent_candidate_pages(self) -> int:
        return sum(extent.pages for extent in self.permanent_candidates)

    @property
    def reclaimable_pages(self) -> int:
        return sum(region.sector_count for region in self.reclaimable_regions)

    @property
    def structured_pages(self) -> int:
        return self.explicit_free_pages + self.permanent_candidate_pages

    @property
    def structured_ratio(self) -> float:
        if not self.managed_sectors:
            return 0.0
        return self.structured_pages / self.managed_sectors

    @property
    def extent_size_histogram(self) -> Counter:
        return Counter(extent.pages for extent in self.permanent_candidates)

    def resolve_virtual(self, address: int) -> Extent | None:
        for extent in self.permanent_candidates:
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

    def count_nonzero_payloads(self, start_lba: int, count: int) -> int:
        if start_lba < 0 or start_lba >= self.sector_count:
            raise ValueError(
                f"LBA {start_lba} is outside image range "
                f"0..{self.sector_count - 1}"
            )
        count = min(count, self.sector_count - start_lba)
        nonzero = 0
        with open(self.path, "rb") as handle:
            handle.seek(start_lba * SECTOR_SIZE)
            for _ in range(count):
                raw = handle.read(SECTOR_SIZE)
                if len(raw) != SECTOR_SIZE:
                    break
                if raw[HEADER_SIZE:] != b"\x00" * PAGE_SIZE:
                    nonzero += 1
        return nonzero


def _header_at(header_bytes: bytes, lba: int) -> bytes:
    start = lba * HEADER_SIZE
    return header_bytes[start : start + HEADER_SIZE]


def _second_page_valid(
    header_bytes: bytes,
    *,
    lba: int,
    header: SectorHeader,
    sector_count: int,
) -> bool:
    if header.extent_pages == 1:
        return True
    if lba + 1 >= sector_count:
        return False

    second_raw = _header_at(header_bytes, lba + 1)
    if second_raw in (ZERO_HEADER, FF_HEADER):
        return False

    second = SectorHeader(second_raw)
    return (
        second.page_aligned
        and second.extent_order == header.extent_order
        and second.virtual_address == header.virtual_address + PAGE_SIZE
    )


def _count_supporting_large_extents(
    header_bytes: bytes,
    *,
    origin: int,
    min_pages: int = 128,
) -> int:
    sector_count = len(header_bytes) // HEADER_SIZE
    support = 0

    for lba in range(origin, sector_count):
        raw = _header_at(header_bytes, lba)
        if raw in (ZERO_HEADER, FF_HEADER, FREE_SPACE_DELIMITER):
            continue

        header = SectorHeader(raw)
        pages = header.extent_pages
        if (
            pages < min_pages
            or not header.page_aligned
            or lba + pages > sector_count
            or (lba - origin) % pages
        ):
            continue

        if _second_page_valid(
            header_bytes,
            lba=lba,
            header=header,
            sector_count=sector_count,
        ):
            support += 1

    return support


def detect_storage_origin(header_bytes: bytes) -> OriginCandidate | None:
    """Infer relative-record zero from IBM's large-free-space delimiter.

    Directory recovery uses relative record numbers, not raw image LBAs.  The
    same order-15 preassigned free-space delimiter appears in both independent
    CISC images.  Its physical LBA modulo 32768 directly reveals the relative
    record zero offset:
      B10 surviving disk -> 2112
      one-disk V2R3 image -> 64

    Multiple occurrences must agree on the same residue.  Large independently
    validated extents are counted as additional confidence evidence.
    """

    sector_count = len(header_bytes) // HEADER_SIZE
    delimiter = SectorHeader(FREE_SPACE_DELIMITER)
    span = delimiter.extent_pages

    occurrences = [
        lba
        for lba in range(sector_count)
        if _header_at(header_bytes, lba) == FREE_SPACE_DELIMITER
    ]
    if not occurrences:
        return None

    residue_counts = Counter(lba % span for lba in occurrences)
    residue, _ = residue_counts.most_common(1)[0]
    matching = tuple(lba for lba in occurrences if lba % span == residue)
    support = _count_supporting_large_extents(
        header_bytes,
        origin=residue,
    )

    return OriginCandidate(
        lba=residue,
        delimiter_header=FREE_SPACE_DELIMITER,
        extent_pages=span,
        delimiter_occurrences=matching,
        supporting_large_extents=support,
    )


def _permanent_extent_candidate(
    header_bytes: bytes,
    *,
    lba: int,
    origin: int,
    sector_count: int,
) -> Extent | None:
    raw = _header_at(header_bytes, lba)
    if raw in (ZERO_HEADER, FF_HEADER, FREE_SPACE_DELIMITER):
        return None

    header = SectorHeader(raw)
    pages = header.extent_pages
    if (
        not header.page_aligned
        or lba + pages > sector_count
        or (lba - origin) % pages
    ):
        return None

    if pages == 1:
        # There is no second page available for the independent validation IBM
        # describes for multi-page extents. Keep these, but mark the weaker
        # evidence level so later stages can treat them conservatively.
        return Extent(
            start_lba=lba,
            pages=pages,
            kind="permanent-candidate",
            header=raw,
            virtual_address=header.virtual_address,
            validation="single-page/aligned",
        )

    if not _second_page_valid(
        header_bytes,
        lba=lba,
        header=header,
        sector_count=sector_count,
    ):
        return None

    return Extent(
        start_lba=lba,
        pages=pages,
        kind="permanent-candidate",
        header=raw,
        virtual_address=header.virtual_address,
        validation="aligned + second-page",
    )


def _build_virtual_chains(extents: list[Extent]) -> list[VirtualChain]:
    """Group candidate extents whose virtual ranges directly adjoin."""

    ordered = sorted(
        (
            extent
            for extent in extents
            if extent.virtual_address is not None
        ),
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
    zero_headers = 0
    ff_headers = 0
    other_headers = 0
    reserved_nonzero = 0

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
    permanent_extents: list[Extent] = []
    reclaimable: list[Region] = []
    reclaim_start: int | None = None
    lba = origin.lba

    def flush_reclaim(end_lba: int) -> None:
        nonlocal reclaim_start
        if reclaim_start is not None and end_lba >= reclaim_start:
            reclaimable.append(
                Region(
                    "reclaimable-by-recovery",
                    reclaim_start,
                    end_lba,
                )
            )
        reclaim_start = None

    while lba < sector_count:
        raw = _header_at(header_bytes, lba)

        if raw == FREE_SPACE_DELIMITER:
            header = SectorHeader(raw)
            pages = header.extent_pages
            if (
                (lba - origin.lba) % pages == 0
                and lba + pages <= sector_count
            ):
                flush_reclaim(lba - 1)
                free_extents.append(
                    Extent(
                        start_lba=lba,
                        pages=pages,
                        kind="large-free-delimiter",
                        header=raw,
                        virtual_address=None,
                        validation="aligned delimiter",
                    )
                )
                lba += pages
                continue

        candidate = _permanent_extent_candidate(
            header_bytes,
            lba=lba,
            origin=origin.lba,
            sector_count=sector_count,
        )
        if candidate is not None:
            flush_reclaim(lba - 1)
            permanent_extents.append(candidate)
            lba += candidate.pages
            continue

        if reclaim_start is None:
            reclaim_start = lba
        lba += 1

    flush_reclaim(sector_count - 1)

    result.free_delimiter_extents = free_extents
    result.permanent_candidates = permanent_extents
    result.reclaimable_regions = reclaimable
    result.virtual_chains = _build_virtual_chains(permanent_extents)
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
