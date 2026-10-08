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

# Real-image evidence from both the surviving B10 disk and the independent
# single-disk V2R3 image identifies two direct storage pointers in the 0D/50
# permanent member cursor. These offsets are observed rather than yet tied to a
# published cursor data-area definition, so keep the names deliberately narrow.
MEMBER_QDDSI_POINTER_OFFSET = 0x128
MEMBER_QDDS_POINTER_OFFSET = 0x300
MEMBER_STORAGE_POINTER_SIZE = 8


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

    def to_bytes(self) -> bytes:
        return (
            self.extender.to_bytes(2, "big")
            + self.address.to_bytes(6, "big")
        )


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
    epa_library_name: str | None = None
    context_library_names: tuple[str, ...] = ()

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
    def object_address(self) -> InternalAddress:
        """Eight-byte address identifying the object's base segment.

        System/38/MI pointer semantics identify an object through its base
        segment. The context documentation describes the final @ field as the
        address of the EPA header, but the real images do not support treating
        that wording as a literal +0x20 byte displacement. Keep the base
        address as the primary candidate and test the literal EPA byte
        location separately in forensic diagnostics.
        """

        return InternalAddress(
            self.segment.header.owner.extender,
            self.segment.virtual_address,
        )

    @property
    def physical_epa_byte_address(self) -> InternalAddress:
        """Literal byte location where the EPA bytes begin in the base page."""

        return InternalAddress(
            self.segment.header.owner.extender,
            self.segment.virtual_address + SEGMENT_HEADER_SIZE,
        )

    @property
    def external_type_hint(self) -> str:
        known = {
            (0x02, 0x01): "*PGM",
            (0x04, 0x01): "*LIB",
            # IBM's MI object-type tables name 06/C1 *DOCBSS:
            # Document byte string space, used by Document Library Services.
            (0x06, 0xC1): "*DOCBSS",
            (0x08, 0x01): "*USRPRF",
            (0x0B, 0x90): "*QDDS",
            (0x0C, 0x90): "*QDDSI",
            (0x0D, 0x50): "*MEM",
            (0x0E, 0x90): "*QDIDX",
            (0x19, 0x01): "*FILE",
            (0x19, 0x02): "*MSGQ",
            # Observed on the real V2R3 QDOC library and corroborated by
            # the objects' DLO metadata/content. IBM documents QDOC as the
            # backing library for *DOC/*FLR document-library objects.
            (0x19, 0x0E): "*DOC",
            (0x19, 0x12): "*FLR",
            (0x19, 0x51): "*FORMAT",
            # IBM/MI documentation and context-index research identify 19/52
            # as the Object Information Repository space associated with a
            # context/library.
            (0x19, 0x52): "*OIRS",
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


@dataclass(frozen=True)
class ContextDirectoryEntry:
    """One reconstructed terminal reference from a permanent *LIB context.

    The terminal bytes are the physical release-2 machine-index representation,
    not the documented expanded T+S+NL+N+@ form. object_address and name_raw_hint
    are therefore explicitly observed/reconstructed hints. The address form has
    been validated against tens of thousands of real recovered primaries; the
    name decoder is limited to the ordinary simple-name and 0D/50 member-key
    encodings that can be round-tripped against recovered EPA names.
    """

    library_name: str
    context_address: InternalAddress
    raw: bytes
    object_type: int | None
    object_subtype: int | None
    object_address: InternalAddress | None
    name_raw_hint: bytes | None
    terminal_element_offset: int
    owned_segment_count: int = 0

    @property
    def type_code(self) -> str:
        if self.object_type is None or self.object_subtype is None:
            return "??/??"
        return f"{self.object_type:02X}/{self.object_subtype:02X}"

    @property
    def name_hint(self) -> str:
        if self.name_raw_hint is None:
            return ""
        return (
            self.name_raw_hint.decode("cp037", errors="replace")
            .rstrip(" \x00")
        )

    @property
    def is_member_cursor(self) -> bool:
        return (
            self.object_type == 0x0D
            and self.object_subtype == 0x50
            and self.name_raw_hint is not None
        )

    @property
    def member_file_name_hint(self) -> str:
        if not self.is_member_cursor:
            return ""
        return (
            self.name_raw_hint[:10]
            .decode("cp037", errors="replace")
            .rstrip(" \x00")
        )

    @property
    def member_name_hint(self) -> str:
        if not self.is_member_cursor:
            return ""
        return (
            self.name_raw_hint[10:20]
            .decode("cp037", errors="replace")
            .rstrip(" \x00")
        )

    @property
    def display_name_hint(self) -> str:
        if self.is_member_cursor:
            file_name = self.member_file_name_hint or "?"
            member_name = self.member_name_hint or "?"
            return f"{file_name}({member_name})"
        return self.name_hint


@dataclass
class ObjectInventory:
    objects: list[RecoveredObject]
    contexts_by_key: dict[tuple[int, int], RecoveredObject]
    context_entries: tuple[ContextDirectoryEntry, ...] = ()
    context_warnings: dict[str, tuple[str, ...]] = field(default_factory=dict)

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

    def context_entries_for_library(
        self,
        name: str,
    ) -> list[ContextDirectoryEntry]:
        wanted = name.upper()
        return [
            entry
            for entry in self.context_entries
            if entry.library_name.upper() == wanted
        ]

    def resolve_context_entry(
        self,
        entry: ContextDirectoryEntry,
    ) -> RecoveredObject | None:
        if entry.object_address is None:
            return None
        for obj in self.objects:
            if obj.object_address.key != entry.object_address.key:
                continue
            if (
                entry.object_type is not None
                and entry.object_subtype is not None
                and (obj.object_type, obj.object_subtype)
                != (entry.object_type, entry.object_subtype)
            ):
                continue
            return obj
        return None

    def unresolved_context_entries(
        self,
        library: str | None = None,
    ) -> list[ContextDirectoryEntry]:
        wanted = library.upper() if library else None
        result = []
        for entry in self.context_entries:
            if wanted is not None and entry.library_name.upper() != wanted:
                continue
            if self.resolve_context_entry(entry) is None:
                result.append(entry)
        return result

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

    def matching_objects(
        self,
        *,
        library: str | None = None,
        name_raw: bytes | None = None,
        object_type: int | None = None,
        object_subtype: int | None = None,
    ) -> list[RecoveredObject]:
        """Return recovered objects matching internal identity fields."""

        library_wanted = library.upper() if library else None
        matches = []
        for obj in self.objects:
            if (
                library_wanted is not None
                and (obj.library_name or "").upper() != library_wanted
            ):
                continue
            if name_raw is not None and obj.epa.name_raw != name_raw:
                continue
            if (
                object_type is not None
                and obj.object_type != object_type
            ):
                continue
            if (
                object_subtype is not None
                and obj.object_subtype != object_subtype
            ):
                continue
            matches.append(obj)

        return sorted(
            matches,
            key=lambda obj: (
                obj.segment.virtual_address,
                obj.segment.start_lba,
            ),
        )


@dataclass(frozen=True)
class DocumentByteStringInfo:
    """Observed V2R3 *DOCBSS byte-stream layout.

    IBM documents MI type/subtype 06/C1 as *DOCBSS (Document byte string
    space). On the real V2R3 image, the first page of ordinary DOCBSS objects
    contains a 16-bit byte length at +0x106 and a duplicate at +0x112. The
    workstation byte stream begins on the following 512-byte page. A 16-bit
    allocation length at +0x10A is normally a 512-byte multiple.

    The offsets are real-image observations, not claimed IBM documentation.
    Safe extraction requires the duplicated lengths to agree and the declared
    bytes to fit inside the recovered segment.
    """

    payload_length: int
    allocated_length: int
    duplicate_payload_length: int
    payload_offset: int = PAGE_SIZE

    @classmethod
    def from_primary_segment(cls, data: bytes) -> "DocumentByteStringInfo":
        if len(data) < 0x114:
            raise ValueError(
                "DOCBSS primary segment is too short for observed length fields"
            )
        return cls(
            payload_length=int.from_bytes(data[0x106:0x108], "big"),
            allocated_length=int.from_bytes(data[0x10A:0x10C], "big"),
            duplicate_payload_length=int.from_bytes(
                data[0x112:0x114],
                "big",
            ),
        )

    @property
    def duplicate_length_matches(self) -> bool:
        return self.payload_length == self.duplicate_payload_length

    def validate_for_export(self, segment_bytes: int) -> None:
        if not self.duplicate_length_matches:
            raise ValueError(
                "DOCBSS duplicate payload lengths disagree "
                f"({self.payload_length} != "
                f"{self.duplicate_payload_length})"
            )
        end = self.payload_offset + self.payload_length
        if end > segment_bytes:
            raise ValueError(
                f"DOCBSS payload length {self.payload_length} exceeds "
                f"recovered segment capacity {max(0, segment_bytes - self.payload_offset)}"
            )
        if self.allocated_length:
            if self.allocated_length % PAGE_SIZE:
                raise ValueError(
                    "DOCBSS allocation length is not a 512-byte multiple"
                )
            if self.payload_length > self.allocated_length:
                raise ValueError(
                    f"DOCBSS payload length {self.payload_length} exceeds "
                    f"declared allocation {self.allocated_length}"
                )


@dataclass(frozen=True)
class MemberStoragePointers:
    """Direct QDDS/QDDSI addresses observed in a permanent member cursor.

    Across the two real CISC images used by this project, +0x128 points to the
    member's QDDSI when one is present and +0x300 points to its QDDS. A missing
    primary segment can therefore still be distinguished from "no storage
    relationship" and can be correlated with surviving secondary segments.
    """

    data_space: InternalAddress | None
    data_index: InternalAddress | None

    @classmethod
    def from_cursor_segment(cls, data: bytes) -> "MemberStoragePointers":
        def read_pointer(offset: int) -> InternalAddress | None:
            end = offset + MEMBER_STORAGE_POINTER_SIZE
            if offset < 0 or end > len(data):
                return None
            address = InternalAddress.from_bytes(data[offset:end])
            if address.is_null:
                return None
            return address

        return cls(
            data_space=read_pointer(MEMBER_QDDS_POINTER_OFFSET),
            data_index=read_pointer(MEMBER_QDDSI_POINTER_OFFSET),
        )


@dataclass(frozen=True)
class MemberStorage:
    """Recovered storage objects associated with one database member cursor."""

    cursor: RecoveredObject
    data_space: RecoveredObject | None
    data_index: RecoveredObject | None
    data_segments: tuple[RecoveredSegment, ...] = ()
    data_space_address: InternalAddress | None = None
    data_index_address: InternalAddress | None = None

    @property
    def data_pages(self) -> int:
        return sum(segment.pages for segment in self.data_segments)

    @property
    def data_bytes(self) -> int:
        return self.data_pages * PAGE_SIZE


QDDS_ENTRY_COUNT_OFFSET = 0x11A
QDDS_FORCE_COUNT_OFFSET = 0x11E

# This four-byte entry-length field is present in both the early B10 image and
# the independent V2R3 image, so use it as the architecture-level value.
QDDS_ENTRY_LENGTH_OFFSET = 0x13C
QDDS_LAYOUT_MIN_SIZE = QDDS_ENTRY_LENGTH_OFFSET + 4

# The V2R3 image also carries later/duplicate scalar fields. They are useful as
# corroboration for ordinary fixed records, but are zero on the older B10 and
# differ on a handful of special system data spaces. Do not require them.
QDDS_V2_RECORD_LENGTH_OFFSET = 0x1E4
QDDS_V2_ENTRY_LENGTH_OFFSET = 0x1EC
QDDS_V2_LAYOUT_MIN_SIZE = QDDS_V2_ENTRY_LENGTH_OFFSET + 2

# Observed QDDSI object-header/key-specification offsets. These are reproduced
# by every recovered ordinary 0C/90 primary examined in both real images, while
# the logical meaning of DKEY/DKYT comes from IBM SY21-0889-5. Keep unresolved
# attribute bits and the DKEY +0x14 scalar raw rather than guessing names.
QDDSI_DKEY_COUNT_OFFSET = 0x11E
QDDSI_DKEY_POINTER_OFFSET = 0x12A
QDDSI_DKEY_ROW_SIZE = 0x40
QDDSI_DKYT_ROW_SIZE = 0x20
QDDSI_LAYOUT_MIN_SIZE = QDDSI_DKEY_POINTER_OFFSET + 6

# The early ordinary samples place the active machine-index root at +0x1000,
# but larger/special real V2R3 indexes place it at +0x1800 or +0x2800. The
# QDDSI object header carries an observed six-byte pointer at +0x13A to a
# machine-index control area; that area's +0x20 six-byte pointer identifies the
# active root page. Keep +0x1000 only as a synthetic/legacy fallback when the
# caller does not supply the QDDSI primary virtual address.
QDDSI_MACHINE_INDEX_CONTROL_POINTER_OFFSET = 0x13A
QDDSI_MACHINE_INDEX_CONTROL_ROOT_POINTER_OFFSET = 0x20
QDDSI_MACHINE_INDEX_ROOT_OFFSET = 0x1000

# Ordinary permanent-context (*LIB / MI 04/01) objects on both real images
# independently place the active release-2 machine-index root at segment offset
# +0x800 when the index fits in the recovered eight-page primary segment.
# This is an observed placement, not yet a published data-area field.
CONTEXT_MACHINE_INDEX_ROOT_OFFSET = 0x800


@dataclass(frozen=True)
class DataSpaceIndexKeyField:
    """One recovered DKYT row from a QDDSI key specification.

    IBM documents DKYT rows as describing key-field ordering attributes,
    length/fork information, relative offset, and field location. The final
    two-byte selector below consistently tracks the source field ordinal in
    the ordinary files checked so far, but remains an observed hint.
    """

    sequence_attributes: int
    field_attributes: int
    length_or_fork: int
    relative_offset: int
    location: int
    field_ordinal_hint: int
    raw: bytes

    @property
    def record_offset_hint(self) -> int | None:
        """Zero-based record offset for ordinary directly mapped fields."""

        if self.location <= 0:
            return None
        return self.location - 1


@dataclass(frozen=True)
class DataSpaceIndexKeySpec:
    """One DKEY row and its referenced DKYT rows."""

    data_space: InternalAddress
    field_table_pointer: InternalAddress
    key_count: int
    auxiliary_scalar_raw: int
    key_field_count: int
    user_key_length: int
    machine_key_length: int
    dkyt_address: int
    fields: tuple[DataSpaceIndexKeyField, ...]
    raw: bytes

    @property
    def appended_key_bytes(self) -> int:
        return max(0, self.machine_key_length - self.user_key_length)

    def split_machine_key(
        self,
        machine_key: bytes,
    ) -> tuple[bytes, bytes] | None:
        """Separate recovered user-key bytes from the four-byte DB reference.

        Ordinary one-data-space indexes store user-key bytes followed directly
        by the documented database-relative address. Multi-DKEY indexes can
        interleave additional one-byte ordering controls between DKYT fields.
        IBM documents fork-character rows for exactly that purpose.

        Real V2R3 indexes show those non-field rows as zero-length,
        zero-location DKYT rows. Consume one machine-key byte for each such row
        while concatenating only the actual field bytes into the user key.
        """

        if len(machine_key) != self.machine_key_length:
            return None
        if self.machine_key_length < 4:
            return None

        database_reference = machine_key[-4:]
        key_body = machine_key[:-4]

        if len(key_body) == self.user_key_length:
            return key_body, database_reference

        cursor = 0
        user_key = bytearray()
        for field in self.fields:
            if field.location > 0 and field.length_or_fork > 0:
                end = cursor + field.length_or_fork
                if end > len(key_body):
                    return None
                user_key.extend(key_body[cursor:end])
                cursor = end
                continue

            if field.location == 0 and field.length_or_fork == 0:
                # Observed non-field DKYT row. IBM documents that DKYT may
                # contain fork-character rows; consume its one ordering byte
                # without assigning any still-unknown attribute bits.
                if cursor >= len(key_body):
                    return None
                cursor += 1
                continue

            return None

        if cursor != len(key_body) or len(user_key) != self.user_key_length:
            return None
        return bytes(user_key), database_reference


@dataclass(frozen=True)
class DataSpaceIndexLayout:
    """Conservatively decoded QDDSI DKEY/DKYT key specifications."""

    dkey_count: int
    dkey_address: int
    keys: tuple[DataSpaceIndexKeySpec, ...]

    @classmethod
    def from_primary_segment(
        cls,
        data: bytes,
        *,
        virtual_address: int,
    ) -> "DataSpaceIndexLayout":
        if len(data) < QDDSI_LAYOUT_MIN_SIZE:
            raise ValueError("QDDSI primary segment is too short for key metadata")

        dkey_count = int.from_bytes(
            data[
                QDDSI_DKEY_COUNT_OFFSET :
                QDDSI_DKEY_COUNT_OFFSET + 2
            ],
            "big",
        )
        dkey_address = int.from_bytes(
            data[
                QDDSI_DKEY_POINTER_OFFSET :
                QDDSI_DKEY_POINTER_OFFSET + 6
            ],
            "big",
        )

        if dkey_count == 0:
            return cls(
                dkey_count=0,
                dkey_address=dkey_address,
                keys=(),
            )
        if dkey_count > 1024:
            raise ValueError(f"implausible QDDSI DKEY count {dkey_count}")
        dkey_offset = dkey_address - virtual_address
        if (
            dkey_offset < 0
            or dkey_offset + dkey_count * QDDSI_DKEY_ROW_SIZE > len(data)
        ):
            raise ValueError("QDDSI DKEY table is outside recovered primary segment")

        specs: list[DataSpaceIndexKeySpec] = []
        for row_number in range(dkey_count):
            offset = dkey_offset + row_number * QDDSI_DKEY_ROW_SIZE
            row = data[offset : offset + QDDSI_DKEY_ROW_SIZE]

            key_field_count = int.from_bytes(row[0x18:0x1A], "big")
            if key_field_count > 1024:
                raise ValueError(
                    f"implausible QDDSI DKYT field count {key_field_count}"
                )
            dkyt_address = int.from_bytes(row[0x1E:0x24], "big")
            fields: list[DataSpaceIndexKeyField] = []

            if key_field_count:
                dkyt_offset = dkyt_address - virtual_address
                if (
                    dkyt_offset < 0
                    or dkyt_offset
                    + key_field_count * QDDSI_DKYT_ROW_SIZE
                    > len(data)
                ):
                    raise ValueError(
                        "QDDSI DKYT table is outside recovered primary segment"
                    )
                for field_number in range(key_field_count):
                    field_offset = (
                        dkyt_offset
                        + field_number * QDDSI_DKYT_ROW_SIZE
                    )
                    field_raw = data[
                        field_offset :
                        field_offset + QDDSI_DKYT_ROW_SIZE
                    ]
                    fields.append(
                        DataSpaceIndexKeyField(
                            sequence_attributes=field_raw[0],
                            field_attributes=field_raw[1],
                            length_or_fork=int.from_bytes(
                                field_raw[2:4], "big"
                            ),
                            relative_offset=int.from_bytes(
                                field_raw[4:6], "big"
                            ),
                            location=int.from_bytes(
                                field_raw[6:8], "big"
                            ),
                            field_ordinal_hint=int.from_bytes(
                                field_raw[8:10], "big"
                            ),
                            raw=field_raw,
                        )
                    )

            specs.append(
                DataSpaceIndexKeySpec(
                    data_space=InternalAddress.from_bytes(row[0:8]),
                    field_table_pointer=InternalAddress.from_bytes(row[8:16]),
                    key_count=int.from_bytes(row[0x10:0x14], "big"),
                    auxiliary_scalar_raw=int.from_bytes(
                        row[0x14:0x18], "big"
                    ),
                    key_field_count=key_field_count,
                    user_key_length=int.from_bytes(row[0x1A:0x1C], "big"),
                    machine_key_length=int.from_bytes(
                        row[0x1C:0x1E], "big"
                    ),
                    dkyt_address=dkyt_address,
                    fields=tuple(fields),
                    raw=row,
                )
            )

        return cls(
            dkey_count=dkey_count,
            dkey_address=dkey_address,
            keys=tuple(specs),
        )


@dataclass(frozen=True)
class DataSpaceLayout:
    """Scalar record-layout fields recovered from a QDDS primary segment.

    The entry count and force count are present in both real CISC images. The
    common four-byte entry length at +0x13C is likewise present in both the B10
    and V2R3 layouts. IBM documents one status byte separating data-space
    entries, so the fixed-record payload is entry_length - 1 bytes.

    V2R3 also exposes duplicate/later length fields near +0x1E4. Those agree
    with the common layout for ordinary fixed database/source members but are
    absent on B10 and disagree on a few special system objects. They are kept as
    hints rather than used as the authoritative layout.
    """

    entry_count: int
    force_count: int
    record_length: int
    entry_length: int
    v2_record_length_hint: int = 0
    v2_entry_length_hint: int = 0

    @classmethod
    def from_primary_segment(cls, data: bytes) -> "DataSpaceLayout":
        if len(data) < QDDS_LAYOUT_MIN_SIZE:
            raise ValueError("QDDS primary segment is too short for layout scalars")

        entry_count = int.from_bytes(
            data[
                QDDS_ENTRY_COUNT_OFFSET :
                QDDS_ENTRY_COUNT_OFFSET + 4
            ],
            "big",
        )
        force_count = int.from_bytes(
            data[
                QDDS_FORCE_COUNT_OFFSET :
                QDDS_FORCE_COUNT_OFFSET + 4
            ],
            "big",
        )
        entry_length = int.from_bytes(
            data[
                QDDS_ENTRY_LENGTH_OFFSET :
                QDDS_ENTRY_LENGTH_OFFSET + 4
            ],
            "big",
        )

        if entry_length <= 1:
            raise ValueError("QDDS entry length is zero or too small")

        v2_record_length_hint = 0
        v2_entry_length_hint = 0
        if len(data) >= QDDS_V2_LAYOUT_MIN_SIZE:
            v2_record_length_hint = int.from_bytes(
                data[
                    QDDS_V2_RECORD_LENGTH_OFFSET :
                    QDDS_V2_RECORD_LENGTH_OFFSET + 4
                ],
                "big",
            )
            v2_entry_length_hint = int.from_bytes(
                data[
                    QDDS_V2_ENTRY_LENGTH_OFFSET :
                    QDDS_V2_ENTRY_LENGTH_OFFSET + 2
                ],
                "big",
            )

        return cls(
            entry_count=entry_count,
            force_count=force_count,
            record_length=entry_length - 1,
            entry_length=entry_length,
            v2_record_length_hint=v2_record_length_hint,
            v2_entry_length_hint=v2_entry_length_hint,
        )

    @property
    def expected_entries_with_default(self) -> int:
        return self.entry_count + 1

    @property
    def per_entry_overhead(self) -> int:
        return self.entry_length - self.record_length

    @property
    def v2_hints_present(self) -> bool:
        return bool(
            self.v2_record_length_hint
            or self.v2_entry_length_hint
        )

    @property
    def v2_hints_match(self) -> bool:
        if not self.v2_hints_present:
            return True
        return (
            self.v2_record_length_hint == self.record_length
            and self.v2_entry_length_hint == self.entry_length
        )

    @property
    def standard_fixed_layout(self) -> bool:
        # IBM's data-space description gives one status byte between entries.
        # A mismatch in the optional V2R3 duplicate fields marks a special
        # layout and should be surfaced, but it does not change the common
        # entry-length boundary used to recover raw ordinal entries.
        return (
            self.per_entry_overhead == 1
            and self.v2_hints_match
        )


@dataclass(frozen=True)
class FormatField:
    """One database record-format field recovered from a 19/51 format object."""

    marker: int
    name: str
    reference_name: str
    type_code: int
    flags: int
    offset: int
    storage_length: int
    digits: int
    decimal_positions: int

    @property
    def type_name(self) -> str:
        return {
            0x00: "BINARY",
            0x02: "ZONED",
            0x03: "PACKED",
            0x04: "CHAR",
        }.get(self.type_code, f"TYPE-{self.type_code:02X}")

    def raw_value(self, record: bytes) -> bytes:
        end = self.offset + self.storage_length
        if self.offset < 0 or end > len(record):
            return b""
        return record[self.offset:end]

    @staticmethod
    def _format_decimal(digits: str, negative: bool, decimal_positions: int) -> str:
        if not digits:
            digits = "0"
        digits = digits.lstrip("0") or "0"
        if decimal_positions:
            digits = digits.rjust(decimal_positions + 1, "0")
            digits = (
                digits[:-decimal_positions]
                + "."
                + digits[-decimal_positions:]
            )
        if negative and digits != "0":
            digits = "-" + digits
        return digits

    def decode_value(self, record: bytes) -> str:
        raw = self.raw_value(record)
        if len(raw) != self.storage_length:
            return "<outside-record>"

        if self.type_code == 0x04:
            return raw.decode("cp037", errors="replace").rstrip()

        if self.type_code == 0x00:
            # System/38 binary numeric fields use signed two's-complement
            # representation. Apply declared decimal positions after converting
            # the big-endian integer.
            value = int.from_bytes(raw, "big", signed=True)
            negative = value < 0
            digits = str(abs(value))
            return self._format_decimal(
                digits,
                negative,
                self.decimal_positions,
            )

        if self.type_code == 0x02:
            # Zoned decimal: one digit per byte. The low nibble is the digit;
            # the high nibble of the final byte carries the sign.
            digits = "".join(str(byte & 0x0F) for byte in raw)
            sign = (raw[-1] >> 4) & 0x0F if raw else 0x0F
            negative = sign in (0x0B, 0x0D)
            return self._format_decimal(
                digits,
                negative,
                self.decimal_positions,
            )

        if self.type_code == 0x03:
            # Packed decimal: two nibbles per byte, final nibble is sign.
            nibbles = []
            for byte in raw:
                nibbles.extend([(byte >> 4) & 0x0F, byte & 0x0F])
            if not nibbles:
                return ""
            sign = nibbles.pop()
            if any(nibble > 9 for nibble in nibbles):
                return raw.hex().upper()
            digits = "".join(str(nibble) for nibble in nibbles)
            negative = sign in (0x0B, 0x0D)
            return self._format_decimal(
                digits,
                negative,
                self.decimal_positions,
            )

        return raw.hex().upper()


def decode_format_fields(
    data: bytes,
    *,
    record_length: int | None = None,
) -> tuple[FormatField, ...]:
    """Recover repeated field-description structures from a 19/51 format.

    Real CISC format objects from both images use a variable-length descriptor
    whose stable prefix is:
      marker byte
      10-byte field name
      10-byte reference name
      0x00, type, flags
      duplicated 16-bit record offset
      16-bit storage length
      16-bit digit count
      16-bit decimal-position count

    Descriptors are found structurally rather than by assuming a fixed stride.
    """

    result: list[FormatField] = []
    seen: set[tuple[str, int, int, int]] = set()

    for pos in range(0, max(0, len(data) - 34) + 1):
        if pos + 34 > len(data):
            break

        name_raw = data[pos + 1 : pos + 11]
        reference_raw = data[pos + 11 : pos + 21]
        if name_raw != reference_raw:
            continue

        try:
            name = name_raw.decode("cp037").rstrip()
            reference_name = reference_raw.decode("cp037").rstrip()
        except UnicodeDecodeError:
            continue

        if not name or not all(32 <= ord(character) <= 126 for character in name):
            continue

        meta = data[pos + 21 : pos + 34]
        if len(meta) < 13:
            continue
        if meta[0] != 0 or meta[2] != 0x03:
            continue

        offset_a = int.from_bytes(meta[3:5], "big")
        offset_b = int.from_bytes(meta[5:7], "big")
        if offset_a != offset_b:
            continue

        storage_length = int.from_bytes(meta[7:9], "big")
        digits = int.from_bytes(meta[9:11], "big")
        decimal_positions = int.from_bytes(meta[11:13], "big")
        if storage_length <= 0:
            continue
        if record_length is not None and (
            offset_a + storage_length > record_length
        ):
            continue

        type_code = meta[1]
        key = (name, offset_a, storage_length, type_code)
        if key in seen:
            continue
        seen.add(key)

        result.append(
            FormatField(
                marker=data[pos],
                name=name,
                reference_name=reference_name,
                type_code=type_code,
                flags=meta[2],
                offset=offset_a,
                storage_length=storage_length,
                digits=digits,
                decimal_positions=decimal_positions,
            )
        )

    return tuple(sorted(result, key=lambda field: (field.offset, field.name)))


@dataclass(frozen=True)
class DataSpaceRecord:
    """One ordinal-addressed data-space entry."""

    ordinal: int
    status: int
    data: bytes
    extra_raw: bytes = b""

    @property
    def rrn(self) -> int:
        """Relative record number; zero is the data-space default entry."""

        return self.ordinal

    @property
    def ebcdic_preview(self) -> str:
        decoded = self.data.decode("cp037", errors="replace")
        return "".join(
            character if character.isprintable() else "."
            for character in decoded
        ).rstrip()


# Observed V2R3 QAOSSS14 anchor-record format. These exact field
# identifiers and 1-based offset/length pairs repeat in the recovered
# WOSFMT14/QAOSSS14 descriptor metadata on the real V2R3 image. The names are
# preserved verbatim; unknown abbreviations are intentionally not expanded.
QAOSSS14_V2_RECORD_LENGTH = 193
QAOSSS14_V2_FIELD_LAYOUT = {
    "WOSEFILD": (17, 8),
    "WOSEDOCD": (25, 4),
    "WOSEDOCN": (33, 44),
    "WOSEDOCT": (77, 2),
    "WOSESYSC": (83, 13),
    "WOSEOWNR": (96, 16),
    "WOSEFDOC": (112, 12),
    "WOSEPLDN": (132, 8),
    "WOSEWIPI": (142, 1),
    "WOSESLVL": (147, 1),
    "WOSECRTD": (150, 6),
    "WOSELCDT": (156, 8),
    "WOSEOCDT": (164, 8),
    "WOSEIXDT": (180, 8),
    "WOSEINTS": (189, 2),
}


@dataclass(frozen=True)
class QAOSSS14AnchorRecord:
    """One V2R3 QAOSSS14 DLO anchor record.

    IBM documents QAOSSS14 as containing an "anchor record" that stores the
    DLO system object name. The field identifiers and layout below come from
    repeated WOSFMT14 descriptors recovered from the real V2R3 image; field
    semantics beyond directly observed string/key relationships remain
    intentionally conservative.
    """

    ordinal: int
    status: int
    raw: bytes

    @classmethod
    def from_data_space_record(
        cls,
        record: "DataSpaceRecord",
    ) -> "QAOSSS14AnchorRecord":
        if len(record.data) != QAOSSS14_V2_RECORD_LENGTH:
            raise ValueError(
                "QAOSSS14 V2R3 record must be exactly "
                f"{QAOSSS14_V2_RECORD_LENGTH} bytes"
            )
        return cls(
            ordinal=record.ordinal,
            status=record.status,
            raw=record.data,
        )

    @property
    def rrn(self) -> int:
        return self.ordinal

    def field(self, name: str) -> bytes:
        key = name.upper()
        if key not in QAOSSS14_V2_FIELD_LAYOUT:
            raise KeyError(key)
        offset_one, length = QAOSSS14_V2_FIELD_LAYOUT[key]
        start = offset_one - 1
        return self.raw[start : start + length]

    def text(self, name: str) -> str:
        return self.field(name).decode(
            "cp037",
            errors="replace",
        ).rstrip(" \x00")

    @property
    def leading_key(self) -> bytes:
        """Eight-byte record prefix preceding the WOSFMT14 field layout."""

        return self.raw[0:8]

    @property
    def secondary_key_raw(self) -> bytes:
        """Second eight-byte record prefix preceding the WOSFMT14 fields."""

        return self.raw[8:16]

    @property
    def secondary_key_text(self) -> str:
        value = self.secondary_key_raw.decode("cp037", errors="replace")
        if all(character.isprintable() for character in value):
            return value.rstrip(" \x00")
        return ""

    @property
    def record_key(self) -> bytes:
        """Observed 8-byte WOSEFILD field value."""

        return self.field("WOSEFILD")

    @property
    def parent_key(self) -> bytes:
        """Observed 8-byte WOSEPLDN value; linkage is validated separately."""

        return self.field("WOSEPLDN")

    @property
    def long_name(self) -> str:
        return self.text("WOSEDOCN")

    @property
    def short_name(self) -> str:
        return self.text("WOSEFDOC")

    @property
    def owner_text(self) -> str:
        return self.text("WOSEOWNR")

    @property
    def object_type_raw(self) -> bytes:
        return self.field("WOSEDOCT")


@dataclass(frozen=True)
class DataSpaceRecordSet:
    """Logical data-space records reconstructed across 03B4 segment groups."""

    layout: DataSpaceLayout
    records: tuple[DataSpaceRecord, ...]
    data_segment_count: int
    raw_stream_bytes: int

    @property
    def complete(self) -> bool:
        return len(self.records) == self.layout.expected_entries_with_default

    @property
    def default_record(self) -> DataSpaceRecord | None:
        if self.records and self.records[0].ordinal == 0:
            return self.records[0]
        return None

    @property
    def user_records(self) -> tuple[DataSpaceRecord, ...]:
        return tuple(record for record in self.records if record.ordinal != 0)


def decode_data_space_records(
    stream: bytes,
    layout: DataSpaceLayout,
) -> tuple[DataSpaceRecord, ...]:
    """Decode ordinal entries using the QDDS header's authoritative lengths.

    IBM documents entry addressing as ordinal * entry-length into the logical
    data-segment address space after segment-group headers are omitted. The
    data-space header's entry count excludes the default entry at ordinal zero.
    """

    records: list[DataSpaceRecord] = []
    for ordinal in range(layout.expected_entries_with_default):
        start = ordinal * layout.entry_length
        end = start + layout.entry_length
        if end > len(stream):
            break

        entry = stream[start:end]
        record_start = 1
        record_end = record_start + layout.record_length
        records.append(
            DataSpaceRecord(
                ordinal=ordinal,
                status=entry[0],
                data=entry[record_start:record_end],
                extra_raw=entry[record_end:],
            )
        )
    return tuple(records)


SOURCE_RECORD_DATA_LENGTH = 92
SOURCE_ENTRY_LENGTH = SOURCE_RECORD_DATA_LENGTH + 1


@dataclass(frozen=True)
class SourceRecord:
    """One recovered standard AS/400 source physical-file record.

    The standard source record is 92 bytes: six bytes of source sequence,
    six bytes of source date, and 80 bytes of source text. On disk the data
    space places a one-byte entry status immediately before the record.
    """

    ordinal: int
    status: int
    sequence_raw: bytes
    date_raw: bytes
    text_raw: bytes

    @property
    def sequence(self) -> str:
        return self.sequence_raw.decode("cp037", errors="replace")

    @property
    def sequence_display(self) -> str:
        value = self.sequence
        if len(value) == 6 and value.isdigit():
            return f"{value[:4]}.{value[4:]}"
        return value

    @property
    def source_date(self) -> str:
        return self.date_raw.decode("cp037", errors="replace")

    @property
    def text(self) -> str:
        return self.text_raw.decode("cp037", errors="replace").rstrip()

    @property
    def is_default_entry(self) -> bool:
        return (
            self.sequence == "000000"
            and self.source_date == "000000"
            and not self.text
        )


@dataclass(frozen=True)
class SourceMemberContent:
    """Recovered standard source records from a member data space."""

    records: tuple[SourceRecord, ...]
    default_entry_present: bool
    data_segment_count: int
    raw_stream_bytes: int

    @property
    def line_count(self) -> int:
        return len(self.records)


def decode_standard_source_stream(
    stream: bytes,
) -> SourceMemberContent | None:
    """Recognize and decode the standard 92-byte AS/400 source record format.

    IBM documents data-space entries as status byte + fields, with the initial
    entry being a default entry. Standard source physical files use 92 data
    bytes: 6 source-sequence bytes, 6 source-date bytes, and 80 source-text
    bytes. Requiring a valid default entry makes this deliberately conservative
    so arbitrary 93-byte database records are not mislabeled as source code.
    """

    candidates: list[SourceRecord] = []
    for offset in range(0, len(stream) - SOURCE_ENTRY_LENGTH + 1, SOURCE_ENTRY_LENGTH):
        entry = stream[offset : offset + SOURCE_ENTRY_LENGTH]
        status = entry[0]
        record = entry[1:]
        sequence_raw = record[0:6]
        date_raw = record[6:12]
        text_raw = record[12:92]

        try:
            sequence = sequence_raw.decode("cp037")
            source_date = date_raw.decode("cp037")
            text = text_raw.decode("cp037")
        except UnicodeDecodeError:
            continue

        # Real valid source entries observed on both images have the high status
        # bit set. Other status bits are preserved but not interpreted yet.
        if not (status & 0x80):
            continue
        if not (sequence.isdigit() and source_date.isdigit()):
            continue
        printable = sum(character.isprintable() for character in text)
        if printable < 72:
            continue

        candidates.append(
            SourceRecord(
                ordinal=offset // SOURCE_ENTRY_LENGTH,
                status=status,
                sequence_raw=sequence_raw,
                date_raw=date_raw,
                text_raw=text_raw,
            )
        )

    default = next(
        (
            record
            for record in candidates
            if record.ordinal == 0 and record.is_default_entry
        ),
        None,
    )
    if default is None:
        return None

    records = tuple(
        record
        for record in candidates
        if not record.is_default_entry
    )
    if not records:
        return None

    return SourceMemberContent(
        records=records,
        default_entry_present=True,
        data_segment_count=0,
        raw_stream_bytes=len(stream),
    )



@dataclass(frozen=True)
class ContextIndexEntry:
    """Expanded System/38/early-AS/400 context machine-index entry.

    IBM's System/38 VMC context-management documentation gives the logical
    entry form as::

        T S NL N @

    where T is object type, S is subtype, NL is the unpadded name length,
    N is the user-specified EBCDIC object name with trailing blanks removed,
    and @ is the eight-byte internal address of the object's EPA header.

    This class represents a *reconstructed logical index entry*. It does not
    imply that these bytes occur contiguously on an index page: machine-index
    common-text compression can split leading entry bytes from terminal text.
    """

    raw: bytes
    object_type: int
    object_subtype: int
    name_raw: bytes
    object_address: InternalAddress

    @classmethod
    def from_bytes(cls, raw: bytes) -> "ContextIndexEntry":
        if len(raw) < 11:
            raise ValueError("context index entry requires at least 11 bytes")
        name_length = raw[2]
        if name_length > 30:
            raise ValueError(
                f"context entry name length {name_length} exceeds 30 bytes"
            )
        expected = 3 + name_length + 8
        if len(raw) != expected:
            raise ValueError(
                f"context index entry length is {len(raw)} bytes; "
                f"expected {expected} from NL={name_length}"
            )
        return cls(
            raw=bytes(raw),
            object_type=raw[0],
            object_subtype=raw[1],
            name_raw=bytes(raw[3 : 3 + name_length]),
            object_address=InternalAddress.from_bytes(raw[-8:]),
        )

    @classmethod
    def from_object(cls, obj: "RecoveredObject") -> "ContextIndexEntry":
        """Build the documented logical entry expected for a recovered object.

        IBM describes the final @ field as the eight-byte address of the
        object's EPA header. System-pointer semantics identify an MI object by
        its base segment, while the literal EPA bytes begin 0x20 bytes into the
        recovered base page. Real-image evidence does not justify equating @
        with that physical byte displacement, so this reconstructed candidate
        uses the object's base address and diagnostics test both forms.
        """

        name_raw = obj.epa.name_raw.rstrip(b"\x40\x00")
        if len(name_raw) > 30:
            raise ValueError("recovered object name exceeds 30 bytes")
        raw = (
            bytes([obj.object_type, obj.object_subtype, len(name_raw)])
            + name_raw
            + obj.object_address.to_bytes()
        )
        return cls.from_bytes(raw)

    @property
    def name_length(self) -> int:
        return len(self.name_raw)

    @property
    def name(self) -> str:
        return self.name_raw.decode("cp037", errors="replace").rstrip(" \x00")

    @property
    def type_code(self) -> str:
        return f"{self.object_type:02X}/{self.object_subtype:02X}"

    @property
    def key_prefix(self) -> bytes:
        """Documented context search-key candidate: T + S + NL + N."""

        return self.raw[:-8]


@dataclass(frozen=True)
class MachineIndexElement:
    """One three-byte release-2 System/38/AS/400 machine-index element.

    IBM's published machine-index format uses three-byte elements. The high
    bits identify text elements, decision nodes, and page pointers.

    The node bit positions below are independently validated by ordinary real
    QDDSI trees. Bit 20 is the inverted common-text flag, bit 19 is direction,
    bits 18-16 select the tested bit, and the low 16 bits are the XOR
    displacement. Bit 21 remains deliberately unnamed.

    text_length preserves the encoded seven-bit field used by the older
    context forensic probes. Real QDDSI common/terminal text demonstrates
    that the stored field is length-minus-one, so text_storage_length exposes
    the byte count used for actual tree traversal.
    """

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != 3:
            raise ValueError("machine-index element must be exactly 3 bytes")

    @property
    def value(self) -> int:
        return int.from_bytes(self.raw, "big")

    @property
    def kind(self) -> str:
        if not (self.value & 0x800000):
            return "text"
        if (self.value & 0xC00000) == 0x800000:
            return "node"
        return "page-pointer"

    @property
    def text_length(self) -> int | None:
        """Encoded seven-bit text-length field (not the byte count)."""

        if self.kind != "text":
            return None
        return (self.value >> 16) & 0x7F

    @property
    def text_storage_length(self) -> int | None:
        """Actual text byte count validated on real QDDSI trees."""

        encoded = self.text_length
        if encoded is None:
            return None
        return encoded + 1

    @property
    def text_displacement(self) -> int | None:
        if self.kind != "text":
            return None
        return self.value & 0xFFFF

    @property
    def unresolved_node_flag(self) -> bool | None:
        """Preserve node bit 21 without assigning undocumented semantics."""

        if self.kind != "node":
            return None
        return bool((self.value >> 21) & 1)

    @property
    def common_text_present(self) -> bool | None:
        if self.kind != "node":
            return None
        # IBM documents zero as common text present; real QDDSI clusters
        # independently place that flag at bit 20.
        return not bool((self.value >> 20) & 1)

    @property
    def direction(self) -> str | None:
        if self.kind != "node":
            return None
        return "right" if ((self.value >> 19) & 1) else "left"

    @property
    def bit_to_test(self) -> int | None:
        if self.kind != "node":
            return None
        return (self.value >> 16) & 0x7

    @property
    def xor_displacement(self) -> int | None:
        if self.kind != "node":
            return None
        return self.value & 0xFFFF

    @property
    def segment_table_index(self) -> int | None:
        if self.kind != "page-pointer":
            return None
        return (self.value >> 16) & 0x3F

    @property
    def page_offset(self) -> int | None:
        if self.kind != "page-pointer":
            return None
        return self.value & 0xFFFF

@dataclass(frozen=True)
class MachineIndexElementProbe:
    """Decoded element at a caller-selected offset within a logical page."""

    offset: int
    element: MachineIndexElement

@dataclass(frozen=True)
class ContextMachineIndexTerminal:
    """One terminal key recovered from a permanent-context machine index.

    The System/38 VMC manual documents the logical context entry as
    T + S + NL + N + @. Real CISC images store that information in the general
    release-2 machine index with front-end/common-text compression, so the
    reconstructed terminal bytes below are preserved without forcing them into
    the documented expanded layout.

    Across both real images, the final six bytes of ordinary terminal keys are
    a compact object reference: two-byte segment extender plus the high four
    bytes of the 48-bit page-aligned object address. Re-appending two zero
    bytes resolves recovered object primaries exactly in the validation set.
    """

    raw: bytes
    terminal_element_offset: int

    @property
    def object_type(self) -> int | None:
        return self.raw[0] if len(self.raw) >= 2 else None

    @property
    def object_subtype(self) -> int | None:
        return self.raw[1] if len(self.raw) >= 2 else None

    @property
    def compact_object_reference(self) -> bytes | None:
        if len(self.raw) < 8:
            return None
        return self.raw[-6:]

    @property
    def object_address_hint(self) -> InternalAddress | None:
        compact = self.compact_object_reference
        if compact is None:
            return None
        return InternalAddress(
            extender=int.from_bytes(compact[:2], "big"),
            address=int.from_bytes(compact[2:], "big") << 16,
        )

    @property
    def key_bytes(self) -> bytes:
        compact = self.compact_object_reference
        if compact is None:
            return self.raw
        return self.raw[:-6]


@dataclass(frozen=True)
class ContextMachineIndexTraversal:
    """Conservative one-segment permanent-context traversal result."""

    entries: tuple[ContextMachineIndexTerminal, ...]
    root_offset: int
    page_offsets: tuple[int, ...] = ()
    page_pointers: tuple["MachineIndexPagePointerRef", ...] = ()
    complete: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def page_count(self) -> int:
        return len(self.page_offsets)

    @property
    def unresolved_page_pointers(self) -> tuple["MachineIndexPagePointerRef", ...]:
        return tuple(
            pointer for pointer in self.page_pointers if not pointer.followed
        )


@dataclass(frozen=True)
class MachineIndexPagePointerRef:
    """Page pointer encountered while walking a QDDSI machine index."""

    element_offset: int
    segment_table_index: int
    page_offset: int
    key_prefix: bytes
    followed: bool = False

    @property
    def target_offset(self) -> int:
        """Observed byte offset encoded by the pointer's 256-byte units."""

        return self.page_offset << 8


@dataclass(frozen=True)
class DataSpaceIndexEntry:
    """One terminal QDDSI machine-index entry recovered in keyed order.

    Most ordinary V2R3 indexes expose enough common/terminal text to rebuild
    the complete machine key. A small long-key family exposes only the
    distinguishing tree text plus the database-relative-address suffix. In
    those cases key_complete is false, machine_key/user_key are empty, and
    key_evidence preserves only the bytes actually recovered from the tree.
    The database reference can still identify the DKEY row and QDDS ordinal
    without inventing the omitted key bytes.
    """

    machine_key: bytes
    user_key: bytes
    database_reference: bytes
    terminal_element_offset: int
    dkey_index: int = 0
    key_complete: bool = True
    key_evidence: bytes = b""

    @property
    def data_space_number_hint(self) -> int | None:
        """Observed adjusted data-space number in an ordinary DB reference.

        IBM documents an adjusted data-space number followed by an encoded
        ordinal in the database-relative address. Across the ordinary V2R3
        indexes validated so far, byte zero of the four-byte suffix equals the
        zero-based DKEY row number.
        """

        if len(self.database_reference) != 4:
            return None
        return self.database_reference[0]

    @property
    def display_key_bytes(self) -> bytes:
        """Complete user key, or conservative tree-text evidence if partial."""

        return self.user_key if self.key_complete else self.key_evidence

    @property
    def ordinal_hint(self) -> int | None:
        """Observed QDDS ordinal/RRN from an ordinary four-byte DB reference.

        The ordinary V2R3 form validated against more than 100,000 recovered
        index entries uses byte zero for the DKEY/data-space number and the
        final three bytes for the ordinal. Keep this as a hint because IBM also
        documents ordering/internal-flag variants that are not all decoded.
        """

        if len(self.database_reference) != 4:
            return None
        if self.data_space_number_hint != self.dkey_index:
            return None
        return int.from_bytes(self.database_reference[1:], "big")


@dataclass(frozen=True)
class DataSpaceIndexTraversal:
    """Conservative traversal result for one recovered QDDSI machine index."""

    entries: tuple[DataSpaceIndexEntry, ...]
    expected_entries: int
    root_offset: int
    page_size: int | None
    page_type: int | None
    free_bytes: int | None
    first_free_offset: int | None
    page_offsets: tuple[int, ...] = ()
    page_pointers: tuple[MachineIndexPagePointerRef, ...] = ()
    complete: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def page_count(self) -> int:
        return len(self.page_offsets)

    @property
    def complete_key_count(self) -> int:
        return sum(1 for entry in self.entries if entry.key_complete)

    @property
    def partial_key_count(self) -> int:
        return sum(1 for entry in self.entries if not entry.key_complete)

    @property
    def unresolved_page_pointers(self) -> tuple[MachineIndexPagePointerRef, ...]:
        return tuple(pointer for pointer in self.page_pointers if not pointer.followed)


def decode_context_machine_index(
    data: bytes,
    *,
    root_offset: int = CONTEXT_MACHINE_INDEX_ROOT_OFFSET,
) -> ContextMachineIndexTraversal:
    """Traverse an ordinary permanent-context release-2 machine index.

    IBM documents permanent contexts as using the general release-2 machine
    index. The node/common-text/text-element mechanics are therefore shared
    with QDDSI, but context placement is validated independently: non-empty
    ordinary eight-page 04/01 contexts on both real images place the active
    root at +0x800.

    Real V2R3 QGPL independently validates context page pointers whose segment
    table index is zero: their low field is in 256-byte units within the
    recovered context segment, the same physical pointer encoding seen in
    QDDSI. Nonzero segment-table indexes remain unresolved and are preserved as
    evidence rather than guessed.
    """

    if root_offset < 0 or root_offset + 3 > len(data):
        raise ValueError("context machine-index root is outside recovered segment")

    root = MachineIndexElement(data[root_offset : root_offset + 3])
    if root.raw == b"\x00\x00\x00":
        return ContextMachineIndexTraversal(
            entries=(),
            root_offset=root_offset,
            page_offsets=(),
            complete=True,
        )
    if root.kind != "node":
        raise ValueError("context machine-index root does not begin with a node")

    entries: list[ContextMachineIndexTerminal] = []
    pointers: list[MachineIndexPagePointerRef] = []
    page_offsets: list[int] = []
    warnings: list[str] = []
    visited_nodes: set[tuple[int, int, int]] = set()
    visited_pages: set[int] = set()
    emitted: set[bytes] = set()
    complete = True

    def mark_incomplete(message: str) -> None:
        nonlocal complete
        complete = False
        if message not in warnings:
            warnings.append(message)

    def expand_low16(page_start: int, low_value: int) -> int:
        result = (page_start & ~0xFFFF) | low_value
        if result < page_start:
            result += 0x10000
        return result

    def walk_page(
        page_start: int,
        prefix: bytes,
        page_depth: int = 0,
    ) -> None:
        if page_depth > 256:
            mark_incomplete("context machine-index page depth exceeded safety limit")
            return
        if page_start in visited_pages:
            mark_incomplete(
                f"context machine-index page loop detected at 0x{page_start:04X}"
            )
            return
        if page_start < 0 or page_start + 3 > len(data):
            mark_incomplete(
                f"context machine-index page 0x{page_start:04X} is outside segment"
            )
            return

        page_root = MachineIndexElement(data[page_start : page_start + 3])
        if page_root.kind != "node":
            mark_incomplete(
                f"context machine-index page 0x{page_start:04X} "
                "does not begin with a node"
            )
            return

        visited_pages.add(page_start)
        page_offsets.append(page_start)

        def read_text(
            element: MachineIndexElement,
            *,
            element_offset: int,
        ) -> bytes | None:
            displacement = element.text_displacement
            length = element.text_storage_length
            if displacement is None or length is None or displacement == 0:
                return None
            text_offset = expand_low16(page_start, displacement)
            end = text_offset + length
            if text_offset < 0 or end > len(data):
                mark_incomplete(
                    f"context text at 0x{element_offset:04X} "
                    "points outside recovered segment"
                )
                return None
            return data[text_offset:end]

        def emit_terminal(
            branch_prefix: bytes,
            element: MachineIndexElement,
            element_offset: int,
        ) -> None:
            text = read_text(element, element_offset=element_offset)
            if text is None:
                return
            raw = branch_prefix + text
            if raw in emitted:
                return
            emitted.add(raw)
            entries.append(
                ContextMachineIndexTerminal(
                    raw=raw,
                    terminal_element_offset=element_offset,
                )
            )

        def walk_node(
            node_offset: int,
            origin_node_offset: int,
            node_prefix: bytes,
            depth: int = 0,
        ) -> None:
            if depth > 512:
                mark_incomplete(
                    "context machine-index node depth exceeded safety limit"
                )
                return
            visit_key = (page_start, node_offset, origin_node_offset)
            if visit_key in visited_nodes:
                mark_incomplete(
                    "context machine-index node loop detected at "
                    f"0x{node_offset:04X}"
                )
                return
            visited_nodes.add(visit_key)

            if node_offset < 0 or node_offset + 3 > len(data):
                mark_incomplete(
                    f"context node offset 0x{node_offset:04X} is outside segment"
                )
                return
            node = MachineIndexElement(data[node_offset : node_offset + 3])
            if node.kind != "node" or node.xor_displacement is None:
                mark_incomplete(f"expected context node at 0x{node_offset:04X}")
                return

            cluster_low = (
                (origin_node_offset & 0xFFFF) ^ node.xor_displacement
            )
            cluster_offset = expand_low16(page_start, cluster_low)
            required = 9 if node.common_text_present else 6
            if cluster_offset < 0 or cluster_offset + required > len(data):
                mark_incomplete(
                    f"context node at 0x{node_offset:04X} points outside segment"
                )
                return

            branch_prefix = node_prefix
            if node.common_text_present:
                common_offset = cluster_offset + 6
                common = MachineIndexElement(
                    data[common_offset : common_offset + 3]
                )
                if common.kind != "text":
                    mark_incomplete(
                        "context common-text slot "
                        f"0x{common_offset:04X} is not text"
                    )
                    return
                common_text = read_text(
                    common,
                    element_offset=common_offset,
                )
                if common_text is None:
                    return
                branch_prefix += common_text

            for branch_offset in (cluster_offset, cluster_offset + 3):
                branch = MachineIndexElement(
                    data[branch_offset : branch_offset + 3]
                )
                if branch.kind == "text":
                    if branch.text_displacement:
                        emit_terminal(
                            branch_prefix,
                            branch,
                            branch_offset,
                        )
                elif branch.kind == "node":
                    walk_node(
                        branch_offset,
                        node_offset,
                        branch_prefix,
                        depth + 1,
                    )
                else:
                    segment_index = branch.segment_table_index or 0
                    pointer_value = branch.page_offset or 0
                    target_offset = pointer_value << 8
                    can_follow = (
                        segment_index == 0
                        and target_offset not in visited_pages
                        and target_offset + 3 <= len(data)
                        and MachineIndexElement(
                            data[target_offset : target_offset + 3]
                        ).kind
                        == "node"
                    )
                    pointers.append(
                        MachineIndexPagePointerRef(
                            element_offset=branch_offset,
                            segment_table_index=segment_index,
                            page_offset=pointer_value,
                            key_prefix=branch_prefix,
                            followed=can_follow,
                        )
                    )
                    if segment_index != 0:
                        mark_incomplete(
                            "context machine-index page pointer uses unresolved "
                            f"segment-table index {segment_index}"
                        )
                    elif target_offset in visited_pages:
                        mark_incomplete(
                            "context machine-index page pointer loops to "
                            f"0x{target_offset:04X}"
                        )
                    elif target_offset + 3 > len(data):
                        mark_incomplete(
                            "context machine-index page pointer target "
                            f"0x{target_offset:04X} is outside recovered segment"
                        )
                    elif not can_follow:
                        mark_incomplete(
                            "context machine-index page pointer target "
                            f"0x{target_offset:04X} does not begin with a node"
                        )
                    else:
                        walk_page(
                            target_offset,
                            branch_prefix,
                            page_depth + 1,
                        )

        walk_node(page_start, page_start, prefix)

    walk_page(root_offset, b"")
    return ContextMachineIndexTraversal(
        entries=tuple(entries),
        root_offset=root_offset,
        page_offsets=tuple(page_offsets),
        page_pointers=tuple(pointers),
        complete=complete,
        warnings=tuple(warnings),
    )


def decode_data_space_index_root(
    data: bytes,
    layout: DataSpaceIndexLayout,
    *,
    virtual_address: int | None = None,
) -> DataSpaceIndexTraversal:
    """Walk an ordinary QDDSI release-2 machine index in keyed order.

    IBM says a data-space index contains a general release-2 machine index.
    Real V2R3 QDDSIs establish the physical details used here: the object
    header points to a machine-index control area whose +0x20 pointer identifies
    the active root page; free-byte/first-free fields constrain each logical
    page; node displacements XOR with the originating node offset; and text
    length is encoded as byte-count minus one.

    Page pointers with segment-table index zero are also validated on four
    multi-page real indexes. Their low field is in 256-byte units within the
    recovered QDDSI segment. Other segment-table indexes remain unresolved
    and are reported without being followed.
    """

    root_offset = QDDSI_MACHINE_INDEX_ROOT_OFFSET

    if layout.dkey_count == 0:
        return DataSpaceIndexTraversal(
            entries=(),
            expected_entries=0,
            root_offset=root_offset,
            page_size=None,
            page_type=None,
            free_bytes=None,
            first_free_offset=None,
            complete=True,
        )
    active_specs = tuple(
        (index, spec)
        for index, spec in enumerate(layout.keys)
        if spec.key_count > 0
    )
    if not active_specs:
        return DataSpaceIndexTraversal(
            entries=(),
            expected_entries=0,
            root_offset=root_offset,
            page_size=None,
            page_type=None,
            free_bytes=None,
            first_free_offset=None,
            complete=True,
        )

    # IBM permits one index to cover multiple data spaces with different key
    # lengths. Real V2R3 machine keys identify the zero-based DKEY row in byte
    # zero of the ordinary four-byte database-relative address, so terminal
    # keys can be matched to their own DKEY shape instead of forcing one global
    # key length.
    expected_entries = sum(spec.key_count for _, spec in active_specs)
    for _, spec in active_specs:
        if spec.user_key_length > spec.machine_key_length:
            raise ValueError("QDDSI user key is longer than machine key")

    if virtual_address is not None:
        control_end = QDDSI_MACHINE_INDEX_CONTROL_POINTER_OFFSET + 6
        if len(data) < control_end:
            raise ValueError("QDDSI segment has no machine-index control pointer")
        control_address = int.from_bytes(
            data[
                QDDSI_MACHINE_INDEX_CONTROL_POINTER_OFFSET :
                control_end
            ],
            "big",
        )
        control_offset = control_address - virtual_address
        root_pointer_offset = (
            control_offset + QDDSI_MACHINE_INDEX_CONTROL_ROOT_POINTER_OFFSET
        )
        if (
            control_address == 0
            or control_offset < 0
            or root_pointer_offset + 6 > len(data)
        ):
            raise ValueError("QDDSI machine-index control area is not recovered")
        root_address = int.from_bytes(
            data[root_pointer_offset : root_pointer_offset + 6],
            "big",
        )
        root_offset = root_address - virtual_address
        if (
            root_address == 0
            or root_offset < 0
            or root_offset + 8 > len(data)
        ):
            raise ValueError("QDDSI active machine-index root is not recovered")

    if len(data) < root_offset + 8:
        raise ValueError("QDDSI segment has no complete root-page header")

    entries: list[DataSpaceIndexEntry] = []
    page_pointers: list[MachineIndexPagePointerRef] = []
    page_offsets: list[int] = []
    warnings: list[str] = []
    visited_pages: set[int] = set()
    visited_nodes: set[tuple[int, int, int]] = set()
    emitted_keys: set[bytes] = set()
    complete = True
    root_metadata: tuple[int, int, int, int] | None = None

    def mark_incomplete(message: str) -> None:
        nonlocal complete
        complete = False
        if message not in warnings:
            warnings.append(message)

    def expand_low16(page_start: int, low_value: int) -> int:
        """Map a 16-bit in-page address into the page's segment window."""

        result = (page_start & ~0xFFFF) | low_value
        if result < page_start:
            result += 0x10000
        return result

    def page_metadata(
        page_start: int,
    ) -> tuple[MachineIndexElement, int, int, int, int]:
        if page_start < 0 or page_start + 8 > len(data):
            raise ValueError(
                f"machine-index page 0x{page_start:X} is outside recovered segment"
            )
        page_root = MachineIndexElement(data[page_start : page_start + 3])
        if page_root.kind != "node":
            raise ValueError(
                f"machine-index page 0x{page_start:X} does not begin with a node"
            )
        page_type = data[page_start + 3]
        free_bytes = int.from_bytes(
            data[page_start + 4 : page_start + 6],
            "big",
        )
        first_free_low = int.from_bytes(
            data[page_start + 6 : page_start + 8],
            "big",
        )
        first_free = expand_low16(page_start, first_free_low)
        if first_free < page_start + 8:
            raise ValueError(
                f"machine-index page 0x{page_start:X} has invalid first-free offset"
            )

        used_bytes = first_free - page_start
        page_sizes = [
            size
            for size in (512, 1024, 2048, 4096, 8192, 16384, 32768)
            if (
                used_bytes <= size
                and free_bytes <= size
                and used_bytes + free_bytes >= size
                and page_start + size <= len(data)
            )
        ]
        if not page_sizes:
            raise ValueError(
                f"machine-index page 0x{page_start:X} does not imply a "
                "supported logical page size"
            )
        page_size = min(page_sizes)
        if first_free > page_start + page_size:
            raise ValueError(
                f"machine-index page 0x{page_start:X} first-free lies past page end"
            )
        return page_root, page_size, page_type, free_bytes, first_free

    def emit_terminal(
        page_start: int,
        page_end: int,
        first_free: int,
        prefix: bytes,
        element: MachineIndexElement,
        element_offset: int,
    ) -> None:
        displacement = element.text_displacement
        length = element.text_storage_length
        if displacement is None or length is None or displacement == 0:
            return
        text_offset = expand_low16(page_start, displacement)
        text_end = text_offset + length
        if (
            text_offset < page_start
            or text_end > first_free
            or text_end > page_end
        ):
            mark_incomplete(
                "text element at "
                f"0x{element_offset:04X} points outside its active page"
            )
            return
        tree_key = prefix + data[text_offset:text_end]
        if len(tree_key) < 4:
            mark_incomplete(
                f"terminal key at 0x{element_offset:04X} is shorter than "
                "the ordinary four-byte database reference"
            )
            return

        database_reference = tree_key[-4:]
        dkey_index = database_reference[0]
        if dkey_index >= len(layout.keys):
            mark_incomplete(
                "terminal key at "
                f"0x{element_offset:04X} names DKEY row {dkey_index}, "
                f"but only {len(layout.keys)} row(s) are decoded"
            )
            return
        spec = layout.keys[dkey_index]
        if spec.key_count <= 0:
            mark_incomplete(
                f"terminal key at 0x{element_offset:04X} names empty "
                f"DKEY row {dkey_index}"
            )
            return
        if len(tree_key) > spec.machine_key_length:
            mark_incomplete(
                "terminal key at "
                f"0x{element_offset:04X} has {len(tree_key)} bytes for "
                f"DKEY {dkey_index}; expected no more than "
                f"{spec.machine_key_length}"
            )
            return

        split = (
            spec.split_machine_key(tree_key)
            if len(tree_key) == spec.machine_key_length
            else None
        )
        key_complete = split is not None
        if key_complete:
            user_key, database_reference = split
            machine_key = tree_key
            key_evidence = b""
        else:
            # IBM's machine-index description allows common/terminal text
            # compression. The long-key V2R3 QAOK* family preserves only
            # distinguishing tree text plus the ordinary four-byte DB reference.
            # Keep that text as evidence and use the validated DB reference for
            # keyed-order/RRN navigation without fabricating omitted key bytes.
            machine_key = b""
            user_key = b""
            key_evidence = tree_key[:-4]

        if tree_key in emitted_keys:
            return
        emitted_keys.add(tree_key)
        entries.append(
            DataSpaceIndexEntry(
                machine_key=machine_key,
                user_key=user_key,
                database_reference=database_reference,
                terminal_element_offset=element_offset,
                dkey_index=dkey_index,
                key_complete=key_complete,
                key_evidence=key_evidence,
            )
        )

    def walk_page(
        page_start: int,
        prefix: bytes,
        page_depth: int = 0,
    ) -> None:
        nonlocal root_metadata
        if page_depth > 256:
            mark_incomplete("machine-index page depth exceeded safety limit")
            return
        if page_start in visited_pages:
            mark_incomplete(
                f"machine-index page loop detected at 0x{page_start:04X}"
            )
            return
        visited_pages.add(page_start)
        page_offsets.append(page_start)

        try:
            page_root, page_size, page_type, free_bytes, first_free = (
                page_metadata(page_start)
            )
        except ValueError as exc:
            mark_incomplete(str(exc))
            return
        if page_start == root_offset:
            root_metadata = (page_size, page_type, free_bytes, first_free)
        page_end = page_start + page_size

        def read_text(
            element: MachineIndexElement,
            *,
            element_offset: int,
        ) -> bytes | None:
            displacement = element.text_displacement
            length = element.text_storage_length
            if displacement is None or length is None or displacement == 0:
                return None
            text_offset = expand_low16(page_start, displacement)
            text_end = text_offset + length
            if (
                text_offset < page_start
                or text_end > first_free
                or text_end > page_end
            ):
                mark_incomplete(
                    "text element at "
                    f"0x{element_offset:04X} points outside its active page"
                )
                return None
            return data[text_offset:text_end]

        def walk_node(
            node_offset: int,
            origin_node_offset: int,
            node_prefix: bytes,
            depth: int = 0,
        ) -> None:
            if depth > 512:
                mark_incomplete("machine-index node depth exceeded safety limit")
                return
            visit_key = (page_start, node_offset, origin_node_offset)
            if visit_key in visited_nodes:
                mark_incomplete(
                    f"machine-index node loop detected at 0x{node_offset:04X}"
                )
                return
            visited_nodes.add(visit_key)

            if node_offset < page_start or node_offset + 3 > first_free:
                mark_incomplete(
                    f"machine-index node offset 0x{node_offset:04X} is outside used page"
                )
                return
            node = MachineIndexElement(data[node_offset : node_offset + 3])
            if node.kind != "node" or node.xor_displacement is None:
                mark_incomplete(f"expected node at 0x{node_offset:04X}")
                return

            cluster_low = (
                (origin_node_offset & 0xFFFF) ^ node.xor_displacement
            )
            cluster_offset = expand_low16(page_start, cluster_low)
            required = 9 if node.common_text_present else 6
            if (
                cluster_offset < page_start + 8
                or cluster_offset + required > first_free
            ):
                mark_incomplete(
                    "node at "
                    f"0x{node_offset:04X} points to invalid cluster "
                    f"0x{cluster_offset:04X}"
                )
                return

            branch_prefix = node_prefix
            if node.common_text_present:
                common_offset = cluster_offset + 6
                common = MachineIndexElement(
                    data[common_offset : common_offset + 3]
                )
                if common.kind != "text":
                    mark_incomplete(
                        f"common-text slot at 0x{common_offset:04X} is not text"
                    )
                    return
                common_text = read_text(common, element_offset=common_offset)
                if common_text is None:
                    mark_incomplete(
                        f"common text at 0x{common_offset:04X} is not recoverable"
                    )
                    return
                branch_prefix += common_text

            for branch_offset in (cluster_offset, cluster_offset + 3):
                branch = MachineIndexElement(
                    data[branch_offset : branch_offset + 3]
                )
                if branch.kind == "text":
                    if branch.text_displacement:
                        emit_terminal(
                            page_start,
                            page_end,
                            first_free,
                            branch_prefix,
                            branch,
                            branch_offset,
                        )
                elif branch.kind == "node":
                    walk_node(
                        branch_offset,
                        node_offset,
                        branch_prefix,
                        depth + 1,
                    )
                else:
                    segment_index = branch.segment_table_index or 0
                    pointer_value = branch.page_offset or 0
                    target_offset = pointer_value << 8
                    can_follow = (
                        segment_index == 0
                        and target_offset not in visited_pages
                        and target_offset + 8 <= len(data)
                    )
                    page_pointers.append(
                        MachineIndexPagePointerRef(
                            element_offset=branch_offset,
                            segment_table_index=segment_index,
                            page_offset=pointer_value,
                            key_prefix=branch_prefix,
                            followed=can_follow,
                        )
                    )
                    if segment_index != 0:
                        mark_incomplete(
                            "machine-index page pointer uses unresolved "
                            f"segment-table index {segment_index}"
                        )
                    elif target_offset in visited_pages:
                        mark_incomplete(
                            f"machine-index page pointer loops to 0x{target_offset:04X}"
                        )
                    elif target_offset + 8 > len(data):
                        mark_incomplete(
                            f"machine-index page pointer target 0x{target_offset:04X} "
                            "is outside recovered segment"
                        )
                    else:
                        walk_page(
                            target_offset,
                            branch_prefix,
                            page_depth + 1,
                        )

        walk_node(page_start, page_start, prefix)

    walk_page(root_offset, b"")

    if root_metadata is None:
        raise ValueError("QDDSI root page could not be decoded")
    page_size, page_type, free_bytes, first_free_offset = root_metadata

    if len(entries) != expected_entries:
        mark_incomplete(
            f"recovered {len(entries)} machine-index key(s); "
            f"populated DKEY rows report {expected_entries}"
        )

    entries_by_dkey = Counter(entry.dkey_index for entry in entries)
    for dkey_index, spec in active_specs:
        if entries_by_dkey[dkey_index] != spec.key_count:
            mark_incomplete(
                f"DKEY {dkey_index} recovered {entries_by_dkey[dkey_index]} "
                f"key(s); row reports {spec.key_count}"
            )

    return DataSpaceIndexTraversal(
        entries=tuple(entries),
        expected_entries=expected_entries,
        root_offset=root_offset,
        page_size=page_size,
        page_type=page_type,
        free_bytes=free_bytes,
        first_free_offset=first_free_offset,
        page_offsets=tuple(page_offsets),
        page_pointers=tuple(page_pointers),
        complete=complete,
        warnings=tuple(warnings),
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

    def read_document_byte_string(
        self,
        obj: RecoveredObject,
    ) -> tuple[DocumentByteStringInfo, bytes]:
        """Read a conservatively validated IBM *DOCBSS workstation byte stream."""

        if (
            obj.object_type != 0x06
            or obj.object_subtype != 0xC1
        ):
            raise ValueError("target object is not IBM *DOCBSS (MI 06/C1)")

        data = self.read_segment_bytes(obj.segment)
        info = DocumentByteStringInfo.from_primary_segment(data)
        info.validate_for_export(len(data))
        start = info.payload_offset
        end = start + info.payload_length
        return info, data[start:end]

    def read_context_machine_index(
        self,
        context: RecoveredObject,
    ) -> ContextMachineIndexTraversal | None:
        """Traverse the ordinary machine-index root of a permanent context."""

        if (
            context.object_type != 0x04
            or context.object_subtype != 0x01
        ):
            raise ValueError("target object is not a permanent context/library")
        data = self.read_segment_bytes(context.segment)
        try:
            return decode_context_machine_index(data)
        except ValueError:
            return None

    def probe_machine_index_page(
        self,
        context: RecoveredObject,
        page_number: int,
        *,
        element_offset: int = 0,
        count: int = 32,
        page_size: int = PAGE_SIZE,
        page_origin: int = 0,
    ) -> list[MachineIndexElementProbe]:
        """Decode three-byte machine-index elements from one context page.

        This is intentionally a forensic/reverse-engineering helper rather
        than a full index traversal. IBM documents release-2 indexes as
        three-byte elements and logical pages from 512 through 32768 bytes.
        Until the context object's index-page header/trunk location is decoded,
        the caller explicitly selects the page origin, page, and element-stream
        offset. The element offset may use any modulo-3 phase because the page
        header/trunk length is not yet known.
        """

        if (
            context.object_type != 0x04
            or context.object_subtype != 0x01
        ):
            raise ValueError("target object is not a permanent context/library")
        if page_size < PAGE_SIZE or page_size % PAGE_SIZE:
            raise ValueError("machine-index page size must be a multiple of 512")
        if page_origin < 0:
            raise ValueError("machine-index page origin must be non-negative")
        if element_offset < 0 or element_offset >= page_size:
            raise ValueError("element offset is outside the logical page")
        if count < 1:
            raise ValueError("count must be positive")

        data = self.read_segment_bytes(context.segment)
        start = page_origin + page_number * page_size
        end = start + page_size
        if start < 0 or end > len(data):
            raise ValueError(
                f"logical page {page_number} at origin 0x{page_origin:X} "
                "is outside the context segment"
            )

        page = data[start:end]
        probes: list[MachineIndexElementProbe] = []
        offset = element_offset
        while len(probes) < count and offset + 3 <= len(page):
            probes.append(
                MachineIndexElementProbe(
                    offset=offset,
                    element=MachineIndexElement(page[offset : offset + 3]),
                )
            )
            offset += 3
        return probes

    def resolve_file_formats(
        self,
        file_obj: RecoveredObject,
        inventory: ObjectInventory,
    ) -> list[RecoveredObject]:
        """Find format objects referenced by a recovered *FILE FCB.

        A physical/logical file's FCB carries the record-format name(s). Rather
        than hard-code one FCB offset, search the recovered FCB segment for the
        10-byte padded names of recovered MI 19/51 format objects. This handles
        both simple source files and larger keyed file FCB layouts.
        """

        if (
            file_obj.object_type != 0x19
            or file_obj.object_subtype != 0x01
        ):
            raise ValueError("target object is not an MI 19/01 *FILE")

        file_data = self.read_segment_bytes(file_obj.segment)
        formats = [
            obj
            for obj in inventory.objects
            if obj.object_type == 0x19 and obj.object_subtype == 0x51
        ]

        matches: list[RecoveredObject] = []
        seen: set[tuple[int, int]] = set()
        for format_obj in formats:
            name10 = format_obj.epa.name_raw[:10]
            if not name10.strip(b"\x40\x00"):
                continue
            if name10 not in file_data:
                continue
            key = (
                format_obj.segment.header.owner.extender,
                format_obj.segment.virtual_address,
            )
            if key in seen:
                continue
            seen.add(key)
            matches.append(format_obj)

        return sorted(
            matches,
            key=lambda obj: (
                obj.name,
                obj.segment.virtual_address,
                obj.segment.start_lba,
            ),
        )

    def read_format_fields(
        self,
        format_obj: RecoveredObject,
        *,
        record_length: int | None = None,
    ) -> tuple[FormatField, ...]:
        """Decode field descriptions from an MI 19/51 format object."""

        if (
            format_obj.object_type != 0x19
            or format_obj.object_subtype != 0x51
        ):
            raise ValueError("target object is not an MI 19/51 format")
        data = self.read_segment_bytes(format_obj.segment)
        return decode_format_fields(
            data,
            record_length=record_length,
        )

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

    def resolve_member_storage(
        self,
        member: RecoveredObject,
        inventory: ObjectInventory,
        segments: SegmentRecoveryResult,
    ) -> MemberStorage:
        """Resolve a 0D50 member cursor to its QDDS/QDDSI storage.

        Real-image validation now gives us a stronger relationship than the
        original same-name heuristic: the cursor itself carries direct QDDSI
        and QDDS internal addresses at observed offsets +0x128 and +0x300.
        Use those addresses when present. Same-name matching remains a fallback
        for cursors whose direct pointer is null or unavailable.

        Importantly, retain a non-null direct QDDS address even when the QDDS
        primary segment is absent from this disk. Secondary segment groups can
        still point back to that owner, which is expected on a scatter-loaded
        multi-disk AS/400 when only one disk image survives.
        """

        if not member.is_member_cursor:
            raise ValueError("object is not a 0D50 member cursor")

        cursor_bytes = self.read_segment_bytes(member.segment)
        cursor_extender = member.segment.header.owner.extender
        pointers = MemberStoragePointers.from_cursor_segment(cursor_bytes)

        def exact_object(
            address: InternalAddress | None,
            *,
            object_type: int,
            object_subtype: int,
        ) -> RecoveredObject | None:
            if address is None:
                return None
            matches = [
                obj
                for obj in inventory.objects
                if obj.object_type == object_type
                and obj.object_subtype == object_subtype
                and obj.object_address.key == address.key
            ]
            if not matches:
                return None
            return sorted(
                matches,
                key=lambda obj: (
                    obj.segment.virtual_address,
                    obj.segment.start_lba,
                ),
            )[0]

        # Preserve the original correlation as a compatibility fallback. QDDS
        # and QDDSI are internal components and do not necessarily carry the
        # library context back-pointer used by external *FILE/*MEM objects.
        qdds_by_name = inventory.matching_objects(
            name_raw=member.epa.name_raw,
            object_type=0x0B,
            object_subtype=0x90,
        )
        qddsi_by_name = inventory.matching_objects(
            name_raw=member.epa.name_raw,
            object_type=0x0C,
            object_subtype=0x90,
        )

        def choose_by_name(
            objects: list[RecoveredObject],
        ) -> RecoveredObject | None:
            if not objects:
                return None
            same_extender = [
                obj
                for obj in objects
                if obj.segment.header.owner.extender == cursor_extender
            ]
            pool = same_extender or objects
            pointed = []
            for obj in pool:
                if obj.object_address.to_bytes() in cursor_bytes:
                    pointed.append(obj)
            if len(pointed) == 1:
                return pointed[0]
            return pool[0]

        if pointers.data_space is not None:
            data_space_address = pointers.data_space
            data_space = exact_object(
                data_space_address,
                object_type=0x0B,
                object_subtype=0x90,
            )
        else:
            data_space = choose_by_name(qdds_by_name)
            data_space_address = (
                data_space.object_address
                if data_space is not None
                else None
            )

        if pointers.data_index is not None:
            data_index_address = pointers.data_index
            data_index = exact_object(
                data_index_address,
                object_type=0x0C,
                object_subtype=0x90,
            )
        else:
            data_index = choose_by_name(qddsi_by_name)
            data_index_address = (
                data_index.object_address
                if data_index is not None
                else None
            )

        owned: list[RecoveredSegment] = []
        if data_space_address is not None:
            owner_key = data_space_address.key
            owned = sorted(
                [
                    segment
                    for segment in segments.segments
                    if segment.owner_key == owner_key
                ],
                key=lambda segment: (
                    segment.virtual_address,
                    segment.start_lba,
                ),
            )

        return MemberStorage(
            cursor=member,
            data_space=data_space,
            data_index=data_index,
            data_segments=tuple(owned),
            data_space_address=data_space_address,
            data_index_address=data_index_address,
        )

    def read_data_space_entry_stream(
        self,
        storage: MemberStorage,
    ) -> tuple[bytes, tuple[RecoveredSegment, ...]]:
        """Return the logical entry stream from recovered QDDS data segments.

        IBM documents the third and subsequent data-space segment groups as
        containing entries strung end-to-end, with 32-byte segment-group
        headers excluded from the logical addressing space. Real source members
        on both images use segment type 03B4 for these data groups.
        """

        data_segments = tuple(
            sorted(
                (
                    segment
                    for segment in storage.data_segments
                    if segment.header.segment_type == 0x03B4
                ),
                key=lambda segment: (
                    segment.virtual_address,
                    segment.start_lba,
                ),
            )
        )
        if not data_segments:
            return b"", ()

        stream = bytearray()
        for segment in data_segments:
            data = self.read_segment_bytes(segment)
            if len(data) < SEGMENT_HEADER_SIZE:
                continue
            stream.extend(data[SEGMENT_HEADER_SIZE:])
        return bytes(stream), data_segments

    def read_data_space_index_layout(
        self,
        storage: MemberStorage,
    ) -> DataSpaceIndexLayout | None:
        """Decode the QDDSI DKEY/DKYT key specification when recovered."""

        if storage.data_index is None:
            return None
        data = self.read_segment_bytes(storage.data_index.segment)
        try:
            return DataSpaceIndexLayout.from_primary_segment(
                data,
                virtual_address=storage.data_index.segment.virtual_address,
            )
        except ValueError:
            return None

    def read_data_space_index_traversal(
        self,
        storage: MemberStorage,
    ) -> DataSpaceIndexTraversal | None:
        """Enumerate complete keys from an ordinary recovered QDDSI machine index."""

        layout = self.read_data_space_index_layout(storage)
        if layout is None or storage.data_index is None:
            return None
        data = self.read_segment_bytes(storage.data_index.segment)
        try:
            return decode_data_space_index_root(
                data,
                layout,
                virtual_address=storage.data_index.segment.virtual_address,
            )
        except ValueError:
            return None

    def read_data_space_layout(
        self,
        storage: MemberStorage,
    ) -> DataSpaceLayout | None:
        """Read record counts and lengths from the QDDS primary segment."""

        if storage.data_space is None:
            return None
        data = self.read_segment_bytes(storage.data_space.segment)
        try:
            return DataSpaceLayout.from_primary_segment(data)
        except ValueError:
            return None

    def read_data_space_records(
        self,
        storage: MemberStorage,
    ) -> DataSpaceRecordSet | None:
        """Recover ordinal records from a member's QDDS data segments."""

        layout = self.read_data_space_layout(storage)
        if layout is None:
            return None

        stream, data_segments = self.read_data_space_entry_stream(storage)
        if not stream:
            return None

        records = decode_data_space_records(stream, layout)
        if not records:
            return None

        return DataSpaceRecordSet(
            layout=layout,
            records=records,
            data_segment_count=len(data_segments),
            raw_stream_bytes=len(stream),
        )

    def read_source_member(
        self,
        storage: MemberStorage,
    ) -> SourceMemberContent | None:
        """Decode a standard source physical-file member when recognized."""

        record_set = self.read_data_space_records(storage)
        if record_set is None:
            return None
        if (
            record_set.layout.record_length != SOURCE_RECORD_DATA_LENGTH
            or record_set.layout.entry_length != SOURCE_ENTRY_LENGTH
        ):
            return None

        # Limit recognition to the header-declared ordinal range. This avoids
        # accidentally interpreting unused tail space/status areas as records.
        stream = bytearray()
        for record in record_set.records:
            stream.append(record.status)
            stream.extend(record.data)
            stream.extend(record.extra_raw)

        decoded = decode_standard_source_stream(bytes(stream))
        if decoded is None:
            return None

        return SourceMemberContent(
            records=decoded.records,
            default_entry_present=decoded.default_entry_present,
            data_segment_count=record_set.data_segment_count,
            raw_stream_bytes=record_set.raw_stream_bytes,
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
