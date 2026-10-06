import tempfile
import unittest
from pathlib import Path

from as400_dasd import (
    HEADER_SIZE,
    KNOWN_B10_SHADOW_LOG_VADDR,
    PAGE_SIZE,
    SECTOR_SIZE,
    DASDImage,
    DataSpaceLayout,
    EPAHeader,
    Extent,
    HeaderSnapshot,
    MachineIndexElement,
    RecoveredObject,
    RecoveredSegment,
    ScanResult,
    SectorHeader,
    SegmentGroupHeader,
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

    def test_machine_index_element_formats(self):
        # IBM Appendix-A release-2 format uses three-byte elements.
        text = MachineIndexElement(bytes.fromhex("051234"))
        self.assertEqual(text.kind, "text")
        self.assertEqual(text.text_length, 5)
        self.assertEqual(text.text_displacement, 0x1234)

        # type=10, common-text bit=0, direction=1, bit-to-test=3,
        # xor displacement=0x01234
        node_value = (
            (0b10 << 22)
            | (0 << 21)
            | (1 << 20)
            | (3 << 17)
            | 0x1234
        )
        node = MachineIndexElement(node_value.to_bytes(3, "big"))
        self.assertEqual(node.kind, "node")
        self.assertTrue(node.common_text_present)
        self.assertEqual(node.direction, "right")
        self.assertEqual(node.bit_to_test, 3)
        self.assertEqual(node.xor_displacement, 0x1234)

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
