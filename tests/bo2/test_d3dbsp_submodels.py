"""The BSP writer's brush models (tools/bo2/d3dbsp.py add_submodel): their surfaces and brushes follow the world's.

    python3 -m unittest discover -s tests/bo2 -v
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "bo2"))
import d3dbsp  # noqa: E402


def lumps(path):
    with open(path, "rb") as f:
        data = f.read()
    count = struct.unpack_from("<I", data, 8)[0]
    at, out = 12 + 8 * count, {}
    for i in range(count):
        lump, length = struct.unpack_from("<II", data, 12 + 8 * i)
        out[lump] = data[at:at + length]
        at += length + (-length & 3)
    return out


class SubmodelTest(unittest.TestCase):
    def test_models_follow_the_world(self):
        bsp = d3dbsp.build_room()
        world_brushes = len(bsp.brushes)
        wood = bsp.add_material("wood_test", 0, 0)
        solid = bsp.add_material("solid_test", 0, d3dbsp.CONTENTS_SOLID)
        board = dict(material=wood, positions=[(-10, -1, -5), (10, -1, -5), (10, -1, 5), (-10, -1, 5)],
                     indices=[0, 1, 2, 2, 3, 0])
        first = bsp.add_submodel((-10, -1, -5), (10, 1, 5), [((-10, -1, -5), (10, 1, 5), solid, [solid] * 6, [])],
                                 [board])
        second = bsp.add_submodel((-2, -2, -2), (2, 2, 2), [], [board, board])
        self.assertEqual((first, second), (1, 2))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "room.d3dbsp")
            bsp.write(path)
            out = lumps(path)
        models = [struct.unpack_from("<3f3fHHiiii", out[d3dbsp.LUMP_MODELS], 44 * i)
                  for i in range(len(out[d3dbsp.LUMP_MODELS]) // 44)]
        surfaces = len(out[d3dbsp.LUMP_TRIANGLES]) // 28
        brushes = len(out[d3dbsp.LUMP_BRUSHES]) // 4
        self.assertEqual(len(models), 3)
        world, one, two = models
        self.assertEqual((world[6], world[11]), (0, world_brushes))
        self.assertEqual((one[6], one[7], one[10], one[11]), (world[7], 1, world_brushes, 1))
        self.assertEqual((two[6], two[7], two[10], two[11]), (world[7] + 1, 2, world_brushes + 1, 0))
        self.assertEqual(surfaces, world[7] + 3)
        self.assertEqual(brushes, world_brushes + 1)
        self.assertEqual(one[0:6], (-10.0, -1.0, -5.0, 10.0, 1.0, 5.0))


if __name__ == "__main__":
    unittest.main()
