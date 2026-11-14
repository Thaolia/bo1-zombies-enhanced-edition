"""The BSP writer's sparse light grid (tools/bo2/d3dbsp.py): every point must be found where the engine looks for it.

    python3 -m unittest discover -s tests/bo2 -v
"""
import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "bo2"))
import d3dbsp  # noqa: E402


def engine_entry(lumps, pos):
    """The entry index R_GetLightGridSampleEntryQuad (rb_light.cpp) gives entries[0] for grid point pos, or None."""
    header = lumps[d3dbsp.LUMP_LIGHTGRIDHEADER]
    mins = struct.unpack_from("<3H", header, 0)
    maxs = struct.unpack_from("<3H", header, 6)
    row_axis, col_axis = struct.unpack_from("<II", header, 12)
    starts = struct.unpack_from("<%dH" % (maxs[row_axis] - mins[row_axis] + 1), header, 20)
    row_index = pos[row_axis] - mins[row_axis]
    if not 0 <= row_index < len(starts) or starts[row_index] == 0xFFFF:
        return None
    data = lumps[d3dbsp.LUMP_LIGHTGRIDROWS]
    at = 4 * starts[row_index]
    col_start, col_count, z_start, z_count, first = struct.unpack_from("<4HI", data, at)
    col = pos[col_axis] - col_start
    z = pos[2] - z_start
    if not 0 <= col < col_count or not 0 <= z < z_count:
        return None
    wide = z_count > 0xFF
    at += 12
    while col >= data[at]:
        col -= data[at]
        first += data[at + 1] * data[at]
        at += (4 if wide else 3) if data[at + 1] else 2
    height = data[at + 1]
    if not height:
        return None
    base = data[at + 2] + ((data[at + 3] << 8) if wide else 0)
    if not 0 <= z - base < height:
        return None
    return first + col * height + z - base


def write(rows, colours):
    bsp = d3dbsp.Bsp()
    all_blocks = [b for row in rows.values() for b in row if b[3]]
    mins = (min(rows), min(r[0][0] for r in rows.values()), min(b[2] for b in all_blocks))
    maxs = (max(rows), max(r[-1][0] + r[-1][1] - 1 for r in rows.values()), max(b[2] + b[3] - 1 for b in all_blocks))
    bsp.set_light_grid(mins, maxs, rows, colours)
    lumps = {}
    d3dbsp._write_light_grid(lumps, *bsp.light_grid)
    return lumps


class LightGridTest(unittest.TestCase):
    def check_every_point(self, rows, colours):
        lumps = write(rows, colours)
        entries = [struct.unpack_from("<HBB", lumps[d3dbsp.LUMP_LIGHTGRIDENTRIES], 4 * i)
                   for i in range(len(lumps[d3dbsp.LUMP_LIGHTGRIDENTRIES]) // 4)]
        found = 0
        for x, row in rows.items():
            for y0, count, z0, height, block in row:
                for c in range(count):
                    for dz in range(height):
                        index = engine_entry(lumps, (x, y0 + c, z0 + dz))
                        self.assertIsNotNone(index, (x, y0 + c, z0 + dz))
                        self.assertEqual(entries[index][:2], block[c * height + dz])
                        found += 1
                    # just under and over the block: no point
                    if height:
                        self.assertIsNone(engine_entry(lumps, (x, y0 + c, z0 + height)) if
                                          z0 + height < max(b[2] + b[3] for b in row) else None)
                    else:
                        self.assertIsNone(engine_entry(lumps, (x, y0 + c, row[0][2])))
        self.assertEqual(found, len(entries))
        return lumps

    def test_blocks_gaps_and_empty_rows(self):
        rng = random.Random(7)
        colours = [(0.5, 0.5, 0.5), (1.0, 1.0, 1.0), (0.2, 0.3, 0.4)]

        def block(y0, n, z0, h):
            return (y0, n, z0, h, [(rng.randrange(3), rng.choice((1, 2, 255))) for _ in range(n * h)])
        rows = {
            4100: [block(4000, 8, 2040, 5), block(4008, 8, 0, 0), block(4016, 3, 2038, 9)],
            4102: [block(3990, 255, 2050, 2)],
            4105: [block(4001, 1, 2045, 1)],
        }
        lumps = self.check_every_point(rows, colours)
        # rows 4101, 4103 and 4104 hold no point
        for x in (4101, 4103, 4104):
            self.assertIsNone(engine_entry(lumps, (x, 4001, 2045)))

    def test_tall_row_takes_two_byte_bases(self):
        rng = random.Random(3)
        rows = {100: [(10, 2, 0, 4, [(0, 1)] * 8), (12, 1, 300, 6, [(rng.randrange(2), 1) for _ in range(6)])]}
        self.check_every_point(rows, [(0.5, 0.5, 0.5), (1.0, 1.0, 1.0)])

    def test_empty_last_block_refused(self):
        with self.assertRaises(ValueError):
            write({5: [(0, 2, 10, 1, [(0, 1)] * 2), (2, 3, 0, 0, [])]}, [(0.5, 0.5, 0.5)])


if __name__ == "__main__":
    unittest.main()
