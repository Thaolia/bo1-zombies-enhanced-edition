# Map kit: Five assets, JSON layouts

Select `+set fs_game mods/mapkit +set bo1_mod_mapkit <layout>` before `+devmap zombie_pentagon`.
Layouts live in `mods/mapkit/layouts/<layout>.json`; JSON comments are accepted. Without the selector, mapkit is off.
The supported asset base is Five (`"base":"zombie_pentagon"`). Coordinates are inches, Z up; the examples use floor Z=16.

```json
{"name":"my_map","base":"zombie_pentagon","empty":true,"edits":[]}
```

A layout with thousands of nodes over a large map (another game's map, `docs/BO2_MAPS.md`) can set a root
`"nodeVisRange": 2048`: node pairs farther apart get no visibility test when the node graph is built (BO1 tests every
pair, which took hours on TranZit's 5 300 nodes); 0 or absent keeps BO1's full test.

`empty:true` removes the retail world, collision, entities, and pathnodes, while retaining its loaded assets.
Author the floors, ceilings, player spawn, zones, windows and zombie spawners. Without a `powerswitch` edit, empty-base perks and
Pack-a-Punch have power from the start; with one, they and doors marked `"power": true` wait until it is thrown. Lighting is flat unless a `light` edit tints an area (mood lighting); decorative light strips do not cast light. Relocated window brush
prefabs use their material's unlit colour technique where available. With `empty` omitted, edits overlay the retail map.

## Current capabilities

Every recognized edit kind is below. Examples are individual edits, not a connected map; use the complete example below.
Self-test suffixes follow `mapkit: check `. “Indirect” means there is no separate PASS for that kind; it is not a claim
that geometry, visual quality, or arbitrary entity behavior has been validated. Names default to `edit<index>`.

| Kind | Status: empty / retail overlay | JSON example | Self-test line or coverage |
|---|---|---|---|
| `room` | Supported / supported | `{"kind":"room","name":"hall","mins":[-1000,2300,16],"maxs":[-600,2720,176],"wall":8,"nodeSpacing":64,"open":["+x"]}` | `pathnodes PASS goal lookup finds N/N layout nodes`; also `mapkit: selftest room hall dir ... hit ... frac ...` trace diagnostics |
| `box` | Supported / supported | `{"kind":"box","name":"panel","mins":[-1000,2380,16],"maxs":[-994,2460,60],"material":"mc/pent_art_wall_wood10"}` (`"contents":"monsterclip"`: hidden, stops zombies and their node links only, not players or shots) | Indirect: collision probes/topdown; no per-box PASS |
| `links` | Supported (meant for `empty`) | `{"kind":"links","file":"imports/zm_nuked/zm_nuked.links.txt"}` (`file` under `mods/mapkit`: one `a b` pair per line, `a` and `b` counting the layout's `node` edits from 0; another game's own node graph, written by `tools/bo2/bo2_layout.py`, never committed) | The console's `mapkit: N node links read from ...` and `mapkit: N of the links file's N links added` lines. Between two `node` edits the file's links replace BO1's link test |
| `node` | Supported / supported | `{"kind":"node","origin":[-900,2500,16]}` (Z = walking surface, feet height) | Included in `pathnodes PASS ...` aggregate |
| `stairs` | Supported / supported | `{"kind":"stairs","name":"steps","mins":[-700,2560,16],"maxs":[-540,2712,64],"up":"+x","rise":12}` | Indirect: builds step boxes + a node per tread; a purchase on top PASSes only if reached (`layouts/raised_example.json`) |
| `collision` | Supported / supported (meant for `empty`) | `{"kind":"collision","file":"imports/zm_nuked/zm_nuked.collision.bin","cut":[{"mins":[1995,122,-73],"maxs":[2099,195,185],"contents":134414848}]}` (`file` under `mods/mapkit`: another game's map collision, `BO2COL2`, made by `tools/bo2`, never committed; `cut`: world brushes inside a box, with exactly `contents` when given, are left out) | `collision editN SKIP (no runtime check for this kind yet)`; the console's `mapkit: collision edit N: ... world brushes ..., terrain prisms ...` load line. Player, actor and physics movement, traces and pathnode links all see it (`docs/BO2_MAPS.md`) |
| `traverse` | Supported / supported (meant for `empty`) | `{"kind":"traverse","begin":[1993,64,-64],"end":[1971,146,-64],"yaw":105,"anim":"zombie_mantle_over_40"}` (Z = walking surface; `anim` a loaded BO1 traverse animscript, default `zombie_mantle_over_40`, or MapKit's `mapkit_jump_up`: BO1's 222-unit zombie jump up brought down to the end's height, for any jump up, or `mapkit_mantle`: Five's wall hop carried on to the end node, for an obstacle of any depth); the pair is linked at any height and distance (other new nodes only within 256 across and 128 up or down) | Indirect: zombies reach the player through it (`riser ... PASS`); `mapkit: traverse node N: animscript '...' is not loaded` warns of a missing script |
| `mesh` | Supported / supported (meant for `empty`) | `{"kind":"mesh","file":"imports/zm_nuked/zm_nuked.mesh.bin","images":"imports/zm_nuked/images","base":"mc/rus_metal_panel03"}` (`BO2MESH4`/`BO2MESH5` and IW images written by `tools/bo2/bo2_mesh.py`: world chunks, prop models with LODs and their placements, the sky model; `base`, default `mc/rus_metal_panel03`, `alphaBase`, default `mc/t5_foliage_tree_sorbus_leaf01_static`, `blendBase`, default `mc/global_glass` (glass, and the decals with a depth offset added), and `skyBase`, default `mc/mtl_skybox_sp_frontend` (a cube map by view direction), the materials each colour map's material is copied from; the sky is drawn centred on the viewer) | The console's `mapkit: mesh edit N: ... chunks, ... surfaces ...; ... materials linked ..., 0 without GPU buffers` load line; screenshots |
| `spawn` | Supported / empty only | `{"kind":"spawn","origin":[-920,2510,16],"yaw":0,"zone":"reception_zone"}` | Indirect: spawned test client completes purchases/reach/round checks |
| `ent` | Supported raw entity / empty only | `{"kind":"ent","keys":{"classname":"script_model","model":"t5_weapon_m14_world","origin":[-990,2510,60]}}` (`"bmodel":{"mins":[...],"maxs":[...]}`: the entity gets an undrawn layout brush model of that box, origin at its centre: a `script_brushmodel` that collides and can move, as the `bus` edit's) | `ent editN SKIP (no runtime check for this kind yet)`; inspect model and console |
| `zone` | Retail zone manager / marker only on overlay | `{"kind":"zone","name":"reception_zone","mins":[-1000,2300,16],"maxs":[-596,2720,176]}` | Empty: `zone reception_zone PASS enabled, test client inside 0` (or 1). Overlay custom zone FAILs without an info_volume; `join` does not implement wiring |
| `spawner` | Retail round spawner / empty only | `{"kind":"spawner","origin":[-880,2100,16],"yaw":90,"zone":"reception_zone"}` | Indirect: source-attributed window reach and `round PASS round A -> B ...` |
| `farrespawn` | Far-zombie replacement / empty or overlay | `{"kind":"farrespawn","distance":2500}` | `mapkit: far respawn 2500 (layout)` at load, then `far respawn: N zombies farther than 2500 replaced, at ...`; off while `zm_farrespawn` (mods/admin) is set |
| `window` | Generated Five prefab / existing retail entrance | `{"kind":"window","name":"intake","room":"hall","origin":[-880,2296,16],"yaw":90}` | `window intake PASS a zombie from it reached the player`; empty also `window intake boards PASS N/6 torn by zombies` |
| `window` `"open": true` | Open entrance (unboardable window/gap: retail window traverse, no boards, no rebuild) / empty only | `{"kind":"window","name":"gap1","room":"room","origin":[-720,2296,16],"yaw":90,"open":true}` + a `spawner` behind it | `window gap1 PASS a zombie from it reached the player`; the boards line is replaced by `window gap1 is an open entrance (no boards, no rebuild)` |
| `riser` | Retail ground riser (Five's climb-out anim and dirt fx, then straight at the player) / empty only | `{"kind":"riser","name":"pit1","origin":[-560,2640,16],"yaw":180,"zone":"room_zone"}` (origin = floor spot inside `zone`) | `riser pit1 PASS a zombie climbed out of it and reached the player` |
| `wallbuy` | Retail purchase / empty only | `{"kind":"wallbuy","origin":[-720,2716,64],"yaw":270,"weapon":"m14_zm","model":"t5_weapon_m14_world"}`. Optional `"trigger"`: `bowie_upgrade` or `claymore_purchase` makes it the retail Bowie knife (`_zombiemode_bowie`, `bowie_knife_zm` + `world_knife_bowie`) or claymore (`_zombiemode_claymore`, `claymore_zm` + `weapon_claymore`) purchase, priced and run by those scripts (BO2's Nuketown and TranZit). `tazer_upgrade` sells BO2's Galvaknuckles (`tazer_knuckles_zm`, from the bo2weapons mod's `mod.ff`, `tools/bo2/bo2_weapon.py` EXTRAS) for the edit's `"cost"` (6000): `_mapkit.gsc` `mapkit_tazer_walls` runs it as retail runs the Bowie knife (their purchase animation `zombie_tazer_flourish`, then they replace the knife and the Bowie knife; a Bowie knife bought later replaces them) and gives the wall their world model (the layout's `"model"` is `tag_origin`); without them loaded the wall is removed. | `wallbuy m14_zm PASS bought after ... ms, score now ...`; `wallbuy tazer_knuckles_zm SKIP (not loaded ...)` without the mod; `mapkit: Galvaknuckles on` / `not loaded` at the start and `mapkit: Galvaknuckles bought by ...` in `games_mp.log` |
| `perk` | Four Five perks / four Five perks | `{"kind":"perk","perk":"specialty_rof","origin":[-520,2696,16],"yaw":270}` | `perk specialty_rof PASS bought after ... ms at ...` |
| `powerswitch` | Five's power switch (lever, sparks, announcer) / unsupported | `{"kind":"powerswitch","name":"switch","origin":[-996,2620,16],"yaw":0,"snap":"wall"}` (one per layout) | `powerswitch switch PASS perk ... refused N uses with the power off; power_on ... ms after the flip` |
| `pap` | Retail Pack-a-Punch, 5000 points, power-gated / unsupported | `{"kind":"pap","name":"pap","origin":[-860,2700,16],"snap":"wall"}` | `pap pap PASS m14_zm -> m14_upgraded_zm after ... ms, paid 5000` |
| `perkspot` | A spot a falling machine can land on (BO2's Nuketown) / unsupported (meant for `empty`) | `{"kind":"perkspot","origin":[804.1,-56.86,-64],"yaw":270,"solo":1,"meshGroup":"pf15_auto2909"}`: a perk or pap edit with `"sky":1` does not stand at its origin but falls from the sky onto one of these, picked at random (`_mapkit.gsc` `mapkit_sky_perks`, BO2's `zm_nuked_perks`). Every machine is placed at load 8000 units up, hidden, its trigger out of reach (the retail perk threads, the power and mods/admin's start perks work as with standing machines). Quick Revive takes a `solo` spot, the others the other spots. Alone (players counted once all have connected: `GetNumExpectedPlayers()` is 0 in a devmap) Quick Revive lands first, 9 to 19 s into the game; the others fall one at random in each of the rounds 3-5, 6-9, 10-14, 15-19 and 20-25, 30 to 120 s into the round, and in co-op Quick Revive falls at random among them (BO2 also lets any machine take a `solo` spot in co-op: here Quick Revive keeps it). The spot has a machine clip (Pack-a-Punch's footprint, the tallest machine's height) all game, as BO2 keeps a crate pile there until a machine lands: its `meshGroup` (`bo2_mesh.py`) is hidden on landing. The landing shakes the ground, players within 300 go prone and take 10 damage, zombies within 500 die (gibbed) and come back later in the round. `+set mapkit_skyperks 0` and the self-test place the machines at their edits' origins; `+set mapkit_skyperks_fast 1` drops one every 20 s from 5 s in (tests) | `mapkit: sky machine <perk> will land on perkspot edit N at (...)` at load, `... falling onto (...) (round R)` and `... landed at (...), K zombies knocked down` in `games_mp.log` |
| `buildable` | A table where a machine is built (BO2's TranZit) / unsupported (meant for `empty`) | `{"kind":"buildable","name":"powerswitch","origin":[12169,8493,-690],"pieces":"p6_zm_buildable_pswitch_hand,p6_zm_buildable_pswitch_body,p6_zm_buildable_pswitch_lever"}`: `name` is `powerswitch` or `pap`, the machine edit with `"buildable"` set to that name, or `turbine` (see `denizens`) (`_mapkit.gsc` `mapkit_buildables`, BO2's `zm_transit_buildables`). With `"weapon"` (`jetgun_zm`, `riotshield_zm`: TranZit's Jet Gun and shield, from the bo2weapons mod's `mod.ff`, `tools/bo2/bo2_weapon.py` EXTRAS) it builds no machine: its `buildpart` `weapon` (the finished weapon on the table) appears, and any player then holds use there to take one into BO1's equipment slot (retail `_zombiemode_equipment`: action slot 1, one item at a time, taken at laststand), as often as he likes; without the weapon loaded the buildable and its pieces are left out. The Jet Gun (`mapkit_jetgun_watch`): its clip is the heat left (a round per 0.06 s of firing, one back per second otherwise); while it fires, the zombies in front within 128 units are ground up and the farther ones, up to 1024, pulled 48 units toward it every 0.25 s; fired dry, it blows up. The shield (`mapkit_shield_damage`, a player damage callback): in hand it stops the zombies' blows from in front, stowed those from behind, up to 2250 damage, then it breaks; firing it or a melee with it bashes the zombies in front within 90 units (2500 damage, flung when killed). That machine is placed at load hidden, its trigger out of reach; each piece lies on one of its `piece` spots picked at random. A player carries one piece at a time (picking up another puts the first back on its spot, as does bleeding out or leaving) and holds use 2 s at the table to build it in (use at a table and on a piece is polled within 96 and 64 units across, not a use trigger's); with every piece in, the machine appears and works. `+set mapkit_buildables 0`: the machines stand from the start and no piece is drawn | `buildable <name> piece <model> PASS built in after ... ms`, `buildable <name> PASS built, its machine stands` (the self-test builds every buildable first); `jetgun PASS taken from its table ...`, `jetgun PASS fired at a zombie N units away: ground up / pulled ...`, `jetgun PASS fired dry: blew up ...`, `riotshield PASS in hand: stops a blow from in front ...`, `riotshield PASS bashed a zombie dead ...`, `riotshield PASS worn out: broke ...` (`SKIP` without the mod); `mapkit: buildable <name> piece <model> on spot N`, `... picked up`, `... built in by player, k/n`, `buildable <name> built`, `mapkit: Jet Gun on, shield on` / `not loaded`, `mapkit: jetgun_zm taken by ...` / `lost by ...` in `games_mp.log` |
| `piece` | A spot a buildable's piece can lie on / unsupported | `{"kind":"piece","buildable":"pap","piece":"p6_zm_buildable_battery","origin":[...],"meshGroup":"piece:pap:battery:0"}`: its `meshGroup` (`bo2_mesh.py`, the piece's model at BO2's spot) is drawn while the piece lies there, hidden on the spots not picked and once picked up | see `buildable` |
| `buildpart` | A part of a finished machine drawn as it is built in / unsupported | `{"kind":"buildpart","buildable":"powerswitch","piece":"p6_zm_buildable_pswitch_lever","origin":[...],"meshGroup":"built:powerswitch:pswitch_lever"}`: hidden at load, shown when its `piece` is built in, hidden again when the machine appears. `"piece":"weapon"`: the finished Jet Gun or shield on its table (BO2's `buildable_jetgun` / `buildable_riotshield` model), shown once built | see `buildable` |
| `safelight` | A lamp that keeps the Denizens away once lit (BO2's TranZit `screecher_escape`) / unsupported | `{"kind":"safelight","name":"busdepot","origin":[-6363,4577.9,-41],"radius":128}`: lit while the planted turbine (`buildable` `turbine`) stands within 335 units of it; a player within `radius` of a lit one is safe from the Denizens, and one clinging to him lets go | see `denizens` |
| `emp` | BO2's EMP grenade in the mystery box (TranZit) / unsupported | `{"kind":"emp"}`: when the bo2weapons mod's `mod.ff` holds `emp_grenade_zm` (`tools/bo2/bo2_weapon.py` EXTRAS), it joins the box as a special grenade (`level.zombiemode_offhand_weapon_give_override`: it takes the Monkey Bombs' place and the reverse) and is thrown with the special grenade button. Where it goes off (`_mapkit.gsc` `mapkit_emp_detonate`, BO2's `_zm_weap_emp_bomb` simplified): BO1's blue power-up wave; the zombies within 600 units stand still 20 s or until hurt; the players within 420 are shaken 2 s; the perk machines within 420 refuse purchases 90 s; a planted turbine within 420 goes back to its table. BO2's machine lights, Pack-a-Punch, local door power and traps are left on | `emp PASS given by the box: ...`, `emp PASS went off at (...), N units from the turbine, which is back on its table` (`SKIP` without the mod); `mapkit: EMP grenade given to ...`, `mapkit: EMP at (...): N zombies stunned, M perk machines off` in `games_mp.log` |
| `denizens` | TranZit's Denizens, simplified / unsupported | `{"kind":"denizens","zones":"_trans_,_amb_","count":2}` with `ent` brush models `mapkit_denizen0`..`1` carrying the mesh edit's movers (`bo2_layout.py`): a player 8 to 15 s in a zone whose name holds one of `zones`, off the bus and out of every lit `safelight`, is leapt on by one (it rises 300 units behind him); it clings to his face, blurs his view and takes 10 health every 2 s until he melees once (50 points), reaches a lit light or goes down. `+set mapkit_denizens 0`: none. The `buildable` `turbine` (no machine edit) is taken from its table and planted by crouching and holding use 1 s; it opens every `door` edit with `"turbine"` within 335 units, which the power no longer opens while a turbine can be built | `denizen PASS clung after ... ms`, `denizen PASS knifed off after ... ms`, `turbine PASS planted at (...), opened <doors>`; `mapkit: denizen rises / clings to / let go (<why>)`, `mapkit: turbine taken / planted at / turbine door <name> opened by ...` in `games_mp.log` |
| `avogadro` / `avogadrospot` | TranZit's Avogadro, simplified / unsupported | `{"kind":"avogadro","origin":[11760,7580,-724],"yaw":0,"core":[...]}` with an `ent` spawner `mapkit_avogadro_spawner` (Five's `actor_zombie_electrician`) and `{"kind":"avogadrospot","origin":[...],"yaw":90,"zone":"zone_din","region":"diner"}` spots (`bo2_layout.py` `avogadro_edits`, BO2's `avogadro_location` structs and `init_regions`; a spot with no region is skipped). Once the power is on, a BO1 AI stands at `origin` (by the reactor), dressed in `c_zom_avagadro_fb` when a loaded zone holds it (`bo1_mapkit_modelloaded`; the bo2weapons `mod.ff`, `bo2_weapon.py` EXTRA_MODELS), else in the thief's model. A player seeing it (or 60 s) sends it up; it comes down 2 to 4 rounds later on a spot 400 to 2500 units from a player, chases, dashes 160 units and throws a bolt (60 damage and a shock). Only melee with its shield down (after a bolt) wounds it, 4 wounds (2 per Galvaknuckles blow) or an EMP within 600 drive it off; bullets, explosions, the nuke and the Jet Gun do nothing. With nobody within 3000 units it leaves for one round. Never counts as a round's zombie. `+set mapkit_avogadro 0`: none | `avogadro PASS spawned in model ...`, `PASS came down N units from the player`, `PASS 5000 bullet damage did it no harm`, `PASS a melee blow wounds it only with its shield down`, `PASS an EMP drove it off`; `mapkit: Avogadro out of the reactor / came down at / bolt hit / wounded by / left (<why>)` in `games_mp.log` |
| `light` | Mood lighting: per-area tint of the flat lighting / unsupported (retail light grid) | `{"kind":"light","name":"bunker_light","room":"room","preset":"dim bunker"}` or `{"kind":"light","mins":[...],"maxs":[...],"color":[0.7,0.9,1],"intensity":1.2}` | `light bunker_light PASS tint (0.55, 0.45, 0.34) at ..., N renderer samples` |
| `door` | Retail buy + zone unlock / unsupported | `{"kind":"door","name":"gate","mins":[-600,2420,16],"maxs":[-592,2690,144],"yaw":0,"from":"reception_zone","to":"transmitter_zone","cost":750}`; optional `"meshGroup":"<name>"` (door and debris): a group of props of the layout's `mesh` edit, another game's door or furniture, drawn instead of the kit's box until the purchase (the box keeps the collision) | `door gate PASS buyable, charged 750`; on another game's map (a `collision` edit) `door_graph` counts the active links through the blocker's box, none while closed and some once bought, since zones also join through windows and traversals there; `unlock transmitter_zone PASS locked -> enabled and active`; `unlock_window intake PASS zombie selected this entrance after opening ...` |
| `debris` | Retail buy + zone unlock / unsupported | `{"kind":"debris","name":"rubble","mins":[-192,2420,16],"maxs":[-184,2690,144],"yaw":0,"from":"transmitter_zone","to":"battery_zone","cost":1000}` | `debris rubble PASS buyable, charged 1000`, plus the same unlock/window checks |
| `bus` | A vehicle driving a loop, stopping with its doors open, called by the players, carrying those standing in it / unsupported (meant for `empty`) | `{"kind":"bus","name":"bus","floor":"mapkit_bus_floor","parts":"mapkit_bus_part","doors":["mapkit_bus_door0","mapkit_bus_door1"],"pivot":[138,3.5,28],"button":[350,50,84],"speed":440,"path":[[x,y,z],...],"yaws":[...],"stops":[[0,19,0],[58,18,0]],"calls":[{"origin":[x,y,z],"yaw":268}]}`: `floor`, `parts` and `doors` name `ent` edits with a `bmodel` box (`script_brushmodel`), standing where the vehicle is parked, at the loop's first point facing the second; the parts and doors are linked to the floor, which moves (`MoveTo` + `RotateTo` point to point at `speed` units a second) and carries a player standing on it as Five's elevators do; `path` is the loop on the ground, `yaws` (optional) the heading at each point, turned over the whole segment (without it: the segment's own heading, turned in 0.5 s at most), `pivot` the floor's centre in the vehicle's space (x forward, origin on the ground); `stops` `[point index, seconds, 0]`: there the doors open (no collision, not drawn), Five's alarm bell rings 5 s before the bus leaves, the doors shut (a player in the doorway is put inside); `calls` (one per stop, optional): a lever box (Five's `zombie_power_lever_short` and its handle) whose use trigger, once the power is on, sends the bus to that stop next, passing the others and cutting a wait elsewhere short; `noun` (optional, default `bus`): what the call levers' hints name it (Mob of the Dead's `gondola`); `button` (optional, vehicle space): a free use trigger (and a lever handle) linked to the floor, by the driver's seat, that opens the doors on the way for 5 s unless the bus reaches a stop by then. The `mesh` edit's `moverModel` (a model of its file, no placement) is drawn on the brush model of the `ent` named by `moverEntity`, shifted by `moverOffset` and turned by `moverYaw` (the vehicle's heading at angles 0), and each of `movers` (`{"model","entity","offset","yaw"}`, up to 8 in all: the doors' panels) the same way, only while its entity is shown (BO2's TranZit bus, `tools/bo2/bo2_layout.py`, `bo2_mesh.py --mover`) | `bus bus PASS rode from (...) to (...)`, `bus_doors bus PASS open at the stop, shut on the way` `bus_call bus PASS called to stop 3 (point P), no stop between` and `bus_button bus PASS the doors opened on the way ... and shut again before the next stop`. `games_mp.log` also has `mapkit: bus <name> on a loop of N points, ... D doors, headings smoothed` once, `mapkit: bus stop S (point P) at (...) yaw Y` at each stop `mapkit: bus called to stop S by <player>`, `mapkit: bus button at (...)` once and `mapkit: bus doors opened on the way by <player>` / `shut again on the way`; with `mapkit_bus_log 1`, `mapkit: bus point P floor (...) yaw Y, player N at (...) (D units out, H up)` at every point; with `mapkit_bus_log 2` (test aid) player 0 is put on the floor two seconds into every stop and its place in the floor's space is logged each 0.1 s (`mapkit: bus trace`). Zombies do not board it |
| `bank` | BO2's bank and weapon locker, kept between games / unsupported (meant for `empty`) | `{"kind":"bank","name":"bank","deposit":{"origin":[564,655.2,-40],"yaw":0},"withdraw":{"origin":[559.5,445.7,-40],"yaw":0},"locker":{"origin":[8220,-6875,165],"yaw":30}}`: a use trigger (radius 40, centred on `origin`) for each part present. Deposit: 1000 points into the account (at most 250 000); withdrawal: 1000 points back less a 100-point fee; locker: stores the weapon in hand (not the last one) with its ammo, gives it back on a later use when the map's zones hold it. The engine keeps the accounts and lockers by player name in `<fs_homepath>/main/mapkit_bank.txt` (`bo1_mapkit_bank_get` / `bo1_mapkit_bank_set`, `g_mapkit.cpp`): the points change only once the file is written | `bank deposit PASS 1000 in, 900 back, account 0` and `bank locker PASS stored and took back <weapon>` (under the account name `mapkit_selftest`, removed after); `mapkit: bank deposit by <name>, account N`, `mapkit: locker took ... / gave ... back` in `games_mp.log` |
| `fx` | A looping BO1 effect placed for good (the server loads it, mods/mapkit's client main plays it on each local client: no entity) / empty only | `{"kind":"fx","fx":"env/fire/fx_embers_falling_md","origin":[758,369,260]}` or, turned, `{"kind":"fx","fx":"env/light/fx_ray_md_1sd","origin":[-895,174,-63],"angles":[300.23,213.19,150.53]}` (without `angles` the effect's forward axis points up, as BO1's createfx places ambient effects; `fx` a BO1 effect name without `fx/`, from a zone the game loads: another game's map brings its own, `docs/BO2_MAPS.md` "Placed effects"; optional `from`, the effect it stands for, is not read; `+set mapkit_fx 0` leaves every fx edit out) | `fx all PASS N edits, M effects loaded`; a client's own count is its dvar `mapkit_fx_placed` |
| `mysterybox` | Retail weapon roll/grant / unsupported | `{"kind":"mysterybox","name":"crate","origin":[10,2670,16],"yaw":270}` | `mysterybox crate PASS bought weapon <weapon>` verifies payment and inventory; relocation is not measured |

## Placement rules

Entrances without boards (`layouts/entrances_example.json`, doctor PASS): the rule is that boards matter only where
zombies tear a window. A window with `"open": true` is placed like a boarded one and needs the same outside `spawner`;
zombies climb through with the retail traverse and there is nothing to tear or rebuild (retail: an `exterior_goal` with
no target has no barrier). Keep players out with the gap height or a `box`. A `riser` is a retail riser spawner of its
`zone` (`script_string "riser"`, rise spot `<zone>_spawners_rise` with `find_flesh`): while the zone is active, round
zombies climb out at the spot (Five/Kino/Moon anim and fx) and go for the player. Several risers in one zone share its
spots at random, as retail. Doctor: `riser-zone` (origin outside its zone), `riser-unverified` / `selftest-riser`.
The self-test checks one riser at a time: its zone offers only that spot during the check, and the client stands 192
units in front of it; on an imported map (a `collision` edit), whose risers can lie outside every zone, it stands
instead on the pathnode of the riser's zone nearest the riser that `FindPath` reaches from it, and moves to another
node if, once put down, it is no longer in the zone (`docs/BO2_MAPS.md`). Each check logs where the client stands and,
on a FAIL, where that riser's zombies are (and the traversal they are in); `+set mapkit_test_risers "riser7,riser10"`
checks only the risers named, `+set mapkit_test_windows "church_baricade1"` only the windows named.

Room `mins/maxs` enclose the usable interior; walls extend outward by `wall` (default 8). `open` accepts `+x,-x,+y,-y`.
`gaps` cut openings: `{"side":"-y","along":[-930,-830],"z":[52,120]}`. `along` uses world Y for X walls and world X
for Y walls. `floor:0` or `ceiling:0` omits that surface. `floorMaterial`, `wallMaterial`, `ceilingMaterial`, and
`texScale` (default 128) select appearance. Box `contents:"none"` is visual only; default `"solid"` collides.

Shared wall: two rooms that touch share ONE wall. The room that owns it keeps that side closed (its `wall` thickness
lies outside its `mins/maxs`) and cuts the doorway as a `gap`; the neighbour lists the same side in `open` and starts
`wall` units further out. Example (sluice_works): `intake` maxs x -600 with a `+x` gap, `pumphall` mins x -592 (= -600
+ 8) with `"open":["-x"]`. Overlapping room boxes are doctor `room-overlap`.

Power: `"power": true` on a `door` makes it Five's electric door (`electric_buyable_door`: "needs power" until the
switch is thrown, then bought for `cost`; with `"cost": 0` it opens by itself at power on). Debris has no power case.
A layout without a `powerswitch` has power from the start (doctor `power-no-switch` WARN on a power door).
Complete small example: `layouts/power_example.json` (switch, Juggernog, Pack-a-Punch; doctor PASS 10/0).

Mood lighting (empty base only): a `light` edit tints everything whose lighting point is inside its area - room/box
faces (sampled at one point inside each room, so a light tints whole rooms; name the room with `room`), perk machines,
zombies, the player's gun. `room` takes the bounds of the room, zone or box edit with that name; else give `mins`/`maxs`.
Presets: `dim bunker` (warm, 0.55), `red alarm` (red, 1.0), `cold lab` (blue-white, 1.15). `color` (0..2 per channel)
and `intensity` (0..2, 1 = today's flat grey) override the preset. Overlapping lights: the later edit wins. The doctor
WARNs `light-dark` (tint luminance < 0.30) and `light-bright` (> 1.60 or a channel at the 2.0 cap), `light-overlay` on
a retail overlay (its light grid stays). The load prints `mapkit: light edit N tint r g b over (mins)-(maxs)`. Example:
`layouts/mood_example.json`.
Rounds: every round start is logged as `mapkit: round N start at <level ms>` (games_mp.log / the doctor's console.log).

Rooms generate walking nodes at `nodeSpacing` (default 56; 0 disables), starting 24 units inside their walls.
Automatic grid candidates inside static standing clearance are omitted; explicit nodes still report bad placements.
Stairs and raised areas: a `stairs` edit is the whole flight; `up` (+x,-x,+y,-y) is the rising direction and `maxs.z` the
top tread. The kit builds round(height/rise) solid steps (`rise` default 12, max 18 = zombie step height) and puts nodes on
every tread (`nodeSpacing` across, default 56); treads must be 32+ deep (use 40+), the load prints a warning otherwise. A `box`
with `"walkable":1` gets a node grid on its top, so a platform/catwalk needs no hand-placed nodes. Hand-placed `node` edits
use the walking-surface Z (the kit adds 16 and drops them to the floor). The doctor's offline walk steps up/down 18 like the engine.
Leave usable routes around furniture and inspect `node_clearance` and topdown after a load. A layout node the engine's
drop finds in solid is tried again 8 then 16 units around (`mapkit: node N in solid at (...), moved to (...)`); only a
node with no free spot there counts as bad. Thin wall panels in Relay
are 6 units deep. A node-lookup PASS alone does not prove all paths are traversable.

For an empty-base window, `origin` is the wall centre at floor height; `yaw` points INTO the play room. Leave an
80–100-unit-wide gap, Z=floor+36..floor+104, and an exterior floor/duct with nodes. The kit supplies the clip, six panels,
repair boards, goal and traverse node pair. Add a `spawner` outside each entrance, with the play room's `zone`.
The goal's zone is inferred from origin + forward*48 + Z32 (the smallest zone box holding that point when boxes
overlap), before retail struct indexing. Spawners are associated with the nearest window in their zone; put each beside
its intended exterior approach. A spawner's `"window": "<name>"` ties it to that window instead: its zombies go to that
window's goal (retail `zombie_think` with a spawner target) rather than one of the three closest goals at random, which
on a map whose outside ground is cut into pockets (BO2's TranZit) sent them to goals they could not reach. Give such a
spawner the window's own zone, or it only wakes when the player stands elsewhere. `"chaser": 1` makes a spawner's
zombies go straight for the player, no window (retail `zombie_chaser`). Source identity stays attached to
the spawned zombie as its AI goals change. `room` names the interior room used by reach validation.
An empty-base layout with no `window` at all (an arena) still works: its spawners become retail `zombie_chaser`
spawners that go straight for the player (the load prints `mapkit: no window edits: spawners are zombie_chaser`).

On a retail overlay, a window instead reuses an existing entrance:
`{"kind":"window","name":"north_window","spawn":[-372,3200,24],"target":"auto2774","every":3,"room":"test_room"}`.
This is the recipe in `mapkit_test.json`; it does not construct a new retail window or zone.

Door/debris `mins/maxs` fill an authored doorway; yaw points from `from` toward `to`. Bounds create the solid blocker
and a usable trigger; `material` controls its visible box. Purchase removes collision, reconnects paths and unlocks
the destination through the retail zone manager. Destination zones start locked except a player-spawn zone.
Without blockers, all authored zones start enabled. Enabled zones become active through player occupancy.
List blockers in progression order for the test route. The self-test verifies a spawn from every destination window
and `door_graph` checks active links before (disconnected) and after (connected) each purchase.

Loops are supported: two blockers may lead to the same zone. The one bought second (in edit order) is a loop-closer, because
its `to` zone is already enabled. For it the test checks only the path through its own doorway (nodes in its `from`/`to`
zones or within 96 units of its bounds) and prints `door_graph NAME PASS ... (loop-closer: path through this doorway only)`
and `unlock ZONE PASS loop-closer: already enabled through another blocker, still active`. Example 2x2 loop
(`layouts/sluice_works.json`): `a -door-> b -door-> d` and `a -debris-> c -debris-> d`; the last debris is the loop-closer.
`{"kind":"debris","name":"sluice_debris","mins":[...],"maxs":[...],"yaw":0,"from":"filter_zone","to":"control_zone","cost":1250}`.
Keep each blocker's `from` and `to` zones on the two sides of its own doorway.

Purchase triggers must not intersect (wall buy: 64-unit cube 24 in front of the model; perk: radius 44 in front of the machine;
box: 80x80). The load prints `mapkit: purchase triggers of edit A and edit B intersect by N units` and the doctor FAILs
`purchase-overlap` with the distance to move; a wall buy beside a perk needs about 100+ units between origins.

Mystery-box origin is floor height; yaw faces the player. Cost defaults to 950. Multiple placements use the retail
location system; `start:0` excludes a location from the initial selection. The shipped proof covers a weapon grant,
not teddy relocation. Door/debris default cost is 750. Perks, `pap` and `powerswitch` accept `snap:"wall"`: the nearest
wall of 8 directions within 200 units wins (it replaces `yaw`), the machine backs off it and stands on the floor; without
`snap` the origin and `yaw` are used as given.

Perk machines, Pack-a-Punch, the power switch panel and the mystery box block players and zombies like retail Five's
clip brushes: the load adds a hidden player+monster clip around each (`mapkit: N machine clips` in the console), buying
through it still works, and pathnodes/links inside it are dropped so zombies path around. A `node` edit placed inside
a machine now fails `node_clearance`; move it clear. Self-test: `+set mapkit_clipshots 1` (passive god test client)
walks into every machine and logs `mapkit: clipshots <kind> edit N ... gap G PASS|FAIL` and `clipshots END`.

## Tested asset catalog

These names load on the empty Five base. Fastfile names below are the source files containing the asset identifiers;
Five also loads shared `common_zombie.ff`. They are not instructions to copy or modify the Steam files.
All four perk purchases and the three wall-buy pairs are exercised by `three_room_progression`; the box check exercises its models
and random weapon grant. This is a deliberately verified starter catalog, not every asset in the game.

**Everything else that is loaded:** `node tools/mapkit/catalog.mjs` lists every wall-buy weapon with its world model
(the `weapon`/`model` pair a `wallbuy` needs) and the perk names; `node tools/mapkit/catalog.mjs xmodel|material|weapon
[substring]` lists one kind, e.g. `catalog.mjs material concrete`. Names come from the loaded base (102 weapons,
710 xmodels, 2272 materials), minus the known stock load failures. Loaded is not tested: run the doctor on a new pick.

| Placement | Layout identifier / model | Fastfile containing the name |
|---|---|---|
| Juggernog | `specialty_armorvest` / `zombie_vending_jugg`, `zombie_vending_jugg_on` | `common_zombie.ff`, `zombie_pentagon.ff` |
| Quick Revive | `specialty_quickrevive` / `zombie_vending_revive`, `zombie_vending_revive_on` | `common_zombie.ff`, `zombie_pentagon.ff` |
| Speed Cola | `specialty_fastreload` / `zombie_vending_sleight`, `zombie_vending_sleight_on` | `common_zombie.ff`, `zombie_pentagon.ff` |
| Double Tap | `specialty_rof` / `zombie_vending_doubletap`, `zombie_vending_doubletap_on` | `common_zombie.ff`, `zombie_pentagon.ff` |
| M14 wall buy or decorative model | `m14_zm` / `t5_weapon_m14_world` | `common_zombie.ff`, `zombie_pentagon.ff` |
| MP5K wall buy or decorative model | `mp5k_zm` / `t5_weapon_mp5_world` | `common_zombie.ff` |
| Stakeout wall buy or decorative model | `ithaca_zm` / `t5_weapon_ithaca_world` | `common_zombie.ff` |
| Mystery box body/lid (automatic) | `zombie_treasure_box`, `zombie_treasure_box_lid` | `zombie_pentagon.ff` |
| Window brush prefab (automatic) | Five `pf82` brush models; not a named xmodel | `zombie_pentagon.ff` |

Use the `perk` kind instead of manually assembling a vending model and trigger. Other perk identifiers are skipped.
The diary's guessed MP5K/Olympia world-model names failed to load. MP5K uses `mp5_world`, not `mp5k_world`. A weapon name alone
does not prove its decorative model is loaded. Test new pairs for `Could not load xmodel` and an actual purchase.

Relay's known materials in `zombie_pentagon.ff`: `mc/jun_art_concrete_base02_dark` (floor), `mc/pent_art_wall_wood10`
(wood wall), `mc/rus_metal_panel02`, `mc/rus_metal_panel03`, `mc/jun_art_metal_green01`, `mc/jun_art_metal_black`,
`mc/mat_zombie_ceiling_tile01`, `mc/global_light`. List more with:

```powershell
node tools/mapkit/materials.mjs zombie_pentagon 'wall|floor|metal'
```

This lists material strings, not validated weapon/model pairs. Empty-base box colours do not provide baked lighting.

## PowerShell build and test loop

**Step 1 after every layout edit: run the doctor.** It performs static checks, drives one private-desktop
game run, and writes a self-contained report with a marked topdown PNG, logs, and player-side window pictures:

```powershell
node tools/mapkit/doctor.mjs mods/mapkit/layouts/relay_station.json
```

Read `build/doctor/relay_station/report.md` (the same report prints to stdout). Problems are ranked with
coordinates, the exact `$.edits[index].field` to inspect, observations and a suggested layout fix. Fix the
first relevant cause, rerun this command, and compare the archived reports next to the latest report.
Exit codes are **0 PASS, 1 FAIL, 2 WARN**; missing DONE, untested purchases, missing telemetry and screenshots
remain visible. `--static` skips the game and reports live coverage as untested. JSON comments are supported.

The doctor uses an isolated build copy of your layout and mod scripts. It does not rewrite the input. Build
and set up the run folder once using the commands below. The doctor launches only through `tools/headless.ps1`,
waits for a free slot, and uses a computed maximum budget. The existing self-test walks the test client to
purchases/windows and opens doors at **4x**. On a layout with a `collision` edit (another game's map) it first puts the
client on the floor at each machine and wall buy, then walks the last step: such a map has props the player collides
with that its node graph does not know, and the straight walk from node to node gets stuck on them
(`+set mapkit_test_walk 1` keeps the walk). The client steers round an obstacle its hull meets 32 units ahead, and a
goal it cannot reach exactly counts as reached once it stands still within 48 units. Walking, it plans with the
traversals when it must and jumps across them. On another game's map only (the self-test sets
`bo1_testclient_carry 1` there), the harness carries it in three cases, and logs each carry
(`bo1_testclient: ... carried`):
- over a traversal it has not crossed in 3 s;
- to the next node, when it has headed for one node 10 s without reaching it;
- to the goal, when it has had no path for 10 s.

Purchases then wait 35 s longer, and a riser check starts once the client stands there (`docs/BO2_MAPS.md`). After DONE it changes to **1x**, places the camera on each window's
player side and takes back-buffer screenshots, then quits; camera placement never contributes to reach tests.
The run is a functional test with funds/power and round cleanup. During purchases it kills attackers within 96 units
of the passive client, so crowds cannot prevent use-button tests. Window trials keep the selected entrance's actors alive.

Static graph links are clearance estimates; the report also checks the actual engine graph and observed
actor positions. Actor lives are tracked separately even when entity numbers are reused. Counts are sampled
every 0.5 level seconds; retail entrance, chunk-destruction and completed-emerging fields distinguish arrival,
tearing and climbing from geometric room entry. Exact reach witnesses also cover the gaps between sampler ticks.
Every no-path event and stationary cluster is retained in the report's linked event file. A no-path attempt is
informational only with recorded movement resuming for the same life, an explicit test cleanup cutting short its first
second of life, or the post-DONE camera phase. Unexplained attempts and stationary episodes remain WARNs.
Asset checks use identifier presence in Five/common_zombie fastfiles; live load/purchase checks establish typed availability.
Unreferenced messages matching the recorded stock Five client baseline are informational. New messages remain WARNs;
an authored asset that fails to load remains a FAIL even if its name occurs in the stock baseline.

The kit omits the two automatic candidates obstructed by `mapkit_room`'s crate and builds the underlying door graph
before dynamic blockers disconnect it. The doctor independently checks the final active graph after purchases.
Relay's original diary includes kit bugs fixed by mapkit-fix-1; the doctor measures the current executable
and does not reproduce historical failures merely because they appear in that diary.

The manual commands below remain useful for focused follow-up and standard baseline measurements.

Run from the project folder. Copy the game into the run folder once with setup.ps1 (see README.md). Never launch the executable directly.

```powershell
$cmake = 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
& $cmake -S . -B build -G 'Visual Studio 17 2022' -A Win32 '-DDXSDK_DIR=C:/path/to/DXSDK'
if ($LASTEXITCODE) { throw 'configure failed' }
& $cmake --build build --config Release -- '-m' '-nr:false' '-v:minimal' '-nologo'
if ($LASTEXITCODE) { throw 'build failed' }
powershell -NoProfile -ExecutionPolicy Bypass -File setup.ps1
```

After JSON/script-only edits, copy the mod, calculate the conservative budget, then require completion and zero FAILs:

```powershell
Copy-Item mods/mapkit -Destination build/Release/mods -Recurse -Force
$layout = 'three_room_progression'
$speed = 4
$budget = node tools/mapkit/selftest_budget.mjs "mods/mapkit/layouts/$layout.json" $speed | ConvertFrom-Json
$log = "build/$layout-$(Get-Date -Format yyyyMMdd-HHmmss).log"
$commands = "+set fs_game mods/mapkit +set bo1_mod_mapkit $layout +set sv_cheats 1 +set timescale $speed +set bo1_testclient 1 +set bo1_testclient_fight 1 +set bo1_testclient_god 1 +set bo1_testclient_passive 1 +set mapkit_selftest 1 +set bo1_scripterrors 100 +devmap zombie_pentagon"
powershell -NoProfile -ExecutionPolicy Bypass -File tools/headless.ps1 -Zombies -Commands $commands -AutoQuitMs $budget.autoQuitMs -TimeoutSec $budget.timeoutSec -WaitSec 60 -SaveLog $log
# exit 21 = the wrapper's watchdog hit -TimeoutSec; with DONE in the log the checks finished and only the quit was late
# (a slow load while other runs hold the CPU): not a layout failure, the DONE line below decides. The doctor reports it as a WARN.
# Without the 'bo1_headless_client: listen server' init line in the log the map never finished loading (timeoutSec allows
# 420 s of startup): a startup timeout, not a failed check - the doctor prints STARTUP TIMEOUT (finding startup-timeout).
if ($LASTEXITCODE -and $LASTEXITCODE -ne 21) { throw "wrapper failed: $LASTEXITCODE" }
$done = Select-String -Path $log -Pattern 'mapkit_selftest DONE pass (\d+) fail (\d+)' | Select-Object -Last 1
if (-not $done -or $done.Matches[0].Groups[2].Value -ne '0') { throw 'self-test incomplete or failed' }
if (Select-String -Path $log -Pattern 'throwing script exception|script runtime error|Unknown function') { throw 'script error' }
Select-String -Path $log -Pattern 'mapkit: check |mapkit_selftest'
node tools/mapkit/topdown.mjs build/Release/mods/mapkit/mapkit_dump.json "build/$layout.png" --zlo 32 --zhi 80 --scale 1
```

`-SaveLog` archives the fresh `fs_game` console log at the requested worktree-relative path, including checks and DONE.
Live files are `build/Release/mods/mapkit/console_mp.log` and `games_mp.log`; the latter appends across runs, so use its
last `InitGame` section. With `-RunDir`, console logs follow that run folder's fs_home/mod path (mods may be junctioned).
Screenshot files for the default run folder are `build/Release/mods/mapkit/screenshots/bo1_<ms>.jpg`; copy them
to distinct evidence names before the next run. Missing DONE is incomplete even if the process exits 0.

The budget includes sequential purchase timeouts, 90 seconds per entrance, zone-unlock spawn checks and round advancement,
divides level time by the requested speed, and adds a real-time allowance. Slower-than-requested simulation can still
need more real time. The self-test grants test funds before each purchase independently of power; uses movement, aim
and use commands; checks the actual perk/weapon inventory; waits for source-attributed window reach and real board
movement; then kills remaining zombies to check round advance. It is a functional route, not an unassisted combat test.
Keep fight/god/passive enabled for that route. For normal combat, omit `mapkit_selftest` and `bo1_testclient_passive`.

Screenshots use `-Client -ShotsAtMs` at **1x**. `bo1_testclient_passive 1` makes the test client walk to
`bo1_testclient_goto x,y,z` and face `bo1_testclient_look x,y,z` (no `bo1_testclient_fight` needed). Closed doors
block the walk: add `+set mapkit_open_all 1` to open every door/debris for free at spawn (console: `mapkit: open_all
triggered N blockers`). Full command for an area behind doors (control room of `sluice_works`):
`tools\headless.ps1 -Zombies -Client -ShotsAtMs "26000 33000" -AutoQuitMs 36000 -TimeoutSec 150 -Commands "+set fs_game mods/mapkit
+set bo1_mod_mapkit sluice_works +set bo1_testclient 1 +set bo1_testclient_god 1 +set bo1_testclient_passive 1
+set mapkit_open_all 1 +set bo1_testclient_goto -340,2940,16 +set bo1_testclient_look -150,3120,60 +devmap zombie_pentagon"`.
Allow ~1 s of walk per 150 units after the ~15 s load before the first shot. `AutoQuitMs`, timeout and shot times are real
time. Use 4x for functional routes; keep the standard 90-second measurement and screenshots at 1x.

Topdown draws walking links in green, actual traverses as cyan dashed arrows, and ordinary walking-wall crossings in
red. A traverse crossing its window wall is expected. `--zlo/--zhi` select the filled brush slice only: nodes/links
include every height, and walking crossing checks use node feet+8..64 independently of the displayed slice. Legacy
dumps without traverse flags use a stated begin/end-node inference. Room outlines, zones and edit marks help orient you.

## Complete progression example

[`layouts/three_room_progression.json`](layouts/three_room_progression.json) is a ready-to-run Relay-derived example:
reception -> 750-point transmitter door -> 1000-point battery debris; a battery mystery box; all four supported perks;
M14, MP5K and Stakeout stations; four exterior ducts/windows/spawners spread over three zones. Rooms have ceilings and generated
nodes. Zone activation, power, blockers and windows need no map-specific GSC. Keep exterior ducts out of playable zone
volumes and retain the gaps matched to their windows.

`relay_station.json` preserves the map maker's two-perk design. `mapkit_room.json` remains the smaller empty example;
`mapkit_test.json` is a retail overlay and includes a legacy zone marker that cannot pass the empty-zone check.
`stress_arena.json` is a crowd experiment, not a complete progression map. Existing checks are retained for these layouts;
only a completed zero-FAIL run proves a particular layout passed.
