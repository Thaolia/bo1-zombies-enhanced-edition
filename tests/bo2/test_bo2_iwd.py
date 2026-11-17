"""tools/bo2/bo2_iwd.py: the native maps' and weapons' images packed as one IWD."""
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "bo2"))
import bo2_iwd  # noqa: E402


class PackTest(unittest.TestCase):
    def test_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            images = os.path.join(folder, "images")
            os.mkdir(images)
            for name, data in (("bo2_b.iwi", b"IWi" + b"b" * 64), ("bo2_a.iwi", b"IWi" + b"a" * 64),
                               ("other.iwi", b"x")):
                with open(os.path.join(images, name), "wb") as f:
                    f.write(data)
            first, second = os.path.join(folder, "1.iwd"), os.path.join(folder, "2.iwd")
            self.assertEqual(bo2_iwd.pack(images, first), ["bo2_a.iwi", "bo2_b.iwi"])
            with zipfile.ZipFile(first) as z:
                # under images/, sorted, deflated, and the data unchanged; other.iwi does not match bo2_*.iwi
                self.assertEqual(z.namelist(), ["images/bo2_a.iwi", "images/bo2_b.iwi"])
                self.assertEqual(z.getinfo("images/bo2_a.iwi").compress_type, zipfile.ZIP_DEFLATED)
                self.assertEqual(z.read("images/bo2_b.iwi"), b"IWi" + b"b" * 64)
            # the same images give the same bytes (fixed dates), whenever they are packed
            os.utime(os.path.join(images, "bo2_a.iwi"), (0, 0))
            bo2_iwd.pack(images, second)
            with open(first, "rb") as a, open(second, "rb") as b:
                self.assertEqual(a.read(), b.read())
            self.assertEqual(bo2_iwd.pack(images, second, "*.iwi"), ["bo2_a.iwi", "bo2_b.iwi", "other.iwi"])

    def test_nothing_to_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(bo2_iwd.main([folder, os.path.join(folder, "out.iwd")]), 1)
            self.assertFalse(os.path.exists(os.path.join(folder, "out.iwd")))


if __name__ == "__main__":
    unittest.main()
