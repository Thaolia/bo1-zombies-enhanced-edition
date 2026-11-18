// The Switch launcher's settings and start-up line (src/platform/switch/launcher_config.cpp): pure, so it runs on the
// host. ./launcher_config_test in the build folder.

#include <platform/launch_cfg.h>
#include <platform/switch/launcher_config.h>

#include <cstdio>
#include <cstring>
#include <string>

namespace
{
int g_failures = 0;

void Check(bool ok, const char *what)
{
    if (!ok)
    {
        std::printf("FAIL: %s\n", what);
        ++g_failures;
    }
}

void CheckLine(const std::string &got, const std::string &want, const char *what)
{
    if (got != want)
        std::printf("  got:  %s\n  want: %s\n", got.c_str(), want.c_str());
    Check(got == want, what);
}

bool SameSettings(const LauncherSettings &a, const LauncherSettings &b)
{
    return a.join == b.join && a.serverHost == b.serverHost && a.serverPort == b.serverPort && a.playerName == b.playerName && a.map == b.map && a.aimAssist == b.aimAssist && a.aimSlowdown == b.aimSlowdown &&
           a.aimLockon == b.aimLockon && a.aimAutoaim == b.aimAutoaim && a.god == b.god && a.tabInfo == b.tabInfo && a.backend == b.backend &&
           a.maxFps == b.maxFps && a.shadows == b.shadows && a.propDistance == b.propDistance && a.fpsCounter == b.fpsCounter &&
           a.texFilter == b.texFilter && a.startPoints == b.startPoints && a.startPerks == b.startPerks &&
           a.startPower == b.startPower && a.startPap == b.startPap && a.farRespawn == b.farRespawn && a.lanAuto == b.lanAuto && a.joinBo2Weapons == b.joinBo2Weapons && a.dualWield == b.dualWield &&
           a.joinDualWield == b.joinDualWield && a.runInfo == b.runInfo && a.height == b.height &&
           a.hitmarker == b.hitmarker && a.unlimitedPap == b.unlimitedPap && a.spawnRate == b.spawnRate &&
           a.spawnRush == b.spawnRush &&
           std::memcmp(&a.pad, &b.pad, sizeof(a.pad)) == 0;
}
} // namespace

int main()
{
    const LauncherSettings defaults;
    Check(std::string(kLauncherMaps[defaults.map].bsp) == "zombie_theater", "the default map is Kino");
    Check(kLauncherMapCount == 15,
          "the ten zombies maps, Dead Ops Arcade, the native Nuketown, TranZit, Mob of the Dead and Buried are listed");
    Check(std::string(kLauncherMaps[10].bsp) == "zombietron", "Dead Ops Arcade follows the ten zombies maps");
    const int nuketown = kLauncherMapCount - 4;
    const int transit = kLauncherMapCount - 3;
    const int prison = kLauncherMapCount - 2;
    const int buried = kLauncherMapCount - 1;
    Check(Launcher_MapKey(nuketown) == "mapkit:bo2_zm_nuked_bsp" && Launcher_MapKey(1) == "zombie_pentagon",
          "the native Nuketown's menu.cfg key is not Five's, whose bsp it shares");
    Check(Launcher_MapFileCount(0) == 0 && Launcher_MapFileCount(nuketown) == 4 &&
              Launcher_MapFile(nuketown, 0) == "mods/mapkit/layouts/bo2_zm_nuked_bsp.json" &&
              Launcher_MapFile(nuketown, 1) == "usermaps/zombie_bo2nuked/zombie_bo2nuked.ff" &&
              Launcher_MapFile(nuketown, 2) == "main/maps/zombie_bo2nuked.d3dbsp" &&
              Launcher_MapFile(nuketown, 3) == "usermaps/zombie_bo2fx/zombie_bo2fx.ff" &&
              Launcher_MapFile(nuketown, 4).empty(),
          "the native Nuketown needs its layout, zone, BSP and effects zone on the SD card; Kino needs nothing");
    Check(SameSettings(Launcher_ParseSettings(""), defaults), "an empty menu.cfg gives the defaults");

    CheckLine(Launcher_BuildLaunchLine(defaults, ""),
              "+set bo1_zombies 1 +set bo1_aimassist 1 +set aim_slowdown_enabled 1 +set aim_lockon_enabled 1"
              " +set aim_autoaim_enabled 0 +set bo1_testclient_god 0 +set fs_mods zinfo +set r_fullscreen 0"
              " +set r_customMode 1280x720 +set com_maxfps 60"
              " +set sm_enable 1 +set r_lodScaleRigid 1 +set bo1_fpscounter 1 +set bo1_runinfo 1 +set r_texFilterAnisoMax 16 +set r_texFilterMipMode 0"
              " +devmap zombie_theater",
              "the default line, with the Tab zombie counter");

    LauncherSettings custom;
    custom.map = 5; // Moon
    custom.aimAssist = false;
    custom.aimAutoaim = true;
    custom.god = true;
    custom.tabInfo = false;
    custom.backend = LAUNCHER_BACKEND_GL;
    custom.maxFps = 30;
    custom.height = 480;
    custom.shadows = false;
    custom.propDistance = 2;
    custom.fpsCounter = false;
    custom.texFilter = LAUNCHER_TEXFILTER_BILINEAR;
    CheckLine(Launcher_BuildLaunchLine(custom, "+set bo1_frameperf 200"),
              "+set bo1_zombies 1 +set bo1_aimassist 0 +set aim_slowdown_enabled 1 +set aim_lockon_enabled 1"
              " +set aim_autoaim_enabled 1 +set bo1_testclient_god 1 +set r_fullscreen 0"
              " +set r_customMode 854x480 +set com_maxfps 30 +set sm_enable 0 +set r_lodScaleRigid 2"
              " +set bo1_fpscounter 0 +set bo1_runinfo 1 +set r_texFilterAnisoMax 1 +set r_texFilterMipMode 2 +set bo1_frameperf 200"
              " +devmap zombie_moon",
              "a custom line, with the extra arguments before +devmap");
    Check(std::string(Launcher_BackendName(custom.backend)) == "gl", "the GL backend's gfx.cfg value");
    Check(std::string(Launcher_BackendName(defaults.backend)) == "deko3d", "the deko3d backend's gfx.cfg value");

    LauncherSettings trilinear;
    trilinear.texFilter = LAUNCHER_TEXFILTER_TRILINEAR;
    const std::string triLine = Launcher_BuildLaunchLine(trilinear, "");
    Check(triLine.find(" +set r_texFilterAnisoMax 1 +set r_texFilterMipMode 1 ") != std::string::npos,
          "trilinear filtering is anisotropy 1 with forced trilinear mips");

    LauncherSettings mid;
    mid.height = 540;
    Check(Launcher_BuildLaunchLine(mid, "").find(" +set r_customMode 960x540 ") != std::string::npos &&
              SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(mid)), mid),
          "540p is 960x540 and menu.cfg keeps it");

    Check(SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(custom)), custom),
          "menu.cfg round-trips a custom setting");
    Check(SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(defaults)), defaults),
          "menu.cfg round-trips the defaults");

    const LauncherSettings bad = Launcher_ParseSettings("map=zombie_nowhere\r\nmaxfps=45\nshadows=yes\nresolution=1080\n"
                                                        "backend=vulkan\ntexfilter=aniso3\nprop_distance=far\nunknown=1\nno equals sign\n");
    Check(SameSettings(bad, defaults), "unknown maps, invalid values and unknown keys keep the defaults");

    const LauncherSettings crlf = Launcher_ParseSettings(" map = zombie_pentagon \r\ngod=1\r\nmaxfps=30\r\nzinfo=0\r\n");
    Check(std::string(kLauncherMaps[crlf.map].bsp) == "zombie_pentagon" && crlf.god && crlf.maxFps == 30 && !crlf.tabInfo,
          "spaces and CRLF line ends are tolerated");

    for (int i = 0; i < kLauncherMapCount; ++i)
    {
        LauncherSettings s;
        s.map = i;
        const std::string line = Launcher_BuildLaunchLine(s, "+set x 1");
        const std::string tail = " +devmap " + std::string(kLauncherMaps[i].bsp);
        Check(line.size() > tail.size() && line.compare(line.size() - tail.size(), tail.size(), tail) == 0,
              "+devmap <map> ends every line");
    }

    LauncherSettings nuke;
    nuke.map = nuketown;
    Check(Launcher_ParseSettings(Launcher_FormatSettings(nuke)).map == nuketown, "menu.cfg keeps the native Nuketown");
    CheckLine(Launcher_BuildLaunchLine(nuke, ""),
              "+set bo1_zombies 1 +set bo1_aimassist 1 +set aim_slowdown_enabled 1 +set aim_lockon_enabled 1"
              " +set aim_autoaim_enabled 0 +set bo1_testclient_god 0 +set fs_game mods/mapkit"
              " +set bo1_mod_mapkit bo2_zm_nuked_bsp +set fs_mods mapkit zinfo +set bo1_mod_zones zombie_bo2nuked"
              " zombie_bo2fx +set bo1_bspworld maps/zombie_bo2nuked.d3dbsp +set r_fullscreen 0 +set r_customMode 1280x720"
              " +set com_maxfps 60 +set sm_enable 1 +set r_lodScaleRigid 1 +set bo1_fpscounter 1 +set bo1_runinfo 1 +set r_texFilterAnisoMax 16"
              " +set r_texFilterMipMode 0 +devmap zombie_pentagon",
              "the native Nuketown: ZmClient's MapKit layout on Five, its zone, its effects zone and BSP world");
    LauncherSettings tranzit;
    tranzit.map = transit;
    Check(Launcher_ParseSettings(Launcher_FormatSettings(tranzit)).map == transit &&
              Launcher_MapKey(transit) == "mapkit:bo2_zm_transit_bsp" && Launcher_MapFileCount(transit) == 4 &&
              Launcher_MapFile(transit, 2) == "main/maps/zombie_bo2transit.d3dbsp" &&
              Launcher_MapFile(transit, 3) == "usermaps/zombie_bo2fx/zombie_bo2fx.ff",
          "menu.cfg keeps the native TranZit, which needs its layout, zone, BSP and effects zone");
    Check(Launcher_BuildLaunchLine(tranzit, "").find(" +set bo1_mod_mapkit bo2_zm_transit_bsp +set fs_mods mapkit zinfo"
                                                     " +set bo1_mod_zones zombie_bo2transit zombie_cosmodrome zombie_bo2fx"
                                                     " +set bo1_bspworld maps/zombie_bo2transit.d3dbsp ") != std::string::npos,
          "the native TranZit loads its zone, Ascension's for Stamin-Up, then the effects, as ZmClient does");
    LauncherSettings motd;
    motd.map = prison;
    Check(Launcher_ParseSettings(Launcher_FormatSettings(motd)).map == prison &&
              Launcher_MapKey(prison) == "mapkit:bo2_zm_prison_bsp" && Launcher_MapFileCount(prison) == 4 &&
              Launcher_MapFile(prison, 2) == "main/maps/zombie_bo2prison.d3dbsp" &&
              Launcher_MapFile(prison, 3) == "usermaps/zombie_bo2fx/zombie_bo2fx.ff",
          "menu.cfg keeps the native Mob of the Dead, which needs its layout, zone, BSP and effects zone");
    Check(Launcher_BuildLaunchLine(motd, "").find(" +set bo1_mod_mapkit bo2_zm_prison_bsp +set fs_mods mapkit zinfo"
                                                  " +set bo1_mod_zones zombie_bo2prison zombie_bo2fx"
                                                  " +set bo1_bspworld maps/zombie_bo2prison.d3dbsp ") != std::string::npos,
          "the native Mob of the Dead loads its zone, then the effects, and its BSP world");
    LauncherSettings town;
    town.map = buried;
    Check(Launcher_ParseSettings(Launcher_FormatSettings(town)).map == buried &&
              Launcher_MapKey(buried) == "mapkit:bo2_zm_buried_bsp" && Launcher_MapFileCount(buried) == 4 &&
              Launcher_MapFile(buried, 2) == "main/maps/zombie_bo2buried.d3dbsp" &&
              Launcher_MapFile(buried, 3) == "usermaps/zombie_bo2fx/zombie_bo2fx.ff",
          "menu.cfg keeps the native Buried, which needs its layout, zone, BSP and effects zone");
    Check(Launcher_BuildLaunchLine(town, "").find(" +set bo1_mod_zones zombie_bo2buried zombie_cosmodrome zombie_bo2fx"
                                                  " +set bo1_bspworld maps/zombie_bo2buried.d3dbsp ") != std::string::npos,
          "the native Buried loads its zone, Ascension's for Stamin-Up, then the effects");
    nuke.tabInfo = false;
    nuke.startPoints = 5000;
    const std::string nukeKit = Launcher_BuildLaunchLine(nuke, "");
    Check(nukeKit.find(" +set fs_mods mapkit admin +set bo1_mod_zones") != std::string::npos &&
              nukeKit.find(" +set zm_startpoints 5000") != std::string::npos,
          "the start kit stacks mods/admin after mapkit");
    nuke.tabInfo = false;
    nuke.startPoints = 0;
    Check(Launcher_BuildLaunchLine(nuke, "").find("fs_mods") == std::string::npos,
          "without Tab info nor kit the native Nuketown sets fs_game only");
    nuke.join = true;
    nuke.serverHost = "192.168.1.10";
    Check(Launcher_BuildLaunchLine(nuke, "").find("mapkit") == std::string::npos,
          "a join ignores the native Nuketown's MapKit settings");

    LauncherSettings join;
    join.join = true;
    join.serverHost = "192.168.1.20";
    join.serverPort = 29070;
    join.playerName = "Switch1";
    join.god = true;
    CheckLine(Launcher_BuildLaunchLine(join, "+set bo1_frameperf 200"),
              "+set bo1_zombies 1 +set bo1_aimassist 1 +set aim_slowdown_enabled 1 +set aim_lockon_enabled 1"
              " +set aim_autoaim_enabled 0 +set bo1_testclient_god 0 +set r_fullscreen 0"
              " +set r_customMode 1280x720 +set com_maxfps 60 +set sm_enable 1 +set r_lodScaleRigid 1"
              " +set bo1_fpscounter 1 +set bo1_runinfo 1 +set r_texFilterAnisoMax 16 +set r_texFilterMipMode 0 +set name Switch1"
              " +set bo1_frameperf 200 +set cl_allowWanConnect 1 +set cl_autoConnect 192.168.1.20:29070",
              "a join: the game's menu, then cl_autoConnect, no +devmap, no local god mode, no fs_mods (the server's)");
    Check(SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(join)), join), "menu.cfg round-trips a join");

    LauncherSettings noServer;
    noServer.join = true;
    noServer.god = true;
    CheckLine(Launcher_BuildLaunchLine(noServer, ""),
              "+set bo1_zombies 1 +set bo1_aimassist 1 +set aim_slowdown_enabled 1 +set aim_lockon_enabled 1"
              " +set aim_autoaim_enabled 0 +set bo1_testclient_god 1 +set fs_mods zinfo +set r_fullscreen 0"
              " +set r_customMode 1280x720 +set com_maxfps 60"
              " +set sm_enable 1 +set r_lodScaleRigid 1 +set bo1_fpscounter 1 +set bo1_runinfo 1 +set r_texFilterAnisoMax 16 +set r_texFilterMipMode 0"
              " +devmap zombie_theater",
              "a join without a server address starts the solo game");

    // The start kit: mods/admin stacked after zinfo, its two dvars, perks in kLauncherPerks order.
    LauncherSettings kit;
    kit.startPoints = 50000;
    kit.startPerks = (1u << 1) | (1u << 0); // revive, jugg
    const std::string kitLine = Launcher_BuildLaunchLine(kit, "");
    Check(kitLine.find(" +set fs_mods zinfo admin +set zm_startpoints 50000 +set zm_startperks jugg,revive ") !=
              std::string::npos,
          "a start kit stacks mods/admin and sets zm_startpoints / zm_startperks");
    Check(SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(kit)), kit), "menu.cfg round-trips a start kit");
    LauncherSettings kitNoTab = kit;
    kitNoTab.tabInfo = false;
    kitNoTab.startPoints = 0;
    const std::string noTabLine = Launcher_BuildLaunchLine(kitNoTab, "");
    Check(noTabLine.find(" +set fs_mods admin +set zm_startperks jugg,revive ") != std::string::npos &&
              noTabLine.find("zm_startpoints") == std::string::npos,
          "perks alone: fs_mods admin, no zm_startpoints");
    LauncherSettings kitJoin = kit;
    kitJoin.join = true;
    kitJoin.serverHost = "192.168.1.20";
    Check(Launcher_BuildLaunchLine(kitJoin, "").find("zm_start") == std::string::npos,
          "a join leaves the start to the server");
    LauncherSettings power;
    power.tabInfo = false;
    power.startPower = true;
    const std::string powerLine = Launcher_BuildLaunchLine(power, "");
    Check(powerLine.find(" +set fs_mods admin +set zm_startpower 1 +set r_fullscreen 0 ") != std::string::npos &&
              Launcher_BuildLaunchLine(defaults, "").find("zm_startpower") == std::string::npos,
          "the start power alone stacks mods/admin and sets zm_startpower, off by default");
    Check(SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(power)), power),
          "menu.cfg round-trips the start power");
    LauncherSettings pap;
    pap.tabInfo = false;
    pap.startPap = true;
    const std::string papLine = Launcher_BuildLaunchLine(pap, "");
    Check(papLine.find(" +set fs_mods admin +set zm_startpap 1 +set r_fullscreen 0 ") != std::string::npos &&
              Launcher_BuildLaunchLine(defaults, "").find("zm_startpap") == std::string::npos,
          "the start Pack-a-Punch alone stacks mods/admin and sets zm_startpap, off by default");
    Check(SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(pap)), pap),
          "menu.cfg round-trips the start Pack-a-Punch");
    LauncherSettings far;
    far.tabInfo = false;
    far.farRespawn = 2500;
    const std::string farLine = Launcher_BuildLaunchLine(far, "");
    Check(farLine.find(" +set fs_mods admin +set zm_farrespawn 2500 +set r_fullscreen 0 ") != std::string::npos &&
              Launcher_BuildLaunchLine(defaults, "").find("zm_farrespawn") == std::string::npos,
          "the far zombies' distance alone stacks mods/admin and sets zm_farrespawn, off by default");
    Check(SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(far)), far) &&
              Launcher_ParseSettings("far_respawn=1234\n").farRespawn == 0,
          "menu.cfg round-trips the far zombies' distance, and refuses one off the list");
    LauncherSettings manual;
    manual.lanAuto = false;
    Check(SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(manual)), manual) &&
              Launcher_ParseSettings("").lanAuto,
          "menu.cfg round-trips the LAN search switch, on by default");
    LauncherSettings joinBo2;
    joinBo2.join = true;
    joinBo2.serverHost = "192.168.1.20";
    const bool noFiles = Launcher_BuildLaunchLine(joinBo2, "").find("bo2weapons") == std::string::npos;
    joinBo2.bo2WeaponsInstalled = true;
    const std::string joinLine = Launcher_BuildLaunchLine(joinBo2, "");
    LauncherSettings soloWith;
    soloWith.bo2WeaponsInstalled = true;
    Check(noFiles && joinLine.find(" +set fs_mods bo2weapons ") != std::string::npos &&
              joinLine.find(" +set fs_mods bo2weapons ") < joinLine.find("cl_autoConnect") &&
              Launcher_BuildLaunchLine(soloWith, "").find("bo2weapons") == std::string::npos,
          "a join loads the BO2 weapons when they are on the SD card, by default; a solo game does not");
    joinBo2.joinBo2Weapons = false;
    Check(Launcher_BuildLaunchLine(joinBo2, "").find("bo2weapons") == std::string::npos &&
              SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(joinBo2)), joinBo2),
          "the BO2 weapons can be left out of a join, and menu.cfg keeps that");
    LauncherSettings dual;
    dual.dualWield = true;
    const bool dualNoFiles = Launcher_BuildLaunchLine(dual, "").find("dualwield") == std::string::npos;
    dual.dualWieldInstalled = true;
    LauncherSettings dualDeadOps = dual;
    while (std::string(kLauncherMaps[dualDeadOps.map].bsp) != "zombietron")
        ++dualDeadOps.map;
    Check(dualNoFiles && Launcher_BuildLaunchLine(dual, "").find(" +set fs_mods zinfo dualwield ") != std::string::npos &&
              Launcher_BuildLaunchLine(dualDeadOps, "").find("dualwield") == std::string::npos &&
              SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(dual)), dual),
          "a solo game stacks the dual-wield weapons when they are on the SD card (not on Dead Ops Arcade); menu.cfg "
          "keeps the choice");
    LauncherSettings joinBoth = joinBo2;
    joinBoth.joinBo2Weapons = true;
    joinBoth.dualWieldInstalled = true;
    LauncherSettings joinDualOff = joinBoth;
    joinDualOff.joinDualWield = false;
    Check(Launcher_BuildLaunchLine(joinBoth, "").find(" +set fs_mods bo2weapons dualwield ") != std::string::npos &&
              Launcher_BuildLaunchLine(joinDualOff, "").find("dualwield") == std::string::npos,
          "a join loads the dual-wield weapons beside the BO2 ones, by default, and can leave them out");
    LauncherSettings mods;
    mods.hitmarker = true;
    mods.unlimitedPap = true;
    mods.spawnRate = 5;
    mods.spawnRush = false;
    const bool upapNoScript = Launcher_BuildLaunchLine(mods, "").find("unlimitedpap") == std::string::npos;
    mods.unlimitedPapInstalled = true;
    LauncherSettings modsDeadOps = mods;
    while (std::string(kLauncherMaps[modsDeadOps.map].bsp) != "zombietron")
        ++modsDeadOps.map;
    LauncherSettings modsJoin = mods;
    modsJoin.join = true;
    modsJoin.serverHost = "192.168.1.20";
    const std::string modsLine = Launcher_BuildLaunchLine(modsDeadOps, "");
    Check(upapNoScript &&
              Launcher_BuildLaunchLine(mods, "").find(" +set fs_mods zinfo hitmarker unlimitedpap spawnrate "
                                                      "+set spawnrate_mult 5 +set spawnrate_rush 0 ") !=
                  std::string::npos &&
              modsLine.find("hitmarker") == std::string::npos && modsLine.find("spawnrate") == std::string::npos &&
              Launcher_BuildLaunchLine(modsJoin, "").find("hitmarker") == std::string::npos &&
              SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(mods)), mods) &&
              Launcher_ParseSettings("spawnrate=7\n").spawnRate == 0,
          "a solo game stacks hitmarker, unlimitedpap (with its script on the SD card) and spawnrate, not on Dead Ops "
          "Arcade nor on a join; menu.cfg keeps them");
    LauncherSettings run;
    run.runInfo = 2;
    Check(Launcher_BuildLaunchLine(run, "").find(" +set bo1_runinfo 2") != std::string::npos &&
              Launcher_BuildLaunchLine(defaults, "").find(" +set bo1_runinfo 1") != std::string::npos &&
              SameSettings(Launcher_ParseSettings(Launcher_FormatSettings(run)), run) &&
              Launcher_ParseSettings("runinfo=7\n").runInfo == 1,
          "the run info setting reaches bo1_runinfo (1 by default) and menu.cfg keeps it, 0 to 2 only");
    const LauncherSettings kitParsed =
        Launcher_ParseSettings("start_points=1234\nstart_perks= mule , nope,jugg\n");
    Check(kitParsed.startPoints == 0 && kitParsed.startPerks == ((1u << 7) | 1u),
          "an unknown point count keeps the default, unknown perks are skipped");

    LauncherSettings noName = join;
    noName.playerName.clear();
    Check(Launcher_BuildLaunchLine(noName, "").find("+set name") == std::string::npos,
          "no name keeps the game's own");

    const LauncherSettings badJoin =
        Launcher_ParseSettings("mode=online\nserver=1.2.3.4 +set x\nport=70000\nname=Bad Name\n");
    Check(!badJoin.join && badJoin.serverHost.empty() && badJoin.serverPort == 3074 && badJoin.playerName.empty(),
          "an unknown mode, a host with a blank, a port past 65535 and a name with a blank keep the defaults");

    Check(Launcher_ValidServerHost("192.168.1.20") && Launcher_ValidServerHost("my-server.lan"),
          "an IPv4 address and a host name are valid hosts");
    Check(!Launcher_ValidServerHost("") && !Launcher_ValidServerHost("1.2.3.4:3074") &&
              !Launcher_ValidServerHost("1.2.3.4;quit") && !Launcher_ValidServerHost(std::string(64, '1')),
          "empty, with a port, with a semicolon and 64 characters are refused hosts");
    int port = 3074;
    Check(Launcher_ParsePort("29070", &port) && port == 29070, "a port parses");
    Check(!Launcher_ParsePort("", &port) && !Launcher_ParsePort("0", &port) && !Launcher_ParsePort("65536", &port) &&
              !Launcher_ParsePort("30a", &port) && !Launcher_ParsePort("123456", &port) && port == 29070,
          "empty, 0, past 65535, non-digits and six digits are refused ports, the value kept");
    Check(Launcher_ValidPlayerName("Player_2") && !Launcher_ValidPlayerName("") &&
              !Launcher_ValidPlayerName("sixteen_letters_") && !Launcher_ValidPlayerName("a\"b"),
          "player names: 1-15 safe characters");

    // The pad layout in menu.cfg.
    {
        Check(Bo1_PadRemapIsIdentity(defaults.pad), "the default pad layout is the game's");
        LauncherSettings custom;
        Bo1_PadRemapAssign(&custom.pad, BO1_PAD_RTRIGGER, BO1_PAD_RSHOULDER); // fire on R, grenade on ZR
        Bo1_PadRemapAssign(&custom.pad, BO1_PAD_A, BO1_PAD_B);                // jump on B, crouch on A
        const std::string text = Launcher_FormatSettings(custom);
        Check(text.find("pad_zr=r\n") != std::string::npos && text.find("pad_r=zr\n") != std::string::npos &&
                  text.find("pad_a=b\n") != std::string::npos && text.find("pad_x=x\n") != std::string::npos,
              "menu.cfg lists every pad control with its button");
        Check(SameSettings(Launcher_ParseSettings(text), custom), "a custom pad layout round-trips through menu.cfg");
        const LauncherSettings dup = Launcher_ParseSettings("map=zombie_moon\npad_a=b\n");
        Check(Bo1_PadRemapIsIdentity(dup.pad) && dup.map == 5,
              "a layout with two controls on one button falls back to the game's, the other settings kept");
        const LauncherSettings swap = Launcher_ParseSettings("pad_a=b\npad_b=a\npad_nope=x\npad_x=nope\n");
        Check(swap.pad.source[BO1_PAD_A] == BO1_PAD_B && swap.pad.source[BO1_PAD_B] == BO1_PAD_A &&
                  swap.pad.source[BO1_PAD_X] == BO1_PAD_X,
              "a swap in two lines loads; unknown pad names are skipped");
        Check(std::string(Launcher_PadButtonLabel(BO1_PAD_RTRIGGER)) == "ZR" &&
                  std::string(Launcher_PadActionLabel(BO1_PAD_RTRIGGER)) == "Tirer" &&
                  std::string(Launcher_PadButtonLabel(BO1_PAD_COUNT)) == "?",
              "pad labels: ZR fires; past the list is \"?\"");
        bool ascii = true;
        for (int i = 0; i < BO1_PAD_COUNT; ++i)
            for (const char *t : {Launcher_PadButtonLabel(i), Launcher_PadActionLabel(i)})
                for (; *t; ++t)
                    ascii = ascii && (unsigned char)*t < 128;
        Check(ascii, "pad labels are ASCII (the console font has no accents)");
        // Cycling one line through every button keeps a permutation at each step.
        LauncherSettings cycle;
        bool perm = true;
        for (int step = 0; step < 40; ++step)
        {
            Bo1_PadRemapAssign(&cycle.pad, BO1_PAD_Y, (cycle.pad.source[BO1_PAD_Y] + 1) % BO1_PAD_COUNT);
            perm = perm && Bo1_PadRemapValid(cycle.pad);
        }
        Check(perm, "changing one line again and again keeps every control on its own button");
    }

    char cfg[64] = "\r\n  +set a 1\r\n+set\tb 2\n\n  ";
    const size_t cfgLen = LaunchCfg_Normalize(cfg, std::char_traits<char>::length(cfg));
    Check(cfgLen == 18 && std::string(cfg) == "+set a 1  +set b 2", "launch.cfg: line breaks read as blanks, ends trimmed");
    char blank[8] = " \r\n\t ";
    Check(LaunchCfg_Normalize(blank, 5) == 0 && blank[0] == 0, "launch.cfg: a blank file is empty");

    if (g_failures)
    {
        std::printf("launcher_config_test: %d check(s) failed\n", g_failures);
        return 1;
    }
    std::printf("launcher_config_test: all checks passed\n");
    return 0;
}
