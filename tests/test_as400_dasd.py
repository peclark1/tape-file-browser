import tempfile
import unittest
from pathlib import Path

from as400_dasd import (
    HEADER_SIZE,
    KNOWN_B10_SHADOW_LOG_VADDR,
    PAGE_SIZE,
    SECTOR_SIZE,
    DASDImage,
    HeaderSnapshot,
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


if __name__ == "__main__":
    unittest.main()
