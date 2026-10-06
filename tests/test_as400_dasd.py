import base64
import gzip
import tempfile
import unittest
from pathlib import Path

from as400_dasd import (
    HEADER_SIZE,
    PAGE_SIZE,
    SECTOR_SIZE,
    DASDImage,
    HeaderSnapshot,
    SectorHeader,
)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "b10_d1_first240k.headers.gz.b64"
)


def make_header(address, order=0, *, low_flag=0, tail=0):
    page_number = address >> 9
    page_word = (page_number << 1) | (low_flag & 1)
    return (
        page_word.to_bytes(5, "big")
        + bytes([order & 0x0F, 0, tail])
    )


def write_image(path, sectors):
    with open(path, "wb") as handle:
        for header, payload in sectors:
            handle.write(header)
            handle.write(payload)


class DASDHeaderTests(unittest.TestCase):
    def test_header_decode(self):
        header = SectorHeader(bytes.fromhex("00a1c30100050000"))
        self.assertEqual(header.virtual_address, 0x00A1C3010000)
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
        compressed = base64.b64decode(FIXTURE.read_text().strip())
        raw = gzip.decompress(compressed)
        self.assertEqual(len(raw), 240000 * HEADER_SIZE)

        result = HeaderSnapshot(
            raw, name="B10 D1 first 240K headers"
        ).scan()

        self.assertIsNotNone(result.origin)
        self.assertEqual(result.origin.lba, 2112)
        self.assertEqual(
            result.origin.header.hex(), "0000fc00000f0000"
        )
        self.assertEqual(result.origin.extent_pages, 32768)
        self.assertEqual(result.origin.repeats, 7)
        self.assertEqual(result.reserved_nonzero_headers, 0)

        self.assertEqual(len(result.free_extents), 7)
        self.assertEqual(result.free_pages, 229376)
        self.assertEqual(len(result.allocated_extents), 434)
        self.assertEqual(result.allocated_pages, 7872)

        first = result.allocated_extents[0]
        self.assertEqual(first.start_lba, 231488)
        self.assertEqual(first.pages, 32)
        self.assertEqual(
            first.virtual_address, 0x00A1C3010000
        )

        second = result.allocated_extents[1]
        self.assertEqual(second.start_lba, 231520)
        self.assertEqual(second.pages, 16)
        self.assertEqual(
            second.virtual_address, 0x00A1C3014000
        )


if __name__ == "__main__":
    unittest.main()
