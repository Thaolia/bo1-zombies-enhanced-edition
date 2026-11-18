"""TranZit's buildable pieces and finished parts (tools/bo2/bo2_layout.py buildable_parts), on made-up entities."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "bo2"))

import bo2_layout  # noqa: E402


def struct(targetname, origin="0 0 0", **keys):
    return dict(classname="script_struct", targetname=targetname, origin=origin, **keys)


class BuildableParts(unittest.TestCase):
    def test_spots_groups_and_built_parts(self):
        ents = [
            {"classname": "trigger_use", "targetname": "powerswitch_buildable_trigger", "origin": "1 2 3",
             "script_gameobjectname": "zclassic"},
            struct("powerswitch_p6_zm_buildable_pswitch_hand", "10 0 0"),
            struct("powerswitch_p6_zm_buildable_pswitch_hand", "20 0 0"),
            struct("powerswitch_p6_zm_buildable_pswitch_body"),
            struct("powerswitch_p6_zm_buildable_pswitch_lever"),
            {"classname": "script_model", "targetname": "powerswitch_p6_zm_buildable_pswitch_lever", "origin": "5 5 5",
             "script_gameobjectname": "zclassic"},
            # a script model of another game mode is no finished part
            {"classname": "script_model", "targetname": "powerswitch_p6_zm_buildable_pswitch_hand", "origin": "6 6 6",
             "script_gameobjectname": "zsurvival"},
        ]
        parts = bo2_layout.buildable_parts(ents)
        self.assertEqual(list(parts), ["powerswitch"])
        ps = parts["powerswitch"]
        self.assertEqual(ps["trigger"]["origin"], "1 2 3")
        self.assertEqual([g for g, _ in ps["pieces"]["p6_zm_buildable_pswitch_hand"]],
                         ["piece:powerswitch:pswitch_hand:0", "piece:powerswitch:pswitch_hand:1"])
        self.assertEqual([g for g, _ in ps["built"]["p6_zm_buildable_pswitch_lever"]], ["built:powerswitch:pswitch_lever"])
        self.assertEqual(ps["built"]["p6_zm_buildable_pswitch_hand"], [])

    def test_shared_piece_told_apart_by_claim_location(self):
        ents = [
            {"classname": "trigger_use", "targetname": "pap_buildable_trigger", "origin": "0 0 0"},
            struct("pap_p6_zm_buildable_battery", "1 0 0", claim_location="pap_battery"),
            struct("pap_p6_zm_buildable_battery", "2 0 0", claim_location="etrap_battery"),
        ]
        spots = bo2_layout.buildable_parts(ents)["pap"]["pieces"]["p6_zm_buildable_battery"]
        self.assertEqual([e["origin"] for _, e in spots], ["1 0 0"])

    def test_turbine_needs_no_machine(self):
        ents = [{"classname": "trigger_use", "targetname": "turbine_buildable_trigger", "origin": "0 0 0"}]
        ents += [struct(f"turbine_{m}") for m in bo2_layout.BUILDABLES["turbine"]["pieces"]]
        parts = bo2_layout.buildable_parts(ents)["turbine"]
        self.assertEqual(sorted(parts["pieces"]), sorted(bo2_layout.BUILDABLES["turbine"]["pieces"]))
        self.assertTrue(all(len(spots) == 1 for spots in parts["pieces"].values()))

    def test_equipment_spots_by_weapon_name_and_table_weapon(self):
        ents = [
            {"classname": "trigger_use", "targetname": "riotshield_zm_buildable_trigger", "origin": "0 0 0",
             "script_gameobjectname": "zclassic"},
            struct("riotshield_zm_t6_wpn_zmb_shield_dolly", "1 0 0"),
            struct("riotshield_zm_t6_wpn_zmb_shield_door", "2 0 0"),
            struct("riotshield_zm_t6_wpn_zmb_shield_door", "3 0 0"),
            {"classname": "script_model", "targetname": "buildable_riotshield", "origin": "4 0 0",
             "model": "t6_wpn_zmb_shield_world", "script_gameobjectname": "zclassic"},
        ]
        parts = bo2_layout.buildable_parts(ents)["riotshield"]
        self.assertEqual([g for g, _ in parts["pieces"]["t6_wpn_zmb_shield_door"]],
                         ["piece:riotshield:shield_door:0", "piece:riotshield:shield_door:1"])
        self.assertEqual([(g, e["origin"]) for g, e in parts["built"]["weapon"]], [("built:riotshield:weapon", "4 0 0")])


if __name__ == "__main__":
    unittest.main()
