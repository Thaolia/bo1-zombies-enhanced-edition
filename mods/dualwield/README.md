# dualwield - dual-wield weapons after Pack-a-Punch (NOT part of the original game)

A mod folder, kept apart from the base game. On every zombie map that has them, Pack-a-Punch turns:

- the Ray Gun into two Ray Guns ("Porter's X2 Ray Guns", `dw_ray_gun_upgraded_zm`);
- the Thundergun into two Thunderguns ("Zeus and Hera", `dw_thundergun_upgraded_zm`), whose shots blow zombies away
  as the Thundergun's do;
- with the archive build only, the PPSh-41 into two PPSh ("The Grim Reapers", `dw_ppsh_upgraded_zm`), and the PPSh-41
  (`dw_ppsh_zm`) joins the box.

This folder ships only the scripts: you build `mod.ff` from your own game, in one of two ways.

- **From your game alone** (`--retail`): the Ray Gun and Thundergun pairs, made from the retail zones
  `common_zombie` and `zombie_theater`. Nothing else is needed.
- **From the "Relaxing Dual Wield" archive** (`--archive`): the weapons of that mod for Call of the Dead (2015,
  `zm_relaxing_dual_wield.rar`, found at
  `https://www.mediafire.com/file/qz3826bx7kdok5q/zm_relaxing_dual_wield.rar/file`), PPSh included, with its own
  reload animations for the Ray Guns. That mod replaces Call of the Dead's `zombie_coast_patch.ff` and gives its
  weapons other weapons' names (the M1911 becomes the PPSh, the M72 LAW the Thundergun). Here they keep names of their
  own, nothing retail is replaced, and they work on every map.

## Build mod.ff

Needs OAT's Unlinker and Linker built as in `tools/bo2/oat/README.md` (the `ImageLoaderExternalT5.patch` matters),
and your Black Ops install (only read); the archive build also needs `bsdtar`:

    tools/dualwield/dualwield_mod.py --retail --game <BO1 install> --work /tmp/dualwield --out /tmp/dualwield/out
    tools/dualwield/dualwield_mod.py --archive zm_relaxing_dual_wield.rar --game <BO1 install> \
        --work /tmp/dualwield --out /tmp/dualwield/out
    build/ffconv/ffconv.exe --verify /tmp/dualwield/out/mod.ff <game folder>/mods/dualwield/mod.ff
    cp /tmp/dualwield/out/images/*.iwi <game folder>/mods/dualwield/images/

`ffconv --verify` must say that narrowing the zone gives the 32-bit body back. Both builds make the same weapon names,
so the scripts, the launchers' options and `make_dist.sh --dualwield` take either.

### From your game alone

Each gun of a pair is the retail upgraded weapon (`ray_gun_upgraded_zm`, `thundergun_upgraded_zm`: damage, ammo, clip,
sounds, effects) held as a retail pair holds its gun. It takes that pair's animations, view offsets and dual-wield
fields: the Mustang & Sally's (`m1911_upgraded_zm`, `m1911lh_upgraded_zm`) for the Ray Guns, and the Typhoid & Mary's
(`hs10_upgraded_zm`, `hs10lh_upgraded_zm`) for the Thunderguns. Its model is a copy of the retail one, rewritten by
`tools/dualwield/glbfit.py`:

- the mesh is moved so its grip sits in the hand, where the 2015 mod put its copies; the Thundergun is also scaled to
  0.63 so that it fits one hand;
- the left gun's bones take BO1's left-hand suffix (`j_gun1`, `tag_flash1`, as `t5_weapon_cz75_dw_lh_viewmodel`), so
  that the pair's animations move each gun by its own bones.

The new zone only references what the retail zones loaded on every zombie map hold (each one's asset list is an
`ignore` of the Linker project). It carries the new models, plus the Thundergun's materials and hands, which are in
Kino's zone only. Their images are in the retail iwds, so `images/` stays empty. Both hands reload with the retail
pair's animation (a pistol's for the Ray Guns), and there is no PPSh.

### From the archive

The script unlinks the archive's zone, keeps the seven weapons (PPSh, then the three pairs, right and left hand),
renames them, and links them against the retail `code_post_gfx`, `common`, `common_zombie` and
`common_zombie_patch`. It changes three things from the mod:

- **Effects.** OAT cannot unlink BO1 effects, so an effect the retail zones lack becomes a close retail one: the
  PPSh's flashes become the SMG flashes, the Thundergun pair's flashes the upgraded shotgun flash (the Thundergun's own
  are in Kino's and Ascension's zones only). The Thundergun's smoke cloud is the script's, as before.
- **Ammo.** The Ray Gun and Thundergun pairs count their ammo as BO1's own pairs do (the right gun in clips, the left
  gun in rounds): 11 clips of 40 and 13 clips of 4, the same supply as the mod's.
- **Names** are `dw_*` instead of the retail names the mod reused.

The images (the mod's own: its iwd's and those its zone embedded) go next to `mod.ff`: BO1 draws the pixels a
`mod.ff` embeds black.

The `--retail` build makes the same effect and ammo changes.

## Start it

`+set fs_mods dualwield`, with the line's other mods (`+set fs_mods zinfo bo2weapons dualwield`). The engine loads the
`mod.ff` of every stacked mod: the first as zone `mod`, the next ones as `mod_<name>` (`DB_ListModZones`,
`src/database/db_registry.cpp`), so this mod stacks with `bo2weapons`. ZmClient (Solo, Serveur local and Rejoindre
rows "Armes doublées (Pack-a-Punch)"), ZmAdmin (local server launch) and the Switch menu ("Armes doublees", start kit
screen for a solo game, server screen to join) offer it when `mods/dualwield/mod.ff` is there.

Dvars, read when the map loads:

- `dualwield_pap` (default 1): Pack-a-Punch gives the Ray Gun and Thundergun pairs;
- `dualwield_ppsh` (default 1): the PPSh-41 is in the box, and Pack-a-Punch gives the PPSh pair.

`games_mp.log` says what it did: `dualwield: dw_ppsh_zm in the box`, `dualwield: ray_gun_zm -> dw_ray_gun_upgraded_zm`
(and the Thundergun's on Kino and Ascension). Without `mod.ff` each weapon is skipped (`... not loaded, skipped`) and
the map stays retail.

A player who joins a server that has the weapons loads the same `mod.ff`, or the game goes back to the menu when it
enters ("The server uses weapon ..., which this game does not have").

## What to know

- Right after the Pack-a-Punch hands it over, the left gun has an empty clip and reloads by itself a few seconds
  later, as BO1's own dual CZ75 does (sooner, its reload is shorter).
- With the archive build, the PPSh and the pairs keep the mod's other values (damage, fire rate, clip sizes, models,
  animations, sounds). With the retail build, `dualwield_ppsh` finds no PPSh and the log says so
  (`dw_ppsh_zm not loaded, skipped`).
- The Thundergun pair only exists on maps that have the Thundergun (Kino der Toten, Ascension).
- Checked on Windows x64:
  - archive build (Kino, with and without `bo2weapons`): the box line, the three pairs drawn in both hands, the
    Pack-a-Punch's give (`GiveWeapon` + `GiveStartAmmo`: both clips full a few seconds later), Thundergun pair shots
    killing zombies, the main menu with both mods; on Linux, the same give;
  - retail build: both pairs drawn in both hands and firing on Kino, the Ray Gun pair on Five.

  Not yet: the Switch in play, and the Pack-a-Punch machine used in play.
