#!/usr/bin/env python3
"""A BO2 map's placed ambient effects (its compiled createfx script) as MapKit "fx" edits with BO1 effects.

    tools/bo2/bo2_createfx.py <clientscripts/mp/createfx/<map>_fx.csc> [--all]

The script comes from the map's patch zone (OAT's Unlinker: --include-assets script on zm_<map>_patch.ff). It is T6
GSC bytecode, read here only as far as createfx needs: each createoneshoteffect / createloopeffect /
createexploder call names an effect id, and the vector pushed before the next "origin" field is its origin
(three numbers, then the vector opcode; GSC pushes a vector's components last to first).

BO2's effects cannot be read (OAT has no FxEffectDef for T6 or T5), so each BO2 effect id that has a BO1 equivalent
(EFFECTS) becomes that BO1 effect, which the zone built from the Mod Tools' raw/fx holds (docs/BO2_MAPS.md, "Placed
effects"). The ambient ones (embers, fires, smoke) do not keep BO2's angles: BO1's spread their particles across the
effect's forward axis, and MapKit spawns them pointing up, as createfx places BO1's own. The directed ones (ORIENTED:
light rays and sparks, which both games lay along the forward axis) keep them (pitch, yaw, roll). Exploders (one-off
scripted blasts) are left out, but for EXPLODERS_KEPT. Prints the BO1 effects used (the fx zone's source) and, with --all, every BO2 effect id
the script places.
"""
import argparse
import struct
import sys

# BO2 effect id -> the BO1 effect (Mod Tools raw/fx path, without fx/) drawn in its place
EFFECTS = {
    # Nuketown's embers and ash, falling around the burning houses, rising from them, and gusting over the street
    "fx_ash_embers_falling_radioactive_md": "env/fire/fx_embers_falling_md",
    "fx_ash_embers_falling_radioactive_sm": "env/fire/fx_embers_falling_sm",
    "fx_ash_embers_up_lg": "env/fire/fx_embers_up_dist",
    "fx_zmb_nuke_radioactive_ash_gusty": "env/fire/fx_ash_embers_light",
    "fx_zmb_nuke_burning_ash_gusty": "env/fire/fx_ash_embers_heavy",
    "fx_zmb_nuke_radioactive_embers": "env/fire/fx_embers_wind_md",
    "fx_zmb_nuke_radioactive_embers_crater": "env/fire/fx_embers_wind_md",
    # its fires, as point fires without a dynamic light: BO2's fire lines run along their angles, which are not kept
    "fx_fire_xsm": "env/fire/fx_fire_detail_sm_nodlight",
    "fx_fire_line_xsm": "env/fire/fx_fire_detail_sm_nodlight",
    "fx_fire_line_xsm_pole": "env/fire/fx_fire_detail_sm_nodlight",
    "fx_fire_line_sm": "env/fire/fx_fire_sm",
    "fx_fire_line_sm_pole": "env/fire/fx_fire_sm",
    "fx_nic_fire_ceiling_edge_sm": "env/fire/fx_fire_sm",
    "fx_fire_wood_floor_int": "env/fire/fx_fire_sm",
    "fx_fire_smolder_area_sm": "env/fire/fx_fire_sm",
    "fx_fire_sm_smolder": "env/fire/fx_fire_sm_smolder",
    "fx_fire_ceiling_md": "env/fire/fx_fire_md",
    "fx_fire_ceiling_edge_md": "env/fire/fx_fire_md",
    "fx_fire_ceiling_rafter_md": "env/fire/fx_fire_md",
    "fx_fire_eaves_md": "env/fire/fx_fire_md",
    "fx_fire_eaves_md_right": "env/fire/fx_fire_md",
    "fx_fire_fireplace_md": "env/fire/fx_fire_md",
    "fx_fire_wall_wood_ext_md": "env/fire/fx_fire_md",
    "fx_fire_pole_md_long": "env/fire/fx_fire_md",
    "fx_zmb_nuke_fire_windblown_md": "env/fire/fx_fire_md",
    "fx_zmb_tranzit_fire_med": "env/fire/fx_fire_md",
    "fx_zmb_tranzit_fire_lrg": "env/fire/fx_fire_lg",
    "fx_nic_fire_building_md_dist": "env/fire/fx_fire_large_distant",
    # and its smoke
    "fx_smk_fire_lg_black": "env/smoke/fx_smk_fire_lg_black",
    "fx_smk_linger_lit": "env/smoke/fx_smk_linger_lit",
    "fx_smk_linger_lit_slow": "env/smoke/fx_smk_linger_lit",
    "fx_smk_linger_lit_z": "env/smoke/fx_smk_linger_lit",
    "fx_smk_plume_md_blk_wispy_dist": "env/smoke/fx_smk_plume_md_blk",
    "fx_smk_smolder_gray_fast": "env/smoke/fx_smk_smolder_sm",
    "fx_smk_smolder_gray_slow": "env/smoke/fx_smk_smolder_sm",
    "fx_smk_smolder_rubble_md_int": "env/smoke/fx_smk_smolder_rubble_md",
    "fx_smk_wood_sm_black": "env/smoke/fx_smk_smolder_sm_blk",
    # its sparks
    "fx_elec_spark_wire_xsm_runner": "env/electrical/fx_elec_wire_sparks",
    "fx_elec_transformer_sparks_runner": "env/electrical/fx_elec_burst_shower_sm_runner",
    "fx_mp_elec_spark_burst_xsm_thin_runner": "env/electrical/fx_elec_short_random",
    # and its light rays: the sun through the roofs, the grates, a fluorescent tube
    "fx_zm_nuked_light_ray_md_wide": "env/light/fx_light_godray_md_white",
    "fx_zm_nuked_light_ray_md_wide_streak": "env/light/fx_ray_md_1sd",
    "fx_zm_nuked_light_ray_md_wide_streak_1s": "env/light/fx_ray_md_1sd",
    "fx_zm_nuked_light_ray_streaks_1s": "env/light/fx_ray_sm_1sd",
    "fx_light_ray_grate_warm": "env/light/fx_light_godray_sm_warm",
    "fx_light_flour_glow_cool_sngl_shrt": "env/light/fx_light_fluorescent",
    # its radiation fog (in a house) and the clouds around the map (BO1's 3D clouds are drawn up to 120 000 units, the
    # flat ones only 25 000: BO2's lie 20 000 to 37 000 away)
    "fx_zmb_fog_low_radiation_140x300": "env/smoke/fx_fog_interior_md",
    "fx_cloud_cover_flat": "env/weather/fx_cloud3d_cmls_lg1_dark",
    "fx_cloud_cover_volume": "env/weather/fx_cloud3d_cmls_lg1_dark",
    # TranZit's ash and embers
    "fx_zmb_ash_ember_2000x1000": "env/fire/fx_ash_embers_light",
    "fx_zmb_ash_ember_1000x1000": "env/fire/fx_ash_embers_light",
    "fx_zmb_ash_windy_heavy_sm": "env/fire/fx_ash_embers_heavy",
    "fx_zmb_ash_windy_heavy_md": "env/fire/fx_ash_embers_heavy",
    "fx_zmb_ash_rising_md": "env/fire/fx_embers_up_dist",
    # its smoke, the lava's steam with it
    "fx_zmb_tranzit_smk_interior_md": "env/smoke/fx_smk_hallway_md",
    "fx_zmb_tranzit_smk_column_lrg": "env/smoke/fx_smk_column_lg_blk",
    "fx_zmb_lava_smoke_tall": "env/smoke/fx_smk_plume_md_wht",
    "fx_zmb_lava_smoke_pit": "env/smoke/fx_smk_smolder_md_wht",
    # its fog: closets, low fog, and the thick fog between the areas
    "fx_zmb_fog_closet": "env/smoke/fx_fog_interior_md",
    "fx_zmb_fog_low_300x300": "env/smoke/fx_fog_low",
    "fx_zmb_fog_thick_600x600": "env/smoke/fx_fog_rolling_thick_600x600",
    "fx_zmb_fog_thick_1200x600": "env/smoke/fx_fog_rolling_thick_600x600",
    "fx_zmb_fog_transition_600x600": "env/smoke/fx_fog_large_slow",
    "fx_zmb_fog_transition_1200x600": "env/smoke/fx_fog_large_slow",
    "fx_zmb_fog_transition_right_border": "env/smoke/fx_fog_large_slow",
    # its light rays (depot, power station, tunnel, bank vault) and fluorescent tubes
    "fx_zmb_tranzit_god_ray_depot_warm": "env/light/fx_light_godray_md_warm",
    "fx_zmb_tranzit_god_ray_interior_long": "env/light/fx_light_godray_lrg_warm",
    "fx_zmb_tranzit_god_ray_interior_med": "env/light/fx_light_godray_md_warm",
    "fx_zmb_tranzit_god_ray_short_warm": "env/light/fx_light_godray_sm_warm",
    "fx_zmb_tranzit_god_ray_tunnel_warm": "env/light/fx_light_godray_sm_warm",
    "fx_zmb_tranzit_god_ray_depot_cool": "env/light/fx_light_godray_md_cool",
    "fx_zmb_tranzit_god_ray_pwr_station": "env/light/fx_light_godray_md_white",
    "fx_zmb_tranzit_god_ray_vault": "env/light/fx_light_godray_md_white",
    "fx_zmb_tranzit_flourescent_glow_lg": "env/light/fx_light_fluorescent",
    "fx_zmb_tranzit_flourescent_glow": "env/light/fx_light_fluorescent",
    "fx_zmb_tranzit_flourescent_flicker": "env/light/fx_light_fluorescent",
    "fx_zmb_tranzit_flourescent_dbl_glow": "env/light/fx_light_fluorescent",
    # and its sparks
    "fx_zmb_tranzit_spark_blue_lg_loop": "env/electrical/fx_elec_wire_sparks",
    # Mob of the Dead's fires (not its candles: BO1's candle carries a dynamic light, and there are 59), embers and ash
    "fx_alcatraz_fire_xsm": "env/fire/fx_fire_detail_sm_nodlight",
    "fx_alcatraz_fire_sm": "env/fire/fx_fire_sm",
    "fx_alcatraz_fire_md": "env/fire/fx_fire_md",
    "fx_alcatraz_ceiling_fire": "env/fire/fx_fire_md",
    "fx_alcatraz_fire_works": "env/fire/fx_fire_sm",
    "fx_alcatraz_embers_flat": "env/fire/fx_embers_falling_sm",
    "fx_alcatraz_embers_indoor": "env/fire/fx_embers_falling_sm",
    "fx_alcatraz_steam_ash": "env/fire/fx_ash_embers_light",
    "fx_alcatraz_tunnel_ash": "env/fire/fx_ash_embers_light",
    # its smoke, steam, fog, light rays and sparks
    "fx_alcatraz_smk_linger": "env/smoke/fx_smk_linger_lit",
    "fx_alcatraz_steam_pipe_2": "env/smoke/fx_pipe_steam_md",
    "fx_alcatraz_steam_3floor": "env/smoke/fx_steam_hallway_md",
    "fx_alcatraz_ground_fog": "env/smoke/fx_fog_low",
    "fx_alcatraz_vista_fog": "env/smoke/fx_fog_rolling_vista_lg",
    "fx_alcatraz_fog_closet": "env/smoke/fx_fog_interior_md",
    "fx_alcatraz_docks_fog": "env/smoke/fx_fog_large_slow",
    "fx_alcatraz_godray_jail": "env/light/fx_light_godray_md_white",
    "fx_alcatraz_godray_grill_lg": "env/light/fx_light_godray_md_white",
    "fx_alcatraz_godray_grill": "env/light/fx_light_godray_sm_white",
    "fx_alcatraz_godray_skinny": "env/light/fx_light_godray_sm_white",
    "fx_alcatraz_sparks_panel": "env/electrical/fx_elec_short_random",
    "fx_alcatraz_sparks_ceiling": "env/electrical/fx_elec_wire_sparks",
    # Buried's fog and low cloud, light rays and the dust in them, steam, smoke, ash and fireplace
    "fx_buried_fog_md": "env/smoke/fx_fog_low",
    "fx_buried_fog_sm": "env/smoke/fx_fog_low_sm",
    "fx_buried_cloud_low": "env/smoke/fx_fog_large_slow",
    "fx_buried_godray_ext_thin": "env/light/fx_light_godray_sm_white",
    "fx_buried_godray_ext_sm": "env/light/fx_light_godray_sm_white",
    "fx_buried_god_ray_sm": "env/light/fx_light_godray_sm_warm",
    "fx_buried_godray_ext_md": "env/light/fx_light_godray_md_white",
    "fx_buried_godray_ext_lg": "env/light/fx_light_godray_md_white",
    "fx_buried_godray_church": "env/light/fx_light_godray_md_warm",
    "fx_buried_dust_motes_xlg": "env/light/fx_light_dust_motes_md",
    "fx_buried_dust_motes_ext_xlg": "env/light/fx_light_dust_motes_md",
    "fx_buried_dust_motes_ext_sm": "env/light/fx_light_dust_motes_sm",
    "fx_buried_steam_md": "env/smoke/fx_steam_hallway_md",
    "fx_buried_smk_plume_lg": "env/smoke/fx_smk_plume_lg_blk",
    "fx_buried_ash_blowing": "env/fire/fx_ash_embers_light",
    "fx_buried_fireplace": "env/fire/fx_fire_md",
    # the lamps, as glows without a dynamic light: the caged ones (tinhats) with their beam down along BO2's angles,
    # the others as a round glow seen from anywhere (BO1's ceiling and desk lamps lay theirs flat along the effect's
    # axis, so a can light seen from below the ceiling showed nothing; fx_mp_light_bulb_sm_no_eo was too faint to see)
    "fx_zmb_tranzit_light_street_tinhat": "env/light/fx_light_tinhat_cage_yellow",
    "fx_zmb_tranzit_light_depot_cans": "env/light/fx_light_incandescent",
    "fx_zmb_tranzit_light_town_cans": "env/light/fx_light_incandescent",
    "fx_zmb_tranzit_light_town_cans_sm": "env/light/fx_light_incandescent",
    "fx_zmb_tranzit_light_desklamp": "env/light/fx_light_incandescent",
    "fx_zmb_tranzit_light_glow_xsm": "env/light/fx_light_incandescent",
    "fx_zmb_tranzit_light_bulb_xsm": "env/light/fx_light_incandescent",
    "fx_zmb_tranzit_light_glow_fog": "env/light/fx_light_incandescent",
    "fx_zmb_tranzit_bar_glow": "env/light/fx_light_incandescent",
    "fx_alcatraz_light_tinhat": "env/light/fx_light_tinhat_cage",
    "fx_alcatraz_light_tinhat_oo": "env/light/fx_light_tinhat_cage",
    "fx_alcatraz_light_round_oo": "maps/zombie/fx_mp_light_corona_bulb_ceiling",
    "fx_buried_glow_kerosene_lamp": "env/light/fx_light_incandescent",
    "fx_buried_glow_sconce": "env/light/fx_light_incandescent",
}
# exploders placed all the same: they are lit for the whole game (Nuketown's clouds)
EXPLODERS_KEPT = {"fx_cloud_cover_flat", "fx_cloud_cover_volume"}
# the BO1 effects placed with BO2's angles (the others point up)
ORIENTED = {"env/electrical/fx_elec_wire_sparks", "env/electrical/fx_elec_burst_shower_sm_runner",
            "env/electrical/fx_elec_short_random", "env/light/fx_light_godray_md_white", "env/light/fx_ray_md_1sd",
            "env/light/fx_ray_sm_1sd", "env/light/fx_light_godray_sm_warm", "env/light/fx_light_fluorescent",
            "env/light/fx_light_godray_md_warm", "env/light/fx_light_godray_lrg_warm", "env/light/fx_light_godray_md_cool",
            "env/light/fx_light_godray_sm_white", "env/smoke/fx_pipe_steam_md", "env/light/fx_light_tinhat_cage",
            "env/light/fx_light_tinhat_cage_yellow"}

GSC_MAGIC = b"\x80GSC\r\n\x00\x06"  # T6 (PC)
OP_GET_ZERO, OP_GET_BYTE, OP_GET_NEG_BYTE, OP_GET_USHORT, OP_GET_NEG_USHORT = 0x03, 0x04, 0x05, 0x06, 0x07
OP_GET_INT, OP_GET_FLOAT, OP_VECTOR, OP_SIMPLE_VECTOR = 0x08, 0x09, 0x5B, 0x5E
CREATE_CALLS = ("createoneshoteffect", "createloopeffect", "createexploder")


def string_refs(data):
    """(code offset, string, kind) of every string the script's code uses, in code order (kind 0: a string literal,
    1: a field or variable name)."""
    fixups, count = struct.unpack_from("<I", data, 24)[0], struct.unpack_from("<H", data, 50)[0]
    refs, p = [], fixups
    for _ in range(count):
        offset, uses, kind = struct.unpack_from("<HBB", data, p)
        p += 4
        text = data[offset:data.index(b"\0", offset)].decode("latin-1")
        refs += [(a, text, kind) for a in struct.unpack_from(f"<{uses}I", data, p)]
        p += 4 * uses
    return sorted(refs)


def simple_vector(data, end):
    """A vector that OP_SIMPLE_VECTOR builds (its flags byte, then one more byte, end just after them, or the flags
    byte last): two bits per component, the last component's in the low bits, 0 for 0 and 2 for a number pushed before
    it ((273, 0, 0) is a GetFloat, then flags 0x20). None for any other code, which this file never had."""
    for at in (end - 3, end - 2):
        if at < 0 or data[at] != OP_SIMPLE_VECTOR:
            continue
        flags = data[at + 1]
        codes = [(flags >> (2 * (2 - i))) & 3 for i in range(3)]
        if any(c not in (0, 2) for c in codes) or flags >> 6:
            return None
        pushed = pushed_numbers(data, at, codes.count(2)) if 2 in codes else []
        if pushed is None:
            return None
        values = iter(reversed(pushed))
        return tuple(round(next(values), 2) if c == 2 else 0.0 for c in codes)
    return None


def pushed_numbers(data, end, count):
    """The count numbers pushed just before end, in push order, or None."""
    # each push is 1 to 9 bytes long (with alignment): decode forward from each possible start
    for start in range(max(0, end - 11 * count), end):
        values, o = [], start
        while o < end:
            op = data[o]
            o += 1
            if op == OP_GET_ZERO:
                values.append(0.0)
            elif op in (OP_GET_BYTE, OP_GET_NEG_BYTE):
                values.append(float(data[o]) * (-1 if op == OP_GET_NEG_BYTE else 1))
                o += 1
            elif op in (OP_GET_USHORT, OP_GET_NEG_USHORT):
                o += o & 1
                values.append(float(struct.unpack_from("<H", data, o)[0]) * (-1 if op == OP_GET_NEG_USHORT else 1))
                o += 2
            elif op in (OP_GET_INT, OP_GET_FLOAT):
                o = (o + 3) & ~3
                values.append(float(struct.unpack_from("<i" if op == OP_GET_INT else "<f", data, o)[0]))
                o += 4
            else:
                break
        if o == end and len(values) == count:
            return values
    return None


def pushed_vector(data, end):
    """The constant vector built just before end (a GetString's opcode), or None."""
    if data[end - 1] != OP_VECTOR:
        return simple_vector(data, end)
    values = pushed_numbers(data, end - 1, 3)
    return tuple(round(v, 2) for v in reversed(values)) if values else None


def read_createfx(path):
    """[{"id", "origin", "angles", "exploder"}] of every effect the createfx script places, in script order (angles
    None where the script sets none or this file cannot read them)."""
    data = open(path, "rb").read()
    if data[:8] != GSC_MAGIC:
        raise ValueError(f"{path}: not a T6 GSC script")
    imports = {}
    p, count = struct.unpack_from("<I", data, 32)[0], struct.unpack_from("<H", data, 54)[0]
    for _ in range(count):
        name, _ns, uses, _params, _flags = struct.unpack_from("<HHHBB", data, p)
        p += 8
        callee = data[name:data.index(b"\0", name)].decode("latin-1")
        for a in struct.unpack_from(f"<{uses}I", data, p):
            imports[a] = callee
        p += 4 * uses
    calls = sorted(imports.items())
    effects, current = [], None
    for offset, text, kind in string_refs(data):
        # a create call's first argument is the effect id: the string literal pushed just before the call
        call = next((c for a, c in calls if offset < a <= offset + 8), None) if kind == 0 else None
        if call in CREATE_CALLS:
            current = {"id": text, "origin": None, "angles": None, "exploder": call == "createexploder"}
            effects.append(current)
        elif text == "origin" and current is not None and current["origin"] is None:
            # GetString "origin" is the opcode byte before offset (plus a pad byte when it fell on an odd address)
            op = offset - 1 if data[offset - 1] == 0x0A else offset - 2
            current["origin"] = pushed_vector(data, op)
        elif text == "angles" and current is not None and current["angles"] is None:
            op = offset - 1 if data[offset - 1] == 0x0A else offset - 2
            current["angles"] = pushed_vector(data, op)
    missing = [e["id"] for e in effects if e["origin"] is None]
    if missing:
        raise ValueError(f"{path}: no origin read for {len(missing)} effects ({', '.join(sorted(set(missing))[:5])})")
    return effects


def fx_edits(effects):
    """MapKit "fx" edits for the effects with a BO1 equivalent, and the BO2 ids left out (with their counts)."""
    edits, left = [], {}
    for e in effects:
        bo1 = EFFECTS.get(e["id"])
        if bo1 and (not e["exploder"] or e["id"] in EXPLODERS_KEPT):
            edit = {"kind": "fx", "fx": bo1, "origin": list(e["origin"]), "from": e["id"]}
            if bo1 in ORIENTED and e["angles"]:
                edit["angles"] = list(e["angles"])
            edits.append(edit)
        else:
            left[e["id"]] = left.get(e["id"], 0) + 1
    return edits, left


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("script", help="the map's compiled clientscripts/mp/createfx/<map>_fx.csc")
    parser.add_argument("--all", action="store_true", help="also list every BO2 effect id the script places")
    args = parser.parse_args(argv)
    effects = read_createfx(args.script)
    edits, left = fx_edits(effects)
    print(f"{len(effects)} placed effects, {len(edits)} with a BO1 equivalent")
    for name in sorted({e["fx"] for e in edits}):
        print(f"fx,{name}")
    if args.all:
        for name, n in sorted(left.items()):
            print(f"  left out: {name} x{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
