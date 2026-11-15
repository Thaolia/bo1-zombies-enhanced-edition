"""TranZit's bus headings, call spots and bank (tools/bo2/bo2_layout.py) and the bus door models (bo2_mesh.py)."""
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "bo2"))

import bo2_layout  # noqa: E402
import bo2_mesh  # noqa: E402


class FlatWorld:
    """A Collision stand-in: a floor at z 0 everywhere, solid where y >= wall_y (a wall along the x axis)."""

    def __init__(self, wall_y=None):
        self.wall_y = wall_y

    def floor(self, point, mask=None):
        return 0.0 if point[2] >= 0 else None

    def solid_at(self, p, skip=()):
        return self.wall_y is not None and p[1] >= self.wall_y


def d180(a):
    return (a + 180.0) % 360.0 - 180.0


class LoopHeadingsTest(unittest.TestCase):
    def test_square_loop_turns_smoothly(self):
        # a 2000-unit square, a point every 100 units, anticlockwise
        points = [[x, 0.0, 0.0] for x in range(0, 2000, 100)] + [[2000.0, y, 0.0] for y in range(0, 2000, 100)]
        points += [[x, 2000.0, 0.0] for x in range(2000, 0, -100)] + [[0.0, y, 0.0] for y in range(2000, 0, -100)]
        yaws = bo2_layout.loop_headings(points, reach=250.0)
        self.assertEqual(len(yaws), len(points))
        self.assertAlmostEqual(yaws[10], 0.0, places=3)  # the middle of the first side
        self.assertAlmostEqual(yaws[30] % 360.0, 90.0, places=3)
        # the corner (point 20) takes the diagonal, and no step between points turns more than 45 degrees
        self.assertAlmostEqual(yaws[20] % 360.0, 45.0, places=3)
        steps = [abs(d180(yaws[(i + 1) % len(yaws)] - yaws[i])) for i in range(len(yaws))]
        self.assertLessEqual(max(steps), 45.0 + 1e-6)

    def test_zigzag_is_flattened(self):
        # a straight road with a point pushed 40 units aside every other point: per-segment headings swing 39 degrees
        points = [[i * 50.0, 40.0 if i % 2 else 0.0, 0.0] for i in range(40)]
        points += [[2000.0 - i * 50.0, 1000.0, 0.0] for i in range(40)]
        yaws = bo2_layout.loop_headings(points, reach=250.0)
        for i in range(8, 32):
            self.assertLess(abs(d180(yaws[i])), 6.0, i)


class CallSpotTest(unittest.TestCase):
    def test_wall_on_the_doors_side(self):
        # the bus heads +x; its doors are on its right (-y); a wall stands at y <= -200
        col = FlatWorld()
        col.solid_at = lambda p, skip=(): p[1] <= -200.0
        spot = bo2_layout.call_spot(col, [0.0, 0.0, 0.0], 0.0)
        self.assertEqual(spot["wall"], 1)
        self.assertAlmostEqual(spot["origin"][0], bo2_layout.CALL_ALONG[0])
        self.assertAlmostEqual(spot["origin"][1], -196.0)  # 4 units off the wall
        self.assertAlmostEqual(spot["yaw"], 90.0)  # facing the road (+y)

    def test_no_wall(self):
        spot = bo2_layout.call_spot(FlatWorld(), [0.0, 0.0, 0.0], 0.0)
        self.assertEqual(spot["wall"], 0)
        self.assertAlmostEqual(spot["origin"][1], -150.0)


class BankEditTest(unittest.TestCase):
    def test_windows_and_locker(self):
        props = [("p6_zm_bank_teller_window", [773.0, 161.0, 4.0], [1.0, 0.0, 0.0]),
                 ("p6_zm_bank_teller_window", [773.0, 74.0, 4.0], [1.0, 0.0, 0.0]),
                 ("p6_zm_bank_teller_window_d1", [773.0, 415.0, 4.0], [1.0, 0.0, 0.0]),
                 ("p6_zm_weapon_locker", [100.0, 0.0, 20.0], [0.0, 1.0, 0.0])]
        edit = bo2_layout.bank_edit(props, FlatWorld())
        self.assertEqual(edit["deposit"], {"origin": [805.0, 74.0, 4.0], "yaw": 180.0})
        self.assertEqual(edit["withdraw"], {"origin": [805.0, 161.0, 4.0], "yaw": 180.0})
        # in front of the locker (its +x... here +y), at a player's chest over the floor under it
        self.assertEqual(edit["locker"], {"origin": [100.0, 32.0, 48.0], "yaw": 270.0})

    def test_no_bank(self):
        self.assertIsNone(bo2_layout.bank_edit([("p6_zm_bank_teller_window", [0, 0, 0], [1, 0, 0])], FlatWorld()))

    def test_read_props(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "m.d3dbsp.smodels.csv")
            with open(path, "w", encoding="latin-1") as f:
                f.write("model,x,y,z,ax0,ax1,ax2,ay0,ay1,ay2,az0,az1,az2,scale\n")
                f.write("p6_zm_weapon_locker,1,2,3,0,1,0,-1,0,0,0,0,1,1\n")
            self.assertEqual(bo2_layout.read_props(path), [("p6_zm_weapon_locker", [1.0, 2.0, 3.0], [0.0, 1.0, 0.0])])
            self.assertEqual(bo2_layout.read_props(os.path.join(folder, "none.csv")), [])


class DoorPartTest(unittest.TestCase):
    def test_holes_and_parts_split_the_model(self):
        inside = (((40.0, -80.0, 20.0), (0.0, 0.0)), ((50.0, -80.0, 20.0), (0.0, 0.0)), ((45.0, -80.0, 60.0), (0.0, 0.0)))
        outside = (((0.0, 0.0, 0.0), (0.0, 0.0)), ((10.0, 0.0, 0.0), (0.0, 0.0)), ((5.0, 0.0, 10.0), (0.0, 0.0)))
        lod = {"body": [inside, outside], "glass": [outside]}
        hole = ((34.0, -84.0, 12.0), (82.0, -58.0, 128.0))
        self.assertEqual(bo2_mesh.cut_holes(lod, [hole]), {"body": [outside], "glass": [outside]})
        self.assertEqual(bo2_mesh.hole_part(lod, hole), {"body": [inside]})


if __name__ == "__main__":
    unittest.main()
