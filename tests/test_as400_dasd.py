import tempfile
import unittest
from pathlib import Path

from as400_dasd import (
    HEADER_SIZE,
    KNOWN_B10_SHADOW_LOG_VADDR,
    PAGE_SIZE,
    SECTOR_SIZE,
    DASDImage,
    Extent,
    HeaderSnapshot,
    ScanResult,
    SectorHeader,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
B10_FIXTURE = FIXTURE_DIR / "b10_d1_first232064.headers.rle.txt"
P02_FIXTURE = FIXTURE_DIR / "p02_v2r3_selected.headers.rle.txt"


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


if __name__ == "__main__":
    unittest.main()
