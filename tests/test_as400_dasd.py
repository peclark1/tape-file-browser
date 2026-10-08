import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from as400_dasd import (
    CONTEXT_MACHINE_INDEX_PAGE_SIZE,
    HEADER_SIZE,
    KNOWN_B10_SHADOW_LOG_VADDR,
    PAGE_SIZE,
    QAOSSS14AnchorRecord,
    QAOSSS14_V2_RECORD_LENGTH,
    SECTOR_SIZE,
    ContextIndexEntry,
    DASDImage,
    DataSpaceIndexKeyField,
    DataSpaceIndexKeySpec,
    DataSpaceIndexLayout,
    DataSpaceLayout,
    DataSpaceRecord,
    DocumentByteStringInfo,
    EPAHeader,
    Extent,
    HeaderSnapshot,
    InternalAddress,
    MachineIndexElement,
    MachineIndexPageHeader,
    MemberStoragePointers,
    RecoveredObject,
    RecoveredSegment,
    SegmentRecoveryResult,
    ScanResult,
    SectorHeader,
    SegmentGroupHeader,
    assemble_document_byte_string,
    decode_context_machine_index,
    decode_context_terminal_name_hint,
    decode_data_space_index_root,
    decode_data_space_records,
    decode_format_fields,
    decode_standard_source_stream,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
B10_FIXTURE = FIXTURE_DIR / "b10_d1_first232064.headers.rle.txt"
P02_FIXTURE = FIXTURE_DIR / "p02_v2r3_selected.headers.rle.txt"
OBJECT_FIXTURE = FIXTURE_DIR / "real_object_headers.txt"
MEMBER_FIXTURE = FIXTURE_DIR / "real_member_metadata.txt"
QDDS_LAYOUT_FIXTURE = FIXTURE_DIR / "real_qdds_layout.txt"
FORMAT_FIELD_FIXTURE = FIXTURE_DIR / "real_format_fields.txt"


def make_header(address, order=0, *, tail=0):
    prefix = address >> 8
    return (
        prefix.to_bytes(5, "big")
        + bytes([order & 0x0F, 0, tail])
    )


def load_rle_fixture(path):
    chunks = []
    expected_start = 0
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        start_text, count_text, hex_header = line.split()
        start = int(start_text)
        count = int(count_text)
        if start != expected_start:
            raise ValueError(
                f"fixture gap/overlap at {start}, expected {expected_start}"
            )
        header = bytes.fromhex(hex_header)
        if len(header) != HEADER_SIZE:
            raise ValueError("fixture header is not 8 bytes")
        chunks.append(header * count)
        expected_start += count
    return b"".join(chunks)




def load_object_fixture(path):
    result = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        label, lba_text, hex_data = line.split()
        result[label] = (int(lba_text), bytes.fromhex(hex_data))
    return result


def load_offset_fixture(path):
    result = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        label, offset_text, hex_data = line.split()
        result[label] = (int(offset_text, 0), bytes.fromhex(hex_data))
    return result


def load_qdds_layout_fixture(path):
    result = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        label, counts_hex, common_entry_hex, layout_hex = line.split()
        primary = bytearray(0x1EE)
        primary[0x118:0x126] = bytes.fromhex(counts_hex)
        primary[0x13C:0x140] = bytes.fromhex(common_entry_hex)
        primary[0x1E0:0x1F0] = bytes.fromhex(layout_hex)
        result[label] = bytes(primary)
    return result


def load_format_field_fixture(path):
    result = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        label, descriptor_hex = line.split()
        result[label] = bytes.fromhex(descriptor_hex)
    return result

def make_internal_address(extender, address):
    return extender.to_bytes(2, "big") + address.to_bytes(6, "big")


def make_qddsi_root_fixture(
    root_hex,
    *,
    key_count,
    user_key_length,
    machine_key_length,
):
    """Build the minimum ordinary QDDSI metadata around a real root shape."""

    base = 0x001000000000
    primary = bytearray(0x1800)
    primary[0x11E:0x120] = (1).to_bytes(2, "big")
    primary[0x12A:0x130] = (base + 0x400).to_bytes(6, "big")

    row = memoryview(primary)[0x400:0x440]
    row[0:8] = make_internal_address(1, 0x000F00000000)
    row[0x10:0x14] = key_count.to_bytes(4, "big")
    row[0x18:0x1A] = (0).to_bytes(2, "big")
    row[0x1A:0x1C] = user_key_length.to_bytes(2, "big")
    row[0x1C:0x1E] = machine_key_length.to_bytes(2, "big")

    root = bytes.fromhex(root_hex)
    primary[0x1000 : 0x1000 + len(root)] = root
    data = bytes(primary)
    layout = DataSpaceIndexLayout.from_primary_segment(
        data,
        virtual_address=base,
    )
    return data, layout

def make_segment_page(
    virtual_address,
    *,
    segment_type,
    object_type,
    object_subtype,
    name,
    context_extender,
    context_address,
    owner_extender=1,
):
    page = bytearray(PAGE_SIZE)

    # 32-byte YYSGHDR
    page[0:2] = segment_type.to_bytes(2, "big")
    page[2:4] = (1).to_bytes(2, "big")
    page[4] = 0
    page[5] = 1
    page[6:8] = (0x8000).to_bytes(2, "big")
    page[8:16] = make_internal_address(
        owner_extender, virtual_address
    )
    page[24:32] = make_internal_address(
        owner_extender, virtual_address + 0x100
    )

    # Common EPA header at +0x20.
    epa = memoryview(page)[32:]
    epa[0] = 0x80
    epa[1] = 0
    epa[2] = object_type
    epa[3] = object_subtype
    epa[4:34] = name.encode("cp037").ljust(30, b"\x40")
    epa[0x48:0x50] = make_internal_address(
        context_extender, context_address
    )
    epa[0x50:0x58] = make_internal_address(
        owner_extender, virtual_address
    )
    return bytes(page)

def write_image(path, sectors):
    with open(path, "wb") as handle:
        for header, payload in sectors:
            handle.write(header)
            handle.write(payload)


class DASDHeaderTests(unittest.TestCase):
    def test_header_decode(self):
        header = SectorHeader(bytes.fromhex("00a1c30100050000"))
        self.assertEqual(header.virtual_page_prefix, 0x00A1C30100)
        self.assertEqual(header.virtual_address, 0x00A1C3010000)
        self.assertTrue(header.page_aligned)
        self.assertEqual(header.extent_order, 5)
        self.assertEqual(header.extent_pages, 32)
        self.assertEqual(header.reserved_byte, 0)





    def test_real_format_field_descriptors(self):
        fixture = load_format_field_fixture(FORMAT_FIELD_FIXTURE)

        qclsrc_blob = (
            b"\x00" * 17
            + fixture["QCLSRC_SRCSEQ"]
            + b"\x00" * 19
            + fixture["QCLSRC_SRCDAT"]
            + b"\x00" * 23
            + fixture["QCLSRC_SRCDTA"]
        )
        qclsrc = decode_format_fields(qclsrc_blob, record_length=92)
        self.assertEqual(
            [
                (
                    field.name,
                    field.type_name,
                    field.offset,
                    field.storage_length,
                    field.digits,
                    field.decimal_positions,
                )
                for field in qclsrc
            ],
            [
                ("SRCSEQ", "ZONED", 0, 6, 6, 2),
                ("SRCDAT", "ZONED", 6, 6, 6, 0),
                ("SRCDTA", "CHAR", 12, 80, 0, 0),
            ],
        )

        pd_blob = b"\x00".join(
            [
                fixture["PD00RC_PDCO"],
                fixture["PD00RC_PDPCTL"],
                fixture["PD00RC_PDTCR"],
                fixture["PD00RC_PDDLM"],
                fixture["PD00RC_PDPGM"],
            ]
        )
        fields = decode_format_fields(pd_blob, record_length=452)
        by_name = {field.name: field for field in fields}

        self.assertEqual(by_name["PDCO"].type_name, "CHAR")
        self.assertEqual((by_name["PDCO"].offset, by_name["PDCO"].storage_length), (0, 3))
        self.assertEqual(by_name["PDPCTL"].type_name, "ZONED")
        self.assertEqual((by_name["PDPCTL"].offset, by_name["PDPCTL"].digits), (6, 6))
        self.assertEqual(by_name["PDTCR"].type_name, "PACKED")
        self.assertEqual((by_name["PDTCR"].offset, by_name["PDTCR"].storage_length, by_name["PDTCR"].digits), (429, 4, 7))
        self.assertEqual(by_name["PDDLM"].digits, 9)
        self.assertEqual(by_name["PDPGM"].type_name, "CHAR")
        gmb = decode_format_fields(
            fixture["GMBREC_GNO"],
            record_length=4,
        )
        self.assertEqual(len(gmb), 1)
        self.assertEqual(gmb[0].name, "GNO")
        self.assertEqual(gmb[0].type_name, "BINARY")
        self.assertEqual((gmb[0].offset, gmb[0].storage_length), (0, 4))
        self.assertEqual(gmb[0].digits, 9)

        b10_blob = b"\x00".join(
            [
                fixture["B10_STAREC_RECTYP"],
                fixture["B10_STAREC_FILL1"],
                fixture["B10_STAREC_STCOD"],
                fixture["B10_STAREC_STNAME"],
                fixture["B10_STAREC_MTD"],
                fixture["B10_STAREC_YTD"],
                fixture["B10_STAREC_LYR"],
                fixture["B10_STAREC_FILL2"],
                fixture["B10_STAREC_ACTCOD"],
            ]
        )
        b10_fields = decode_format_fields(b10_blob, record_length=128)
        self.assertEqual(
            [
                (field.name, field.type_name, field.offset, field.storage_length)
                for field in b10_fields
            ],
            [
                ("RECTYP", "CHAR", 0, 3),
                ("FILL1", "CHAR", 3, 5),
                ("STCOD", "CHAR", 8, 1),
                ("STNAME", "CHAR", 9, 40),
                ("MTD", "ZONED", 49, 5),
                ("YTD", "ZONED", 54, 6),
                ("LYR", "ZONED", 60, 6),
                ("FILL2", "CHAR", 66, 61),
                ("ACTCOD", "CHAR", 127, 1),
            ],
        )

    def test_observed_v2_dbcs_open_format_field_type(self):
        # Synthetic descriptor shaped like the validated V2R3 19/51 fields
        # whose independently recovered DDS definitions use data type O.
        descriptor = bytearray(34)
        descriptor[0] = 0x01
        descriptor[1:11] = "DBCSFIELD".encode("cp037").ljust(10, b"\x40")
        descriptor[11:21] = descriptor[1:11]
        descriptor[21] = 0x00
        descriptor[22] = 0x06
        descriptor[23] = 0x03
        descriptor[24:26] = (0).to_bytes(2, "big")
        descriptor[26:28] = (0).to_bytes(2, "big")
        descriptor[28:30] = (30).to_bytes(2, "big")
        descriptor[30:32] = (0).to_bytes(2, "big")
        descriptor[32:34] = (0).to_bytes(2, "big")

        fields = decode_format_fields(bytes(descriptor), record_length=30)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].type_name, "DBCS-OPEN")

        raw = bytes(range(30))
        self.assertEqual(fields[0].decode_value(raw), raw.hex().upper())

    def test_format_field_value_decoding(self):
        fixture = load_format_field_fixture(FORMAT_FIELD_FIXTURE)
        fields = {
            field.name: field
            for field in decode_format_fields(
                b"".join(
                    [
                        fixture["QCLSRC_SRCSEQ"],
                        fixture["PD00RC_PDCO"],
                        fixture["PD00RC_PDPCTL"],
                        fixture["PD00RC_PDTCR"],
                    ]
                ),
                record_length=452,
            )
        }

        record = bytearray(452)
        record[0:6] = "000100".encode("cp037")
        self.assertEqual(fields["SRCSEQ"].decode_value(record), "1.00")

        record[0:3] = "ABC".encode("cp037")
        self.assertEqual(fields["PDCO"].decode_value(record), "ABC")

        record[6:12] = "001234".encode("cp037")
        self.assertEqual(fields["PDPCTL"].decode_value(record), "1234")

        record[429:433] = bytes.fromhex("1234567C")
        self.assertEqual(fields["PDTCR"].decode_value(record), "1234567")
        binary_field = decode_format_fields(
            fixture["GMBREC_GNO"],
            record_length=4,
        )[0]
        binary_record = (123456).to_bytes(4, "big", signed=True)
        self.assertEqual(binary_field.decode_value(binary_record), "123456")
        negative_record = (-123).to_bytes(4, "big", signed=True)
        self.assertEqual(binary_field.decode_value(negative_record), "-123")

        b10_fields = {
            field.name: field
            for field in decode_format_fields(
                b"".join(
                    [
                        fixture["B10_STAREC_RECTYP"],
                        fixture["B10_STAREC_STCOD"],
                        fixture["B10_STAREC_STNAME"],
                        fixture["B10_STAREC_YTD"],
                        fixture["B10_STAREC_LYR"],
                    ]
                ),
                record_length=128,
            )
        }
        state_record = bytearray(b"\x40" * 128)
        state_record[0:3] = "STA".encode("cp037")
        state_record[8:9] = "1".encode("cp037")
        state_record[9:49] = "MISSOURI".encode("cp037").ljust(40, b"\x40")
        state_record[54:60] = "003896".encode("cp037")
        state_record[60:66] = "003996".encode("cp037")
        self.assertEqual(b10_fields["RECTYP"].decode_value(state_record), "STA")
        self.assertEqual(b10_fields["STCOD"].decode_value(state_record), "1")
        self.assertEqual(b10_fields["STNAME"].decode_value(state_record), "MISSOURI")
        self.assertEqual(b10_fields["YTD"].decode_value(state_record), "3896")
        self.assertEqual(b10_fields["LYR"].decode_value(state_record), "3996")

    def test_qddsi_dkey_dkyt_layout_from_real_b10_shape(self):
        base = 0x0014EC000000
        primary = bytearray(0x800)
        primary[0x11E:0x120] = (1).to_bytes(2, "big")
        primary[0x12A:0x130] = (base + 0x400).to_bytes(6, "big")

        row = memoryview(primary)[0x400:0x440]
        row[0:8] = make_internal_address(0x00ED, 0x00093A000000)
        row[8:16] = make_internal_address(0x00ED, 0x00134A000020)
        row[0x10:0x14] = (1).to_bytes(4, "big")
        row[0x14:0x18] = (0).to_bytes(4, "big")
        row[0x18:0x1A] = (1).to_bytes(2, "big")
        row[0x1A:0x1C] = (2).to_bytes(2, "big")
        row[0x1C:0x1E] = (6).to_bytes(2, "big")
        row[0x1E:0x24] = (base + 0x440).to_bytes(6, "big")

        field = memoryview(primary)[0x440:0x460]
        field[0:10] = bytes.fromhex(
            "20 00 00 02 00 00 00 01 00 01"
        )

        layout = DataSpaceIndexLayout.from_primary_segment(
            bytes(primary),
            virtual_address=base,
        )
        self.assertEqual(layout.dkey_count, 1)
        self.assertEqual(layout.dkey_address, base + 0x400)
        spec = layout.keys[0]
        self.assertEqual(
            spec.data_space,
            InternalAddress(0x00ED, 0x00093A000000),
        )
        self.assertEqual(spec.key_count, 1)
        self.assertEqual(spec.key_field_count, 1)
        self.assertEqual(spec.user_key_length, 2)
        self.assertEqual(spec.machine_key_length, 6)
        self.assertEqual(spec.appended_key_bytes, 4)
        self.assertEqual(len(spec.fields), 1)
        self.assertEqual(spec.fields[0].length_or_fork, 2)
        self.assertEqual(spec.fields[0].location, 1)
        self.assertEqual(spec.fields[0].record_offset_hint, 0)
        self.assertEqual(spec.fields[0].field_ordinal_hint, 1)

    def test_context_terminal_name_hint_decodes_real_ordinary_shapes(self):
        simple = bytes.fromhex(
            "1901d8e2f3f6e2d9c3401700d0003a3c00"
        )
        simple_name = decode_context_terminal_name_hint(simple)
        self.assertIsNotNone(simple_name)
        self.assertEqual(
            simple_name.decode("cp037").rstrip(" "),
            "QS36SRC",
        )

        member = bytes.fromhex(
            "0d50d8c4c4e2e2d9c340fd"
            "c1c4c4c6e4d5c4c4400c"
            "00ed001c3500"
        )
        member_name = decode_context_terminal_name_hint(member)
        self.assertIsNotNone(member_name)
        self.assertEqual(
            member_name[:10].decode("cp037").rstrip(" "),
            "QDDSSRC",
        )
        self.assertEqual(
            member_name[10:20].decode("cp037").rstrip(" "),
            "ADDFUNDD",
        )

        # Composite special-object encodings use high-marker forms that are
        # intentionally left raw rather than misnamed.
        special = bytes.fromhex(
            "0ed1d8e2e8e240fcd8e2e8e24012014900572c00"
        )
        self.assertIsNone(decode_context_terminal_name_hint(special))

    def test_recover_objects_can_assign_context_only_membership(self):
        context_va = 0x001000000000
        object_va = 0x001200000000

        context_first = bytearray(
            make_segment_page(
                context_va,
                segment_type=0x0190,
                object_type=0x04,
                object_subtype=0x01,
                name="QTEST",
                context_extender=0,
                context_address=0,
            )
        )
        context_first[2:4] = (8).to_bytes(2, "big")
        context_data = bytearray(8 * PAGE_SIZE)
        context_data[:PAGE_SIZE] = context_first

        terminal = (
            bytes([0x19, 0x01])
            + "TEST".encode("cp037")
            + bytes([0x40, 26])
            + bytes.fromhex("000100120000")
        )
        self.assertEqual(len(terminal), 14)
        context_data[0x800:0x808] = bytes.fromhex(
            "97 00 08 CC 00 00 00 00"
        )
        context_data[0x808:0x80E] = bytes.fromhex(
            "0D 08 0E 60 00 00"
        )
        context_data[0x80E:0x80E + len(terminal)] = terminal

        object_page = make_segment_page(
            object_va,
            segment_type=0x0180,
            object_type=0x19,
            object_subtype=0x01,
            name="TEST",
            context_extender=0,
            context_address=0,
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context-membership.hda"
            sectors = []
            for page_index in range(8):
                start = page_index * PAGE_SIZE
                sectors.append(
                    (
                        make_header(
                            context_va + page_index * PAGE_SIZE,
                            order=3,
                        ),
                        bytes(context_data[start:start + PAGE_SIZE]),
                    )
                )
            sectors.append(
                (
                    make_header(object_va),
                    object_page,
                )
            )
            write_image(path, sectors)

            context_extent = Extent(
                start_lba=0,
                pages=8,
                kind="permanent-candidate",
                header=make_header(context_va, order=3),
                virtual_address=context_va,
            )
            object_extent = Extent(
                start_lba=8,
                pages=1,
                kind="permanent-candidate",
                header=make_header(object_va),
                virtual_address=object_va,
            )
            context_segment = RecoveredSegment(
                start_extent=context_extent,
                extents=(context_extent,),
                header=SegmentGroupHeader.from_bytes(
                    bytes(context_first[:32])
                ),
            )
            object_segment = RecoveredSegment(
                start_extent=object_extent,
                extents=(object_extent,),
                header=SegmentGroupHeader.from_bytes(
                    object_page[:32]
                ),
            )

            image = DASDImage(path)
            inventory = image.recover_objects(
                SimpleNamespace(),
                SegmentRecoveryResult(
                    segments=[context_segment, object_segment]
                ),
            )

            target = next(
                obj
                for obj in inventory.objects
                if obj.name == "TEST"
            )
            self.assertIsNone(target.epa_library_name)
            self.assertEqual(target.context_library_names, ("QTEST",))
            self.assertEqual(target.library_name, "QTEST")

            entries = inventory.context_entries_for_library("QTEST")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].name_hint, "TEST")
            self.assertIs(
                inventory.resolve_context_entry(entries[0]),
                target,
            )
            self.assertFalse(
                inventory.unresolved_context_entries("QTEST")
            )

    def test_machine_index_page_header_prefix(self):
        data = bytes.fromhex(
            "93 00 08 CC 00 23 03 DD"
        )
        header = MachineIndexPageHeader.from_bytes(data)
        self.assertEqual(header.page_type, 0xCC)
        self.assertEqual(header.free_bytes, 0x0023)
        self.assertEqual(header.first_free_low16, 0x03DD)
        self.assertEqual(header.first_free_offset(), 0x03DD)
        self.assertEqual(header.current_tree_offset_hint, 0x08)
        self.assertEqual(
            header.tail_free_bytes(
                page_size=CONTEXT_MACHINE_INDEX_PAGE_SIZE,
            ),
            0x23,
        )
        self.assertEqual(
            header.non_tail_free_bytes_hint(
                page_size=CONTEXT_MACHINE_INDEX_PAGE_SIZE,
            ),
            0,
        )

        child = MachineIndexPageHeader.from_bytes(
            bytes.fromhex(
                "97 00 0E 55 03 DF 0C 21 "
                "08 00 00 00 08 00"
            ),
            offset=0,
        )
        self.assertEqual(child.page_type, 0x55)
        self.assertEqual(
            child.backpointer_raw,
            bytes.fromhex("08 00 00 00 08 00"),
        )
        self.assertEqual(child.backpointer_words, (0x0800, 0, 0x0800))
        self.assertEqual(
            child.shared_high16_node_pair_hint,
            (0x0800, 0x0800),
        )
        self.assertEqual(
            child.rotated_virtual_address_hint,
            0x000008000800,
        )
        self.assertEqual(child.current_tree_offset_hint, 0x0E)

        v2_child = MachineIndexPageHeader.from_bytes(
            bytes.fromhex(
                "97 00 0E 55 03 DF 8C 21 "
                "8C 17 00 01 8C 20"
            ),
            offset=0,
        )
        self.assertEqual(
            v2_child.shared_high16_node_pair_hint,
            (0x00018C17, 0x00018C20),
        )

        b10_child = MachineIndexPageHeader.from_bytes(
            bytes.fromhex(
                "97 00 0E 55 03 DF 0C 21 "
                "08 08 00 4D 16 00"
            ),
            offset=0,
        )
        self.assertEqual(
            b10_child.rotated_virtual_address_hint,
            0x004D16000808,
        )

        with self.assertRaisesRegex(ValueError, "begin with a node"):
            MachineIndexPageHeader.from_bytes(
                bytes.fromhex("01 00 00 CC 00 00 00 00")
            )

    def test_context_machine_index_single_terminal(self):
        data = bytearray(0x1000)
        # Synthetic one-entry release-2 tree rooted at the independently
        # observed ordinary context offset +0x800.
        data[0x800:0x808] = bytes.fromhex(
            "97 00 08 CC 03 E5 08 1B"
        )
        terminal = (
            bytes([0x19, 0x01])
            + "TEST".encode("cp037")
            + bytes([0x14])
            + bytes.fromhex("000100001234")
        )
        self.assertEqual(len(terminal), 13)
        data[0x808:0x80E] = bytes.fromhex(
            "0C 08 0E 60 00 00"
        )
        data[0x80E:0x80E + len(terminal)] = terminal

        traversal = decode_context_machine_index(bytes(data))
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.entry_count, 1)
        self.assertEqual(len(traversal.page_headers), 1)
        self.assertEqual(traversal.page_headers[0].offset, 0x800)
        self.assertEqual(traversal.page_headers[0].page_type, 0xCC)
        entry = traversal.entries[0]
        self.assertEqual(entry.object_type, 0x19)
        self.assertEqual(entry.object_subtype, 0x01)
        self.assertEqual(
            entry.compact_object_reference,
            bytes.fromhex("000100001234"),
        )
        self.assertEqual(
            entry.object_address_hint,
            InternalAddress(0x0001, 0x000012340000),
        )

    def test_context_machine_index_follows_same_segment_page_pointer(self):
        data = bytearray(0x1200)
        data[0x800:0x808] = bytes.fromhex(
            "97 00 08 CC 03 F2 08 0E"
        )
        data[0x808:0x80E] = bytes.fromhex(
            "C0 00 0C 60 00 00"
        )

        data[0xC00:0xC0E] = bytes.fromhex(
            "97 00 0E 55 03 DF 0C 21 "
            "08 00 00 00 08 00"
        )
        terminal = (
            bytes([0x19, 0x01])
            + "TEST".encode("cp037")
            + bytes([0x14])
            + bytes.fromhex("000100001234")
        )
        data[0xC0E:0xC14] = bytes.fromhex(
            "0C 0C 14 60 00 00"
        )
        data[0xC14:0xC14 + len(terminal)] = terminal

        traversal = decode_context_machine_index(bytes(data))
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.page_offsets, (0x800, 0xC00))
        self.assertEqual(traversal.page_count, 2)
        self.assertEqual(
            [header.page_type for header in traversal.page_headers],
            [0xCC, 0x55],
        )
        self.assertEqual(
            traversal.page_headers[1].backpointer_words,
            (0x0800, 0, 0x0800),
        )
        self.assertEqual(
            traversal.page_headers[1].current_tree_offset_hint,
            0xC0E,
        )
        self.assertEqual(len(traversal.page_pointers), 1)
        self.assertTrue(traversal.page_pointers[0].followed)
        self.assertEqual(
            traversal.page_pointers[0].target_offset,
            0xC00,
        )
        self.assertEqual(traversal.entry_count, 1)
        self.assertEqual(
            traversal.entries[0].object_address_hint,
            InternalAddress(0x0001, 0x000012340000),
        )

    def test_context_machine_index_empty_root(self):
        traversal = decode_context_machine_index(bytes(0x1000))
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.entry_count, 0)

    def test_qddsi_single_entry_root_traversal(self):
        data, layout = make_qddsi_root_fixture(
            "97 00 08 CC 07 E4 10 1C "
            "0D 10 0E 60 00 00 "
            "5C D7 E4 C2 D3 C9 C3 40 40 40 00 00 00 01",
            key_count=1,
            user_key_length=10,
            machine_key_length=14,
        )
        traversal = decode_data_space_index_root(data, layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.page_size, 0x800)
        self.assertEqual(traversal.page_type, 0xCC)
        self.assertEqual(traversal.entry_count, 1)
        entry = traversal.entries[0]
        self.assertEqual(entry.user_key.decode("cp037"), "*PUBLIC   ")
        self.assertEqual(entry.database_reference, bytes.fromhex("00000001"))
        self.assertEqual(entry.dkey_index, 0)
        self.assertEqual(entry.data_space_number_hint, 0)
        self.assertEqual(entry.ordinal_hint, 1)

    def test_qddsi_multi_dkey_one_populated_row_traversal(self):
        data, _layout = make_qddsi_root_fixture(
            "97 00 08 CC 07 E4 10 1C "
            "0D 10 0E 60 00 00 "
            "5C D7 E4 C2 D3 C9 C3 40 40 40 00 00 00 01",
            key_count=1,
            user_key_length=10,
            machine_key_length=14,
        )
        primary = bytearray(data)
        primary[0x11E:0x120] = (2).to_bytes(2, "big")
        second = memoryview(primary)[0x440:0x480]
        second[0:8] = make_internal_address(1, 0x001000000000)
        second[0x10:0x14] = (0).to_bytes(4, "big")
        second[0x18:0x1A] = (0).to_bytes(2, "big")
        second[0x1A:0x1C] = (10).to_bytes(2, "big")
        second[0x1C:0x1E] = (14).to_bytes(2, "big")

        layout = DataSpaceIndexLayout.from_primary_segment(
            bytes(primary),
            virtual_address=0x001000000000,
        )
        self.assertEqual(layout.dkey_count, 2)

        traversal = decode_data_space_index_root(bytes(primary), layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.entry_count, 1)
        self.assertEqual(
            traversal.entries[0].user_key.decode("cp037"),
            "*PUBLIC   ",
        )
        self.assertEqual(traversal.entries[0].ordinal_hint, 1)

    def test_qddsi_mixed_key_shapes_and_fork_rows(self):
        def field(length, location):
            return DataSpaceIndexKeyField(
                sequence_attributes=0,
                field_attributes=0x30,
                length_or_fork=length,
                relative_offset=0,
                location=location,
                field_ordinal_hint=1,
                raw=bytes(0x20),
            )

        def fork():
            return DataSpaceIndexKeyField(
                sequence_attributes=0x40,
                field_attributes=0,
                length_or_fork=0,
                relative_offset=0,
                location=0,
                field_ordinal_hint=0,
                raw=bytes(0x20),
            )

        def spec(user_length, machine_length, fields):
            return DataSpaceIndexKeySpec(
                data_space=InternalAddress(1, 0x000F00000000),
                field_table_pointer=InternalAddress(1, 0),
                key_count=6,
                auxiliary_scalar_raw=0,
                key_field_count=len(fields),
                user_key_length=user_length,
                machine_key_length=machine_length,
                dkyt_address=0,
                fields=tuple(fields),
                raw=bytes(0x40),
            )

        layout = DataSpaceIndexLayout(
            dkey_count=3,
            dkey_address=0,
            keys=(
                spec(8, 13, (field(1, 1), fork(), field(3, 2), field(4, 5))),
                spec(1, 6, (field(1, 1), fork())),
                spec(4, 9, (field(1, 1), fork(), field(3, 2))),
            ),
        )

        # Real V2R3 QASULE01 root-page shape. This compact system-index fixture
        # exercises three populated DKEY rows with different machine-key
        # lengths and interleaved fork/control bytes.
        root = bytes.fromhex(
            "92 00 37 CC 07 02 11 04 60 00 00 8E 00 CE "
            "E3 01 F0 F0 F1 40 C3 F0 F0 00 00 00 01 "
            "0B 10 0F 9F 00 22 00 10 0E 02 01 00 00 01 "
            "04 10 24 07 10 2F 03 F0 F0 F1 02 00 00 01 "
            "96 00 84 9D 00 D5 C3 01 F0 F0 F2 C3 E2 F0 F4 00 00 00 02 "
            "87 00 34 9F 00 DF 00 10 3D 02 01 00 00 02 "
            "85 00 8C 8D 00 86 03 F0 F0 F2 02 00 00 02 "
            "00 10 49 00 10 6F 03 10 45 03 00 10 57 00 10 79 "
            "03 10 53 03 00 10 65 00 10 83 06 10 5E 03 "
            "86 00 A0 8E 00 7D C1 01 F0 F0 F2 40 C2 F0 F4 00 00 00 04 "
            "0B 10 8B 9F 00 21 00 10 8A 02 01 00 00 04 "
            "04 10 A0 07 10 AB 03 F0 F0 F2 02 00 00 04 "
            "87 00 2C 04 10 BC 06 10 3E F5 00 00 00 05 "
            "97 00 28 00 10 CA 03 10 53 05 97 00 21 00 10 D4 "
            "06 10 5E 05 97 00 32 8E 00 D2 "
            "E4 01 F0 F0 F2 C4 E2 F0 F1 00 00 00 06 "
            "0B 10 DC 9F 00 2E 00 10 DB 02 01 00 00 06 "
            "04 10 F1 07 10 FC 03 F0 F0 F2 02 00 00 06"
        )
        data = bytearray(0x1800)
        data[0x1000 : 0x1000 + len(root)] = root

        traversal = decode_data_space_index_root(bytes(data), layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.expected_entries, 18)
        self.assertEqual(traversal.entry_count, 18)
        self.assertEqual(
            {entry.dkey_index for entry in traversal.entries},
            {0, 1, 2},
        )
        self.assertEqual(
            sorted(
                entry.ordinal_hint
                for entry in traversal.entries
                if entry.dkey_index == 1
            ),
            [1, 2, 3, 4, 5, 6],
        )
        self.assertEqual(
            {len(entry.user_key) for entry in traversal.entries},
            {1, 4, 8},
        )

    def test_qddsi_compact_long_key_preserves_reference_only(self):
        data, layout = make_qddsi_root_fixture(
            "97 00 08 CC 07 EC 10 14 "
            "05 10 0E 60 00 00 "
            "3F FF 00 00 00 01",
            key_count=1,
            user_key_length=66,
            machine_key_length=102,
        )
        traversal = decode_data_space_index_root(data, layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.entry_count, 1)
        self.assertEqual(traversal.complete_key_count, 0)
        self.assertEqual(traversal.partial_key_count, 1)

        entry = traversal.entries[0]
        self.assertFalse(entry.key_complete)
        self.assertEqual(entry.machine_key, b"")
        self.assertEqual(entry.user_key, b"")
        self.assertEqual(entry.key_evidence, bytes.fromhex("3FFF"))
        self.assertEqual(entry.display_key_bytes, bytes.fromhex("3FFF"))
        self.assertEqual(entry.database_reference, bytes.fromhex("00000001"))
        self.assertEqual(entry.dkey_index, 0)
        self.assertEqual(entry.ordinal_hint, 1)

    def test_qddsi_multi_dkey_all_empty_is_complete(self):
        data, _layout = make_qddsi_root_fixture(
            "",
            key_count=0,
            user_key_length=10,
            machine_key_length=14,
        )
        primary = bytearray(data)
        primary[0x11E:0x120] = (2).to_bytes(2, "big")
        second = memoryview(primary)[0x440:0x480]
        second[0:8] = make_internal_address(1, 0x001000000000)
        second[0x10:0x14] = (0).to_bytes(4, "big")
        second[0x18:0x1A] = (0).to_bytes(2, "big")
        second[0x1A:0x1C] = (10).to_bytes(2, "big")
        second[0x1C:0x1E] = (14).to_bytes(2, "big")

        layout = DataSpaceIndexLayout.from_primary_segment(
            bytes(primary),
            virtual_address=0x001000000000,
        )
        traversal = decode_data_space_index_root(bytes(primary), layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.expected_entries, 0)
        self.assertEqual(traversal.entry_count, 0)

    def test_qddsi_common_text_two_entry_traversal(self):
        data, layout = make_qddsi_root_fixture(
            "97 00 08 CC 07 DA 10 26 "
            "86 00 1C 60 00 00 "
            "40 40 40 40 40 40 40 40 40 40 00 00 00 01 "
            "00 10 1B 00 10 25 0C 10 0E 02",
            key_count=2,
            user_key_length=10,
            machine_key_length=14,
        )
        traversal = decode_data_space_index_root(data, layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(
            [entry.user_key for entry in traversal.entries],
            [b"\x40" * 10, b"\x40" * 10],
        )
        self.assertEqual(
            [entry.ordinal_hint for entry in traversal.entries],
            [1, 2],
        )

    def test_qddsi_nested_xor_and_common_text_traversal(self):
        data, layout = make_qddsi_root_fixture(
            "97 00 08 CC 07 B3 10 4D "
            "60 00 00 88 00 22 "
            "E3 C7 E3 E2 E8 E2 40 40 40 40 40 40 40 40 "
            "40 40 00 00 00 09 "
            "0D 10 14 9B 00 32 05 10 0E "
            "C1 E2 40 40 40 40 40 40 40 40 00 00 00 0A "
            "0D 10 2B 0D 10 3F "
            "D3 D5 40 40 40 40 40 40 40 40 00 00 00 0B",
            key_count=3,
            user_key_length=16,
            machine_key_length=20,
        )
        traversal = decode_data_space_index_root(data, layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(
            [entry.user_key.decode("cp037") for entry in traversal.entries],
            ["TGTSYS          ", "TGTSYSAS        ", "TGTSYSLN        "],
        )
        self.assertEqual(
            [entry.ordinal_hint for entry in traversal.entries],
            [9, 10, 11],
        )

    def test_qddsi_binary_multifield_key_traversal(self):
        data, layout = make_qddsi_root_fixture(
            "90 00 46 CC 07 A2 10 64 "
            "83 00 70 60 00 00 00 02 80 01 00 00 00 01 "
            "06 10 0F 06 10 1F 00 10 0E "
            "06 80 00 00 00 00 02 "
            "95 00 20 06 10 2F 00 10 0E "
            "0B 80 00 00 00 00 03 "
            "94 00 2E 06 10 3F 00 10 0E "
            "1E 80 00 00 00 00 04 "
            "97 00 08 8F 00 54 80 00 00 0B 00 00 00 05 "
            "06 10 4D 06 10 5D 00 10 4C "
            "01 00 02 00 00 00 06",
            key_count=6,
            user_key_length=4,
            machine_key_length=8,
        )
        traversal = decode_data_space_index_root(data, layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(
            [entry.user_key.hex() for entry in traversal.entries],
            [
                "00028001",
                "00068000",
                "000b8000",
                "001e8000",
                "8000000b",
                "80010002",
            ],
        )
        self.assertEqual(
            [entry.ordinal_hint for entry in traversal.entries],
            [1, 2, 3, 4, 5, 6],
        )

    def test_qddsi_active_root_pointer_can_move_root_page(self):
        base = 0x001000000000
        data, layout = make_qddsi_root_fixture(
            "97 00 08 CC 07 E4 10 1C "
            "0D 10 0E 60 00 00 "
            "5C D7 E4 C2 D3 C9 C3 40 40 40 00 00 00 01",
            key_count=1,
            user_key_length=10,
            machine_key_length=14,
        )
        primary = bytearray(0x2000)
        root = bytearray(data[0x1000:0x101C])
        root[6:8] = (0x181C).to_bytes(2, "big")
        root[9:11] = (0x180E).to_bytes(2, "big")
        primary[0x1800 : 0x1800 + len(root)] = root

        # Observed QDDSI control pointer at +0x13A, then active-root pointer at
        # control +0x20.
        primary[0x13A:0x140] = (base + 0x0A00).to_bytes(6, "big")
        primary[0x0A20:0x0A26] = (base + 0x1800).to_bytes(6, "big")

        traversal = decode_data_space_index_root(
            bytes(primary),
            layout,
            virtual_address=base,
        )
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.root_offset, 0x1800)
        self.assertEqual(traversal.entry_count, 1)
        self.assertEqual(traversal.entries[0].ordinal_hint, 1)

    def test_qddsi_follows_same_segment_page_pointer(self):
        data, layout = make_qddsi_root_fixture(
            "97 00 08 CC 07 F2 10 0E "
            "C0 00 18 60 00 00",
            key_count=1,
            user_key_length=10,
            machine_key_length=14,
        )
        primary = bytearray(data)
        primary.extend(b"\x00" * (0x2000 - len(primary)))
        secondary = bytes.fromhex(
            "97 00 08 55 07 E4 18 1C "
            "0D 18 0E 60 00 00 "
            "5C D7 E4 C2 D3 C9 C3 40 40 40 00 00 00 01"
        )
        primary[0x1800 : 0x1800 + len(secondary)] = secondary

        traversal = decode_data_space_index_root(bytes(primary), layout)
        self.assertTrue(traversal.complete)
        self.assertEqual(traversal.page_offsets, (0x1000, 0x1800))
        self.assertEqual(traversal.page_count, 2)
        self.assertEqual(len(traversal.page_pointers), 1)
        pointer = traversal.page_pointers[0]
        self.assertTrue(pointer.followed)
        self.assertEqual(pointer.segment_table_index, 0)
        self.assertEqual(pointer.page_offset, 0x18)
        self.assertEqual(pointer.target_offset, 0x1800)
        self.assertFalse(traversal.unresolved_page_pointers)
        self.assertEqual(traversal.entry_count, 1)
        self.assertEqual(
            traversal.entries[0].user_key.decode("cp037"),
            "*PUBLIC   ",
        )
        self.assertEqual(traversal.entries[0].ordinal_hint, 1)
    def test_qdds_layout_scalars_from_real_metadata(self):
        fixture = load_qdds_layout_fixture(QDDS_LAYOUT_FIXTURE)
        expected = {
            "QCLSRC_REFRESH2": (71, 71, 92, 93),
            "PTFSUM_PTFSUM": (1941, 1941, 80, 81),
            "DBUUSERS_DBUUSERS": (1, 1, 22, 23),
            "PDPICKORG_PDPICKDEMO": (1880, 1880, 452, 453),
            "B10_QLBLSRC_PROTO": (107, 107, 92, 93),
        }

        for label, values in expected.items():
            with self.subTest(label=label):
                layout = DataSpaceLayout.from_primary_segment(
                    fixture[label]
                )
                self.assertEqual(
                    (
                        layout.entry_count,
                        layout.force_count,
                        layout.record_length,
                        layout.entry_length,
                    ),
                    values,
                )
                self.assertTrue(layout.standard_fixed_layout)
                self.assertEqual(layout.per_entry_overhead, 1)
                if label.startswith("B10_"):
                    self.assertFalse(layout.v2_hints_present)
                else:
                    self.assertTrue(layout.v2_hints_present)
                    self.assertTrue(layout.v2_hints_match)


    def test_qdds_special_v2_hint_mismatch_is_flagged(self):
        primary = bytearray(0x1EE)
        primary[0x11A:0x11E] = (10).to_bytes(4, "big")
        primary[0x11E:0x122] = (10).to_bytes(4, "big")
        primary[0x13C:0x140] = (1648).to_bytes(4, "big")
        primary[0x1E4:0x1E8] = (11387).to_bytes(4, "big")
        primary[0x1EC:0x1EE] = (1648).to_bytes(2, "big")

        layout = DataSpaceLayout.from_primary_segment(bytes(primary))
        self.assertEqual(layout.entry_length, 1648)
        self.assertEqual(layout.record_length, 1647)
        self.assertTrue(layout.v2_hints_present)
        self.assertFalse(layout.v2_hints_match)
        self.assertFalse(layout.standard_fixed_layout)

    def test_v2_dent_live_and_deleted_hints(self):
        live = DataSpaceRecord(
            ordinal=1,
            status=0x80,
            data=b"A",
        )
        deleted = DataSpaceRecord(
            ordinal=2,
            status=0xC0,
            data=b"B",
        )
        unknown = DataSpaceRecord(
            ordinal=3,
            status=0x40,
            data=b"C",
        )

        self.assertTrue(live.is_live_hint)
        self.assertFalse(live.is_deleted_hint)
        self.assertFalse(deleted.is_live_hint)
        self.assertTrue(deleted.is_deleted_hint)
        self.assertFalse(unknown.is_live_hint)
        self.assertFalse(unknown.is_deleted_hint)

    def test_generic_data_space_record_decoder_uses_header_count(self):
        layout = DataSpaceLayout(
            entry_count=2,
            force_count=2,
            record_length=4,
            entry_length=5,
        )
        stream = (
            b"\x80" + b"DEFA"
            + b"\x80" + b"ONE1"
            + b"\x40" + b"TWO2"
            + b"garbage that must not be parsed"
        )

        records = decode_data_space_records(stream, layout)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].ordinal, 0)
        self.assertEqual(records[1].rrn, 1)
        self.assertEqual(records[1].data, b"ONE1")
        self.assertEqual(records[2].status, 0x40)
        self.assertEqual(records[2].data, b"TWO2")

    def test_docbss_extended_payload_uses_continuation_after_metadata_page(self):
        primary = bytearray(PAGE_SIZE * 2)
        continuation = bytearray(PAGE_SIZE * 2)
        payload = b"A" * 600
        primary[0x106:0x108] = len(payload).to_bytes(2, "big")
        primary[0x112:0x114] = len(payload).to_bytes(2, "big")
        primary[PAGE_SIZE:] = payload[:PAGE_SIZE]
        continuation[PAGE_SIZE:PAGE_SIZE + 88] = payload[PAGE_SIZE:]

        info = DocumentByteStringInfo.from_primary_segment(bytes(primary))
        recovered = assemble_document_byte_string(
            info,
            bytes(primary),
            (bytes(continuation),),
        )
        self.assertEqual(recovered, payload)

    def test_docbss_extended_payload_rejects_missing_continuation(self):
        primary = bytearray(PAGE_SIZE * 2)
        payload_length = 600
        primary[0x106:0x108] = payload_length.to_bytes(2, "big")
        primary[0x112:0x114] = payload_length.to_bytes(2, "big")
        info = DocumentByteStringInfo.from_primary_segment(bytes(primary))

        with self.assertRaisesRegex(ValueError, "missing 88 byte"):
            assemble_document_byte_string(info, bytes(primary))

    def test_docbss_observed_length_layout(self):
        data = bytearray(PAGE_SIZE * 3)
        data[0x106:0x108] = (424).to_bytes(2, "big")
        data[0x10A:0x10C] = (512).to_bytes(2, "big")
        data[0x112:0x114] = (424).to_bytes(2, "big")

        info = DocumentByteStringInfo.from_primary_segment(bytes(data))
        self.assertEqual(info.payload_length, 424)
        self.assertEqual(info.allocated_length, 512)
        self.assertTrue(info.duplicate_length_matches)
        info.validate_for_export(len(data))

        broken = bytearray(data)
        broken[0x112:0x114] = (423).to_bytes(2, "big")
        bad = DocumentByteStringInfo.from_primary_segment(bytes(broken))
        with self.assertRaises(ValueError):
            bad.validate_for_export(len(broken))

    def test_qaosss14_anchor_record_observed_offsets(self):
        raw = bytearray(QAOSSS14_V2_RECORD_LENGTH)
        raw[0:8] = bytes.fromhex("a1a2a3a4a5a6a7a8")
        raw[8:16] = "S1011111".encode("cp037")
        raw[16:24] = bytes.fromhex("0102030405060708")
        raw[32:76] = "CKPCSPTH.EXE".encode("cp037").ljust(44, b"\x40")
        raw[76:78] = bytes.fromhex("000e")
        raw[95:111] = "QSECOFR QSECOFR ".encode("cp037")
        raw[111:123] = "CKPCSPTH.EXE".encode("cp037")
        raw[131:139] = bytes.fromhex("1112131415161718")

        record = SimpleNamespace(
            ordinal=695,
            status=0x80,
            data=bytes(raw),
        )
        anchor_record = QAOSSS14AnchorRecord.from_data_space_record(record)
        self.assertEqual(anchor_record.rrn, 695)
        self.assertEqual(
            anchor_record.leading_key,
            bytes.fromhex("a1a2a3a4a5a6a7a8"),
        )
        self.assertEqual(anchor_record.secondary_key_text, "S1011111")
        self.assertEqual(
            anchor_record.record_key,
            bytes.fromhex("0102030405060708"),
        )
        self.assertEqual(anchor_record.short_name, "CKPCSPTH.EXE")
        self.assertEqual(anchor_record.long_name, "CKPCSPTH.EXE")
        self.assertEqual(
            anchor_record.parent_key,
            bytes.fromhex("1112131415161718"),
        )
        self.assertEqual(anchor_record.object_type_raw, bytes.fromhex("000e"))

    def test_standard_source_record_decoder(self):
        def entry(sequence, source_date, text, status=0x80):
            payload = (
                sequence.encode("cp037")
                + source_date.encode("cp037")
                + text.encode("cp037").ljust(80, b"\x40")
            )
            self.assertEqual(len(payload), 92)
            return bytes([status]) + payload

        stream = b"".join(
            [
                entry("000000", "000000", ""),
                entry("000100", "941225", "       IDENTIFICATION DIVISION."),
                entry("000200", "941228", "          PROGRAM-ID. TEST."),
                b"\x00" * 93,
            ]
        )

        decoded = decode_standard_source_stream(stream)
        self.assertIsNotNone(decoded)
        self.assertTrue(decoded.default_entry_present)
        self.assertEqual(decoded.line_count, 2)
        self.assertEqual(decoded.records[0].sequence, "000100")
        self.assertEqual(decoded.records[0].sequence_display, "0001.00")
        self.assertEqual(decoded.records[0].source_date, "941225")
        self.assertEqual(
            decoded.records[0].text,
            "       IDENTIFICATION DIVISION.",
        )
        self.assertEqual(
            decoded.records[1].text,
            "          PROGRAM-ID. TEST.",
        )


    def test_context_index_entry_documented_format(self):
        object_address = make_internal_address(0x00D0, 0x0038D5000000)
        name = "JHUDGINS".encode("cp037")
        raw = bytes([0x08, 0x01, len(name)]) + name + object_address

        entry = ContextIndexEntry.from_bytes(raw)
        self.assertEqual(entry.type_code, "08/01")
        self.assertEqual(entry.name_length, 8)
        self.assertEqual(entry.name, "JHUDGINS")
        self.assertEqual(entry.key_prefix, raw[:-8])
        self.assertEqual(entry.object_address.extender, 0x00D0)
        self.assertEqual(entry.object_address.address, 0x0038D5000000)
        self.assertEqual(entry.raw, raw)

        with self.assertRaises(ValueError):
            ContextIndexEntry.from_bytes(raw[:-1])

    def test_context_index_entry_from_object_tracks_base_and_epa_bytes(self):
        extent = Extent(
            start_lba=10,
            pages=2,
            kind="test",
            header=b"",
            virtual_address=0x0037AE000000,
        )
        header = SegmentGroupHeader(
            raw=b"\x00" * 32,
            segment_type=0x0180,
            size_pages=2,
            new_flags=0,
            flags=0,
            domain=0,
            owner=InternalAddress(0x0001, 0x0037AE000000),
            space=InternalAddress(0, 0),
        )
        segment = RecoveredSegment(
            start_extent=extent,
            extents=(extent,),
            header=header,
        )
        epa = SimpleNamespace(
            name_raw="QCLSRC".encode("cp037").ljust(30, b"\x40"),
            object_type=0x19,
            object_subtype=0x01,
            name="QCLSRC",
        )
        obj = RecoveredObject(segment=segment, epa=epa)

        self.assertEqual(obj.object_address.extender, 0x0001)
        self.assertEqual(obj.object_address.address, 0x0037AE000000)
        self.assertEqual(obj.physical_epa_byte_address.extender, 0x0001)
        self.assertEqual(
            obj.physical_epa_byte_address.address,
            0x0037AE000020,
        )

        entry = ContextIndexEntry.from_object(obj)
        self.assertEqual(entry.name, "QCLSRC")
        self.assertEqual(entry.object_address, obj.object_address)
        self.assertTrue(entry.raw.endswith(bytes.fromhex("00010037ae000000")))

    def test_member_storage_pointer_offsets(self):
        cursor = bytearray(0x308)
        cursor[0x128:0x130] = make_internal_address(
            0x00ED, 0x0014EC000000
        )
        cursor[0x300:0x308] = make_internal_address(
            0x00ED, 0x00093A000000
        )

        pointers = MemberStoragePointers.from_cursor_segment(bytes(cursor))
        self.assertEqual(
            pointers.data_index,
            InternalAddress(0x00ED, 0x0014EC000000),
        )
        self.assertEqual(
            pointers.data_space,
            InternalAddress(0x00ED, 0x00093A000000),
        )

        empty = MemberStoragePointers.from_cursor_segment(bytes(0x308))
        self.assertIsNone(empty.data_index)
        self.assertIsNone(empty.data_space)

    def test_machine_index_element_formats(self):
        # IBM Appendix-A release-2 format uses three-byte elements.
        text = MachineIndexElement(bytes.fromhex("051234"))
        self.assertEqual(text.kind, "text")
        self.assertEqual(text.text_length, 5)
        self.assertEqual(text.text_storage_length, 6)
        self.assertEqual(text.text_displacement, 0x1234)

        # Real QDDSI node: type=10, common text present, left direction,
        # bit-to-test=6, XOR displacement 0x001C.
        node = MachineIndexElement(bytes.fromhex("86001C"))
        self.assertEqual(node.kind, "node")
        self.assertFalse(node.unresolved_node_flag)
        self.assertTrue(node.common_text_present)
        self.assertEqual(node.direction, "left")
        self.assertEqual(node.bit_to_test, 6)
        self.assertEqual(node.xor_displacement, 0x001C)

        # A second real node validates direction/common bit placement.
        right = MachineIndexElement(bytes.fromhex("9B0032"))
        self.assertFalse(right.common_text_present)
        self.assertEqual(right.direction, "right")
        self.assertEqual(right.bit_to_test, 3)
        self.assertEqual(right.xor_displacement, 0x0032)

        page_value = (
            (0b11 << 22)
            | (0x15 << 16)
            | 0x2345
        )
        page = MachineIndexElement(page_value.to_bytes(3, "big"))
        self.assertEqual(page.kind, "page-pointer")
        self.assertEqual(page.segment_table_index, 0x15)
        self.assertEqual(page.page_offset, 0x2345)

    def test_geometry_and_sector_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.hda"
            write_image(
                path,
                [
                    (make_header(0x1000), b"A" * PAGE_SIZE),
                    (make_header(0x1200), b"B" * PAGE_SIZE),
                ],
            )
            image = DASDImage(path)
            self.assertEqual(image.sector_count, 2)
            self.assertEqual(path.stat().st_size, 2 * SECTOR_SIZE)
            sector = image.read_sector(1)
            self.assertEqual(sector.header.virtual_address, 0x1200)
            self.assertEqual(sector.data, b"B" * PAGE_SIZE)

    def test_rejects_non_520_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.hda"
            path.write_bytes(b"x" * 521)
            with self.assertRaisesRegex(ValueError, "not divisible"):
                DASDImage(path)

    def test_probe_machine_index_page_supports_origin_and_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.hda"
            va = 0x001000000000
            pages = []
            raw_pages = [bytearray(PAGE_SIZE) for _ in range(3)]

            # Logical page 0 begins at segment offset 0x80. Put a text element
            # at page-relative phase 2 so the probe must not assume phase 0.
            raw_pages[0][0x82:0x85] = bytes.fromhex("050123")
            for index, payload in enumerate(raw_pages):
                pages.append(
                    (
                        make_header(va + index * PAGE_SIZE),
                        bytes(payload),
                    )
                )
            write_image(path, pages)

            extent = Extent(
                start_lba=0,
                pages=3,
                kind="test",
                header=make_header(va),
                virtual_address=va,
            )
            header = SegmentGroupHeader(
                raw=b"\x00" * 32,
                segment_type=0x0190,
                size_pages=3,
                new_flags=0,
                flags=0,
                domain=0,
                owner=InternalAddress(1, va),
                space=InternalAddress(0, 0),
            )
            segment = RecoveredSegment(
                start_extent=extent,
                extents=(extent,),
                header=header,
            )
            context = SimpleNamespace(
                object_type=0x04,
                object_subtype=0x01,
                segment=segment,
            )

            probes = DASDImage(path).probe_machine_index_page(
                context,
                0,
                page_size=512,
                page_origin=0x80,
                element_offset=2,
                count=1,
            )
            self.assertEqual(len(probes), 1)
            self.assertEqual(probes[0].offset, 2)
            self.assertEqual(probes[0].element.kind, "text")
            self.assertEqual(probes[0].element.text_length, 5)
            self.assertEqual(probes[0].element.text_displacement, 0x0123)

    def test_real_b10_header_fixture(self):
        raw = load_rle_fixture(B10_FIXTURE)
        self.assertEqual(len(raw), 232064 * HEADER_SIZE)

        result = HeaderSnapshot(
            raw, name="B10 D1 first 232064 headers"
        ).scan()

        self.assertIsNotNone(result.origin)
        self.assertEqual(result.origin.lba, 2112)
        self.assertEqual(
            result.origin.delimiter_header.hex(),
            "0000fc00000f0000",
        )
        self.assertEqual(result.origin.extent_pages, 32768)
        self.assertEqual(
            result.origin.delimiter_occurrences,
            (2112, 34880, 67648, 100416, 133184, 165952, 198720),
        )
        self.assertEqual(result.reserved_nonzero_headers, 0)

        self.assertEqual(len(result.free_delimiter_extents), 7)
        self.assertEqual(result.explicit_free_pages, 229376)
        self.assertEqual(len(result.permanent_candidates), 31)
        self.assertEqual(result.permanent_candidate_pages, 574)
        self.assertEqual(result.reclaimable_pages, 2)

        first = result.permanent_candidates[0]
        self.assertEqual(first.start_lba, 231488)
        self.assertEqual(first.pages, 32)
        self.assertEqual(first.virtual_address, 0x00A1C3010000)

        second = result.permanent_candidates[1]
        self.assertEqual(second.start_lba, 231520)
        self.assertEqual(second.pages, 16)
        self.assertEqual(second.virtual_address, 0x00A1C3014000)

    def test_independent_p02_v2r3_header_fixture(self):
        raw = load_rle_fixture(P02_FIXTURE)
        self.assertEqual(len(raw), 426048 * HEADER_SIZE)

        result = HeaderSnapshot(
            raw, name="P02 V2R3 selected real headers"
        ).scan()

        self.assertIsNotNone(result.origin)
        self.assertEqual(result.origin.lba, 64)
        self.assertEqual(
            result.origin.delimiter_occurrences,
            (393280,),
        )
        self.assertGreaterEqual(result.origin.supporting_large_extents, 10)
        self.assertEqual(result.reserved_nonzero_headers, 0)

        self.assertEqual(len(result.free_delimiter_extents), 1)
        self.assertEqual(result.explicit_free_pages, 32768)
        self.assertEqual(len(result.permanent_candidates), 10)
        self.assertEqual(result.permanent_candidate_pages, 41216)
        self.assertEqual(result.reclaimable_pages, 352000)

        first = result.permanent_candidates[0]
        self.assertEqual(first.start_lba, 64)
        self.assertEqual(first.pages, 16384)
        self.assertEqual(first.virtual_address, 0x00000B000000)

        shadow = result.resolve_virtual(KNOWN_B10_SHADOW_LOG_VADDR)
        self.assertIsNotNone(shadow)
        self.assertEqual(shadow.start_lba, 147520)
        self.assertEqual(shadow.pages, 256)
        self.assertEqual(shadow.virtual_address, 0x000083000000)


    def test_second_pass_recovers_objects_and_library_backpointer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "objects.hda"
            qgpl_va = 0x000000100000
            qclsrc_va = 0x000000200000

            write_image(
                path,
                [
                    (
                        make_header(qgpl_va),
                        make_segment_page(
                            qgpl_va,
                            segment_type=0x0190,
                            object_type=0x04,
                            object_subtype=0x01,
                            name="QGPL",
                            context_extender=0,
                            context_address=0x0000000D000000,
                        ),
                    ),
                    (
                        make_header(qclsrc_va),
                        make_segment_page(
                            qclsrc_va,
                            segment_type=0x0180,
                            object_type=0x19,
                            object_subtype=0x01,
                            name="QCLSRC",
                            context_extender=1,
                            context_address=qgpl_va,
                        ),
                    ),
                ],
            )

            scan = ScanResult(
                path=str(path),
                sector_count=2,
                zero_headers=0,
                ff_headers=0,
                other_headers=2,
                zero_payloads=0,
                reserved_nonzero_headers=0,
                origin=None,
                permanent_candidates=[
                    Extent(
                        start_lba=0,
                        pages=1,
                        kind="permanent-candidate",
                        header=make_header(qgpl_va),
                        virtual_address=qgpl_va,
                    ),
                    Extent(
                        start_lba=1,
                        pages=1,
                        kind="permanent-candidate",
                        header=make_header(qclsrc_va),
                        virtual_address=qclsrc_va,
                    ),
                ],
            )

            image = DASDImage(path)
            segments = image.recover_segments(scan)
            self.assertEqual(len(segments.segments), 2)
            self.assertEqual(len(segments.primary_segments), 2)
            self.assertFalse(segments.unrecovered_candidates)

            inventory = image.recover_objects(scan, segments)
            self.assertEqual(
                [library.name for library in inventory.libraries],
                ["QGPL"],
            )
            qgpl_objects = inventory.in_library("QGPL")
            self.assertEqual(len(qgpl_objects), 1)
            self.assertEqual(qgpl_objects[0].name, "QCLSRC")
            self.assertEqual(qgpl_objects[0].type_code, "19/01")
            self.assertEqual(
                qgpl_objects[0].external_type_hint,
                "*FILE",
            )


    def test_real_segment_and_epa_object_headers(self):
        fixture = load_object_fixture(OBJECT_FIXTURE)

        lba, raw = fixture["MARK_QSYS"]
        self.assertEqual(lba, 76024)
        segment = SegmentGroupHeader.from_bytes(raw[:32])
        epa = EPAHeader.from_bytes(raw[32:])
        self.assertEqual(segment.segment_type, 0x0190)
        self.assertEqual(segment.size_pages, 904)
        self.assertEqual(segment.owner.extender, 1)
        self.assertEqual(segment.owner.address, 0x000233000000)
        self.assertEqual((epa.object_type, epa.object_subtype), (0x04, 0x01))
        self.assertEqual(epa.name, "QSYS")
        self.assertEqual(epa.context.extender, 0)
        self.assertEqual(epa.context.address, 0x0000000D000000)

        lba, raw = fixture["MARK_QGPL"]
        self.assertEqual(lba, 76968)
        segment = SegmentGroupHeader.from_bytes(raw[:32])
        epa = EPAHeader.from_bytes(raw[32:])
        self.assertEqual(segment.segment_type, 0x0190)
        self.assertEqual(segment.size_pages, 56)
        self.assertEqual(segment.owner.address, 0x000274000000)
        self.assertEqual((epa.object_type, epa.object_subtype), (0x04, 0x01))
        self.assertEqual(epa.name, "QGPL")
        self.assertEqual(epa.context.address, 0x0000000D000000)

        lba, raw = fixture["MARK_QCLSRC"]
        self.assertEqual(lba, 1760434)
        segment = SegmentGroupHeader.from_bytes(raw[:32])
        epa = EPAHeader.from_bytes(raw[32:])
        self.assertEqual(segment.segment_type, 0x0180)
        self.assertEqual(segment.size_pages, 2)
        self.assertEqual(segment.owner.address, 0x0037AE000000)
        self.assertEqual((epa.object_type, epa.object_subtype), (0x19, 0x01))
        self.assertEqual(epa.name, "QCLSRC")
        self.assertEqual(epa.context.extender, 1)
        self.assertEqual(epa.context.address, 0x000274000000)

        lba, raw = fixture["B10_QOOADGPM"]
        self.assertEqual(lba, 231552)
        segment = SegmentGroupHeader.from_bytes(raw[:32])
        epa = EPAHeader.from_bytes(raw[32:])
        self.assertEqual(segment.segment_type, 0x0181)
        self.assertEqual(segment.size_pages, 46)
        self.assertEqual(segment.owner.extender, 0x00E0)
        self.assertEqual(segment.owner.address, 0x00A1C6000000)
        self.assertEqual((epa.object_type, epa.object_subtype), (0x02, 0x01))
        self.assertEqual(epa.name, "QOOADGPM")

    def test_real_member_cursor_name_and_qgpl_backpointer(self):
        fixture = load_object_fixture(OBJECT_FIXTURE)
        lba, raw = fixture["MARK_QCLSRC_REFRESH2"]
        self.assertEqual(lba, 1668664)

        segment = SegmentGroupHeader.from_bytes(raw[:32])
        epa = EPAHeader.from_bytes(raw[32:])
        self.assertEqual(segment.segment_type, 0x0199)
        self.assertEqual(segment.size_pages, 5)
        self.assertEqual((epa.object_type, epa.object_subtype), (0x0D, 0x50))
        self.assertEqual(
            epa.name_raw[:10].decode("cp037").rstrip(" "),
            "QCLSRC",
        )
        self.assertEqual(
            epa.name_raw[10:20].decode("cp037").rstrip(" "),
            "REFRESH2",
        )
        self.assertEqual(epa.context.extender, 1)
        self.assertEqual(epa.context.address, 0x000274000000)

    def test_real_jhudgins_provenance_objects(self):
        fixture = load_object_fixture(OBJECT_FIXTURE)

        expected = {
            "B10_JHUDGINS_USRPRF": ((0x08, 0x01), "JHUDGINS"),
            "B10_JHUDGINS_LIB": ((0x04, 0x01), "JHUDGINS"),
            "B10_JHUDGINS_QDIDX": ((0x0E, 0x90), "JHUDGINS"),
            "B10_JHUDGINS_1902": ((0x19, 0x02), "JHUDGINS"),
        }
        for label, (type_pair, name) in expected.items():
            _, raw = fixture[label]
            epa = EPAHeader.from_bytes(raw[32:])
            self.assertEqual(
                (epa.object_type, epa.object_subtype),
                type_pair,
                label,
            )
            self.assertEqual(epa.name, name, label)

    def test_real_jhudgins_msgq_contains_observed_usrprf_address(self):
        fixture = load_object_fixture(OBJECT_FIXTURE)

        _, usr_raw = fixture["B10_JHUDGINS_USRPRF"]
        _, msg_raw = fixture["B10_JHUDGINS_1902"]

        usr_segment = SegmentGroupHeader.from_bytes(usr_raw[:32])
        usr_epa = EPAHeader.from_bytes(usr_raw[32:])
        msg_epa = EPAHeader.from_bytes(msg_raw[32:])

        observed = InternalAddress.from_bytes(
            msg_epa.raw[0x38:0x40]
        )

        self.assertEqual(usr_epa.name, "JHUDGINS")
        self.assertEqual(msg_epa.name, "JHUDGINS")
        self.assertEqual(observed.key, usr_segment.owner.key)
        self.assertEqual(observed.extender, 0x00D0)
        self.assertEqual(observed.address, 0x0038D5000000)

    def test_real_member_header_metadata(self):
        object_fixture = load_object_fixture(OBJECT_FIXTURE)
        member_fixture = load_offset_fixture(MEMBER_FIXTURE)

        _, first_page_meta = object_fixture["MARK_QCLSRC_REFRESH2"]
        page_data = bytearray(5 * PAGE_SIZE)
        page_data[: len(first_page_meta)] = first_page_meta

        for _, (offset, raw) in member_fixture.items():
            page_data[offset : offset + len(raw)] = raw

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "real-member-meta.hda"
            with open(path, "wb") as handle:
                for page_index in range(5):
                    start = page_index * PAGE_SIZE
                    handle.write(make_header(0x00F3C2000000 + start))
                    handle.write(page_data[start : start + PAGE_SIZE])

            extent = Extent(
                start_lba=0,
                pages=5,
                kind="permanent-candidate",
                header=make_header(0x00F3C2000000),
                virtual_address=0x00F3C2000000,
            )
            segment_header = SegmentGroupHeader.from_bytes(
                first_page_meta[:32]
            )
            segment = RecoveredSegment(
                start_extent=extent,
                extents=(extent,),
                header=segment_header,
            )
            epa = EPAHeader.from_bytes(first_page_meta[32:])
            obj = RecoveredObject(
                segment=segment,
                epa=epa,
                library_name="QGPL",
            )

            info = DASDImage(path).read_member_info(obj)
            self.assertIsNotNone(info)
            self.assertEqual(info.associated_space_offset, 0x440)
            self.assertEqual(info.member_header_offset, 0x8D0)
            self.assertEqual(
                info.text,
                "Refresh PkMS demo data - new version (GE 170)",
            )
            self.assertEqual(info.member_type, "CLP")
            self.assertEqual(
                info.source_change,
                "1998-01-03 02:31:14",
            )
            self.assertEqual(
                info.created,
                "1998-01-03 02:31:11",
            )

    def test_member_cursor_properties_and_inventory_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "members.hda"
            qgpl_va = 0x000000100000
            member_va = 0x000000200000

            write_image(
                path,
                [
                    (
                        make_header(qgpl_va),
                        make_segment_page(
                            qgpl_va,
                            segment_type=0x0190,
                            object_type=0x04,
                            object_subtype=0x01,
                            name="QGPL",
                            context_extender=0,
                            context_address=0x0000000D000000,
                        ),
                    ),
                    (
                        make_header(member_va),
                        make_segment_page(
                            member_va,
                            segment_type=0x0199,
                            object_type=0x0D,
                            object_subtype=0x50,
                            name="QCLSRC    REFRESH2",
                            context_extender=1,
                            context_address=qgpl_va,
                        ),
                    ),
                ],
            )

            scan = ScanResult(
                path=str(path),
                sector_count=2,
                zero_headers=0,
                ff_headers=0,
                other_headers=2,
                zero_payloads=0,
                reserved_nonzero_headers=0,
                origin=None,
                permanent_candidates=[
                    Extent(
                        start_lba=0,
                        pages=1,
                        kind="permanent-candidate",
                        header=make_header(qgpl_va),
                        virtual_address=qgpl_va,
                    ),
                    Extent(
                        start_lba=1,
                        pages=1,
                        kind="permanent-candidate",
                        header=make_header(member_va),
                        virtual_address=member_va,
                    ),
                ],
            )

            image = DASDImage(path)
            segments = image.recover_segments(scan)
            inventory = image.recover_objects(scan, segments)
            members = inventory.members(
                library="QGPL",
                file_name="QCLSRC",
            )
            self.assertEqual(len(members), 1)
            member = members[0]
            self.assertTrue(member.is_member_cursor)
            self.assertEqual(member.external_type_hint, "*MEM")
            self.assertEqual(member.member_file_name, "QCLSRC")
            self.assertEqual(member.member_name, "REFRESH2")


if __name__ == "__main__":
    unittest.main()
