"""tools/unlimitedpap/make_perks.py: reading a rawfile out of a PC fastfile and applying the mod's edits.

    python3 -m unittest discover -s tests/unlimitedpap -v

The fastfiles here are made up from the edits' own anchors: no retail script is needed or held.
"""
import os
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "unlimitedpap"))
import make_perks as M  # noqa: E402


def fastfile(path, rawfiles, magic=b"IWffu100"):
    """A PC fastfile holding `rawfiles` ({name: text}) as make_perks reads them."""
    stream = b"\x00" * 64
    for name, text in rawfiles.items():
        body = text.encode("latin-1")
        packed = zlib.compress(body)
        stream += (b"\xff\xff\xff\xff" + name.encode() + b"\x00" + len(body).to_bytes(4, "little")
                   + len(packed).to_bytes(4, "little") + packed + b"\x00" * 16)
    with open(path, "wb") as f:
        f.write(magic + b"\x00\x00\x01\xd9" + zlib.compress(stream))


def script(edits):
    """A script whose lines are the edits' anchors, in order, between filler lines."""
    return "init()\r\n{\r\n}\r\n" + "".join(old + "\t// filler\r\n" for old, _ in edits)


class MakePerks(unittest.TestCase):
    def test_reads_and_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            ff = os.path.join(tmp, "common_zombie_patch.ff")
            fastfile(ff, {"maps/_zombiemode.gsc": "other\r\n", M.SCRIPT: script(M.EDITS)})
            text = M.apply_edits(M.read_rawfile(ff, M.SCRIPT))
            self.assertEqual(text, "init()\r\n{\r\n}\r\n" + "".join(new + "\t// filler\r\n" for _, new in M.EDITS))
            self.assertEqual(text.count("UNLIMITEDPAP"), 8)
            self.assertNotIn("is_weapon_upgraded", text)
            self.assertNotIn("minus_to_player_score( self.cost )", text)

    def test_missing_or_repeated_anchor(self):
        text = script(M.EDITS)
        with self.assertRaisesRegex(ValueError, "found 0 times"):
            M.apply_edits(text.replace(M.EDITS[4][0], ""))
        with self.assertRaisesRegex(ValueError, "found 2 times"):
            M.apply_edits(text + M.EDITS[7][0])

    def test_not_a_fastfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            ff = os.path.join(tmp, "x.ff")
            fastfile(ff, {M.SCRIPT: "x"}, magic=b"IWffs100")
            with self.assertRaisesRegex(ValueError, "not a PC fastfile"):
                M.read_rawfile(ff, M.SCRIPT)
            fastfile(ff, {"maps/_zombiemode.gsc": "x"})
            with self.assertRaisesRegex(ValueError, "0 copies"):
                M.read_rawfile(ff, M.SCRIPT)


if __name__ == "__main__":
    unittest.main()
