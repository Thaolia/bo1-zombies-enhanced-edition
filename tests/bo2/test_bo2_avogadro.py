"""TranZit's Avogadro: its layout edits (tools/bo2/bo2_layout.py avogadro_edits) and the colour maps the converter
draws for its model (tools/bo2/bo2_weapon.py GENERATED_COLOURS), on made-up data."""
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "bo2"))

import bo2_layout  # noqa: E402
import bo2_weapon  # noqa: E402


def spot(zone, origin, angles="0 90 0"):
    return {"classname": "script_struct", "script_noteworthy": "avogadro_location", "targetname": zone + "_spawners",
            "origin": origin, "angles": angles}


class AvogadroEdits(unittest.TestCase):
    def test_spawner_core_and_spots(self):
        ents = [
            {"classname": "script_model", "targetname": "core_mover", "origin": "1000 0 -700"},
            spot("zone_pow", "900 0 -720", "0 45 0"),
            spot("zone_din", "-5000 0 40"),
            spot("zone_din", "-5000 0 40"),  # listed twice, as BO2 does for a few
            spot("zone_roof", "0 3000 300"),  # a zone no region names
            # another struct with the same targetname is no spot
            {"classname": "script_struct", "targetname": "zone_pow_spawners", "origin": "1 1 1"},
        ]
        edits = bo2_layout.avogadro_edits(ents)
        ent, core = edits[0], edits[1]
        self.assertEqual(ent["kind"], "ent")
        self.assertEqual(ent["keys"]["classname"], bo2_layout.AVOGADRO_CLASS)
        self.assertEqual(ent["keys"]["targetname"], "mapkit_avogadro_spawner")
        # it stands on the spot nearest to the core, not in the reactor's pit
        self.assertEqual(ent["keys"]["origin"], [900.0, 0.0, -719.0])
        self.assertEqual(ent["keys"]["angles"], [0, 45.0, 0])
        self.assertEqual(core, {"kind": "avogadro", "origin": [900.0, 0.0, -720.0], "yaw": 45.0,
                                "core": [1000.0, 0.0, -700.0]})
        spots = edits[2:]
        self.assertEqual([(s["zone"], s["region"]) for s in spots],
                         [("zone_pow", "power"), ("zone_din", "diner"), ("zone_roof", "")])
        self.assertTrue(all(s["kind"] == "avogadrospot" for s in spots))

    def test_none_without_core_or_spots(self):
        self.assertEqual(bo2_layout.avogadro_edits([spot("zone_pow", "0 0 0")]), [])
        self.assertEqual(bo2_layout.avogadro_edits([{"targetname": "core_mover", "origin": "0 0 0"}]), [])

    def test_every_region_zone_named_once(self):
        zones = [z for zs in bo2_layout.AVOGADRO_REGIONS.values() for z in zs]
        self.assertEqual(len(zones), len(set(zones)))


class GeneratedColours(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        bo2, bo1, out = (os.path.join(root, d) for d in ("bo2", "bo1", "out"))
        for d in (os.path.join(bo1, "materials"), os.path.join(bo1, "xanim"), os.path.join(bo2, "images")):
            os.makedirs(d)
        self.project = bo2_weapon.Project(types.SimpleNamespace(dump=[bo2], bo1=bo1, out=out, bo1_map=[]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_vein_map_is_drawn(self):
        bo2_name = "~-gc_zom_avagadro_veins_c"
        name = self.project.image(bo2_name)
        self.assertTrue(name.endswith("_gen"))
        iwi = os.path.join(self.project.raw, "images", name + ".iwi")
        with open(iwi, "rb") as f:
            self.assertEqual(f.read(3), b"IWi")
        self.assertFalse(os.path.exists(iwi[:-4] + ".dds"))
        self.assertTrue(any("generated" in n for n in self.project.notes))
        # asked again, the same image without drawing it twice
        self.assertEqual(self.project.image(bo2_name), name)
        self.assertEqual(sum("generated" in n for n in self.project.notes), 1)

    def test_other_missing_image_still_kept_from_the_template(self):
        self.assertIsNone(self.project.image("~-gsome_streamed_c"))


if __name__ == "__main__":
    unittest.main()
