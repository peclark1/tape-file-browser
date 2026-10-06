import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from as400_dasd import PAGE_SIZE
from as400_dasd_tool import main


def header_for(address):
    return address.to_bytes(6, "big") + b"\x12\x34"


def write_sample(path):
    with open(path, "wb") as handle:
        for i in range(12):
            handle.write(header_for(0x100000 + i * PAGE_SIZE))
            handle.write(
                ("QGPL TEST%02d" % i).encode("cp037").ljust(PAGE_SIZE, b"\x40")
            )


class DASDToolTests(unittest.TestCase):
    def test_info_map_regions_and_sector(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "sample.hda"
            write_sample(image)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["info", str(image)])
            self.assertEqual(rc, 0)
            self.assertIn("Sector size:   520 bytes", stdout.getvalue())
            self.assertIn("Sector count:  12", stdout.getvalue())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["map", str(image), "--top", "3"])
            self.assertEqual(rc, 0)
            text = stdout.getvalue()
            self.assertIn("Address-header hypothesis", text)
            self.assertIn("big-endian, stride 0x200", text)
            self.assertIn("address runs:    1", text)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["regions", str(image), "--only-runs"])
            self.assertEqual(rc, 0)
            self.assertIn("address-run", stdout.getvalue())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["sector", str(image), "0", "--hex-bytes", "32"])
            self.assertEqual(rc, 0)
            self.assertIn("QGPL TEST00", stdout.getvalue())

    def test_bad_image_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "bad.hda"
            image.write_bytes(b"bad")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(["info", str(image)])
            self.assertEqual(rc, 1)
            self.assertIn("not divisible", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
