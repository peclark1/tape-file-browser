import tempfile
import unittest
from pathlib import Path

from as400_dasd import (
    KNOWN_B10_SHADOW_LOG_VADDR,
    PAGE_SIZE,
    SECTOR_SIZE,
    DASDImage,
)


def header_for(address, flags=b"\x12\x34"):
    return address.to_bytes(6, "big") + flags


def write_image(path, sectors):
    with open(path, "wb") as handle:
        for header, payload in sectors:
            assert len(header) == 8
            assert len(payload) == PAGE_SIZE
            handle.write(header)
            handle.write(payload)


class DASDImageTests(unittest.TestCase):
    def test_geometry_and_sector_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.hda"
            sectors = [
                (header_for(0x1000), b"A" * PAGE_SIZE),
                (header_for(0x1200), b"B" * PAGE_SIZE),
            ]
            write_image(path, sectors)
            image = DASDImage(path)
            self.assertEqual(image.sector_count, 2)
            self.assertEqual(path.stat().st_size, 2 * SECTOR_SIZE)
            sector = image.read_sector(1)
            self.assertEqual(sector.header, sectors[1][0])
            self.assertEqual(sector.data, b"B" * PAGE_SIZE)

    def test_rejects_non_520_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.hda"
            path.write_bytes(b"x" * 521)
            with self.assertRaisesRegex(ValueError, "not divisible"):
                DASDImage(path)

    def test_finds_six_byte_big_endian_512_stride(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "structured.hda"
            sectors = []
            address = 0x1234000000
            for i in range(40):
                sectors.append(
                    (header_for(address + i * PAGE_SIZE), bytes([i]) * PAGE_SIZE)
                )
            write_image(path, sectors)

            result = DASDImage(path).scan(min_run=4)
            best = result.best_layout
            self.assertIsNotNone(best)
            self.assertEqual(best.layout.offset, 0)
            self.assertEqual(best.layout.width, 6)
            self.assertEqual(best.layout.byteorder, "big")
            self.assertEqual(best.layout.stride, PAGE_SIZE)
            self.assertEqual(best.matches, 39)
            self.assertEqual(len(result.sequential_regions), 1)
            self.assertEqual(result.sequential_regions[0].sector_count, 40)

    def test_regions_separate_zero_header_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regions.hda"
            sectors = []
            for i in range(8):
                sectors.append((header_for(0x2000 + i * PAGE_SIZE), b"A" * PAGE_SIZE))
            for _ in range(3):
                sectors.append((b"\x00" * 8, b"\x00" * PAGE_SIZE))
            for i in range(6):
                sectors.append((header_for(0x8000 + i * PAGE_SIZE), b"B" * PAGE_SIZE))
            write_image(path, sectors)

            result = DASDImage(path).scan(min_run=4)
            kinds = [region.kind for region in result.regions]
            self.assertEqual(kinds, ["address-run", "zero-header", "address-run"])
            self.assertEqual(result.regions[1].sector_count, 3)

    def test_known_anchor_can_be_located_under_selected_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "anchor.hda"
            start = KNOWN_B10_SHADOW_LOG_VADDR - 3 * PAGE_SIZE
            sectors = [
                (header_for(start + i * PAGE_SIZE), b"X" * PAGE_SIZE)
                for i in range(10)
            ]
            write_image(path, sectors)
            image = DASDImage(path)
            result = image.scan()
            matches = image.find_virtual(
                KNOWN_B10_SHADOW_LOG_VADDR, result.best_layout.layout
            )
            self.assertEqual(matches, [3])


if __name__ == "__main__":
    unittest.main()
