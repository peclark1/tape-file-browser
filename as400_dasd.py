#!/usr/bin/env python3

"""Read-only exploratory parser for CISC AS/400 520-byte DASD images.

The physical facts are deliberately kept separate from interpretations that are
still being validated. A CISC sector is 520 bytes: an eight-byte storage-
management header followed by a 512-byte page.

The recovery path follows IBM's documented System/38 storage-management model:
find relative record zero, recognize aligned large-free-space delimiter extents,
collect aligned permanent-extent candidates, then reconstruct permanent segment
groups from those candidates.

For CISC AS/400 object discovery, the parser also recognizes the 32-byte
YYSGHDR segment header and the following EPA object header as they appear in the
two real images used by this project. Unknown flag bits remain deliberately
unlabeled.

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
SEGMENT_HEADER_SIZE = 32
EPA_MIN_SIZE = 0x58
ZERO_HEADER = b"\x00" * HEADER_SIZE
FF_HEADER = b"\xff" * HEADER_SIZE

# The same preassigned large-free-space delimiter is present in both the B10
# surviving disk and the independent single-disk V2R3 image. IBM's System/38
# VMC documentation describes exactly this kind of preassigned virtual address
# on the first page of large unallocated extents.
FREE_SPACE_DELIMITER = bytes.fromhex("0000fc00000f0000")

# 9404 Service Guide: 64-KB shadow error log on the load-source disk.
KNOWN_B10_SHADOW_LOG_VADDR = 0x000083000000


@dataclass(frozen=True)
class InternalAddress:
    """Eight-byte CISC internal address: 2-byte extender + 6-byte address."""

    extender: int
    address: int

    @classmethod
    def from_bytes(cls, raw: bytes) -> "InternalAddress":
        if len(raw) != 8:
            raise ValueError("internal address must be exactly 8 bytes")
        return cls(
            extender=int.from_bytes(raw[:2], "big"),
            address=int.from_bytes(raw[2:], "big"),
        )

    @property
    def is_null(self) -> bool:
        return self.extender == 0 and self.address == 0

    @property
    def key(self) -> tuple[int, int]:
        return self.extender, self.address

    def __str__(self) -> str:
        return f"{self.extender:04X}:{self.address:012X}"


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

    @property
    def key(self) -> tuple[int, int, int]:
        return self.start_lba, self.virtual_address or -1, self.pages


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


@dataclass(frozen=True)
class SegmentGroupHeader:
    """32-byte AS/400 segment-group header (YYSGHDR).

    The AS/400 dump layout observed in both real CISC images uses a 16-bit
    segment type, 16-bit page count, flag/domain fields, an 8-byte owning-object
    address, and an 8-byte space address. This is the layout shown by IBM dump
    formatting on later systems as well. The individual flag meanings are not
    interpreted here.
    """

    raw: bytes
    segment_type: int
    size_pages: int
    new_flags: int
    flags: int
    domain: int
    owner: InternalAddress
    space: InternalAddress

    @classmethod
    def from_bytes(cls, raw: bytes) -> "SegmentGroupHeader":
        if len(raw) < SEGMENT_HEADER_SIZE:
            raise ValueError("segment group header requires 32 bytes")
        data = raw[:SEGMENT_HEADER_SIZE]
        return cls(
            raw=data,
            segment_type=int.from_bytes(data[0:2], "big"),
            size_pages=int.from_bytes(data[2:4], "big"),
            new_flags=data[4],
            flags=data[5],
            domain=int.from_bytes(data[6:8], "big"),
            owner=InternalAddress.from_bytes(data[8:16]),
            space=InternalAddress.from_bytes(data[24:32]),
        )


@dataclass(frozen=True)
class RecoveredSegment:
    start_extent: Extent
    extents: tuple[Extent, ...]
    header: SegmentGroupHeader

    @property
    def virtual_address(self) -> int:
        return self.start_extent.virtual_address or 0

    @property
    def start_lba(self) -> int:
        return self.start_extent.start_lba

    @property
    def pages(self) -> int:
        return self.header.size_pages

    @property
    def end_virtual_address(self) -> int:
        return self.virtual_address + self.pages * PAGE_SIZE - 1

    @property
    def is_primary(self) -> bool:
        return self.header.owner.address == self.virtual_address

    @property
    def owner_key(self) -> tuple[int, int]:
        return self.header.owner.key


@dataclass
class SegmentRecoveryResult:
    segments: list[RecoveredSegment] = field(default_factory=list)
    unrecovered_candidates: list[Extent] = field(default_factory=list)

    @property
    def primary_segments(self) -> list[RecoveredSegment]:
        return [segment for segment in self.segments if segment.is_primary]

    @property
    def secondary_segments(self) -> list[RecoveredSegment]:
        return [segment for segment in self.segments if not segment.is_primary]

    @property
    def recovered_extent_count(self) -> int:
        return sum(len(segment.extents) for segment in self.segments)

    @property
    def segment_type_histogram(self) -> Counter:
        return Counter(segment.header.segment_type for segment in self.segments)


@dataclass(frozen=True)
class EPAHeader:
    """Subset of the common EPA object header needed for offline browsing."""

    raw: bytes
    att1: int
    jopt: int
    object_type: int
    object_subtype: int
    name_raw: bytes
    context: InternalAddress
    object_space: InternalAddress

    @classmethod
    def from_bytes(cls, raw: bytes) -> "EPAHeader":
        if len(raw) < EPA_MIN_SIZE:
            raise ValueError(
                f"EPA header requires at least {EPA_MIN_SIZE} bytes"
            )
        return cls(
            raw=raw,
            att1=raw[0],
            jopt=raw[1],
            object_type=raw[2],
            object_subtype=raw[3],
            name_raw=raw[4:34],
            context=InternalAddress.from_bytes(raw[0x48:0x50]),
            object_space=InternalAddress.from_bytes(raw[0x50:0x58]),
        )

    @property
    def name(self) -> str:
        decoded = self.name_raw.decode("cp037", errors="replace")
        return decoded.rstrip(" \x00")

    @property
    def name_is_printable(self) -> bool:
        name = self.name
        return all(32 <= ord(character) <= 126 for character in name)


@dataclass(frozen=True)
class MemberCursorInfo:
    """Decoded member-header metadata from a permanent 0D50 cursor.

    IBM MI documentation places the cursor associated space at the YYSGHDR
    SPACE address. A four-byte offset at associated-space +4 locates the
    member header. The header begins with five system pointers, followed by
    status, descriptive text, source type, and source/create timestamps.
    """

    associated_space_offset: int
    member_header_offset: int
    status: bytes
    text_raw: bytes
    member_type_raw: bytes
    source_change_raw: bytes
    create_raw: bytes

    @staticmethod
    def _decode_text(raw: bytes) -> str:
        return raw.decode("cp037", errors="replace").rstrip(" \x00")

    @staticmethod
    def _decode_timestamp(raw: bytes) -> str:
        value = raw.decode("cp037", errors="replace").strip(" \x00")
        if len(value) != 13 or not value.isdigit():
            return value
        century = int(value[0])
        year = 1900 + century * 100 + int(value[1:3])
        month = int(value[3:5])
        day = int(value[5:7])
        hour = int(value[7:9])
        minute = int(value[9:11])
        second = int(value[11:13])
        if not (
            1 <= month <= 12
            and 1 <= day <= 31
            and 0 <= hour <= 23
            and 0 <= minute <= 59
            and 0 <= second <= 59
        ):
            return value
        return (
            f"{year:04d}-{month:02d}-{day:02d} "
            f"{hour:02d}:{minute:02d}:{second:02d}"
        )

    @property
    def text(self) -> str:
        return self._decode_text(self.text_raw)

    @property
    def member_type(self) -> str:
        return self._decode_text(self.member_type_raw)

    @property
    def source_change(self) -> str:
        return self._decode_timestamp(self.source_change_raw)

    @property
    def created(self) -> str:
        return self._decode_timestamp(self.create_raw)


@dataclass(frozen=True)
class RecoveredObject:
    segment: RecoveredSegment
    epa: EPAHeader
    library_name: str | None = None

    @property
    def name(self) -> str:
        if self.epa.name:
            return self.epa.name
        if self.epa.object_type == 0x81:
            return "<MACHINE-CONTEXT>"
        return "<unnamed>"

    @property
    def object_type(self) -> int:
        return self.epa.object_type

    @property
    def object_subtype(self) -> int:
        return self.epa.object_subtype

    @property
    def type_code(self) -> str:
        return f"{self.object_type:02X}/{self.object_subtype:02X}"

    @property
    def external_type_hint(self) -> str:
        known = {
            (0x02, 0x01): "*PGM",
            (0x04, 0x01): "*LIB",
            (0x08, 0x01): "*USRPRF",
            (0x0D, 0x50): "*MEM",
            (0x0E, 0x90): "*QDIDX",
            (0x19, 0x01): "*FILE",
            (0x19, 0x02): "*MSGQ",
        }
        return known.get(
            (self.object_type, self.object_subtype),
            "",
        )

    @property
    def is_member_cursor(self) -> bool:
        return (
            self.object_type == 0x0D
            and self.object_subtype == 0x50
        )

    @property
    def member_file_name(self) -> str:
        if not self.is_member_cursor:
            return ""
        return (
            self.epa.name_raw[:10]
            .decode("cp037", errors="replace")
            .rstrip(" \x00")
        )

    @property
    def member_name(self) -> str:
        if not self.is_member_cursor:
            return ""
        return (
            self.epa.name_raw[10:20]
            .decode("cp037", errors="replace")
            .rstrip(" \x00")
        )


@dataclass
class ObjectInventory:
    objects: list[RecoveredObject]
    contexts_by_key: dict[tuple[int, int], RecoveredObject]

    @property
    def libraries(self) -> list[RecoveredObject]:
        return sorted(
            [
                obj
                for obj in self.objects
                if obj.object_type == 0x04
                and obj.object_subtype == 0x01
            ],
            key=lambda obj: obj.name,
        )

    @property
    def assigned_objects(self) -> list[RecoveredObject]:
        return [obj for obj in self.objects if obj.library_name is not None]

    def in_library(self, name: str) -> list[RecoveredObject]:
        wanted = name.upper()
        return sorted(
            [
                obj
                for obj in self.objects
                if (obj.library_name or "").upper() == wanted
            ],
            key=lambda obj: (
                obj.object_type,
                obj.object_subtype,
                obj.name,
                obj.segment.virtual_address,
            ),
        )

    def members(
        self,
        *,
        library: str | None = None,
        file_name: str | None = None,
    ) -> list[RecoveredObject]:
        library_wanted = library.upper() if library else None
        file_wanted = file_name.upper() if file_name else None
        result = []
        for obj in self.objects:
            if not obj.is_member_cursor:
                continue
            if (
                library_wanted is not None
                and (obj.library_name or "").upper() != library_wanted
            ):
                continue
            if (
                file_wanted is not None
                and obj.member_file_name.upper() != file_wanted
            ):
                continue
            result.append(obj)

        return sorted(
            result,
            key=lambda obj: (
                obj.library_name or "",
                obj.member_file_name,
                obj.member_name,
                obj.segment.virtual_address,
            ),
        )


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

    def read_segment_bytes(
        self,
        segment: RecoveredSegment,
    ) -> bytes:
        """Read a recovered virtual segment in virtual-address order."""

        data = bytearray()
        with open(self.path, "rb") as handle:
            for extent in segment.extents:
                for page_index in range(extent.pages):
                    lba = extent.start_lba + page_index
                    handle.seek(lba * SECTOR_SIZE + HEADER_SIZE)
                    page = handle.read(PAGE_SIZE)
                    if len(page) != PAGE_SIZE:
                        raise ValueError(
                            f"short page read at LBA {lba}"
                        )
                    data.extend(page)

        expected = segment.pages * PAGE_SIZE
        if len(data) != expected:
            raise ValueError(
                f"segment read returned {len(data)} bytes; "
                f"expected {expected}"
            )
        return bytes(data)

    def read_member_info(
        self,
        obj: RecoveredObject,
    ) -> MemberCursorInfo | None:
        """Decode the permanent cursor's associated-space member header."""

        if not obj.is_member_cursor:
            return None

        segment = obj.segment
        data = self.read_segment_bytes(segment)

        if (
            segment.header.space.extender
            != segment.header.owner.extender
        ):
            return None

        space_offset = (
            segment.header.space.address
            - segment.virtual_address
        )
        if space_offset < 0 or space_offset + 8 > len(data):
            return None

        relative = int.from_bytes(
            data[space_offset + 4 : space_offset + 8],
            "big",
        )
        member_header = space_offset + relative

        # Five 16-byte system pointers precede the documented scalar fields.
        minimum_end = member_header + 0xB4
        if relative == 0 or minimum_end > len(data):
            return None

        return MemberCursorInfo(
            associated_space_offset=space_offset,
            member_header_offset=member_header,
            status=data[member_header + 0x50 : member_header + 0x52],
            text_raw=data[member_header + 0x54 : member_header + 0x86],
            member_type_raw=data[
                member_header + 0x86 : member_header + 0x90
            ],
            source_change_raw=data[
                member_header + 0x9A : member_header + 0xA7
            ],
            create_raw=data[
                member_header + 0xA7 : member_header + 0xB4
            ],
        )

    def recover_segments(
        self,
        scan_result: ScanResult | None = None,
    ) -> SegmentRecoveryResult:
        """Perform the second directory-recovery pass.

        Candidates are examined in virtual-address order. A plausible first
        segment page supplies the segment's total page count; subsequent extents
        must begin exactly where the previous extent ends in virtual storage.
        Only exact chains are accepted.
        """

        result = scan_result or self.scan()
        candidates = sorted(
            (
                extent
                for extent in result.permanent_candidates
                if extent.virtual_address is not None
            ),
            key=lambda extent: (
                extent.virtual_address,
                extent.start_lba,
            ),
        )

        by_virtual: dict[int, list[Extent]] = {}
        for extent in candidates:
            by_virtual.setdefault(
                extent.virtual_address or 0,
                [],
            ).append(extent)
        for extents in by_virtual.values():
            extents.sort(key=lambda extent: extent.start_lba)

        recovered: list[RecoveredSegment] = []
        consumed: set[tuple[int, int, int]] = set()

        with open(self.path, "rb") as handle:
            for extent in candidates:
                if extent.key in consumed:
                    continue

                handle.seek(extent.start_lba * SECTOR_SIZE + HEADER_SIZE)
                first_page = handle.read(PAGE_SIZE)
                if len(first_page) != PAGE_SIZE:
                    continue

                try:
                    segment_header = SegmentGroupHeader.from_bytes(first_page)
                except ValueError:
                    continue

                if (
                    segment_header.size_pages <= 0
                    or segment_header.size_pages < extent.pages
                    or segment_header.owner.is_null
                    or segment_header.owner.address % PAGE_SIZE
                ):
                    continue

                chain = [extent]
                chain_keys = {extent.key}
                pages = extent.pages
                expected = (
                    (extent.virtual_address or 0)
                    + extent.pages * PAGE_SIZE
                )
                valid = True

                while pages < segment_header.size_pages:
                    remaining = segment_header.size_pages - pages
                    options = [
                        candidate
                        for candidate in by_virtual.get(expected, [])
                        if candidate.key not in consumed
                        and candidate.key not in chain_keys
                        and candidate.pages <= remaining
                    ]
                    if not options:
                        valid = False
                        break

                    # Directory recovery should normally have one candidate at
                    # the required virtual address. Keep selection deterministic
                    # if stale duplicate headers exist.
                    next_extent = options[0]
                    chain.append(next_extent)
                    chain_keys.add(next_extent.key)
                    pages += next_extent.pages
                    expected += next_extent.pages * PAGE_SIZE

                if not valid or pages != segment_header.size_pages:
                    continue

                segment = RecoveredSegment(
                    start_extent=extent,
                    extents=tuple(chain),
                    header=segment_header,
                )
                recovered.append(segment)
                consumed.update(chain_keys)

        unrecovered = [
            extent for extent in candidates if extent.key not in consumed
        ]
        return SegmentRecoveryResult(
            segments=recovered,
            unrecovered_candidates=unrecovered,
        )

    def recover_objects(
        self,
        scan_result: ScanResult | None = None,
        segment_result: SegmentRecoveryResult | None = None,
    ) -> ObjectInventory:
        """Recover common EPA object identities and library back-pointers."""

        scan = scan_result or self.scan()
        segments = segment_result or self.recover_segments(scan)

        recovered: list[RecoveredObject] = []
        with open(self.path, "rb") as handle:
            for segment in segments.primary_segments:
                handle.seek(
                    segment.start_lba * SECTOR_SIZE
                    + HEADER_SIZE
                    + SEGMENT_HEADER_SIZE
                )
                epa_raw = handle.read(PAGE_SIZE - SEGMENT_HEADER_SIZE)
                if len(epa_raw) < EPA_MIN_SIZE:
                    continue

                try:
                    epa = EPAHeader.from_bytes(epa_raw)
                except ValueError:
                    continue

                # ATT1 high bit is present on the permanent common object
                # headers seen in both real images. The machine context has a
                # blank name; ordinary recovered objects must have a printable
                # EBCDIC name.
                if not (epa.att1 & 0x80):
                    continue
                if epa.object_type == 0:
                    continue
                if not epa.name_is_printable:
                    continue
                if not epa.name and epa.object_type != 0x81:
                    continue

                recovered.append(
                    RecoveredObject(
                        segment=segment,
                        epa=epa,
                    )
                )

        context_map: dict[tuple[int, int], RecoveredObject] = {}
        for obj in recovered:
            if (
                (obj.object_type, obj.object_subtype) == (0x04, 0x01)
                or obj.object_type == 0x81
            ):
                context_map[
                    (
                        obj.segment.header.owner.extender,
                        obj.segment.virtual_address,
                    )
                ] = obj

        assigned: list[RecoveredObject] = []
        for obj in recovered:
            context = context_map.get(obj.epa.context.key)
            library_name = None
            if context is not None:
                library_name = (
                    "*MACHINE"
                    if context.object_type == 0x81
                    else context.name
                )
            assigned.append(
                RecoveredObject(
                    segment=obj.segment,
                    epa=obj.epa,
                    library_name=library_name,
                )
            )

        return ObjectInventory(
            objects=assigned,
            contexts_by_key=context_map,
        )


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
    """Infer relative-record zero from IBM's large-free-space delimiter."""

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
