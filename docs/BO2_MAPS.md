# Black Ops II zombies maps in this BO1 port: feasibility (2026-11-09)

Question (the user): can the BO2 zombies maps of a Steam install (`Call of Duty Black Ops II\zone\all`) be brought
into this BO1, with MapKit for example? Answer so far: **the whole content of Nuketown Zombies (`zm_nuked`) can be
extracted; there is no official way to compile it into a BO1 map, so the import goes through MapKit**, which has to
learn real geometry (collision first, then drawing). Nothing of the game goes into this repository: extractions live
outside it (`~/bo2tools/` on the session's machine), as every other game file of this project.

## What a BO2 zone is

- `zone/all/*.ff` are **T6** fastfiles (header `TAff0100`, then `PHEEBs71`: Salsa20-encrypted and signed); textures
  of a map are in its `.ipak`. Asset formats, shaders (D3D11) and scripts (T6 GSC bytecode) all differ from T5: the
  engine cannot load them, and `ffconv` (T5 32-bit to 64-bit) does not apply.
- Zombies zones present: `zm_nuked` (Nuketown), `zm_transit` (+ its streamed `gump` zones), `zm_highrise`,
  `zm_prison`, `zm_buried`, `zm_tomb`, `common_zm`, and the `so_*` game-mode zones.

## Dead end: the BO1 Mod Tools

Steam's *Call of Duty: Black Ops Mod Tools* (app 42740, `steamapps\common\Call of Duty Black Ops 42740`, 3.1 GB) hold
`linker_pc`, `converter`, `asset_manager`, `AssetViewer`, `effectsed3`, the Maya export plugins and the retail map
sources (`map_source\zombie_*.map`), but **no Radiant and no map compiler** (`cod2map`, `cod2rad`): Treyarch never
released them for BO1. A BO1 map cannot be compiled from new geometry. Their `steam_launch_mods.cmd` also creates
junctions inside the retail game folder (and its `clean` mode deletes folders there): it is not used.

### Update (2026-11-12): the linker is stubbed, the engine's BSP loader is not

The Mod Tools' `raw/maps/` holds two compiled BO1 BSPs (`asset_viewer.d3dbsp`, `effectsEd_box.d3dbsp`: `IBSP`
version 43, a table of (lump id, size) pairs, the lumps 4-aligned after it) and `zone_source/` the retail zombie map
CSVs (`col_map_sp,maps/zombie_theater.d3dbsp`). But `linker_pc.exe` cannot build a map: its `Com_LoadBsp` (0x401940)
and `Path_LoadPathsInternal` only raise "Not allowed at this time!", so Treyarch shipped no way to make a BO1 map.

The decompiled engine still has the whole BSP loader (`com_bsp_load_obj.cpp`, `cm_load_obj.cpp`,
`r_bsp_load_obj.cpp`, `pathnode_load_obj.cpp`; lump ids in `com_bsp_load_obj.h`), used when `useFastFile` is 0. The
`bspworld` branch reads a map's render world from a BSP with fastfiles on: `+set bo1_bspworld maps/<name>.d3dbsp`
(`LoadWorld`, `cl_cgame_mp.cpp`) loads the BSP, its primary lights, water and burnable data into `comWorld`, builds the
`GfxWorld` from it on the main thread and unloads it. Its lightmap and probe textures and its world vertex buffer
are made on the render thread (`Image_Generate2D_OnRenderThread`, `Image_GenerateCube_OnRenderThread`,
`RB_Resource_LoadVertexBuffer`, each followed by `RB_Resource_Flush`): the zombies device is not
`D3DCREATE_MULTITHREADED` (`r_multithreaded_device 0`), and creating them from the main thread while the render
thread presented the loading screen froze the game now and then at "Loading nodes and leafs" (2026-11-13: Present
waited forever inside `d3d9.dll` holding `CRITSECT_DBHASH`, the main thread waited for that lock). With `asset_viewer.d3dbsp` on Kino every load step passes (materials, lights,
lightmaps, light grid, surfaces, cull groups, AABB trees, cells, portals, nodes, entities, probes; version 43 probes
are widened to the version 45 layout) and the game starts; it then stops on Kino's brush model `*8`, which the test
BSP does not have.

`+set bo1_bspworld 1` now reads a whole map's world from its own `maps/<map>.d3dbsp` when it has one (the front end
and the retail maps keep their zones): the server's spawn and a remote client load the BSP for the collision
(`CM_LoadMapFromBsp`, static models, dynamic entities, the entity string), the lights and the path nodes
(`Com_WorldFromBsp()` replaces `useFastFile` at those switches), the client's `LoadWorld` for the render world. The
map's zone still brings its scripts: `zombie_bsptest` (a `zombie_` name, so an SP zombies level) is a 1 KB zone of one
rawfile, `maps/zombie_bsptest.gsc` (`maps\_callbacksetup::SetupCallbacks()`, `maps\_zombiemode_load::main()`),
built by the Mod Tools' `linker_pc` (it builds zones fine, only not maps) and widened by `ffconv`. With
`asset_viewer.d3dbsp` as `maps/zombie_bsptest.d3dbsp` the map runs for the whole test minute, the player walks on its
floor (x 0 to 581, y 0 to 464, eye height kept) and a drop from z 400 lands on the collision; Kino is unchanged with or
without the dvar.

The load-obj paths had never run in the 64-bit port; they held the usual 32-bit sizes: `cbrushside_t` (12) and
`cbrush_t` (96) in `CMod_LoadBrushes`, `cLeafBrushNode_s` (20) as the base of the leaf brush tree, `DynEntityDef` (84,
which then overwrote the collision nodes with its 511 constraint sentinels), five `GfxTexture` arrays (4 per lightmap
or probe), and two Hex-Rays-split stack buffers (`className[7]` + 61 bytes in `DynEnt_LoadEntities`, `char nptr` + 3
bytes taking 2048-byte values in the world parameters) that GCC placed apart. `LoadRopeParams` also kept a script
string reference on every targetname (SL_CheckLeaks at quit): they are released with the collision.

### A BSP of our own (2026-11-12)

`tools/bo2/d3dbsp.py` writes a world BSP without Radiant or cod2map, in the Mod Tools' version 43 layout. It is a
library (`Bsp`: `add_material`, `add_brush`, `add_mesh`, `add_entity`, `write`) and `d3dbsp.py room OUT.d3dbsp`
writes a test room: a 2 048-unit floor, four 512-unit walls and a sky box. What it writes, and why that is enough:

| Part | Written | The loader then |
|---|---|---|
| Collision | axial brushes (six bound sides, no plane sides), their 8 corners; one node splitting the world in z, two leaves listing the brushes that reach into them | builds its own brush trees inside each leaf (`CMod_LoadLeafBrushNodes`) |
| Render surfaces | one triangle soup per material and mesh piece (16-bit counts), clockwise front faces (front normal = `(c - a) x (b - a)`, checked on `asset_viewer`), planar UVs, tangent/binormal as the compiler writes them | sorts them, builds the static surface data |
| Visibility | one cell holding every surface (one AABB tree), no portals, every leaf in cell 0 | draws everything from everywhere (the render tree collapses to the cell) |
| Lightmaps | lightmap index 0 on lit surfaces, 31 on the sky, no `LIGHTBYTES` lump | fills the one lightmap with white ("No Lightmap found"); a lit world material refuses a surface without one (`Com_ERROR: ... doesn't have a lightmap`) |
| Light grid | an empty grid (one row, no entries, no colours) | `R_InitEmptyLightGrid` |
| Lights | primary light 0 empty, 1 the sun from the worldspawn's `sundirection`; light regions present, 0 hulls each | |
| Probes, water, burnable | none, empty headers | adds its dummy probe |
| Brush edges | none | only the compiler uses them |

The surfaces take retail BO1 world materials, and the map's zone must hold them: `material,wc/<name>` lines in its
zone source, which `linker_pc` builds from the Mod Tools' `raw/materials/` with the images copied from the player's
own `.iwd` files into the tool copy's `raw/images/` (never into the repository). The test room uses
`eb_art_floor_concrete_tile_dirty`, `cub_art_plaster_white_brick` and `sky_day`.

Lit world materials reached two more 32-bit sizes: `GfxShadowGeometry` (12 bytes, 24 on x64, crash in
`R_AddShadowSurfaceToPrimaryLight`) and `GfxAabbTree` (40, 48 on x64, in the static model tree of
`r_staticmodel_load_obj.cpp`, whose children's offsets are signed and now read as such). `codediff` against the
32-bit build: both files identical.

The room, `+set bo1_bspworld 1 +devmap zombie_bsptest`, with a scripted walk (`bo1_clientCommands`: forward 8 s,
left 8 s, then a drop from z 300):

| Build | Positions | Picture |
|---|---|---|
| Linux x64 (GL, llvmpipe) | (0 0 60), (1008 0 60), (1008 1008 60): the walls stop the player at 1024 minus the player's radius | floor and walls textured |
| win64-msvc (D3D9, `headless.ps1 -Client`) | the same three | the same, brighter (the white lightmap) |
| Switch (deko3d, Ryujinx) | the same three; clean exit at `bo1_autoquit` | |

Still wrong, all lighting: the sky draws as a flat colour (orange in D3D9, blue or orange in GL), and the view model is
cyan (the empty light grid lights models with nothing). They wait for the lighting step (a real light grid, lightmaps
baked from BO2's).

### Nuketown's world as a native map (2026-11-12)

`tools/bo2/bo2_bsp.py <dump> zm_nuked --templates <BO1 wc/ materials> --out <folder>` turns OAT's dump of `zm_nuked`
into `zombie_bo2nuked`: a world BSP and an OAT Linker (T5) project for its zone.

| Part | From BO2 | In BO1 |
|---|---|---|
| Render world | the world OBJ: 130 683 triangles, 463 materials (`caulk`, `nodraw` and shadow materials left out) | one surface per material, the OBJ's winding as is (front `(c - a) x (b - a)`: 87 % of the play area's near-horizontal area faces up) |
| Materials | each material's colour map and its blend state (`bo2_mesh.py`'s `blend_flags`) | `wc/bo2w_<name>`: a copy of a BO1 world material from `zombie_theater` (OAT's Unlinker), with the colour map swapped: `global_white` (`wc_l_sm_r0c0`) for opaque, `mtl_theater_poster_1` (`wc_l_sm_t0c0x0`) alpha-tested, `decal_glue` (`wc_l_sm_b0c0x0`) for decals and glass. 109 colour maps as external `.iwi` (`main/images/`, 28 MB); the techniquesets come with the zone (Linker `-l zombie_theater.ff`) |
| Collision brushes | the clipMap's 7 357 world brushes with their 33 971 non-axial sides | the same brushes, corners computed; one BSP material per (contents, surface flags) pair |
| Terrain | 24 359 collision triangles | BO1's own collision triangles, one per partition |
| Tree | | a k-d tree over brushes and partitions: 3 786 leaves |
| Entities | the worldspawn's sun, the player start | the same; gameplay entities wait for the gameplay step |

The zone (`zombie_bo2nuked.ff`, 70 KB: 463 materials, 109 image headers, 3 techniquesets, the level script) is linked by
OAT's Linker, converted by `ffconv --verify` like any zone, and loaded from `usermaps/zombie_bo2nuked/`. Treyarch's
linker always adds an empty rawfile named after the zone, its build report, which `G_PrintFastFileErrors` asserts on:
the project adds it.

Formats and limits met on the way:
- **Planes are 16-bit** (`CMod_LoadPlanes`: 65 536 at most). Terrain as 16-unit prisms, as MapKit's import does it,
  needs five planes per triangle: 120 000. The terrain is BO1's own collision triangles instead.
- **Brushes are 16-bit too** (`cm.numBrushes`): the props' collision (`bo2_props_collision.py`, step 3) does not fit
  as brushes. It will need the props as collision triangles or as models.
- **A partition is a convex hull for the physics.** Player and actor movement runs through the physics
  (`gjk_partition_t`, `phys_colgeom.cpp`), which collides with a partition as the convex hull of its vertices. With 32
  triangles per partition the player stood in the air over the street, inside the hulls. With one triangle per
  partition every drop lands on BO2's ground: (0, 0) at -43 (render ground -43), (0, -376) at -66 (-65), (-600, 150)
  at -54 (-57), (-300, -700) at -60 (-60), and (600, -600) on a solid low wall at 34.
- **A leaf's first collision AABB is 16-bit.** 76 368 references to partitions do not fit, so each leaf gets one root
  per collision material (they come first in the lump), with the leaf's partitions as children.
- **The world lives in the hunk** when it comes from a BSP. With `bo1_bspworld` set the hunk is 64 MB instead of
  15 MB. Nuketown used 27.4 MB (26.6 on the Switch), logged as `bspworld: hunk ... MB used after the render world`.

Verified, `+set bo1_bspworld 1 +devmap zombie_bo2nuked`, the drops above on each build:

| Build | Result |
|---|---|
| Linux x64 (GL, llvmpipe) | the five drops; screenshots at the player start and down the street: houses, garages, the shelter at the end, the backdrop |
| win64-msvc (D3D9, `headless.ps1 -Client`) | the same positions; the same views, brighter (the white lightmap) |
| Switch (deko3d, Ryujinx) | the same positions to a tenth of a unit; clean exit at `bo1_autoquit` (88 s). Some earlier runs took minutes to close after `CL_Shutdown` (Kino too, and this morning's NRO 3 min 40), two of them beside a Windows build; the idle reruns closed at once: not the map |
| win32-msvc | builds |

Build it (paths of this machine; the output is the player's own game data, kept out of the repository):

    U=~/bo2tools/oat-src/build/bin/Release_x64/Unlinker; L=~/bo2tools/oat-src/build/bin/Release_x64/Linker
    B="<BO1 install>/zone/Common"; D=~/bo2tools/dump
    $U --include-assets material -o $D/bo1wmat/?zone? "$B/zombie_theater.ff"     # the BO1 templates, once
    tools/bo2/bo2_bsp.py $D/zm_nuked zm_nuked --templates $D/bo1wmat/zombie_theater/materials/wc --out $OUT
    cd $OUT/linker && $L -b . -l "$B/code_post_gfx.ff" -l "$B/common.ff" -l "$B/common_zombie.ff" \
        -l "$B/zombie_theater.ff" zombie_bo2nuked                                   # zone_out/zombie_bo2nuked/
    ffconv --verify zombie_bo2nuked.ff <game>/usermaps/zombie_bo2nuked/zombie_bo2nuked.ff
    cp $OUT/zombie_bo2nuked.d3dbsp <game>/main/maps/; cp $OUT/images/*.iwi <game>/main/images/

The packages carry the colour maps of every native map as one IWD instead of loose files (2026-11-18, asked by the
user): `make_dist.sh --bo2` packs `DIR/main/images/bo2_*.iwi` into `main/iw_bo2maps.iwd` (`tools/bo2/bo2_iwd.py`:
deflated, 1 292 images in 214 MB against 283 MB, sorted with fixed dates so the same images give the same bytes)
and removes the loose ones an older package holds. In `main/` the engine opens only an IWD whose name starts with
`iw_` (`com_files.cpp`, "Invalid IWD"). Loose files still load, which a run folder for development keeps. Windows
client, native Nuketown, the loose images moved away: `main/iw_bo2maps.iwd (1292 files)` in the search path, the
garage view the same as from loose files but for the effects' flicker (377 pixels). A Switch's SD card that held an
older package keeps its `main/images/bo2_*.iwi`: delete them (both load the same pictures, but the copy is longer).

The props, the gameplay and the lighting followed (next section).

### Props, gameplay and lighting on the native world (2026-11-12)

**Props** (`bo2_bsp.py --models <dump>`, `tools/bo2/bo2_bsp_props.py`). The Unlinker dumps the zone's xmodels again
with `--model-format GLTF` (`$U --include-assets xmodel,material --model-format GLTF -o $D/nukedgltf/?zone?
zm_nuked.ff`). Each of the 332 placed xmodels becomes a BO1 xmodel of the same LODs, its 222 materials copies of
BO1 model templates from `zombie_theater` (`mtl_dest_glo_paper_01`, `mtl_filament`, `mtl_theater_paper_scrawl`:
colour map only; BO2's blended rock techsets name theirs `Micro_1_ColorMap`). Each of the 2 082 placements is a
`misc_model`, which the engine draws as a static model, culled and with its LODs. The engine gives a static model
collision only from its xmodel's collision surfaces, which OAT's Linker does not build. The props collide through the
BSP instead, as `bo2_props_collision.py` makes them collide for MapKit:
- 721 box-like props are oriented box brushes;
- the 113 rock and rubble piles are 949 brushes, one per rock (a connected piece of the collision LOD): its bounds
  with the four upper corners cut off; stones under 16 units are stepped over. As triangles, Nuketown's 99 rubble
  clumps alone took 67 000 of the 65 536 collision vertices (16-bit indices), and the school bus, the clock tower and
  the overhanging roof, last in line, fell back to boxes: a 465-unit box stood in the street. A pile's convex hull
  fills the hollows between its rocks (a ring of rocks around a mystery box swallowed the box: the box was paid for
  and its weapon could not be taken), and a hull per rock would cost a plane per face (65 536 planes at most) for
  some 4 500 rocks, where a box side costs none: 23 944 planes in all;
- the 108 other larger meshes become 18 862 collision triangles (the terrain takes 15 864 vertices; any mesh past
  the budget would become a box).

OAT's T5 xmodel loader set `lodInfo[i].lod` for IW4/IW5 only, and BO1's static model cache asserts on it:
`tools/bo2/oat/XModelLodT5.patch`.

**Gameplay** (step 4). MapKit's `bo2_zm_nuked` layout already plays Nuketown: zones, spawns, the 36 risers, BO2's 703
nodes and their 5 254 links, the traversals, the wall buys, the doors and debris, the box, the perks and
Pack-a-Punch. It now runs on the BSP world instead of its own mesh and collision:

    +set fs_game mods/mapkit +set fs_mods mapkit +set bo1_mod_mapkit bo2_zm_nuked_bsp \
    +set bo1_mod_zones zombie_bo2nuked +set bo1_bspworld maps/zombie_bo2nuked.d3dbsp +devmap zombie_pentagon

- `bo2_bsp.py --layout <bo2_zm_nuked.json>` leaves out the brushes inside the layout's cut boxes (the clips at the
  machine spots: 20 brushes) and writes `bo2_zm_nuked_bsp.json`, the layout without its `collision` and `mesh` edits.
  Without more, the doors and debris lose their BO2 props with the mesh, and each blocker shows MapKit's box: a plain
  brown block where a door, a couch or the truck's furniture stood (the user's screenshots, 2026-11-13).
  `bo2_mesh.py --blockers-only` writes `zm_nuked.blockers.mesh.bin`, the blockers' props alone (15 props of 5 models:
  doors, couches, armoires, chairs; no world chunk, no placed prop, no sky), and `bo2_bsp.py --blocker-mesh
  imports/zm_nuked/zm_nuked.blockers.mesh.bin` gives the BSP layout a `mesh` edit of that file and keeps the blockers'
  `meshGroup`: MapKit draws BO2's doors and furniture until the purchase, as on its own mesh, and the box only collides.
  `--layout-only` writes that layout without rebuilding the BSP (the same file as a full run). Checked on Windows with
  the test client: house 2's white door drawn in the doorway (the props there take the BSP's warm model light, as the
  hedges beside it do), and gone with `mapkit_open_all 1`.
- `CM_Mapkit_Empty()` meant two things: "the layout supplies the level script, entities and pathnodes" and "there is
  no world". `CM_Mapkit_WorldEmpty()` is the second one, false when the world comes from a BSP. The render, static
  model, collision, physics, PVS, sky and model lighting switches use it.
- A `bo1_mod_zones` zone found nowhere else is read from `usermaps/<zone>/<zone>.ff` (`DB_ModXFileHandle`).
- The server waits for the zones before it reads a BSP world. Queued just before, the extra zone was still loading
  while the static models looked up its xmodels, and the level zone linked its clipMap over the world being built:
  `cm.numStaticModels` became Five's 5 395 in the middle of the BSP's 2 082.
- A layout's pathnodes hold user-1 string references (`SL_GetString`, `g_mapkit_path.cpp`), as on a zone world:
  `Path_Shutdown` and `Scr_FreePathnode` now treat them so. Freeing them as a BSP world's own nodes asserted at quit.
- The layout's nodes keep their links: on a BSP world `Path_InitPaths` read them again from the BSP
  (`Path_LoadPaths`), found no `LUMP_PATHCONNECTIONS` in ours and erased every link (`Path_ErasePaths`). Zombies then
  could not find a path and the MapKit self-test's client stood still. It now skips that read on a MapKit empty base.
  The self-test's door check treats a layout on a BSP world as an imported map (doorway links, not zone links).
- The layout's nodes survive a restart (2026-11-13). On a BSP world `Path_Shutdown` (`Path_ShutdownStatic`) and
  `Path_Init(restart)` set the node count to 0, since retail rebuilds the nodes from the entity string. The layout's
  nodes are appended on the first load only, so after a game over (`loadgame_continue` -> fast restart)
  `actualNodeCount` stayed 0. The kd tree still found layout nodes, and the first zombie A* asserted
  (`pathnode.cpp(1961)`, "705 not in [0, 0)"). This happened on every death on native Nuketown: 4 runs out of 4 with
  the headless client, which has no god mode. `G_Mapkit_RestorePathnodeCount`, called right after `Path_Init` on a
  restart, gives the count back: 4 runs out of 4 clean, two of them with a second game over (the zombies reached the
  player again).
- MapKit's self-test (`+set mapkit_selftest 1` with the test client, Linux headless, timescale 4) passes 106 of 106
  checks on the BSP world, as on the MapKit mesh: every door and debris (their doorway links cut, then given back),
  the four perks, the seven wall buys, the box, Pack-a-Punch, the ten zones, and a zombie out of each of the 36 risers
  reaching the player.
- `bo1_bspworld <path>` gives that BSP to the level only, never to the front end (`frontend`, `menu_*`). The console
  boots through the front end before its `+devmap`, which then read Nuketown's BSP without Nuketown's zone:
  `R_CheckValidStaticModel: could not find xmodel 'default_static_model'` on Ryujinx. A `+devmap` from the command
  line, as on Linux and Windows, skips the front end.
- On the Switch, `GetCommandLineA` read `/proc/self/cmdline`, which the console does not have: the command line was
  empty, so `bo1_mod_zones` never raised the asset pools, the asset entries, the physical memory or the streamed image
  parts there (Nuketown's 333 xmodels: "Exceeded limit of 1000 'xmodel' assets"). It now returns `launch.cfg`'s
  arguments, which `switch_main` hands over before `WinMain`; `DB_InitXAssets` sets the streamed image parts with
  the pools, since `r_stream.cpp`'s static initialiser runs before `launch.cfg` is read.
- `PickAabbSplitPlane` (`universal/aabbtree.cpp`) never returned: its sweep ends when the next distance reaches
  `FLT_MAX`, which the decompiled code compared with the double literal `3.4028235e38`, slightly above it. Only a world
  read from a BSP builds that tree (`R_GenerateHighmipAabbs`), and Five's high-mip images gave it 34 static models.

**Lighting** (step 5).
- The world surfaces are cut into 1 024-unit cells per material and lightmap (2 130 surfaces) under an AABB tree, so
  that the renderer culls them. The tree needed a split it could make, and culling is worth having on the console.
- Lightmaps (`tools/bo2/bo2_bsp_light.py`): each of BO2's three lightmaps becomes one 512 x 512 BO1 lightmap with
  the same coordinates. Every texel a world triangle covers is baked again with BO2's model (`bo2_worldlight.py`:
  its lightmap slices, the sun's visibility or the triangle's lamp, with the triangle's normal), then divided by the
  light of the sunlit ground. The sunlit ground thus keeps its colour map, as MapKit's vertex colours do. The whole
  light goes into the first half of BO1's lightmap; the second half and the sun visibility stay 0, since BO2's sun is
  already in it. A fourth, white lightmap serves the lit surfaces BO2 drew without one.
- Models: a world without a light grid now takes MapKit's flat ground lighting. The empty grid lit every model with
  one stray colour (cyan). That flat grey plus BO1's sun drew Nuketown's props nearly white in D3D9.
- The light grid (`bo2_bsp_light.light_grid`, written by `d3dbsp.set_light_grid` as the version 43 loader reads it):
  a point every 32 units across and 64 up over the zones plus 1 024 units (199 x 123 x 25 on Nuketown, 2 078
  colours). Each point takes BO2's light of the floor under it without the sun (the lightmap's first slice plus half
  its directional second slice) over the same reference as the lightmaps, at least the mean of the floors 64 units
  around it (a bus or a rock lit from the floor its own shadow darkens came out black) and at least 0.12; the sun
  primary light where most of those floors see BO2's sun. BO1's sun takes BO2's sun colour over the reference
  (0.56, 0.73, 0.75), so sunlit ground and a model facing the sun match.
- The lamps: BO2's 16 spots and cube-lit lamps (`<map>.d3dbsp.lights.csv`) are the BSP's primary lights 2 to 17
  (`bo2_bsp_light.add_lamps`, `d3dbsp.add_primary_light`: spots stay spots, the lamps become omni lights, colours
  over the reference's luminance (see "Model light" below), no shadow map, `white_light` as Kino's spots, read from its zone). The lightmaps already hold
  their light; a light grid point takes the primary light of its floor in BO2 (the sun or a lamp) when that light
  reaches it, by majority over the floors around it: 1 255 points sit under a lamp, the houses' and the garage's.
  The BSP then has no light regions: with them (`hasLightRegions`), the engine replaces a grid entry's lamp by the
  caller's nearest light (`R_GetLightingAtPoint`).
- The sky: BO2's sky model (`skybox_dlc0_zm_nuketown`) is the worldspawn's `skyboxmodel`, which BO1 draws around the
  viewer, its material a copy of `zombie_theater`'s `mtl_skybox_zombie_theater` (`mc_sky_cubemap_hdr`) with BO2's
  cube map, BO2's `skyBoxRotationSize` and a brightness (`cloudsHeights.z`) of 0.5 (2026-11-13). BO1's vertex
  shader samples the cube map at the view direction turned by the constant's x, y, z, and through the origin when its
  w (the size) is negative: Kino's sky is authored that way (w -8000), so with Kino's constant BO2's cube map hung
  upside down, its grey, grainy ground overhead (the user's screenshots). BO2's constant (w 8000) keeps the sky up.
  Kino's brightness, 4, then clipped 89 % of the sky to white (the engine's sky multiplier on a BSP world is far
  above Five's, where the MapKit mesh shows the same cube map unclipped); 0.5 gives a blue sky with dark clouds and
  no clipped pixel (mean grey 142 looking up from the street).
- Model light (2026-11-13): props drew orange near the houses (a white door 104, 68, 49; the hedges brown). The light
  grid's floor light without the sun is mostly light bounced off the orange ground, and over the reference (BO2's blue
  sunlit ground) it came out 1.8 times more red than blue; the lamps, over the reference channel by channel too,
  became up to 28 times more red than blue. The grid's colours are now grey at their luminance
  (`AMBIENT_SATURATION` 0) and the lamps' colours go over the reference's luminance (they light the models only:
  the lightmaps hold their light already), so a lamp keeps BO2's own colour. The same door: 80, 71, 60 (the warm
  lamp beside it); the hedges keep their texture's red/green ratio (1.13, 1.11 on the MapKit mesh, which draws them
  unlit).
- The hunk is 112 MB with `bo1_bspworld` (96 MB until TranZit): 45.9 MB for the world with its props, plus 37.7 MB of
  temporary memory while the lightmaps load (one merged 2 048 x 2 048 group). The `bspworld: hunk` line gives the
  use after the render world, the most in use at once (temporary memory included) and the size: 36.5, 58.1 and 112
  MB on Nuketown since the light grid is sparse.

### TranZit's world as a native map (2026-11-14, started)

`zm_transit` goes through the same tools as Nuketown, as `zombie_bo2transit`, with the MapKit layout
`bo2_zm_transit_bsp` (the classic gameplay of `bo2_zm_transit`: zones, doors, perks, power, box, bus) on its world.
TranZit is three times Nuketown: 380 024 world triangles in 6 532 surfaces, 20 597 brushes, 69 680 terrain
triangles, 10 835 placed props of 509 models, 140 lamps, 26 000 x 18 000 units. What it needed:

- **The light grid is sparse.** Over TranZit's zones the dense grid was 857 x 611 x 51 points: 20 million, and its
  primary-light vote (one array per lamp, 143 of them) went past 10 GB, so `bo2_bsp.py` was killed. The grid is now
  written as the compiler writes them (`d3dbsp.set_light_grid`, `R_GetLightGridSampleEntryQuad`): per row, blocks of
  8 columns, each from its lowest floor to 192 units over its highest, a block without a floor holding no point
  (the engine extrapolates there, as on a retail map); a row without a point is 0xFFFF in the header. It is built in
  slabs of 32 rows. TranZit: 1 934 076 points, 68 s and 1 GB for the whole world. `tests/bo2/test_d3dbsp_lightgrid.py`
  looks every point up as the engine does. Nuketown's grid went from 611 925 points to 141 485: 141 152 of them
  give the same entry as before, 333 differ by at most 0.08 (columns at the edge of the zones), the 470 440 others
  were points far over every floor.
- **Surfaces are cut into 1 024-unit cells over the zones** (and 2 048 units around them), not in a square around the
  origin: TranZit's play area runs to 13 000 units from it. Nuketown: 2 133 surfaces instead of 2 130.
- **The props' collision does not fit in the BSP.** Collision vertices are 16-bit (`cm.triIndices`) and TranZit's
  terrain takes 46 333 of the 65 536, all of them inside the zones. Its boxes (2 133) and rocks (851 brushes) stay
  brushes, its meshes take the vertices left (714 meshes, 25 160 triangles), and with `--props-collision
  imports/zm_transit/zm_transit.props.collision.bin` the 1 028 meshes past them go to a BO2COL2 file of prism
  brushes (434 168, as MapKit's import makes them), which the BSP layout loads with a `collision` edit: MapKit's
  import joins every trace and the physics on a BSP world too. Without it they were boxes.
- **The bridge and the bus.** BO2's brush models are not in the BSP: `bo2_mesh.py --blockers-only` now keeps the
  standing brush models (the two bridge sections) and the `--mover` models (the bus) with the blockers.
- **Models from the gump zones.** The xmodels are dumped as GLTF from `zm_transit.ff` and its eleven
  `zm_transit_gump_*` zones (tunnel included: its pipes, cones and debris), merged as for MapKit.
- **The image streamer's tables.** With `bo1_mod_zones` the material pool holds 6 144 entries and the xmodel pool
  2 000, but `r_stream.cpp` kept 4 096 and 1 000: TranZit's materials past 4 095 asserted ("materialIndex <
  MAX_MATERIAL_POOL_SIZE"), and an xmodel past 999 wrote its distance past `modelDistance` without a check. The
  tables now have the mod pools' sizes (`R_STREAM_MATERIAL_COUNT`, `R_STREAM_XMODEL_COUNT`, a `static_assert` in
  `db_registry.cpp` ties them), and `DB_GetXModelAtIndex` asserts against the pool, not 1 000.
- **The static model cache.** Some of TranZit's props are xmodels BO1's own zones hold (`p_glo_cinder_block`,
  `p_glo_electrical_pipes_short`), whose lods carry the cache indices Treyarch's linker gave them; a world read from
  a BSP assigns its own (`R_AssignSModelCacheResources`) and asserted on them (`smcIndexPlusOne == 0`). It now clears
  the indices of the lods it assigns.
- **Props missing faces (2026-11-17, a user's screenshot of Nuketown's garage).** The cache lays a lod's surfaces one
  after the other, each at its `baseTriIndex` / `baseVertIndex`. Treyarch's linker sums them (as
  `XModelReadSurfaces` does for a raw xmodel); OAT's T5 loader leaves every surface at 0. A BO2 prop of two surfaces
  then had its second one written over the first: `p6_zm_nuked_cardboard_box04` (a box of 12 triangles and labels of
  6) lost three sides to its labels. `R_SModelLodSetBaseIndices` gives each lod the cache takes its sums; a retail lod
  holds them already and is not written. Nuketown: 73 of its 214 cached lods rebased. Windows screenshots of the
  garage: the boxes whole, as with `r_smc_enable 0`.
- **Windows: Five's board models in the BSP.** MapKit's boarded window is the base map's own brush models (Five's
  `*7`..`*19`: boards, clip, repair boards, `MkE_Window`), which a BSP world did not have: the window entities got
  MapKit's own layout brush models at those indices (zone volumes), bounds thousands of units wide, which put 3 172 of
  the 5 350 pathnodes in solid and ended the load ("Max number of disconnected paths exceeded"). `d3dbsp` writes
  brush models now (`add_submodel`: their brushes and surfaces after the world's, outside its collision and surface
  trees; `R_SortSurfaces` sorts model 0's surfaces only), and `bo2_bsp.py --window-models` puts Five's `*1`..`*19` at
  the same indices, read from a JSON that `+set mapkit_dump_bmodels <file>` writes when a map loads
  (`r_mapkit_mesh.cpp`, a developer's tool, run once on Five; the JSON is the player's game data, kept out of the
  repository). Their surfaces take one of the map's materials (`--window-material`, a part of its name, default
  `wood_floor_planks_rustic`): with Five's own `wc/` materials (the BSP loader adds the `wc/` itself) the boards drew
  pure white, their specular taking the dummy reflection probe of a BSP of ours. Without `--window-models` the
  windows are `"open"` (no boards, no clip). 56 pathnodes in solid either way (115 on MapKit's own TranZit).
- **The props' own models.** A converted xmodel is named `bo2x_<name>`: TranZit places BO2 copies of BO1 models
  (`t5_foliage_tree_burnt03`, `p_glo_cinder_block`), and a zone asset named as one already loaded is dropped for it.
  BO2's vertex colours are left out of the models: they are data (a tree's wind weights, each channel over 0..1),
  which BO1's model shaders multiplied in: the burnt trees drew red, blue and violet.
- **The hunk** (above): 97.8 MB after the render world, at most 99.8 MB at once.

Checked on win64-msvc (D3D9, `headless.ps1 -Client`): the player spawns in the depot, which is drawn with its props
(chairs, the route map, Quick Revive, the bus behind the glass), the round starts, the bank vault's hole is boarded
with planks, the burnt trees, bushes and corn by the bank draw in their own colours, and the view over the depot's
yard shows the road, the cabin, the river, the lava and the rocks; the run quits cleanly (hunk 97.9 MB, at most
100.0). Nuketown's five drops land where they did (-43, -66, -54, 33, -60).
- **Self-test** (Linux headless, the commands of the MapKit maps with `bo1_bspworld` and the BSP layouts; TranZit with
  `bo1_mod_zones "zombie_bo2transit zombie_cosmodrome"` and `mapkit_test_risers riser1,riser9`). Nuketown native:
  `pass 105 fail 1` (riser4: its zombie was still on its way at 90 s; `pass 71 fail 0` when rerun with riser4 alone,
  which passes). TranZit native: `pass 179 fail 18`, then `166 / 31`: a round hung 11 and 22 minutes, and every window
  checked meanwhile saw no spawn. A zombie that took another entrance through the retail entrance logic (its
  `first_node` names that window, but it has no `mapkit_source_window`) was never culled by the window check and
  chased the teleported client from window to window across the map (the farm, the town, the depot, the forest)
  for the whole round. The window check now culls those too, as the unlock check did: `pass 187 fail 10`, rounds
  every one to three minutes, against `185 / 12` for MapKit's own TranZit. The last ten, then `pass 195 fail 0`:
  - Retail `zombie_think` sends a zombie to one of the three exterior goals closest to its spawner, at random; on
    TranZit the ground outside each barricade is a pocket of the node graph, so two of the three were often out of
    reach (bad paths, unfed windows). BO2's `spawn_location` names its barricade (`script_string`): `bo2_layout.py`
    writes it as the spawner's `"window"` and MapKit gives the spawner that window's goal as its target. The
    `find_flesh` ones become `"chaser": 1` (straight for the player).
  - BO2 hangs some of those spawners on a neighbouring zone (church_baricade1's on `zone_town_church`, 800 units
    away) and wakes them through its own zone adjacency, which MapKit does not import (its zones are adjacent only
    through doors). The spawner now belongs to the zone the window guards: the smallest zone box holding the point
    just inside it (the farmhouse's box lies inside the farm's), the same zone in `bo2_layout.py`, MapKit's window
    goal label and the self-test.
  - BO2's TranZit replaces the zombies far from every player. Without that, a round waited 24 minutes on zombies
    walking across the map or stuck there, and none spawned meanwhile. A layout whose zones span more than 10 000
    units gets a `"farrespawn"` edit (2 500 units): mods/admin's `zm_farrespawn` on by default, off while that dvar
    is set. Nuketown (4 600) gets none.
  - The self-test: the window and unlock checks cull risers and chasers too; chasers are no window's spawners; the
    client stands at the window's floor level (160 units in put it on a raised prop at the depot) and on what a
    player stands on (`PlayerPhysicsTrace`: a bullet passes through the power station's clip landing, the client
    fell into the pit under it and the zone manager woke its first zone, the bank, instead).
    `mapkit_test_windows <names>` checks only those windows.
  Nuketown native stays `106 / 0`. MapKit's TranZit (the same layout on its mesh) goes from `185 / 12` to `193 / 2`
  and `194 / 1`: each time one or two windows whose zombies came late (a spawn 80 s into the check; 21 zombies that
  tore bank_baricade3's boards and waited outside until the client left), a different one each run and each passing
  in the other runs.
- **The lava and the glow cards** (the MapKit mesh too, `bo2_mesh.py`). OAT's `.mtl` gives a material the first of
  its images, which for the molten lava is `Heat_Map3` (`warp3`, a distortion map): a band of red and cyan noise along
  the lava pools. An image the material's JSON puts in a sampler that is no colour map gives way to its colour map,
  else its `Emissive_Map` (`rock_lava_cooling_c`: dark rock, orange veins); one material on TranZit, none on
  Nuketown. BO2's additive cards (`src one, dst one`: `atmos_glow_fire`, `atmos_glow_fire_02`) are left out with the
  caulk: our BO1 templates draw them opaque, a flat orange quad by the bank.

Build it (the procedure of Nuketown's world with these differences):

    $U --include-assets xmodel,material --model-format GLTF -o $D/transitgltf/?zone? zm_transit.ff   # and each
    # zm_transit_gump_*.ff, then rsync -a --ignore-existing zm_transit_gump_*/ zm_transit/ in $D/transitgltf
    tools/bo2/bo2_mesh.py $D/zm_transit zm_transit --out $OUT/imports --blockers-only --mover veh_t6_civ_bus_zombie \
        --mover p6_anim_zm_buildable_turbine --mover c_zom_screecher_fb   # the last two since 2026-11-18
    # (the buildables' piece models are in so_zclassic_zm_transit.ff: its dump merged with rsync --ignore-existing)
    # Five's brush models, once: a headless client on Five with +set mapkit_dump_bmodels five_bmodels.json
    tools/bo2/bo2_bsp.py $D/zm_transit zm_transit --name zombie_bo2transit --templates <wc> --models \
        $D/transitgltf/zm_transit --layout <layouts/bo2_zm_transit.json> \
        --blocker-mesh imports/zm_transit/zm_transit.blockers.mesh.bin \
        --props-collision imports/zm_transit/zm_transit.props.collision.bin --window-models $D/five_bmodels.json \
        --out $OUT
    # Linker as for Nuketown; ffconv --verify; then main/maps, main/images, usermaps/zombie_bo2transit, and in
    # mods/mapkit: layouts/bo2_zm_transit_bsp.json, imports/zm_transit/ (blockers mesh, images, props collision, links)

    +set fs_game mods/mapkit +set fs_mods mapkit +set bo1_mod_mapkit bo2_zm_transit_bsp \
    +set bo1_mod_zones zombie_bo2transit zombie_cosmodrome +set bo1_bspworld maps/zombie_bo2transit.d3dbsp \
    +devmap zombie_pentagon

(Ascension's zone gives the Stamin-Up machine.) The renderer sorts at most 4 096 materials, Five brings about 2 600 and a client's HUD lookups some 90 more: `bo2_bsp.py` writes one world material per template and colour map (our copies keep nothing else), 153 for TranZit's 953 BO2 world materials, and a client stays near 3 350. ZmClient offers it as « Mapkit : TranZit native (Black Ops II, monde
BSP) » when the package holds its zone and BSP, the Switch start menu as « TranZit (BO2, natif) »; `make_dist.sh --bo2`
packages its zone, BSP, colour maps, layout and `imports/zm_transit/` (on the Switch: the links, the blockers mesh and
its images, and the props collision its layout's collision edit names, 88 MB). Not yet run on the console: the
Windows and Linux runs used 97.8 MB of the 112 MB hunk.

### Draw calls on the Switch (2026-11-15)

The user's console run of native TranZit drew 5 000 to 11 000 times a frame at ~24 fps with the GPU busy 19 ms: the
frame was CPU-bound. `r_mod_drawStats 60` (Windows client, the Switch's settings: 720p, sun shadows, depth prepass) put
the depot view at 12 986 draws: the world one surface at a time (3 958 in the lit pass, 3 667 in the prepass) and the
props one instance at a time. `d3dbsp.py` now writes the world's surfaces in vertex batches (as Treyarch's compiler
does), and the engine empties its pre-tessellated index buffer each frame again; the world then draws a few hundred
batches: 5 539 draws from the depot, 2 823 in town, 3 126 from the depot without the depth prepass (`r_depthPrepass 0`,
which costs the GPU more overdraw). Same images in the four test views. The BSP changes in its surface and index lumps
only (`bsp1`, installed in `dist_bo2src`); its zone is unchanged. The static model cache then took the props it can
(placed at least twice, at most 512 vertices, an even triangle count on every surface): 4 966 draws from the depot,
2 616 at the farm. BO2's bigger props (trees, rocks, houses) still draw one per instance (`docs/PORTING.md`).

### TranZit's bus and bank (2026-11-15)

Asked once the native TranZit played on Windows. Both MapKit layouts (`bo2_zm_transit`, `bo2_zm_transit_bsp`) get them
from `bo2_layout.py`; `mods/mapkit/MAPKIT.md` has the `bus` and `bank` edits.

- **The rider slid in the turns.** A trace of the rider in the floor's own space (`mapkit_bus_log 2`, Windows client)
  showed the engine carrying it exactly (`G_PushEntity` turns it with the floor) through the gentle turns, and the
  slide starting where BO2's vehicle nodes zigzag (+-50 degrees between points 21 and 24, and 60 to 63): the floor's
  yaw went 101, 150, 94, 55, 92 degrees within two seconds, because each segment's own heading was reached in 0.5 s at
  most, whatever the segment's length. The layout now carries `yaws`, each point's heading from 250 units back to
  250 units ahead along the loop (`loop_headings`), and the floor turns over the whole segment: 87 degrees a second at
  most. Same trace after: the rider stayed at the floor's centre to the diner, the farm and the power station but for
  one slip of 48 units in a slow turn, and stayed in the bus.
- **The first try boarded no one.** A player put on the floor while the zombies' spawn logic still moved them fell
  78 units under the bus: the floor and the traces were fine (a `BulletTrace` and a `PlayerPhysicsTrace` stopped on it).
  The test aid now boards player 0 two seconds into each stop.
- **Stops and doors.** At a stop the two door brush models (`mapkit_bus_door0/1`, filling the right wall's openings)
  stop colliding and are hidden; Five's alarm bell (`evt_thief_alarm_single`, no BO2 sounds here) rings 5 s before
  the bus leaves; the doors shut (a player in the doorway is put inside) with Five's freight elevator sounds, and the bus
  goes a second later. `bo2_mesh.py --mover` writes the panels its `MOVER_HOLES` cut as two models
  (`veh_t6_civ_bus_zombie_door0/1`), which the mesh edit's new `movers` draw on the door entities: only in the frames
  the client game posed them, so a hidden door (and a bus out of the snapshot) is not drawn at an old pose. Checked
  on Windows screenshots: the rear opening empty at the depot, the folding panels shut the second before it leaves.
- **Calls.** Once the power is on, a lever box (Five's power switch models) by each stop sends the bus to that stop
  next: it passes the others and cuts a wait elsewhere short. `call_spot` puts it 4 units off the first world wall on
  the doors' side (depot, farm, power station, town); the diner's has no wall within 400 units and stands beside the
  road. BO2's own call spots are not in the dump (its scripts place them).
- **Driver's button** (asked after the first package). The bus never opened between stops, so a rider was shut in to
  the next stop. A free use trigger by the driver's seat (`BUS_BUTTON`, vehicle space: the dashboard left of the
  wheel, out of reach from the front door's step), with Five's lever handle on it, opens the doors on the way; they
  shut again 5 s later (a player in the doorway is put inside), unless the bus has reached a stop by then. The trigger
  and the handle are linked to the floor (`EnableLinkTo`). Regenerated layouts: identical to the installed ones but for
  the bus edit's `button`. Self-test `bus_button` (once the bus has left a stop, the client holds use toward the
  button from beside the driver's seat: the doorway must open, then shut before the next stop): native TranZit (Linux,
  focused windows and risers as above) 125/0.
- **Bank.** Deposit (1 000 points, account at most 250 000) and withdrawal (1 000 back less a 100-point fee) at the
  vault's deposit boxes, as in BO2: the withdrawal at the box the keys hang from (`p6_zm_keys`), the deposit at the
  box farthest from it on the same wall whose trigger stays 64 units off a door's use volume (the last one, by the
  lab hatch, took that door's prompt: "You must turn on the power first!"). BO2's own `bank_withdraw` /
  `bank_deposit` structs are not in TranZit's dump (Buried's are). The first version stood them at the teller windows
  in the lobby, where a player looking for them in the vault found nothing (a user's report, 2026-11-18). Both
  triggers stand on the floor, on the vault side of the wall (toward the nearest pathnode), with BO2's prompts
  ("Hold [use] to withdraw from deposit box [Amount: 1000] [Fee: 100]"). Windows client, native TranZit, the account
  seeded with 5 000: a withdrawal at the keys (500 to 1 400 points, account 4 000), then a deposit (1 400 to 400,
  account 5 000). The weapon locker stands in front of BO2's
  `p6_zm_weapon_locker` (the farmhouse's fridge): it keeps the weapon in hand (not the last one) with its ammo and gives
  it back on a later use when the map's zones hold it. The engine keeps them by player name in
  `<fs_homepath>/main/mapkit_bank.txt` (`bo1_mapkit_bank_get` / `_set`, `g_mapkit.cpp`), read at each call and
  rewritten through a temporary file; a game's points change only once it is written.
- Self-test: `bus_doors` (a player trace crosses the front doorway at the stop, not on the way), `bus_call` (called to
  stop 3 from stop 1, the bus stops nowhere between), `bank deposit` and `bank locker` (under the account
  `mapkit_selftest`, removed after). Native TranZit (Linux): pass 198 fail 1, all five bus and bank checks passing; the
  failure, `depot_baricade3` ("zombies got spawned outside only", a spawner in the depot's basement, far from the bus),
  passed on a focused rerun (`mapkit_test_windows depot_baricade3`: 124/0) and had failed the same way in an earlier run.
- Not done: zombies chasing and boarding the bus, its roof hatch, ladder, horn, lights and driver, the bus's own wall
  buy, BO2's sounds.

### Mob of the Dead's world as a native map (2026-11-16)

`zm_prison` goes through the same tools as TranZit, as `zombie_bo2prison` with the layout `bo2_zm_prison_bsp`: the
island without its afterlife, plane, bridge or Brutus. 209 895 world triangles in 3 125 surfaces, 15 818 placed props of
415 models, 15 120 brushes, 18 659 terrain triangles, 198 lamps; BSP 99 MB, zone 6 MB, 338 colour maps, props collision
43 MB; hunk 69.0 MB after the render world, 71.6 at most (Windows). What it needed:

- **The DLC's images.** The zone reads `dlc2.ipak`, the install has `dlczm2.ipak`: without a link under the zone's name
  (`tools/bo2/oat/README.md`) 850 images had no data, 507 of the world's materials were left out and 10 969 placements
  drew nothing (their models' materials were gone).
- **A layout node left in solid.** On a BSP world `Path_InitPaths` builds the friendly chains after MapKit added its
  nodes, and `Path_BuildChains` drops the map for a bad node in one ("bad node [1211] in friendly chain"); two of the
  cell block's nodes find no free spot within 16 units. MapKit gives a node left bad `spawnflags` 2, which keeps it out
  of the chains (zombies do not use them; `g_mapkit_path.cpp`).
- **Spawners named Mob of the Dead's way.** A zone's volume targets its spawn structs (`spawner_shower`,
  `zone_cafetaria_spawner`); `bo2_layout.py` took only `<zone>_spawners` (Nuketown, TranZit) and found 13 of them: now
  47 risers and 68 spawners. A spawn_location names no barricade there: it targets the pathnode its zombies go to first,
  100 to 120 units outside the barricade they come in by, which makes it that window's spawner. A spawner added for a
  window stands 128 units out unless no pathnode is near there (the cells behind the corridor's barricades): then 48.
- **Climbs.** The zombies reach the upper barricades and roofs by `zm_alcatraz_*` climbs: a jump down, MapKit's jump up
  or a mantle by the pair's own height (51 pairs; the jump to the bridge is left out).
- **Pack-a-Punch.** Classic's stands on the Golden Gate Bridge, a zone of its own 8 000 units under the island that only
  the plane reaches: a Pack-a-Punch out of the zones a player walks to from the start (boxes touching) gives way to
  another mode's, Grief's in the cell block (888, 9057, 1544).
- **Doors.** The afterlife doors (`afterlife_door`, cost 0) are bought for 750. The cell doors round the players' start
  (`cellblock_start_door`, one blocker from x 535 to 2113 over the whole corridor) open by script at the start: as a door
  to buy, its box held the player in solid (the user's first game). A door whose box holds a start point is a free power
  door, open at once on a layout without a power switch.
- **Machines and props.** A floor lamp 55 units in front of Juggernog kept the player out of its trigger: a machine's
  side is free only without a colliding prop taller than a step (24 units, OAT's OBJ) whose origin lies within 20 units
  of its front. Juggernog faces +x. Deadshot and Electric Cherry have no BO1 machine on Five; the Thompson and Uzi wall
  buys no BO1 equivalent.

- **The gondola** (`zipline_gondola`, asked by the user): MapKit's bus on a two-stop line, the cell block's roof
  (901, 8231, floor 1543) to the docks (901.6, 5983, floor 265), 2 586 units at 150 a second, 20 s at each station,
  running from the start (BO2 powers it from afterlife). Its heading stays fixed, so the cabin never turns; floor,
  side walls and ends with a doorway each that shuts on the way (`GONDOLA_*` in `bo2_layout.py`, BO2's cabin turned 180
  degrees: each end against its station's gates). The cabin `p6_zm_al_gondola` is the mesh edit's mover
  (`bo2_mesh.py --mover p6_zm_al_gondola`); a lever box on each station calls it ("noun": the levers say gondola). No
  button in it (the bus's opens its doors on the way). With `mapkit_bus_log 2` (Linux) the client put on its floor at
  the roof stays at (0, 0, 8.1) in its space down to the docks and back, on the ground throughout; Windows screenshots
  from the roof's platform show the cabin docked, leaving downwards, then gone.

Each change leaves Nuketown's and TranZit's layouts and blocker meshes byte for byte as they were.

Checked: Windows client (D3D9): spawn in the cell block, the round starts, the cell doors open at 0:00, `+forward` walks
423 units down the corridor, clean exit. Self-test (Linux, timescale 4), last full run before the start door and the
near spawners: pass 166 fail 43; the doors, the three perks, the box, the Pack-a-Punch (MP5K upgraded), 6 of 7 wall buys,
the 29 zones and 30 of 47 risers pass, the rounds go on (16 in 18 minutes). Failing: 17 of 22 windows ("zombies got
spawned outside only": they walk into the room by another way, or none comes), 17 risers whose zombies do not reach the
client, the CZ75 wall buy on the cell block's second tier (the client stays on the floor below); most of them are
fixed since (201/7, "Mob of the Dead's self-test failures" below). Not yet run by the user after the start door fix,
nor on the console.

    tools/bo2/bo2_layout.py $D/zm_prison zm_prison --out bo2_zm_prison.json --links-out zm_prison.links.txt
    tools/bo2/bo2_mesh.py $D/zm_prison zm_prison --out $OUT/imports/zm_prison --blockers-only --mover p6_zm_al_gondola
    tools/bo2/bo2_bsp.py $D/zm_prison zm_prison --name zombie_bo2prison --templates <wc> --models $D/prisongltf/zm_prison \
        --layout bo2_zm_prison.json --blocker-mesh imports/zm_prison/zm_prison.blockers.mesh.bin \
        --props-collision imports/zm_prison/zm_prison.props.collision.bin --window-models $D/five_bmodels.json --out $OUT

    +set fs_game mods/mapkit +set fs_mods mapkit +set bo1_mod_mapkit bo2_zm_prison_bsp +set bo1_mod_zones zombie_bo2prison \
    +set bo1_bspworld maps/zombie_bo2prison.d3dbsp +devmap zombie_pentagon

ZmClient offers it as « Mapkit : Mob of the Dead native (Black Ops II, monde BSP) », the Switch start menu as « Mob of
the Dead (BO2, natif) »; `make_dist.sh --bo2` packages it as TranZit.

### Buried's world as a native map (2026-11-16)

`zm_buried` (images in `dlc3.ipak`, through the same links) goes through the tools unchanged but for four traversals,
as `zombie_bo2buried` with the layout `bo2_zm_buried_bsp`: the town and its cave, without Leroy, the haunted mansion's
ghosts, the maze's puzzles or the buildables. 122 110 world triangles in 1 782 surfaces, 9 774 props of 619 models,
11 684 brushes, 196 lamps; BSP 80 MB, zone 10 MB, 301 colour maps, props collision 62 MB; hunk 55.4 MB after the render
world, 57.4 at most (Windows). Layout: 41 zones, 35 windows, 60 risers, 38 spawners, 9 doors, 7 debris, 7 box spots,
Juggernog, Double Tap, Quick Revive, Speed Cola and Stamin-Up (Ascension's zone, as TranZit), the Pack-a-Punch by the
maze, 5 wall buys; no power switch, so the power is on from the start. Left out: Mule Kick and Vulture Aid (no machine
on Five), the LSAT, `zm_jump_across_120` (TranZit has it too and keeps its layout). `zm_jump_down_240`,
`zm_jump_up_grabbed_48` and the start's railing jumps take the climbs' rule (by height).

Checked: Windows client (D3D9): spawn in the processing plant, walking, the town's street, cave and mansion drawn, the
round starts, clean exit. Self-test (Linux, timescale 4, before the four traversals): pass 246 fail 12, 32 of 35
windows and 58 of 60 risers, rounds on to 28 in 38 minutes. Failing: the candy store's staircase debris and so its
upper floor's zone (the client stands beside the steps), Quick Revive (a shovel by the machine stops the client 49 units
from the trigger), the start's upper Ithaca (the client stays on the floor below), 3 windows, 2 risers.

Props' collision, after the user got stuck three times (`bo2_bsp_props.py`, `bo2_props_collision.py`; every case
checked with a Windows client walking through it):
- **The slide** from the start down to the tunnels. BO2 lays thin player clips over it as its floor. Its rock piles
  were boxes: those of the rocks hanging from the ceiling (turned over: their up axis points down) filled the space
  under the rocks (37 units left where the rocks leave 84), and those of the rocks under the clips stood up to 40 units
  over it, so the player walked on them into the hanging ones. A pile turned over, or under a player clip with a floor
  (`clip_ramps`: player clip only, a side of normal z 0.7 or more), now keeps its triangles, and the faces under such a
  clip, up to `RAMP_COVER` (36) units over it, are left out: the real rocks rise 22 units through the clip under rocks
  hanging 47 units over them, which no player passes. 1 014 piles, 49 341 triangles left under clips.
- **Leroy's cell** in the jail: the frame's collision LOD keeps the closed door's rails across the doorway (the door is
  a script model, left out with Leroy). `DOORWAYS` cuts the frame's triangles between x = -42 and 12 (model space; the
  door's hinge is at -42): the cell is open, as after Leroy is freed.
- **The general store's stairs** and the doorway at their top: each prism went 16 units behind its face, so the
  prisms of a part thinner than that (a railing's spindles, a door frame's trim) came out of its other side, 13 units
  into the stairs and at head height in the doorway (a standing player stopped, a crouching one passed).
  `prism_depths` stops each prism at the model's next face behind it (a ray from the face's centre, at least 1 unit):
  the railing's prisms are now 1.8 to 4 units deep. MapKit's own import (`bo2_props_collision.py` run alone) still
  writes 16-unit prisms.

The BSP is otherwise the same (zone unchanged); the props' collision file holds 360 154 prisms (302 366 before) in
73 MB. Self-test after these changes: pass 244 fail 14 (247/11 and 246/12 on the two runs before): the candy store's
debris and zone, Quick Revive, the upper Ithaca, 4 windows and a riser as before, plus two of the general store's
window checks, whose zombies came through those windows earlier in the run but not within the check's 90 s (the
props do not block the AI; `bank_1` failed the same way on the first run and passed on the second). The changes apply
to every map at its next `bo2_bsp.py` run. Nuketown, TranZit and Mob of the Dead were rebuilt with them on 2026-11-17
(below, "The other maps rebuilt").

    tools/bo2/bo2_bsp.py $D/zm_buried zm_buried --name zombie_bo2buried ... (as Mob of the Dead, no --mover)
    +set bo1_mod_mapkit bo2_zm_buried_bsp +set bo1_mod_zones zombie_bo2buried zombie_cosmodrome \
    +set bo1_bspworld maps/zombie_bo2buried.d3dbsp +devmap zombie_pentagon

ZmClient: « Mapkit : Buried native (Black Ops II, monde BSP) »; Switch start menu: « Buried (BO2, natif) ».

### The other maps rebuilt (2026-11-17)

Nuketown, TranZit and Mob of the Dead went through `bo2_bsp.py` again with Buried's props collision (same dumps,
layouts and blocker meshes; their `_bsp` layouts come out byte for byte the same):

| Map | Props collision | Self-test (Linux, all checks) |
|---|---|---|
| Nuketown | 24 piles as 170 rocks; 89 piles hanging or under a player clip, 29 830 of their triangles left out | 106/0, as before |
| Mob of the Dead | 102 such piles (3 720 triangles left out); 216 191 prisms in 44.1 MB (209 696, 42.8 MB before) | 167/41 (166/43 before): the same windows and risers |
| TranZit | 85 such piles (3 248 triangles left out); 446 321 prisms in 91.0 MB (88.6 MB before) | 296/5: five risers of the 100-odd (the earlier runs checked two), which fail the same on the previous BSP (`mapkit_test_risers` on those five: 198/5 new, 197/6 previous) |

TranZit's and Mob of the Dead's zones are unchanged. Nuketown's had to be linked again: its last BSP in the packages
(2026-11-14) predates the props as static models, and its zone holds none of their 333 xmodels; the new BSP places
them, and a client (not the headless self-test, which draws nothing) stops at the first one with
`R_CheckValidStaticModel: could not find xmodel 'default_static_model'` (`bad static model 'bo2x_...'` before it).
Check a rebuilt BSP's zone for every `xmodel` and `material` line of `linker/zone_source/<zone>.zone`, not only the
materials. Nuketown's layout also takes the current `bo2_layout.py`'s jump downs by height (three traversals).

### Placed effects (2026-11-17)

OAT reads no effect (`FxEffectDef` is unsupported for T6 and T5), so a BO2 map's effects cannot be converted. Its
placed effects can be placed again with BO1's own: the map's patch zone (`zm_nuked_patch.ff`) holds its compiled
createfx script, `clientscripts/mp/createfx/zm_nuked_fx.csc`, which `tools/bo2/bo2_createfx.py` reads (T6 GSC:
each `createoneshoteffect` / `createloopeffect` / `createexploder` call's string argument, and the vectors pushed
before the next `origin` and `angles` fields; 287 effects on Nuketown, 51 of them exploders). A constant vector is
three number pushes then opcode `0x5b`, its components pushed last to first, or opcode `0x5e` and a flags byte, two
bits a component (the last component's in the low bits): 0 for 0, 2 for a number pushed before it (`(273, 0, 0)`:
a float, then flags `0x20`). Every Nuketown angle reads either way, (pitch, yaw, roll): the vertical electric arc is
(270, ...), the grates' light rays pitch 40 to 80 (down through them). Its `EFFECTS` table gives a BO1
effect for some BO2 ids, and `bo2_layout.py --createfx` adds an `fx` edit for each such placement:

| BO2 (Nuketown) | BO1 | Placed |
|---|---|---|
| `fx_ash_embers_falling_radioactive_md` / `_sm` | `env/fire/fx_embers_falling_md` / `_sm` | 13 / 4 |
| `fx_ash_embers_up_lg` | `env/fire/fx_embers_up_dist` | 4 |
| `fx_zmb_nuke_radioactive_ash_gusty` | `env/fire/fx_ash_embers_light` | 3 |
| `fx_zmb_nuke_burning_ash_gusty` | `env/fire/fx_ash_embers_heavy` | 3 |
| `fx_zmb_nuke_radioactive_embers` (and `_crater`) | `env/fire/fx_embers_wind_md` | 2 |
| the small flames (`fx_fire_xsm`, `fx_fire_line_xsm`, `_pole`) | `env/fire/fx_fire_detail_sm_nodlight` | 41 |
| the small fires (`fx_fire_line_sm`, `_pole`, ceiling edges, floor, smoulder areas) | `env/fire/fx_fire_sm` | 20 |
| `fx_fire_sm_smolder` | `env/fire/fx_fire_sm_smolder` | 33 |
| the eaves, ceilings, rafters, walls, poles, fireplace, wind-blown and TranZit medium fires | `env/fire/fx_fire_md` | 19 |
| `fx_zmb_tranzit_fire_lrg` | `env/fire/fx_fire_lg` | 3 |
| `fx_nic_fire_building_md_dist` (the burning houses beyond the map) | `env/fire/fx_fire_large_distant` | 8 |
| `fx_smk_fire_lg_black` | `env/smoke/fx_smk_fire_lg_black` | 1 |
| `fx_smk_linger_lit` (and `_slow`, `_z`) | `env/smoke/fx_smk_linger_lit` | 6 |
| `fx_smk_plume_md_blk_wispy_dist` | `env/smoke/fx_smk_plume_md_blk` | 3 |
| `fx_smk_smolder_gray_fast` / `_slow` | `env/smoke/fx_smk_smolder_sm` | 4 (the other 10 are exploders) |
| `fx_smk_smolder_rubble_md_int` | `env/smoke/fx_smk_smolder_rubble_md` | 4 |
| `fx_smk_wood_sm_black` | `env/smoke/fx_smk_smolder_sm_blk` | 1 |
| `fx_elec_spark_wire_xsm_runner` | `env/electrical/fx_elec_wire_sparks` | 2 |
| `fx_elec_transformer_sparks_runner` | `env/electrical/fx_elec_burst_shower_sm_runner` | 1 |
| `fx_mp_elec_spark_burst_xsm_thin_runner` | `env/electrical/fx_elec_short_random` | 4 |
| `fx_zm_nuked_light_ray_md_wide` (the sun through the roofs) | `env/light/fx_light_godray_md_white` | 2 |
| `fx_zm_nuked_light_ray_md_wide_streak` (and `_1s`) | `env/light/fx_ray_md_1sd` | 9 |
| `fx_zm_nuked_light_ray_streaks_1s` | `env/light/fx_ray_sm_1sd` | 2 |
| `fx_light_ray_grate_warm` | `env/light/fx_light_godray_sm_warm` | 7 |
| `fx_light_flour_glow_cool_sngl_shrt` | `env/light/fx_light_fluorescent` | 1 |
| `fx_zmb_fog_low_radiation_140x300` (in a house) | `env/smoke/fx_fog_interior_md` | 2 |
| `fx_cloud_cover_flat` / `_volume` (exploders, kept: lit all game) | `env/weather/fx_cloud3d_cmls_lg1_dark` | 5 / 7 |

TranZit's createfx script (`zm_transit_patch.ff`, `clientscripts/mp/createfx/zm_transit_fx.csc`) places 752 effects,
165 of them exploders; 271 get a BO1 effect: ash and embers (`fx_zmb_ash_ember_*` 45, `fx_zmb_ash_windy_heavy_*` 25,
`fx_zmb_ash_rising_md` 9), the fires (27, as Nuketown's), smoke (`fx_zmb_tranzit_smk_interior_md` 9 as
`fx_smk_hallway_md`, `_smk_column_lrg` 4 as `fx_smk_column_lg_blk`, the lava's `fx_zmb_lava_smoke_tall` 8 and
`_pit` 2 as white plumes and smoulder), fog (the closets' 15 as `fx_fog_interior_md`, `fx_zmb_fog_low_300x300` 12 as
`fx_fog_low`, `fx_zmb_fog_thick_*` 9 as `fx_fog_rolling_thick_600x600`, the fog between the areas,
`fx_zmb_fog_transition_*` 17, as `fx_fog_large_slow`), the light rays (depot, interiors, tunnel, power station, bank
vault: 71, as BO1's godrays), fluorescent tubes (16), sparks (2) and, since the lamps (below), 56 lamps: the street
tinhats (10, as `fx_light_tinhat_cage_yellow`, beam down) and the cans, bulbs and desk lamps (46, as
`fx_light_incandescent`). Left out: the lava's glows, edges and heat distortion (the lava itself is in the world),
the Avogadro's storm, insects, papers and the exploders (the lamps the power or the alarm lights among them).

Mob of the Dead's script (`zm_prison_patch.ff`) places 724 effects, 28 of them exploders; 345 get a BO1 effect: the
fires (47: `fx_alcatraz_fire_xsm` 31 as the small flames, `_fire_sm` and the fire works 12, `_fire_md` and the ceiling
fires 4), embers (`fx_alcatraz_embers_flat` and `_indoor` 51 as `fx_embers_falling_sm`), ash (the steam's and the
tunnel's, 9), the ground fog (60 as `fx_fog_low`), the fog over the bay (25 as `fx_fog_rolling_vista_lg`), the
closets' and the docks' (9), smoke (4), steam (the pipes' 5 as `fx_pipe_steam_md`, turned, and one more), the light
rays through the cells and grilles (114, as BO1's white godrays) and sparks (the panels' and ceilings', 20). Left
out: the 59 candles (BO1's candle carries a dynamic light), papers, flies, blood and water drips, the falling fire
(BO1's falling debris does not loop) and the exploders. Its lamps: the tinhats (92, as `fx_light_tinhat_cage`, beam
down) and the round ceiling lamps (47, as `fx_mp_light_corona_bulb_ceiling`).

Buried's (`zm_buried_patch.ff`) places 629, 24 of them exploders; 153 get a BO1 effect: fog (49, as `fx_fog_low` and
`_sm`) and the low cloud (2, as `fx_fog_large_slow`), the light rays outside, through the church and the town (38),
the dust in the light (`fx_buried_dust_motes_*` 42, as BO1's dust motes), steam (9), the smoke plumes over the cave (3,
as `fx_smk_plume_lg_blk`), ash (9), the fireplace and the lamps (the 93 kerosene lamps and 51 sconces, as
`fx_light_incandescent`). Left out: the tunnels' falling dust, sand and the sandstorm, insects, bats, water and the
exploders (the meteors, the barriers breaking).

The lamps (2026-11-17, asked by the user): 339 glows, none with a dynamic light. The caged lamps keep BO2's angles
(their beam points down); the others are a round glow seen from anywhere. Tried and dropped on Windows screenshots:
BO1's ceiling and desk lamps (`fx_zombie_light_overhead_amber`, `fx_light_desk_lamp`) lay their glow flat along the
effect's axis, so a can light seen from below its ceiling showed nothing, and `fx_mp_light_bulb_sm_no_eo` was too
faint to see on a lantern. Effects placed: TranZit 327, Mob of the Dead 484, Buried 297 (Nuketown unchanged, 214).

The fires are point fires without a dynamic light (none of these BO1 effects has a light element): a BO2 fire line
runs along its angles, which are not kept, so a BO1 line fire would point anywhere. The rays and sparks keep BO2's
angles (`ORIENTED`, an `angles` field on the edit, `AnglesToForward` / `AnglesToUp` in MapKit): both games lay a ray
along the effect's forward axis (BO1's godray spawns its beam at `spawnOrgX 350`, and BO2 still uses BO1's
`fx_ray_sun_sm_short`). Left out: the vertical electric arc, the sun's lens flare (no BO1 equivalent here) and
the mushroom cloud's remains 10 800 units down (BO1's largest smoke is drawn up to 8 000). BO1's 3D clouds stand
for BO2's cloud cover: drawn up to 120 000 units (the flat ones only 25 000, BO2's lie 20 000 to 37 000 away).

The BO1 effects are none of the zones a BO2 map loads, so they get a zone of their own, `zombie_bo2fx`, built by the
Mod Tools' `linker_pc` from their `raw/fx/*.efx` (it builds any zone but a map): a zone source of `fx,` lines (the
ones `bo2_createfx.py` prints), the effects' images copied from the player's own `.iwd` files into the tool copy's
`raw/images/` (the zone then holds no image: they load from the `.iwd` in play; the linker names each missing image, and the
player's `.iwd` files held every one the 50 effects of the four maps use), widened by `ffconv --verify`. One zone
serves the four maps (the union of their effects, 73 assets). It is loaded after the map's zones (`bo1_mod_zones
zombie_bo2nuked zombie_bo2fx`, `zombie_bo2transit zombie_cosmodrome zombie_bo2fx`, `zombie_bo2prison zombie_bo2fx`,
`zombie_bo2buried zombie_cosmodrome zombie_bo2fx`: ZmClient's `MAPKIT_FX_ZONES`, the Switch menu's `fxZone`, both of
which also require its file).

The server loads each effect before the level script's first wait (`_mapkit.gsc` `mapkit_fx_load`: a client finds
an effect only once the server has loaded it), and mods/mapkit's client main (`mapkit_main.csc` `mapkit_fx`) plays
every `fx` edit once on each local client with `playfx`, as BO1's createfx plays its ambient effects: they loop by
themselves, and no server entity stands for them. A first version spawned one server effect entity each
(`SpawnFx` / `TriggerFx`): TranZit's 271 ran the server out of entities (`G_Spawn: no free entities` at the start,
the round never began), and an entity triggered in the level's first frame never started (its trigger time, 0,
equals the one a client starts with). The client reads the layout through two client script builtins,
`bo1_mapkit_editcount` and `bo1_mapkit_get` (`cg_scr_sp_client.cpp`, as the server's), and leaves its count in the
dvar `mapkit_fx_placed`.

    U --include-assets script -o out/?zone? "$Z/zm_nuked_patch.ff"     # and each map's zm_<map>_patch.ff
    tools/bo2/bo2_createfx.py out/zm_nuked_patch/clientscripts/mp/createfx/zm_nuked_fx.csc --all
    tools/bo2/bo2_layout.py $D/zm_nuked zm_nuked --createfx out/zm_nuked_patch/clientscripts/mp/createfx/zm_nuked_fx.csc
    # TranZit: bo2_layout.py ... --collision-file <its zm_transit.collision.bin> --createfx <its csc>
    # then bo2_bsp.py --layout-only as before; zone_source/zombie_bo2fx.csv: every map's printed fx lines, sorted -u
    linker_pc.exe -language english zombie_bo2fx; ffconv --verify zombie_bo2fx.ff <game>/usermaps/zombie_bo2fx/zombie_bo2fx.ff

Checked on a Windows client (D3D9): Nuketown `mapkit_fx_placed` 214 (flames on the roofs, a column of black smoke,
embers falling over the street, sparks, a pale shaft of light, the clouds massed in the sky; the rays are faint as
in BO1, the fog in the green house too), TranZit 271 (the round starts; fires under the shelter, a burning shack and
bushes, embers), Mob of the Dead 345 and Buried 153 (the rounds start; embers seen, the rest faint on the views
taken). Cost on a PC (win64, headless client, the camera still before the burning house, 5 s
windows after 40 s): 136 and 142 fps without the effects, 116 and 128 with them (frame 6.1 / 6.2 ms against 7.0 / 6.9
ms), about 0.8 ms, measured with the 172 ambient ones; `+set mapkit_fx 0` leaves them out (a console's GPU may pay more for the smoke). Linux self-tests (the server's side: every effect loaded):
Nuketown 107/0 (`check fx all PASS 214 edits, 28 effects loaded`), TranZit 297/5 (271 edits, 20 effects; the five risers that fail without the effects too), Mob of the Dead 168/41 (345 edits, 16 effects; the same windows and risers as before), Buried 247/12 (153 edits, 13 effects; the candy store, Quick Revive, the upper Ithaca, windows and risers as before); 106/0 and `SKIP` with `mapkit_fx 0`. Not done: the water streams, the arc, the lens
flare, the other exploders (Nuketown's meteor impacts), TranZit's lava glows and storm, the candles (the same route:
an `EFFECTS` entry and its BO1 effect in the zone). The lamps: Windows client with the new zone, `mapkit_fx_placed`
327, 484 and 297, no effect error; screenshots of each kind lit (the farm's tinhat lights its door, the cell block's
tinhat its beam). Not run: the Linux self-tests and a frame-time measure with the lamps.

### Mob of the Dead's self-test failures (2026-11-17)

From 168/41 to 201/7 (Linux self-test, all checks, same zones and BSP). One fix per cause, each measured on its own run:

| Cause | Fix | Checks it fixed |
|---|---|---|
| 8 windows share their name with their zone (`zone_cafeteria`, `zone_start`, ...): the self-test's room lookup took the window edit, listed after the zone, which has no `mins`, so no zombie ever counted as inside | `_mapkit.gsc` `mapkit_window_track`: only an edit with `mins` is a room (as `mapkit_check_lights` already did) | 168/41 to 176/33: those windows |
| `g_mapkit_path.cpp` linked new nodes only within 256 units across and 128 up or down, traverse pairs too: none of the 19 climbs taller than 128 had its link (the 240-unit climbs to `zone_start_5/6/7`, the 560-unit ones to the infirmary roof, the dock's water jump up), and their zombies stood on a bad path | a negotiation pair (`Path_IsNegotiationLink`, either way) is always offered to `Path_CanLinkNodes`, which links it at any distance as the engine does | with the CZ75 fix, 176/33 to 199/10: `zone_start_5/6/7`, the roof's and the dock's risers |
| the CZ75 hangs over a player-clip catwalk 58 units under it; the self-test's bullet trace found the floor 104 units lower | on an imported map, the stand spot takes the higher floor a `PlayerPhysicsTrace` finds | the wall buy |
| 5 MotD spawn structs target a pathnode near no barricade (BO2's zombies walk in from there): without a window, retail `zombie_think` sent them to the nearest exterior goal, often unreachable (zone_dock_gondola's on a roof 200 units over zone_studio's) | `bo2_layout.py`: such a spawner is a chaser (`"chaser": 1`, as BO2's `find_flesh`) | `zone_studio`, the `zone_studio_21` unlock |
| `zone_cellblock_west`'s window opens on a roof whose parapet stands 128 units out: its added spawner stood on the parapet's top, 28 units over the roof, with no path | `bo2_layout.py`: an added spawner whose floor out there is not the window's (18 units) stands behind the boards (48 units), as without an outside pathnode | that window |
| riser pairs 46 units apart (`riser4`/`riser8`, `riser16`/`riser17`, `riser43`/`riser44` in the old numbering): the self-test named a riser by the spot nearest where its zombie stood up, and the climb carries it 45 units on, onto the other spot | `mapkit_riser_track` names it by where `do_zombie_rise` put it under the ground (0.2 s in, horizontal distance) | those three risers |
| `electric_room_spawn` hangs 220 units over the rocks (zone_electric_room has no pathnode either) | `bo2_layout.py` leaves out a riser spot more than 32 units over its floor (the following risers are numbered one lower) | that riser |

Nuketown's, TranZit's and Buried's layouts come out byte for byte the same; their self-tests with the new binary and
scripts: Nuketown 107/0, TranZit 298/4 (297/5: `riser88`/`riser89` now reach the client; `power_baricade1`'s unlock
check saw no spawn in its 90 s, a draw among the zone's spawners that passed before), Buried 248/11 (247/12: the upper
Ithaca and `riser60` pass; `general_store_2`'s unlock check the same draw). Left on Mob of the Dead (pr_st4): node 581 of the cell block's
catwalk in solid under a prop (no free spot within 32 units either); `riser32` (the dock's water riser: its zombie
climbs onto the pier and was jumping down to the client when the 90 s ran out); `riser37`/`riser38`, the gondola
zone's risers at the citadel station while the client stands at the dock's; and two that pass in other runs
(`zone_start`: its first zombie came 3 s late, over a round break; the `zone_studio_21` unlock, one spawner among the
zone's).

### Nuketown's falling machines, TranZit's buildables and Denizens (2026-11-18)

Asked by the user, in this order: Nuketown's perks falling from the sky, then TranZit's map weapons, buildables and
Denizens. The decompiled BO2 scripts (`zm_nuked_perks`, `zm_transit_buildables`, `_zm_buildables`,
`_zm_equip_turbine`, `zm_ai_screecher`, `zm_transit`) are the reference; MAPKIT.md's `perkspot`, `wallbuy`
(`"trigger"`), `buildable`, `piece`, `buildpart` rows and `_mapkit.gsc` hold the details.

- **Nuketown's machines from the sky** (`perkspot` edits, `"sky"` on the perk and pap edits): the four perks and
  Pack-a-Punch land on 5 of BO2's 10 `zm_random_machine` spots, picked at random; Quick Revive first and alone on a
  `solo` spot, the others one per round range (3-5, 6-9, 10-14, 15-19, 20-25). Each spot keeps BO2's crate pile
  (`bo2_mesh.py` groups, 25 props, 2 new images) and a machine clip until a machine lands on it. Windows (test client,
  `mapkit_skyperks_fast 1`): the five machines landed in 2 minutes, crates hidden under each, no script error.
- **Bowie knife and claymores** on Nuketown and TranZit: BO2's `bowie_upgrade` and `claymore_purchase` triggers become
  wall buys of BO1's own purchases (`"trigger"`; the engine names the trigger so). BO2's Galvaknuckles wall
  (`tazer_upgrade`) has no BO1 weapon and was left out at first (it came with the bo2weapons mod, below). A first
  Windows run gave 5 script errors: that exe predated the engine's `"trigger"` (`cm_mapkit.cpp` built a second
  earlier), so both were plain wall buys of weapons BO1's table lacks; none with the rebuilt exe. Self-test: both bought on Nuketown and TranZit.
- **Buildables** (TranZit): the power switch, Pack-a-Punch and the turbine are built from three pieces each, lying on
  one of their BO2 spots (`piece` edits drawn by `bo2_mesh.py` groups; 20 spots, the models from
  `so_zclassic_zm_transit.ff`). The power switch shows its parts at the switch as they are built in (`buildpart`).
  Use at a table and on a piece is polled by distance, not a use trigger's: BO2's table triggers stand inside the
  tables, and the self-test's client never built the power switch (nor picked up the turbine's fan, on a shelf)
  through the trigger, whose use test looks for its centre from the eye.
- **The turbine**: once built, a player takes it from its table and plants it by crouching and holding use 1 s; it
  opens the doors BO2 opens with a turbine (`local_electric_door`: the depot's two, the diner's, the town's and the
  lab hatch to Pack-a-Punch), within BO2's 335 units, for good (BO2's need it running beside them, and it wears out).
  It is drawn by a mesh mover (`p6_anim_zm_buildable_turbine`) on an undrawn layout brush model the script moves.
  Without buildables (`mapkit_buildables 0`) those doors open with the power, as before.
- **Denizens**, simplified: in a fog zone (`_trans_`/`_amb_`, BO2's `init_screecher_zones`), off the bus and away
  from a lit safety light (BO2's 8 `screecher_escape` lamps, lit by a planted turbine within 335 units), a player is
  hunted after 8-15 s: the screecher's model rises behind him, leaps on him and clings to his face, blurring the view
  and clawing 10 health every 2 s until one melee throws it off (50 points). No BO2 teleport, no push minigame, no
  Denizen anim (its bind pose). Its colour map is streamed from an `.ipak` OAT does not dump: it is drawn with its
  grey rim mask.
- Checks. TranZit Windows self-test client (win64, screenshots every 3 s): the six pieces of the power switch and
  Pack-a-Punch built, the turbine's three, the turbine taken, planted (drawn) and the two depot doors opened, a
  Denizen clinging (blurred view) then knifed off; no script error. Linux self-tests (all checks, timescale 4):
  Nuketown 109/0 (the Bowie knife and claymore walls; the machines stand at their edits there), TranZit 315/3
  (`riser101` to `riser103`, which fail the same way in the 298/4 run before; the old fourth failure passes).

### The Galvaknuckles and the EMP grenade (2026-11-18)

The fourth item of the same request. Both are BO2 weapons BO1 lacks, so they come from the player's bo2weapons
`mod.ff` (`tools/bo2/bo2_weapon.py` EXTRAS, docs/BO2_WEAPONS.md), and MapKit runs them only when that mod is stacked
(`+set fs_mods "mapkit bo2weapons"`); `games_mp.log` says `mapkit: Galvaknuckles on, EMP grenade in the box` or
`not loaded`. The decompiled `_zm_weap_tazer_knuckles`, `_zm_melee_weapon` and `_zm_weap_emp_bomb` are the reference.

- **Galvaknuckles** (Nuketown's and TranZit's `tazer_upgrade` wall, 6000 points): a wallbuy edit with that
  `"trigger"`. `_mapkit.gsc` sells them as retail sells the Bowie knife: their purchase animation, then they replace
  the knife and the Bowie knife (BO2's melee weapons replace each other: a Bowie knife bought later replaces them, and
  the Bowie wall sells again). 1500 melee damage (BO2's), the Bowie knife's sounds. The wall shows their world model
  (the layout says `tag_origin`, so a game without the mod loads no missing model; the script then removes the wall).
- **EMP grenade** (TranZit's box, `emp` edit): a special grenade, given in place of the Monkey Bombs and the reverse,
  thrown with the special grenade button. Where it goes off: BO1's blue power-up wave (BO2's effect is not in BO1);
  zombies within 600 units stand still 20 s or until hurt; players within 420 are shaken 2 s; perk machines within
  420 refuse purchases 90 s; a planted turbine within 420 goes back to its table (BO2 breaks it). Left out: the
  machines' lights going dark, Pack-a-Punch, the doors' local power, the traps, the Avogadro.
- The box's retail give (`treasure_chest_give_weapon`) goes on after the offhand override, which the Monkey Bomb skips
  with an early return: it switched the player to the grenade itself. MapKit switches him back to his gun.
- `bo2_layout.py build()` reused `name` in its loops: the layouts' `"name"` field held the last chest or Denizen name
  (unused at runtime). Fixed; the layouts otherwise differ by the new wall and the `emp` edit only.
- Checks. Linux self-tests (timescale 4, `fs_mods "mapkit bo2weapons"`): TranZit 315/7. Its new checks pass: the
  Galvaknuckles wall bought, the EMP given by the box with the gun kept in hand, thrown, a zombie 221 units away
  stunned and still 3 s later, the turbine 225 units away sent back to its table. The failures: `riser101`-`103` as
  before; the power switch's lever, which the draw now lays beside its table, where the client stops 85 units short of
  the table centre it walks to and never presses (the same check failed once on 2026-11-18 with another spot); the
  switch check that follows; `depot_baricade3` (a spawn draw). Nuketown 108/2 with the mod (the Galvaknuckles bought,
  then replaced by the Bowie knife); `riser7` and `riser16` fail with the mod stacked even on the old layout without
  the wall (107/2), and pass without it (109/0, the wall removed: `SKIP`). Windows client (`mapkit_galvashots 1`,
  screenshots): the knuckles drawn on BO1's hands through their purchase animation, the EMP from the box with the
  pistol kept in hand, thrown and gone off, the shake greying the view; no script error. The knuckles' swing is not
  seen on the shots taken during the melee presses.

### The Jet Gun and the shield (2026-11-18)

The fifth and last item of the same request. Both are TranZit buildables whose result is a BO2 weapon, from the
player's bo2weapons `mod.ff` like the Galvaknuckles (`tools/bo2/bo2_weapon.py` EXTRAS: the Jet Gun on Five's Death
Machine, which needs `--bo1-map` with Five's dump, the shield on the M1911; docs/BO2_WEAPONS.md). The decompiled
`zm_transit_buildables`, `_zm_weap_jetgun`, `_zm_weap_riotshield` and `_zm_riotshield` are the reference.
`games_mp.log` says `mapkit: Jet Gun on, shield on` or `not loaded`; without them both tables and their pieces are
left out.

- **Building** (`bo2_layout.py` BUILDABLES `jetgun`, `riotshield`): the Jet Gun's four pieces (wires, engine, gauges,
  handles: 12 spots across the map) and the shield's two (dolly, car door: 6 spots around the diner) lie on BO2's
  spots, named after the weapon (`jetgun_zm_<model>`). The buildable edit gets `"weapon"`; its `buildpart` `weapon`
  is the finished weapon BO2 lays on the table (`buildable_jetgun`, `buildable_riotshield`), drawn once built. The
  blockers mesh gains 22 groups and 6 images; the wires piece keeps no colour map (`battery_wires_col` is no DXT
  image in the dump, `bo2_mesh.py` leaves it out).
- **Taking**: any player holds use at the table to take one, again after losing it (BO2's tables are persistent).
  They go into BO1's own equipment slot (retail `_zombiemode_equipment`, Moon's hacker): action slot 1 with BO2's
  hint, one item at a time (taking the shield gives up the Jet Gun), taken at laststand, and `is_equipment` keeps the
  box, the wall buys and the perk machines from trading it away. Retail `is_limited_equipment` returns nothing on a
  map that never set `level._limited_equipment` (only Moon does), which stopped `equipment_take`: MapKit sets the
  empty list.
- **Jet Gun**: it spins up 0.6 s, then fires (shots of 0 damage). Its clip is the heat left, shown by the ammo
  counter: a round per 0.06 s of firing (BO2's 17 % a second), one back per second otherwise (BO2's `cooldownRate`).
  Every 0.25 s while it fires, the zombies in front within 128 units are gibbed and killed (a zombie clawing at the
  player stands beside the muzzle and below the eye, out of a cone from either), and those farther, up to 1024, in
  BO2's 0.7 cone from the eye and in sight, are pulled 48 units toward it where `PlayerPhysicsTrace` finds the way
  clear and a floor. `DamageConeTrace`, which BO2 and BO1's Thundergun use from the muzzle, gave 0 from the eye for
  every zombie in sight: `SightTracePassed` does it.
- **In play**: only a zombie out of the ground and in through its window is pulled. Retail marks a window's zombie
  (`completed_emerging_into_playable_area`) at the end of the window's traversal, which MapKit's windows never send,
  so `mapkit_zombie_in_play` also takes one that reached its window and walked 128 units away from it. The EMP's stun
  (above) used the retail flag alone and so never stunned a window's zombie; it uses the same test now. Fired dry, it blows up (the
  grenade explosion's sound, a shake) and the table gives another; BO2 scatters its pieces instead. Not done: its
  effects and sounds (BO1 has none; the Death Machine's spin plays), the power-ups it pulls in, reversing it.
- **Shield**: held, it stops the zombies' blows from in front (a player damage callback, `mapkit_shield_damage`);
  stowed, the blows from behind. Each blow stopped wears it by its damage, up to 2250 (BO2's hit points), then it
  breaks. Firing it (its melee animation) or a melee with it in hand bashes the zombies in front within 90 units:
  2500 damage, flung when killed, 100 more wear each. Not done: planting it, its damaged models, the model on the
  back.
- A function reached from a watch thread that ends on `<weapon>_taken` (`equipment_take` notifies it) runs in a thread
  of its own: the first overheat stopped half-way, the Jet Gun still in hand with an empty clip.
- `bo2_weapon.py` read BO2's localize dump as Latin-1, but OAT writes it in UTF-8: every accented name reached BO1 as
  two characters ("ExÃ©cuteur", the box weapons' too). It reads UTF-8 and writes Windows-1252 now.
- Checks. Windows client (`mapkit_galvashots 2`, screenshots): the Jet Gun drawn on BO1's hands, its heat going from
  100 to 49 in 4 s of firing; the shield in hand, its bash (fire and melee); the finished Jet Gun and shield on their
  tables; no script error; with `mapkit_jetdebug 1`, a zombie put in front of the player ground up. Linux
  self-tests (timescale 4, `fs_mods "mapkit bo2weapons"`): TranZit 333/4: all six pieces built, the Jet Gun taken,
  fired at a zombie 305 units away (pulled in and ground up, 12 % of its heat spent), fired dry (blew up), taken
  again; the shield taken, stopping a blow from in front and not one from behind, worn out (broke); its bash `SKIP`
  (no zombie in play came near in 120 s; the run before bashed one dead); the EMP stunned a zombie 222 units away.
  The four failures: `riser101`-`103` as before, `depot_baricade1` (a spawn draw). Other runs failed on the test
  client's walks: a power switch lever or a Jet Gun piece carried but never brought to its table (it stops short).
  Nuketown 109/1 (`riser7`, which fails with the mod stacked since the Galvaknuckles). With the previous `mod.ff`
  (no Jet Gun or shield): TranZit 316/6, both tables left out and their checks `SKIP`. win32-msvc builds (no C++
  change).

## What comes out of `zm_nuked`

With [OpenAssetTools](https://github.com/Laupetin/OpenAssetTools) 0.34.0 (GPL v3) and a world dumper written for it
(`tools/bo2/oat/`, the build and the commands are there):

| Part | Result |
|---|---|
| Zone contents | 6 100 assets: 1 711 xanim, 1 460 image, 1 399 material, 697 xmodel, 244 fx, 98 weapon, 42 script, one each of gfxworld, clipmap, comworld, gameworldmp, mapents |
| Entities (`mapents`) | 703 `node_pathnode`, 93 traversal pairs (`node_negotiation_begin/end`), 8 `initial_spawn_points`, 12 `info_volume` zones, 65 zone spawners (`<zone>_zone_spawners`), 8 `weapon_upgrade` wall buys, 6 `zombie_door`, 5 magic box spots, 169 script models, 33 trigger_multiple |
| World (`gfxworld`) | 195 091 vertices, 9 865 static surfaces, **131 032 triangles**, 464 materials, all 464 with their colour map extracted; 2 082 placed static models (name, origin, axes, scale) |
| Models and textures | 1 801 OBJ (all LODs) with `.mtl`, 1 419 DDS images; one HUD icon missing (`hud_mp_firerate_auto`) |
| Collision (`clipmap`) | 7 620 brushes (7 357 world, 263 of 140 submodels: doors, debris), 33 971 non-axial sides, 24 502 terrain triangles (128 of a submodel, 15 without a collision material), 766 collision materials |
| Not yet extracted | the collision of the 1 349 static models with collision (cars, fences: it comes from their xmodels), `comworld` lights (the primary spot lights: the houses' lamps), the T6 pathnode graph (`gameworldmp`; the nodes are also in the entities) |

The exported world and the entities share one frame: in a top-down plot the spawns, spawners, magic boxes and
pathnodes fall on the geometry (the two houses, the cul-de-sac, the garages). The world's bounding box (about 85 000
by 70 000 units) includes the distant backdrop; the playable area is about 5 000 units across.

The collision falls on the world in a top-down plot (houses, garages, the invisible walls at the edges); submodel
brushes sit around the origin, in their model's own space. Its content flags read from the collision material names are
BO1's bits: `0x1` solid, `0x10000` `clip_player`, `0x20000` `clip_ai`, `0x80` `clip_missile`, `0x2040` `clip_weapon`,
`0x200` `clip_vehicle`, `0x400` `clip_physics`, `0x800` sky, `0x8000000` detail; the 4 700 `0x2080` brushes are
`caulk` that only stops shots. BO1's player mask (`0x810011`, `g_active_mp.cpp`) and actor mask (`0x2820011`,
`actor_mp.cpp`) test the same bits, so the flags can be kept as they are.

The world vertex format is not described anywhere: it was worked out from the buffer (36 bytes, half-float UVs, indices
relative to each surface's `vertexDataOffset0`; details in `tools/bo2/oat/README.md`). A first guess (44 bytes,
global indices) gave coordinates of 3e38; the check that caught it (bounding box, edge lengths, UV ranges) is the one
to rerun on another map.

## The import through MapKit (state on 2026-11-09)

MapKit (`mods/mapkit/MAPKIT.md`) already had every gameplay piece Nuketown needs on an `"empty": true` base: `spawn`,
`zone`, `riser`, `node`, `mysterybox`, `wallbuy`, `perk`, `pap`. What it lacked was real geometry and traversals; its
own boxes are axial brushes (at most 512), drawn through the code mesh (16-bit indices: 65 536 vertices at most, when
Nuketown has about 195 000 world vertices before its props).

### Done: collision, layout, traversals (headless, Linux)

1. **Collision** (`collision` edit, `src/qcommon/cm_mapkit_import.cpp`). The BO2 clipMap dumped as `BO2COL2` (brushes
   with their planes, terrain triangles, each with its owner: world or submodel) is loaded into `cbrush_t`s like the
   retail ones: the world brushes (7 344 of 7 357: 13 cut, see 2.), and each world terrain triangle as a 16-unit prism
   under it (24 374). Every
   brush gets its corners (the points where three of its planes meet), filed in a 2D grid (583 x 523 cells). They join
   the world in `CM_Mapkit_TraceThrough`/`TestIn`/`PointContents`/`SightTrace` (traces) **and** in the physics'
   `colgeom_visitor_t::intersect_box` (`phys_traverse.cpp`), which serves player and actor movement, `Path_CanLinkNodes`
   and ragdolls through GJK (the reason for the corners). Without that second hook the player fell through the floor
   (z -131 000): player movement never runs the trace hooks. Submodel geometry is left out: it sits in its model's
   own space (BO2's 128-triangle `nodraw` sheet at z 0.2 over the whole map is one, which the player stood on until the
   owner was exported).
2. **Layout generator** (`tools/bo2/bo2_layout.py <dump> zm_nuked`): 10 zones (a zone's several volumes become one
   box), 1 spawn, 36 risers, 703 nodes and BO2's 5 254 links between them, 93 traversals, 102 barrier clips, the
   box, 7 wall buys, 4 perks and Pack-a-Punch. Findings it
   encodes:
   - **One spawn edit** (2026-11-13), at the centre of BO2's four start points in the first one's zone (the
     cul-de-sac street), facing their mean yaw. MapKit spreads a spawn edit over the four players, 40 units apart
     across its facing, and `_zombiemode`'s `coop_player_spawn_placement` puts player *i* on the *i*-th
     `initial_spawn_points` struct. BO2's 8 points are already one per player, so 8 edits gave 32 points and only the
     first edit's 4 were used. Their outer ones went into the fences and house walls ("Spawn point entity ... is in
     solid", 4 of the 32: player 4 of the first edit, at (57, -402), touched a house's player clip; (-310, -359) sat
     7 units inside `p6_zm_white_fence_64_03`). The doors' unlocked side still comes from all of BO2's start zones. The 6
     "Spawner ... is in solid" lines are BO2 riser spots below the ground or in a crater: the spawner only holds the
     zombie until `do_zombie_rise` moves it to its rise spot, and every one of the 36 risers delivers zombies
     (self-test).
   - BO2's entities are **not on the floor**: its compiler drops pathnodes into its own path data, and the entities
     keep them where the designer put them, 0 to 175 units above it. BO1 links nodes on the floor (`Path_CanLinkNodes`
     ends within 18 units of the target's height): with the raw heights, 0 of 703 nodes linked. Dropped onto the floor
     under them (brush planes and terrain, actor mask), they make 6 724 links.
   - A machine's `zm_random_machine` struct floats at z 2204 and targets its real spot (on the ground, with a yaw).
     Each spot holds a clip brush (`0x8030200`, the crate pile's footprint, larger than a BO1 machine), so the
     `collision` edit takes `cut` boxes (each with the brush's exact contents) and MapKit's machine brings its own clip.
     The machine and box face the first side with room in front of them.
   - BO2 lays a wall weapon along the wall: a BO1 wall buy faces BO2's yaw + 90 (true for all 7).
   - Traversals (`traverse` edit, `g_mapkit_path.cpp`): jump-downs map to the BO1 zombie animscript of the nearest
     height that the Five base loads (`zombie_jump_down_40/72/127/184`), mantles to MapKit's `mapkit_mantle` (below); the level
     loader compiles each one (`g_sp_levelstart.cpp`: a traversal's script is only loaded when a node names it). BO1
     zombies have one jump up, 222 units (`ai_zombie_jump_up_222`); BO2's 16 jump-ups (72 to 154 units: from the
     yards to both houses' upper floors) take MapKit's own `mapkit_jump_up` (`mods/mapkit/animscripts/traverse`),
     which plays it and moves the zombie each frame so that it follows the animation's own path. The rise is scaled
     to the end node's height, and the gap to the end node's spot is spread over the first 80% of the animation. The
     animation goes 32 units forward and 186 up, so the zombie lands on the end node, not in the ceiling. A first
     version corrected only the height, linearly over the first half (`teleportThreadEx`, as retail corrects a
     traverse's height). The jump into house 1's attic, `(-828, 398, 88) -> (-870, 301, 160)`, is 105 units long:
     its zombies landed 70 units short, in the attic's edge, and stayed there. The same correction also sank them
     under the floor while the animation crouched before its jump. Logged on that jump, every zombie now ends on the
     end node to a thousandth of a unit. BO2's mantles cross obstacles up to 84 units deep, where Five's wall hop (`zombie_mantle_over_40`'s
     animations) carries a zombie 63 to 70 units: `mapkit_mantle` plays the same hop and spreads the gap between where
     it ends and the end node over its frames (the actor is noclip while it traverses). BO1 has no crawl under a
     garage door: BO2's 2 garage-door pairs (flat) take the mantle.
   - **BO2's node graph** (`links` edit). The dump's `gameworldmp` asset holds the links BO2's compiler made
     (`GameWorldPathDumperT6`, `<map>.d3dbsp.paths.csv`: the 703 pathnodes in their entity order, at their placed
     origins, 5 254 links between them). The generator writes them as node pairs (`zm_nuked.links.txt`), and between
     two layout `node`s they are the graph instead of BO1's link test (which made 7 422 links and refused 624 of BO2's).
     BO1's test refused the terrain behind the houses: an actor walks no facet steeper than 45.6 degrees (normal z
     0.7, hard-coded for players and actors alike), and the north ditch and the slope behind house 1 have many at 46
     to 49. It also linked over a window: house 1's front window has a 37-unit sill of monster clip with debris in
     front, which BO1's test climbs as steps; zombies then walked onto the sill without the mantle and stuck in the
     opening.
   - **Barrier clips** (`box` edits, `"contents":"monsterclip"`: hidden, they stop actors only). Each thin monster
     clip that a mantle pair crosses (30 to 80 units tall, at most 48 deep: the fences and that sill) gets a clip
     72 units over its top, so that no zombie stands on it; a slanted one becomes 8-unit strips along its shape, and
     a strip within an actor's radius of a node is left out (102 boxes over 19 barriers, 3 strips left out).
3. **Headless self-test** (Linux build, `mapkit_selftest 1`, a test client in god mode, timescale 4; with the prop
   collision, the client put on the floor at each purchase, see below):

   | Check | Result |
   |---|---|
   | Zones | 10/10 PASS |
   | Pathnodes | 703/703 found by the actors' goal lookup; 0 bad nodes (10 moved 8 to 16 units out of solid, see below) |
   | Mystery box | PASS (FN FAL; RPK, Monkey Bomb, Winter's Howl, CZ75 on earlier runs) |
   | Perks | 4/4 PASS |
   | Wall buys | 7/7 PASS, upstairs in both houses included |
   | Pack-a-Punch | PASS (AK-74u upgraded, 5 000 points), upstairs in house 2 |
   | Risers | 36/36 PASS (a zombie climbs out and reaches the player), the north ditch's included |
   | Round | PASS; whole run: `mapkit_selftest DONE pass 62 fail 0` |

   The test client walks straight from node to node along `Path_FindPath`'s route. BO2's node graph goes round the
   props, but not by much: with the props solid for players, the client caught on house 2's back ramp
   (`p6_zm_nuked_zombie_ramp`) and its handrail posts and stayed on the deck, and every check after it failed. On a layout with a `collision` edit the self-test therefore puts the client on the floor at each machine
   and wall buy (`mapkit_test_place`) and lets it walk only the last step: the checks test the purchases and the
   zombies, not the walk. MapKit's own layouts keep walking, and `+set mapkit_test_walk 1` keeps it on an imported
   map. The test client also steers round what the node graph does not know (`SP_HeadlessAvoid`, `g_sp_client.cpp`:
   a player hull probed 32 units ahead from step height; when it hits, the nearest clear heading in 20-degree steps,
   keeping the side it found while blocked) and counts a goal it cannot reach exactly as reached once it stands still
   within 48 units. Walking all the way (`mapkit_test_walk 1`, before the wall fix below) it bought the box, 3 of 4
   perks and 6 of 7 wall buys; Juggernog (house 2's backyard), the M16 and Pack-a-Punch (house 2's upper floor) had
   no route in the node graph (BO2 reaches them with mantles and `zm_jump_up` traversals).

   Rerun at 6472db7: `pass 36 fail 26`, the client stuck by and on house 2. The test client's walk
   (`SP_HeadlessWalk`, `g_sp_client.cpp`) then took these fixes:
   - `Path_FindPath` without negotiation links fails as soon as its best route has one; it does not look for another.
     The client then walked straight at the goal into a wall. It now plans with the traversals when it must.
   - Across a traversal (or the plain link the graph also holds back from its end to its begin, the fence by
     Juggernog) the client walks at the end node and jumps, which takes it over low fences and off ledges. After 3
     seconds short of the end (a zombie's jump up to an upper floor) the harness carries it there.
   - A client no node sees within 192 units gets no path. It plans from the last node it reached instead, or heads
     back to that node. Back there with still no path (a carry over a jump up left it in house 1's attic), it is
     carried to the goal after 10 seconds.
   - A walk that has not covered 32 units in 3 seconds sidesteps. After 10 seconds heading for one node, the harness
     carries the client to the node after it. Zombies climb debris piles a player cannot, since props collide with
     players only.
   - A point counts as reached only within 48 units of height, and purchases wait 35 seconds longer when walking
     (`mapkit_test_wait`): the box to Juggernog is about 3 500 units.
   - A riser check starts its 90 seconds once the walking client reaches its stand point (60 seconds at most).

   The carries need `bo1_testclient_carry 1`, which the self-test sets on another game's map only: a MapKit layout's
   walk must make it on its own. Every carry is logged (`bo1_testclient: ... carried over traversal`,
   `... carried past a link it could not walk`, `... carried to the goal with no path`), and a blocked client every 2
   seconds (`... stuck N ms at`).

   With these fixes and the jump-up fix (Traversals, above: house 1's attic), a full walking run gives
   `mapkit_selftest DONE pass 62 fail 0`. The client was carried 31 times over traversals, 50 times past links and 9
   times to a goal. Before the attic fix the walk gave `pass 58` to `pass 60`, with fails that changed from run to
   run: risers, Pack-a-Punch (bought too late) or two wall buys. The default mode places the client and stays the
   reference: `pass 62 fail 0` on the same build with no carry, and `entrances_example` `pass 6 fail 0` with no
   carry.

   Pack-a-Punch took three fixes, each found by logging the engine's use search (`Player_GetUseList`):
   - BO2's machine yaws are rounded to right angles (`bo2_layout.py`, at most 15 degrees on Nuketown). MapKit's
     machine clip is the axial box around the turned model; at Pack-a-Punch's 105 degrees it reached 37 units in
     front, over the spot a player stands to use it, and the client put there was stuck in it.
   - Wall prisms go behind the wall (`cm_mapkit_import.cpp`). BO2 winds its triangles clockwise (10 983 of 13 089
     near-horizontal ones give a downward cross product); the loader turned only near-horizontal ones up, so a wall's
     16-unit prism came out of its visible face: house 2's walls stood 16 units into its rooms, and the use search's
     sight trace (mask `0x11`) from the player's eye to the trigger hit the wall behind Pack-a-Punch. Steep triangles
     now take BO2's front; the bad nodes went from 15 to 9 and the goal lookup from 692 to 694 nodes.
   - The check looks at the trigger's origin: Pack-a-Punch's trigger requires the look-at
     (`UseTriggerRequireLookAt`, a dot of 0.76 with the bounds centre, which for a `trigger_radius_use` is its
     origin).

   Risers went from 12 to 36 of 36, in four steps:
   - **Where the client stands.** A riser rises only while its zone is active, and with no adjacent zones (Nuketown
     has no doors, the layout none) that means occupied: `do_zombie_rise` takes a random spot of the spawner's own
     zone (`zone_init`: `rise_locations`). BO2 scatters each zone's risers round the map edge: 30 of the 36 lie in no
     zone volume (`riser17` belongs to house 1's backyard and stands in the cul-de-sac). The check stood 192 units in
     front of the riser, mostly outside every volume, where the zone manager falls back to the first zone; and at the
     riser's height, under a slope, `riser1`'s zombie reached the client's spot 74 units above it. On an imported map
     the client now stands on a plain pathnode of the riser's zone: the nearest one (height counted 4 times: a zone
     box, the union of BO2's volumes, also holds the upper floors) that `FindPath` reaches from the riser; nearer
     nodes without a path are logged (house 1's backyard pocket at (-921, 1024), house 2's upper floor from
     `riser8`).
   - **One riser at a time.** With 4 to 6 risers a zone, one could go unpicked for 90 s (`riser10`: its zone's 5
     zombies came out of `riser11` 4 times, `riser3` once). For its check the zone offers only that riser, restored
     afterwards.
   - **Spots that hold the client.** House 1's stairs carry actors but not players: the client put on their nodes
     (z 107 to 131) fell to the ground floor, out of the upper floor's zone. Once put down it must still be in the
     zone, or a node 96 units from every spot tried is taken (6 tries).
   - **Jump-ups** (above): the node graph led from the upper floors to the yards only (one-way jump-downs): from the
     east yard (`riser8`), 272 nodes could not be reached, the upper floors among them; with the jump-ups 226, the
     rest lying behind mantles that BO2 crosses one way only, inwards.

   The north ditch (around (700..1500, 1150..1450), `riser28` and `riser29`) had no node graph: `Path_CanLinkNodes`
   walks an actor capsule from each node, and every step hit a terrain facet steeper than an actor walks (hit entity
   1022, the world). Those two checks passed only when a zombie happened to climb the slope without a path. With
   BO2's graph (above) the ditch is linked, and in the last run 4 zombies of `riser28` and the one of `riser29` walked
   up it to the player. With BO2's graph `riser7` failed instead: its zombies stood on house 1's window sill (the
   barrier clips fixed it).

   **Nodes in solid.** 10 layout nodes failed the engine's drop (`node_droptofloor`): the actor capsule, put down on
   the floor, overlapped the world by a fraction of a unit (the GJK trace reports a negative distance) at terrain
   creases, slopes and walls whose 16-unit prisms stand out of a thin wall's far side; an offline box test found
   nothing at 6 of them. `G_Mapkit_LinkPathnodes` now tries a bad layout node again 8 then 16 units around (8
   directions each), as a designer would nudge it, and rebuilds the empty base's node tree if one moved: all 10 found
   a spot (`mapkit: node N in solid at (...), moved to (...)`).

### Not done

- **Drawing (2026-11-09).** `tools/bo2/bo2_mesh.py` cuts the world OBJ into 258 chunks (512 units in the playable
  area, 8 192 beyond), one surface per material (2 088 surfaces, 128 847 triangles, normals smoothed over shared
  vertices), writes each prop model with its LODs (331 models, 700 515 triangles over all LODs, distances from OAT's
  xmodel JSON) and its 2 081 placements, and converts the 254 colour maps used to IW images (DXT1/3/5 kept as they
  are, mips smallest first). The `mesh` edit (`src/gfx_d3d/r_mapkit_mesh.cpp`) builds one rigid XModel per chunk and
  per prop model at the end of `R_FinishLoadingModels` (buffers made by `_XModelOptimize` on the render thread) and
  adds them every frame with `R_FilterXModelIntoScene`, as the skybox model is added (a prop past its last LOD's
  distance x 1.5 is not added); none of them is in the asset database. Each colour map gets one material: a copy of
  `mc/rus_metal_panel03` (a model material, the 32-byte packed vertex), or of the alpha-tested leaf
  `mc/t5_foliage_tree_sorbus_leaf01_static` for the BO2 materials that test or blend alpha (from OAT's material
  JSON; decals and glass since 2026-11-10, below), with that colour map, the flat normal map and a black specular map, linked into the database
  (`DB_AddXAsset`) so that the material sort gives it a sorted index. Screenshots (GL backend, llvmpipe) show the
  cul-de-sac, the burnt sidings, fences, hedges, rocks, cars, power poles and the mushroom cloud of the backdrop.
  - The colour map is the base layer's: a BO2 material can hold several colour-map samplers (embers, thermal,
    reveal, specular), so OAT's dumper takes the sampler named `colorMap`, `Diffuse_Map`, `Color_Map` or
    `radiantDiffuseMap` first (the first version took the first one: red ember maps on the walls).
  - **Sky.** The worldspawn's `skyboxmodel` (`skybox_dlc0_zm_nuketown`, a 448-triangle dome) is written as one more
    prop model, its materials flagged as sky; its cube map (`skybox_zm_nuked_ft`, DXT5, 512 pixels, six faces, IWI flag
    4) gets a copy of Five's `mc/mtl_skybox_sp_frontend` (technique `skycubemaphdr`: the cube map sampled by view
    direction, the `skyBase` of the edit). The engine draws it centred on the viewer, as `R_AddSkyboxModel` places a
    map's own skybox. The dump's winding faces outwards, so the dome was culled from inside: the tool writes its
    triangles both ways round.
  - **Windows (2026-11-10).** The first Windows client crashed at Nuketown's first frame
    (`R_StreamUpdate_AddDynamicXModelDistance`). The image streamer indexes each scene model by its place in the
    asset database's XModel pool (`DB_GetXModelIndex`), and these models are outside it: the pointer difference was
    taken as an index, which wrote far outside the streamer's arrays. Linux had shown nothing, because its runs were
    headless with no renderer. The streamer now skips a model outside the pool (`DB_IsXModelInPool`), since their
    images are loaded whole, not streamed. A Windows client (`tools/headless.ps1 -Client`, D3D9) then draws the map and
    plays on to its scheduled quit (219 s with the load), with a normal exit.
  - The scene takes 1 024 models a frame (`GfxScene::sceneModel`). The chunks and the visible props go past it, and
    `R_AllocSceneModel` drops the rest ("too many existing models (more than 1024)"). The props are added nearest
    first, sorted each frame by the distance to their bounding sphere, so the dropped ones are the farthest. The sort
    uses the sphere, not the origin, because a prop's origin can lie far from its geometry. The clock tower's origin is
    1 000 units off, and the tower was dropped in front of the viewer, leaving its clock hanging in the sky. A first
    version added the props within 1 024 units first but in file order, and in front of a house the budget ran out
    before the doors, which `bo2_mesh.py` writes last.
  - **A larger scene (2026-11-10, asked by the user).** `r_mod_sceneModels` (1024 to 4096, default 1024, ZmClient's
    Lancement view: "Modèles affichés par image") raises that budget. The renderer frustum-culls before it counts
    (camera and sun-shadow views), so the 1 024 were all in view: from the street, 2 092 to 2 099 models are wanted a
    frame, and at 4096 the clock and the distant mountain come back.
    - The next limit was the per-frame surface buffer (`GfxBackEndData::surfsBuffer`). A draw surface's 16-bit
      `objectId` addresses it in 4-byte units, so it holds 256 KB. At 1 024 models, Nuketown already filled 220 to
      231 KB of it; at 4096 it wanted 305 to 313 KB a frame and dropped the rest, zombies included, since DObjs share
      the buffer.
    - On 64-bit every entry of that buffer is a multiple of 8 bytes, so the unit is now `R_SURF_UNIT` (8 on 64-bit,
      retail's 4 on 32-bit) and the buffer 512 KB. The hidden-surface marker (`-3`) takes one unit too.
    - Each model past retail's also needs a model lighting entry: ZmClient passes `r_mod_modelLightingEntries` at the
      count + 1 024 (5 120 at 4096: none refused; with the retail 1 024, the test run logged one `MODEL_LIGHTING_EXHAUSTED`).
  - **Props drawn inside out (fixed 2026-11-10).** The engine draws a triangle whose right-hand normal points away
    from the viewer, BO2's own winding, which the world OBJ keeps. `bo2_mesh.py` wound the props the other way, with
    their right-hand normals out, as `bo2_props_collision.py` needs for its prisms. Every prop then showed its back
    faces. The clock's face turned to the tower with its numbers mirrored, signs and the garage door were missing,
    and inner faces showed through walls. `read_lods` now reverses the props' triangles for drawing only.
  - **Wall buys.** Retail `init_weapon_upgrade` hides a wall buy's weapon model until its first purchase, since a BO1
    map shows the weapon with a chalk drawing. Nuketown has no such drawing (BO2 draws its chalk by script), so on
    another game's map MapKit shows the models from the start (`mapkit_show_wallbuys`, `_mapkit.gsc`).
  - **Doors and debris (2026-11-10).** A first version left them out, wrongly. BO2 has 6 doors and 5 debris on
    Nuketown, each a group of `zombie_door` / `zombie_debris` triggers that share a target: the house fronts (750),
    the back doors and the upper floor door (1000), the stairs' debris (1000 and 1250), the truck (3000) and the ammo
    room (3000).
    - `bo2_layout.py` makes each group a MapKit `door` or `debris` with BO2's cost. Its box is the targeted brush
      models' (the door panel, the debris clip), placed by entity origin plus submodel bounds from the collision
      dump. Its zones come from the `script_flag` (`culdesac_2_openhouse2_f1`; `culdesac` is the nearer of the
      yellow and green zones). A walk from the start zones gives the one it unlocks.
    - `bo2_mesh.py` writes the group's script models (BO2's white and brown doors, couches, chairs, armoires) as
      props, plus a table of groups at the end of the file. The engine draws them until the purchase
      (`CM_Mapkit_EditShown`), in place of the kit's box.
    - The self-test buys all 11 and checks each zone's unlock. Its `door_graph` check counts the active links through
      the doorway on an imported map: the houses also join the street through their windows.
    - A cost retail has no hint for (its `default_buy_debris_<cost>` and `default_buy_door_<cost>` stop at 2000) showed
      "UNDEFINED!! PLEASE SET THE SCRIPT_HINT ON THE ENT PROPERLY!" on Nuketown's two 3000 debris (the truck and the
      ammo room). No localized string takes the cost as a parameter, so `_mapkit.gsc` (`mapkit_blocker_hints`)
      registers the missing ones with retail's text, unlocalized: "Hold [use] to Clear Debris [Cost: 3000]".
  - **Mystery box (2026-11-10, reported by the user).** The first layout kept only the start chest. With one chest,
    retail's `treasure_chest_init` never moves the box and never shows its beam. `bo2_layout.py` now writes BO2's five
    chest locations, "start" on its two start chests (retail picks one of them). Retail's beam (`lght_marker`, Five's
    `fx_zombie_coast_marker`) is a faint additive column made for a dark sky, and hardly shows over Nuketown's
    daylight sky. So on an imported map `_mapkit.gsc` (`mapkit_pandora_fx`, as `level.pandora_fx_func`) stacks the
    same effect, two on the chest and two every 1 000 units up to 5 000, deleted with the retail light when the box
    moves. Checked on D3D9 client screenshots: the beam stands over the box from across the map (about 2 900 units
    away).
  - **Machine clips (2026-11-10, reported by the user: "I walk through the mystery box").** MapKit puts a hidden
    player and monster clip around each box, perk machine and Pack-a-Punch (`CM_Mapkit_AddMachineClips`), but its
    table held 256 edits: on Nuketown (about 980 edits) the boxes, perks and Pack-a-Punch come past edit 850 and had
    none. It now holds one per edit (`MK_MAX_SPOTS` = `MK_MAX_EDITS`, 1 024).
  - **Baked light on the props (2026-11-10).** BO2 bakes the light of a static model placement into one colour per
    vertex (`GfxStaticModelDrawInst::lmapVertexInfo`, per LOD). The OAT dumper writes them to
    `<map>.d3dbsp.smodellight.bin` (`BO2SMLT1`: per placement, its LODs' colours; per model, its LODs' vertex
    positions in the same order, since the OBJ export reorders and splits vertices). `bo2_mesh.py` finds each OBJ
    vertex's colour by its position (exact to 1/100 unit for 97 %, else the nearest within 1 unit), gives each lit
    placement its own copy of the model, and writes `BO2MESH5`: a `u32` colour after each vertex. The engine puts it in
    the packed vertex colour, which BO1's model shaders multiply with the colour map.
    - The first version read the stored colour as `0xAARRGGBB`, doubled RGB by eye and dropped the alpha. BO2's lit
      static model shaders (`lprobe` techniques, read with `fxc /dumpbin`) say otherwise, and it was corrected on
      2026-11-10 (below).
    - 716 of the 2 082 placements carry colours. The other 1 366 have none (BO2 lights them from its light grid) and
      stay white.
    - Side by side with the unlit mesh (D3D9, same views): the truck and the couch are no longer washed out, the
      street's rubble stands out, and the freezer in house 1 is green again.
    - Cost: 333 prop models become 898 (a model whose placements are all lit copies is left out), the mesh's vertices
      go from 0.93 M to 1.84 M (+29 MB at 32 bytes each) and the file from 35 to 78 MB. The number of props drawn, and
      so the 1 024-model scene budget, does not change.
  - **The world's lightmaps (2026-11-10, asked by the user).** The world surfaces get BO2's own light as vertex
    colours (`tools/bo2/bo2_worldlight.py`, called by `bo2_mesh.py`).
    - The pixels are in the fastfile after all: three uncompressed RGBA images (`*lightmap0..2_secondary`, 2048, 1024
      and 512 wide, 3072 high), each three slices of 1 024 rows stacked. A world vertex is 36 bytes: xyz, binormal
      sign, colour, texCoord (2 halves), two packed 10:10:10 vectors, then lmapCoord as two 16-bit unorms (u low,
      v high), over one slice. The OAT dumper writes them per OBJ vertex (`worldlight.bin`) with each surface's
      lightmap and primary light, and the sun (`worldlight.txt`).
    - The decoding is BO2's own: its `lmap` pixel shaders, disassembled with `fxc /dumpbin`, light a pixel with
      `A + B * saturate(dot(dir, N)) + vis * sunDiffuse * saturate(dot(sunDir, N))`, where `A` and `B` are slices 0
      and 1 as `rgb / a`, `dir` is slice 2's `rgb * 2 - 1` and `vis` its alpha (the sun's baked visibility, the shadow
      map taking over near the viewer), then output `sqrt(albedo^2 * light * exposure)`. On Nuketown the sun is
      `(4.78, 11.64, 15)` from `(-0.41, -0.35, 0.84)`, and sunlit ground gets about `(8.9, 15.5, 18.8)`.
    - BO1's model shaders multiply the colour map by the vertex colour, so the colour is `sqrt(light / reference)`,
      the reference being the 75th percentile of the sunlit corners: sunlit ground looks as before, the shade
      darkens and takes BO2's bounce (green in the green house's kitchen). `LIGHT_FLOOR` (0.12) keeps the darkest
      surfaces from black.
    - A vertex colour only follows the lightmap at the vertices, so a triangle is split where the light at its edge
      midpoints or centre differs from the corners' by more than 0.06, down to 16 units (about one texel): 123 099
      splits, 131 032 triangles become 252 000 (175 000 vertices become 303 000).
    - Checked on D3D9 client screenshots before and after, same views: shaded façades, eaves, sidewalks and rocks,
      the houses' interiors darker and tinted; no crack along the split edges.
    - **The lamps (2026-11-10, asked by the user).** A surface's primary light can also be one of `comworld`'s:
      Nuketown has 4 spots over the street (type 2, `white_light`) and 12 lamps in and around the houses (type 5,
      `white_light_cube`, a cube shadow map: omni lights), green, orange and blue. OAT's new
      `ComWorldLightsDumperT6` writes them (`<map>.d3dbsp.lights.csv`), and the bake adds, for a surface whose
      primary light is one of them, `vis * colour * saturate(dot(L, N)) * min(dAttenuation / d^2, 1) * cone *
      window` (L toward the light, `window` = `(1 - (d / radius)^2)^2`, a cone only for the spots).
    - A spot's `dir` points from the lit area to the light, as the sun's does: every spot's surfaces lie at cos
      -0.97 to -0.82 of it. Read the other way, the cone cut off almost every lamp. The lamps' surfaces lie on every
      side of theirs, so they get no cone.
    - BO2 shapes the cone and the end of the range with constants (`lightFallOffA/B`, an attenuation texture) the
      bake approximates with those curves. Checked on D3D9 screenshots before and after: house 1's living room and
      stairs lit, its kitchen ceiling green from the green lamps, house 2's upper floor warm.
  - **The props' light as BO2 computes it (2026-11-10, asked by the user).** The vertex shader of a lit static model
    takes the baked colour `c` as an indirect light `32 * c.rgb^2` (divided by the light grid's value at the vertex
    normal, which the pixel shader multiplies back at the pixel's normal, so about 1), and passes `c.a` to the pixel
    shader as the sun's visibility: `L = 32 * c.rgb^2 + c.a * sunDiffuse * saturate(dot(sunDir, N))`, then
    `sqrt(albedo^2 * L * exposure)` as the world. `bo2_mesh.py` (`prop_light`) now computes that `L` with each
    vertex's normal turned by its placement, and turns it into a colour with the world's reference and floor
    (`WorldLight.colour`): props and world share one exposure, and `LIGHT_SCALE` is gone.
    - The bytes are R, G, B, A in memory (`0xAABBGGRR` as a `u32`), not `0xAARRGGBB`: the first version swapped red
      and blue. Measured against the world's lightmaps, whose indirect light in the shade is red-poor (R / G 0.75,
      B / G 1.03): the props' low byte gives R / G 0.73 and the third byte B / G 1.03. Sunlit props (alpha above 220)
      get an indirect `(4.5, 5.5, 5.9)` against the world's `(2.6, 3.5, 3.6)`: the same scale.
    - What stays approximate: the reference itself (the 75th percentile of the sunlit ground maps to the colour map
      as it is). BO2 then applies its exposure, tone curve and colour grading, which MapKit does not reproduce.
  - **Decals and glass (2026-11-10, asked by the user).** `bo2_mesh.py` (`blend_flags`) reads the state of each
    material's lit pass. BO2 blends almost all its see-through materials (fences, leaves, overlays), after a depth
    prepass that writes their depth first; BO1 has no such pass for these models, and a hedge blended without it
    would draw its leaves out of order. So:
    - a layer that lies on another surface (a depth offset on the lit pass and a decal sort below BO2's 40, or a decal
      or overlay name: `decal_`, `_dec`, `_blend`) is a decal, flag 4: 45 materials on Nuketown (cracks, rugs,
      burnt floors, radiation puddles, dirt and ash overlays). The engine draws it with a copy of the blended base
      (`blendBase`, default `mc/global_glass`: premultiplied blend, alpha above 0, no depth write) with the decal
      depth offset added to its states (`loadBits[1]` 0x10, `R_ForceSetPolygonOffset`) and sort key 29, the sort of
      Five's own blended model decal (`mc/mtl_veh_jet_f4_decals`), between the opaque materials and the glass (43).
      Five has no model decal to copy as it is: its decals either test alpha or carry samplers of their own;
    - six decals multiply the colour under them (`zero / srccolor`: burn stains, the blast crater, a wall fillet, red
      numbers). No base material multiplies, so the tool converts their colour map to DXT5 black with alpha
      `1 - luminance`: blended over the surface it gives `dst * luminance`, the same darkening for grey maps (the red
      numbers lose their red);
    - glass, blended but not a decal, is flag 8 and draws with the blended base: Nuketown's broken glass and two
      character materials;
    - every other blended or alpha-tested material stays alpha tested (36 drawn on Nuketown).
    Decals that overlap draw in the order of their materials, not BO2's sort keys.
    - Checked on D3D9 client screenshots before and after, same views: the props lose their yellow cast (the truck is
      grey, the couch beige, the kitchen's stove and freezer green), the green radiation puddles lie on house 1's
      floors, the street keeps its cracks, the garage door its burns, the mountains of the backdrop (a decal-sorted
      BO2 material, `mc/mtl_p6_zm_vista_mountain`, whose colour map the first versions left out) stand behind the
      clock, and the burnt walls and floors drawn as decals show no holes. All 274 colour maps load.
  - **`vid_restart` (2026-11-10).** The mesh's vertex and index buffers are `D3DPOOL_DEFAULT` ones, which a device
    Reset needs released: `vid_restart` after a mode change, or a full-screen window losing its device. The engine
    releases the database's models (`R_ReleaseLostDeviceAssets2`) and rebuilds them (`R_RecoverLostDevice`), but
    these models are outside the database, so the Reset was attempted with them alive. Both functions now call
    `R_Mapkit_ReleaseMeshBuffers` / `R_Mapkit_RestoreMeshBuffers` (`mapkit: mesh buffers rebuilt on the reset device`
    in the console). Checked with two `vid_restart`s after a `r_vsync` change on the D3D9 client: both recover the
    device, rebuild the buffers (0 surfaces without) and draw the map as before. That test client runs a D3D9Ex device
    (`bo1_headless_client`), whose Reset does not require the default pool released, so it could not show the
    failure a plain D3D9 device would have had: the fix follows D3D9's rule, not an observed crash.
- **Prop collision (2026-11-09).** BO2's clipMap lists the 1 349 static models that collide (`smodelcoll.csv`, written
  by the OAT dumper: model, contents, origin, inverse scaled axes; every row matches a drawn placement by name and
  origin). `tools/bo2/bo2_props_collision.py` adds them to the `BO2COL2` file as world brushes, from each model's
  collision LOD: a model at most 160 units across becomes an oriented box around it (865), a larger one keeps its
  triangles as 16-unit prisms (31 465: ramps, roofs, rock piles stay their shape). Only props inside the zones (64
  units around them) are kept (380 lie past the invisible walls), and lights are left out (27: hanging lamps caught
  the player's head). Their contents are BO1's player clip plus the shot-stopping bits (`0x10000|0x2000|0x80`): they
  stop players and bullets but not actors, whose mask (`0x2820011`) leaves the player clip out. Blocking actors too
  put 43 nodes "in solid" (on rock piles, under lamps), changed the node links and dropped the self-test from 31 to 16
  passes; with player clip the graph is the clipMap's again (6 722 links, 15 bad nodes), and BO2's own nodes already
  go round its props.
- Windows checks (`tools/headless.ps1`), and the Switch.
- Dog rounds (Five's dogs are not converted), BO2's own mechanics (the bus, buildables, Who's Who...), its characters
  and animations (T6 skeletons and xanims), its sounds and its dynamic lights. The game is BO1's zombies on Nuketown's
  geometry.

### TranZit (`zm_transit`, 2026-11-10)

TranZit goes through the same tools, with what its size and its bus needed:

- **Dump.** 449 of its 511 prop models live in the streamed `zm_transit_gump_*` zones, and the map's XModels are
  references named `,<name>`. The OAT dumper drops the comma (also in `smodelcoll.csv` and `smodellight.bin`), and the
  gump dumps are merged into the map's (`rsync -a --ignore-existing zm_transit_gump_*/{xmodel,model_export,images,materials}/`).
  Its vertex buffer ends 20 bytes past a whole vertex: only the counted vertices must fit.
- **Scale.** 26 000 x 18 000 units, 5 350 pathnodes, 40 703 links, about 45 zones, 424 000 collision brushes with
  70 000 terrain prisms, 690 000 world triangles and 10 866 props. MapKit's tables grew (JSON values 65 536, strings
  1 MB, edits 8 192, boxes 2 048, brush models 512, marks 2 048, extra links 65 536). BO1's node visibility tests
  every node pair at load: on 5 350 nodes it never finished. A layout with more than 2 000 nodes gets
  `"nodeVisRange": 2048`, which skips the pairs farther apart (`Path_BuildNodeVis`), and the map loads in about
  4.5 minutes on the Linux headless build. MapKit's node link pool held 32 768 links: TranZit needs 42 255, and the
  nodes past the limit silently got none (1 466, found through two doors whose doorway no link crossed). It holds
  131 072 now and logs its use (`mapkit: link pool N of 131072 used`) or its overflow.
- **A crash.** A player among the power station's dense terrain prisms touched more than 128 planes at once:
  `gjk_push_out` wrote through the NULL of the full plane array (segfault on the Linux server). The extra contacts are
  left out now (`bg_slidemove.cpp`, `add_hit_info`).
- **Game modes.** One map holds TranZit's classic mode and the Survival and Grief locations (town, farm, depot). Its
  `zm_perk_machine` structs and power switch carry the gametype in `script_string` / `script_gameobjectname`, its
  wall buys in `script_noteworthy` (`zrace_town`, `zstandard_farm, zgrief_farm`...): `bo2_layout.py` keeps the
  classic ones (and the wall buys without one). The wall buy on the bus (`bus_buyable_weapon1`) is left out: it would
  stay behind when the bus drives off. Double Tap stands in the barn's loft, whose floor is a clip brush only: a
  machine stands on the walkable floor when BO2's spot is on it and the solid floor is far below.
- **Doors.** 15 doors: their `script_flag` often names no zone, so a blocker takes the two zones beside its box.
  `local_electric_door` doors are power doors (MapKit `"power": 1`, cost 0): they open when the power comes on.
  Two (`pf1766_auto2357`, `pf1766_auto2358`) have no zone beside them and are left out.
- **Machines and power.** Juggernog, Quick Revive, Speed Cola, Double Tap, Pack-a-Punch (the buildable one's spot)
  and the power switch at the classic spot, no building needed. Stamin-Up's machine and bottle come with another
  map's zone (`bo1_mod_zones zombie_cosmodrome`): MapKit places it only when a loaded zone holds
  `zombie_perk_bottle_marathon` (`bo1_mapkit_weaponloaded`); ZmClient sets that zone for TranZit. Tombstone has no
  BO1 machine. BO1 sells a player 4 perks: with Stamin-Up, a fifth machine stays refused until a perk is lost (the
  self-test drops one before buying the next).
- **The bus.** BO2's bus is a `script_vehicle` driven along `info_vehicle_node` chains. Here it is a MapKit `bus`
  edit (`mods/mapkit/MAPKIT.md`): the loop is the chain through the depot's stop node (278 points), the stops are the
  nodes whose `script_notify` is `reached_stop_point` (depot, diner, farm, power station, town), with BO2's
  `script_float` as the wait. Its collision is ten layout brush models (floor, a step outside each door, walls with
  the door openings, roof) that `_mapkit.gsc` moves point to point at 440 units a second; a player standing on the
  floor rides as on Five's elevators. The mesh edit draws the bus model (`bo2_mesh.py --mover`) on the floor's
  brush model (`R_Mapkit_SetMoverPose`, from `CG_ScriptMover`). The 23 pathnodes inside and on the parked bus are
  left out (they would be a floating island), and the layout's brush models are off while MapKit drops its nodes,
  so the nodes beside the parked bus are not left in solid. The loop's points stand on what an actor walks on:
  on the solid brushes alone, five points by the diner fell 2 400 units under the road (terrain is prisms) and the
  bus dove with them, leaving its rider behind. The front wall stands behind the windshield (model x 368), not at the
  bumper (449): a rider pushed forward had the eye past the glass, where the one-sided faces showed no bus.
  The engine carries a rider along a mover's translation but not around its turns: the rider slides until a wall
  holds it, then stays there. The self-test's `bus` check boards the client at the depot, on the floor's centre, and
  finds it on the floor at the diner. On a Windows client (D3D9, `mapkit_bus_log 1` logs the floor and the players
  at every point) the player rode a whole loop and on, 8 units over the floor at every point, against the rear wall
  after the first sharp turn, the bus drawn around them. Zombies do not board it, it has no doors, horn, lights or
  driver, and it does not wait for the players: a player who misses it waits a loop (4 minutes 55).
- **Self-test** (Linux headless, `bo1_mod_zones zombie_cosmodrome`, `mapkit_test_risers riser1,riser9`, the run
  folder holding Ascension's converted zone): `pass 113 fail 0`: the 15 doors (10 bought, their zones unlocked, 5
  opened by the power), the box, the five machines, Pack-a-Punch, the six wall buys, the power switch, two risers
  and the bus ride. `pow_door_rr` is a SKIP: BO2's graph reaches its room by stairs below the doorway, so no link crosses
  it.
- **Not done.** The props are unlit (TranZit's placements carry no `smodellight` colours), the fog and the lava,
  the Avogadro and the other buildables (the bank and the bus's doors and calls came on 2026-11-15: "TranZit's bus and
  bank" below; the power switch, Pack-a-Punch and turbine buildables, the Bowie knife, the claymores and simplified
  Denizens on 2026-11-18: "Nuketown's falling machines, TranZit's buildables and Denizens" below; the Galvaknuckles,
  the EMP grenade, the Jet Gun and the shield the same day, from the bo2weapons mod).

#### The user's first TranZit run (2026-11-11)

- **A bridge walked on but not drawn, doors not drawn.** They are BO2 brush models (`script_brushmodel`: the two
  `bridge_section`s, the panels of `auto2389`, `pow_door_rr`, `pf1766_auto2355`...), whose surfaces the world OBJ
  never held (it has the static surfaces only). The OAT dumper writes `<map>.d3dbsp.bmodels.obj` (one group per
  `GfxWorld::models[m]`, positions relative to the entity's origin) and `bo2_mesh.py` makes each a prop model: in
  its blocker's group for a door, standing for the bridge (`STANDING_BMODELS`).
- **Huts a player could not enter, stairs that only went down.** `bo2_props_collision.py` made every prop up to 160
  units across one oriented box: a door frame (`p_cub_door_wood_frame01`) was a solid box across its doorway, the
  power station's stairs (126 x 151 x 82, ten 8-unit steps) one box 82 units high that a player dropped off and never
  climbed. A small prop keeps its triangles when a player could pass through it (a quarter of the lines across its
  thinnest axis hit nothing) or climb it (4 upward faces each within a step of the next): TranZit 527 000 prisms
  instead of 400 000, Nuketown 76 000 instead of 31 000.
- **The bus drove backwards, its doors shut.** Its brush models spawn with angles 0 while the loop starts at 179.5
  degrees: the mesh edit's `moverYaw` turns the model by that heading. The doors are folding panels in the model's
  exterior surfaces (the OBJ has no bone weights): `bo2_mesh.py` cuts the triangles inside the two door openings
  (`MOVER_HOLES`).
- **Barricades not rebuildable.** BO2's 38 `zbarrier_zmcore_BasicWoodBarrier` become MapKit windows (Five's prefab:
  six boards zombies tear off and players rebuild). A zbarrier stands about 40 units in front of its wall: the window
  goes on the wall, found by walking in along its yaw (placed at the zbarrier, its inner traversal node fell into the
  wall), the mantle BO2's barricade traversal was is left out, and a window no BO2 spawner feeds gets a spawner 128
  units outside it (7). Five's boards are narrower than BO2's openings and washed out by the lighting there. Self-test:
  `pass 185 fail 12`: 33 of the 38 windows had a zombie tear the boards, climb in and reach the player; the others
  are an upper-floor window of the farmhouse (its outside is a roof), windows a spawner's path does not reach, and
  zones opened by a door whose windows saw no zombie within 90 s.
- **A very long load.** Timings now logged (`mapkit: collision edit N loaded in`, `node load times`, `mesh load
  times`). Measured on Windows: the node visibility at 2 048 units took 28 s (55 s on Linux), the mesh's models 31 s
  (BO1's `Vec3PackUnitVec` tries 256 scales for each of 3 million vectors), and a listen server imported the
  collision twice (server and client, 10 s each). Now: visibility within 1 024 units (7.6 s on Linux), each distinct
  normal packed once (524 000 of 1.47 million: 18 s), the client reuses the server's import when the file and cuts
  are the same (0.45 s). A Windows client's load went from about 150 to 120 s, most of the rest being the zones.

The user's second TranZit run (2026-11-12):
- **White objects.** A model dumped from a gump zone can list a material without its `map_Kd` although the material's
  JSON names its colour map and the image was dumped: 7 674 prop placements were drawn white (dry corn, rubble, pipes,
  the bus station's pillar and sink). `bo2_mesh.py` now falls back to the JSON's base colour map (`colorMap`,
  `Diffuse_Map`, `Color_Map`, `radiantDiffuseMap`, as OAT's world dumper picks it): 91 placements left without a map,
  527 images instead of 220.
- **Walking under the bridge.** BO2's script turns the two `bridge_section` brush models to their `script_angles`
  (pitch 10 and 350: the bridge sags in a V, and the world collision under it has that V). They were drawn level, so
  the deck the player saw stood above the one they walked on. Drawn with `script_angles`, the deck and the collision
  match: a player dropped at the middle lands on the deck (z -62, the V's bottom), shots `br_walk2` / `br_side`.
- **Power from the start.** mods/admin's `zm_startpower 1` uses the map's power switch trigger as the first player
  spawns (ZmClient's Solo view and the Switch start menu, "Départ"): TranZit's MapKit switch came on at 2.6 s.

### Running it

On the session's machine (paths to adapt), with OAT built as `tools/bo2/oat/README.md` says:

    Z="/mnt/c/Program Files (x86)/Steam/steamapps/common/Call of Duty Black Ops II/zone/all"
    Unlinker --include-assets gfxworld,clipmap,comworld,gameworldmp,mapents -o out/?zone? "$Z/zm_nuked.ff"
    Unlinker --include-assets xmodel,image,material --model-format OBJ --image-format DDS -o out/?zone? "$Z/zm_nuked.ff"
    I=<run>/mods/mapkit/imports/zm_nuked
    tools/bo2/bo2_props_collision.py out/zm_nuked zm_nuked --out $I/zm_nuked.collision.bin
    tools/bo2/bo2_layout.py out/zm_nuked zm_nuked --collision-file $I/zm_nuked.collision.bin \
        --out <run>/mods/mapkit/layouts/bo2_zm_nuked.json --links-out $I/zm_nuked.links.txt
    tools/bo2/bo2_mesh.py out/zm_nuked zm_nuked --out $I
    BO1Zombies +set fs_game mods/mapkit +set bo1_mod_mapkit bo2_zm_nuked +devmap zombie_pentagon

The run folder is a normal game folder (the player's converted Five zones); the layout, the collision, links and mesh files
and the images are the player's own extraction and stay out of the repository.

`tools/make_dist.sh --bo2 <run> windows` puts that extraction into a package, the layout under `mods/mapkit/layouts/`
and the files under `mods/mapkit/imports/`. ZmClient's Solo view then offers "Mapkit : Nuketown (Black Ops II)", which
starts `+set fs_game mods/mapkit +set bo1_mod_mapkit bo2_zm_nuked +devmap zombie_pentagon`.

The native Nuketown goes with it when the `--bo2` folder also holds `usermaps/zombie_bo2nuked/zombie_bo2nuked.ff`
(the OAT Linker zone after `ffconv`), `main/maps/zombie_bo2nuked.d3dbsp`, `main/images/bo2_*.iwi` and the layout
`bo2_zm_nuked_bsp.json` (`bo2_bsp.py`, "Props, gameplay and lighting on the native world"; with `--blocker-mesh`, also
`mods/mapkit/imports/zm_nuked/zm_nuked.blockers.mesh.bin`). ZmClient offers
"Mapkit : Nuketown native (Black Ops II, monde BSP)" only when the zone and the BSP are in the package, and adds
`+set bo1_mod_zones zombie_bo2nuked +set bo1_bspworld maps/zombie_bo2nuked.d3dbsp` to the line.

The Switch package carries the native map too (2026-11-13; `make_dist.sh`'s `bo2_switch_data`, about 220 MB): the
`_bsp` layout, the zone, the BSP and the `bo2_*.iwi`, and of `imports/zm_nuked/` the links, the blockers' props and
their images (not the MapKit mesh and collision, which the console does not offer). The start menu lists
"Nuketown (BO2, natif)" when its layout, zone and BSP are on the SD card (`Launcher_MapFile`), with ZmClient's line:
`+set fs_game mods/mapkit +set bo1_mod_mapkit bo2_zm_nuked_bsp`, `mapkit` first in a `fs_mods` stack, the zone and
the BSP world, `+devmap zombie_pentagon`; `menu.cfg` keeps it as `map=mapkit:bo2_zm_nuked_bsp`. Checked by
`launcher_config_test` and the NRO build; not yet run on the console.
