#include "launcher_config.h"

#include <cstdlib>
#include <cstring>

// The labels of tools/mod-launcher.hta's MAPS, Kino first: it is the default and the map every console test used.
// Dead Ops Arcade is not in the .hta's list.
const LauncherMap kLauncherMaps[] = {
    {"zombie_theater", "Kino der Toten", nullptr, nullptr, nullptr, nullptr},
    {"zombie_pentagon", "Five", nullptr, nullptr, nullptr, nullptr},
    {"zombie_cosmodrome", "Ascension", nullptr, nullptr, nullptr, nullptr},
    {"zombie_coast", "Call of the Dead", nullptr, nullptr, nullptr, nullptr},
    {"zombie_temple", "Shangri-La", nullptr, nullptr, nullptr, nullptr},
    {"zombie_moon", "Moon", nullptr, nullptr, nullptr, nullptr},
    {"zombie_cod5_prototype", "Nacht der Untoten", nullptr, nullptr, nullptr, nullptr},
    {"zombie_cod5_asylum", "Verruckt", nullptr, nullptr, nullptr, nullptr},
    {"zombie_cod5_sumpf", "Shi No Numa", nullptr, nullptr, nullptr, nullptr},
    {"zombie_cod5_factory", "Der Riese", nullptr, nullptr, nullptr, nullptr},
    {"zombietron", "Dead Ops Arcade", nullptr, nullptr, nullptr, nullptr},
    // ZmClient's "Mapkit : Nuketown native": MapKit's Nuketown on the world of its own BSP (tools/bo2/bo2_bsp.py)
    // and the BO1 effects on BO2's createfx spots (docs/BO2_MAPS.md, "Placed effects")
    {"zombie_pentagon", "Nuketown (BO2, natif)", "bo2_zm_nuked_bsp", "zombie_bo2nuked", nullptr, "zombie_bo2fx"},
    // ZmClient's "TranZit native", with Ascension's zone for the Stamin-Up machine (_mapkit.gsc mapkit_marathon_perk)
    // and the BO1 effects on BO2's createfx spots, as Nuketown
    {"zombie_pentagon", "TranZit (BO2, natif)", "bo2_zm_transit_bsp", "zombie_bo2transit", "zombie_cosmodrome",
     "zombie_bo2fx"},
    // ZmClient's "Mob of the Dead native": the island's world (tools/bo2/bo2_bsp.py) and its BO1 effects
    {"zombie_pentagon", "Mob of the Dead (BO2, natif)", "bo2_zm_prison_bsp", "zombie_bo2prison", nullptr,
     "zombie_bo2fx"},
    // ZmClient's "Buried native", with Ascension's zone for its Stamin-Up machine and its BO1 effects, as TranZit
    {"zombie_pentagon", "Buried (BO2, natif)", "bo2_zm_buried_bsp", "zombie_bo2buried", "zombie_cosmodrome",
     "zombie_bo2fx"},
};
const int kLauncherMapCount = int(sizeof(kLauncherMaps) / sizeof(kLauncherMaps[0]));

std::string Launcher_MapKey(int map)
{
    const LauncherMap &m = kLauncherMaps[map];
    return m.mapkit ? std::string("mapkit:") + m.mapkit : std::string(m.bsp);
}

int Launcher_MapFileCount(int map)
{
    const LauncherMap &m = kLauncherMaps[map];
    return (m.mapkit ? 1 : 0) + (m.zone ? 2 : 0) + (m.fxZone ? 1 : 0);
}

std::string Launcher_MapFile(int map, int i)
{
    const LauncherMap &m = kLauncherMaps[map];
    if (m.mapkit && i-- == 0)
        return std::string("mods/mapkit/layouts/") + m.mapkit + ".json";
    if (m.zone && i == 0)
        return std::string("usermaps/") + m.zone + "/" + m.zone + ".ff";
    if (m.zone && i == 1)
        return std::string("main/maps/") + m.zone + ".d3dbsp";
    if (m.fxZone && i == (m.zone ? 2 : 0))
        return std::string("usermaps/") + m.fxZone + "/" + m.fxZone + ".ff";
    return "";
}

const int kLauncherStartPoints[] = {0, 1000, 2500, 5000, 10000, 25000, 50000, 100000};
const int kLauncherStartPointCount = int(sizeof(kLauncherStartPoints) / sizeof(kLauncherStartPoints[0]));
const LauncherPropDistance kLauncherPropDistances[] = {
    {"normal", "Normale", "1"},
    {"reduced", "Reduite", "1.5"},
    {"short", "Courte", "2"},
};
const int kLauncherPropDistanceCount = int(sizeof(kLauncherPropDistances) / sizeof(kLauncherPropDistances[0]));

const LauncherUpscaler kLauncherUpscalers[] = {
    {"off", "Non", nullptr},
    {"fsr1", "FSR 1.0", "fsr1"},
    {"asr_quality", "ASR qualite", "asr"},
    {"asr_balanced", "ASR equilibre", "asr_balanced"},
    {"asr_performance", "ASR performance", "asr_performance"},
};
const int kLauncherUpscalerCount = int(sizeof(kLauncherUpscalers) / sizeof(kLauncherUpscalers[0]));

bool Launcher_UpscalerIsAsr(int index)
{
    const char *mode = index >= 0 && index < kLauncherUpscalerCount ? kLauncherUpscalers[index].mode : nullptr;
    return mode && !std::strncmp(mode, "asr", 3);
}

const LauncherFsrSharpness kLauncherFsrSharpness[] = {
    {"max", "Maximale", "0"},
    {"strong", "Forte", "0.2"}, // AMD's default
    {"medium", "Moyenne", "0.5"},
    {"soft", "Douce", "1"},
    {"low", "Faible", "2"},
};
const int kLauncherFsrSharpnessCount = int(sizeof(kLauncherFsrSharpness) / sizeof(kLauncherFsrSharpness[0]));

const int kLauncherFarRespawns[] = {0, 1500, 2500, 4000};
const int kLauncherFarRespawnCount = int(sizeof(kLauncherFarRespawns) / sizeof(kLauncherFarRespawns[0]));
const int kLauncherSpawnRates[] = {0, 2, 3, 5, 10};
const int kLauncherSpawnRateCount = int(sizeof(kLauncherSpawnRates) / sizeof(kLauncherSpawnRates[0]));
const LauncherPerk kLauncherPerks[] = {
    {"jugg", "Juggernog"},   {"revive", "Quick Revive"}, {"speed", "Speed Cola"},       {"doubletap", "Double Tap"},
    {"staminup", "Stamin-Up"}, {"phd", "PhD Flopper"},   {"deadshot", "Deadshot Daiquiri"}, {"mule", "Mule Kick"},
};
const int kLauncherPerkCount = int(sizeof(kLauncherPerks) / sizeof(kLauncherPerks[0]));

namespace
{
const char *const kBackendNames[LAUNCHER_BACKEND_COUNT] = {"deko3d", "gl"};

struct TexFilterInfo
{
    const char *key;   // menu.cfg value
    const char *label; // menu text
    int anisoMax;      // r_texFilterAnisoMax
    int mipMode;       // r_texFilterMipMode: 0 Unchanged, 1 Force Trilinear, 2 Force Bilinear
};

const TexFilterInfo kTexFilters[LAUNCHER_TEXFILTER_COUNT] = {
    {"aniso16", "Anisotrope 16x", 16, 0}, {"aniso8", "Anisotrope 8x", 8, 0},
    {"aniso4", "Anisotrope 4x", 4, 0},    {"aniso2", "Anisotrope 2x", 2, 0},
    {"trilinear", "Trilineaire", 1, 1},   {"bilinear", "Bilineaire", 1, 2},
};

struct PadInfo
{
    const char *key;    // menu.cfg: pad_<key>=<key>
    const char *label;  // the button as printed on the Switch's pads
    const char *action; // what the game control does (ASCII: the console font has no accents)
};

// Bo1PadControl order. The actions are the Switch build's binds: retail buttons_default.cfg, then
// Switch_ApplyPadLayout (qcommon/cmd.cpp: Y reloads, L switches weapon, d-pad down throws the special grenade).
static_assert(BO1_PAD_COUNT == 16, "kPads lists every control");
const PadInfo kPads[BO1_PAD_COUNT] = {
    {"a", "A", "Sauter / valider"},
    {"b", "B", "S'accroupir / retour"},
    {"x", "X", "Utiliser / recharger"},
    {"y", "Y", "Recharger"},
    {"l", "L", "Changer d'arme"},
    {"r", "R", "Grenade"},
    {"zl", "ZL", "Viser"},
    {"zr", "ZR", "Tirer"},
    {"plus", "+", "Pause (menu du jeu)"},
    {"minus", "-", "Tableau des scores"},
    {"lstick", "Stick G", "Sprint"},
    {"rstick", "Stick D", "Couteau"},
    {"up", "Haut", "Emplacement 1"},
    {"down", "Bas", "Grenade speciale"},
    {"left", "Gauche", "Emplacement 3"},
    {"right", "Droite", "Emplacement 4"},
};

int PadIndex(const std::string &key)
{
    for (int i = 0; i < BO1_PAD_COUNT; ++i)
        if (key == kPads[i].key)
            return i;
    return -1;
}

bool ParseBool(const std::string &value, bool *out)
{
    if (value == "1")
        *out = true;
    else if (value == "0")
        *out = false;
    else
        return false;
    return true;
}

std::string Trim(const std::string &s)
{
    size_t b = 0, e = s.size();
    while (b < e && std::strchr(" \t\r\n", s[b]))
        ++b;
    while (e > b && std::strchr(" \t\r\n", s[e - 1]))
        --e;
    return s.substr(b, e - b);
}

bool AddressChar(char c)
{
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '.' || c == '-';
}

void Apply(LauncherSettings *s, const std::string &key, const std::string &value)
{
    if (key == "mode")
    {
        if (value == "solo" || value == "join")
            s->join = value == "join";
    }
    else if (key == "server")
    {
        if (Launcher_ValidServerHost(value))
            s->serverHost = value;
    }
    else if (key == "port")
        Launcher_ParsePort(value, &s->serverPort);
    else if (key == "name")
    {
        if (Launcher_ValidPlayerName(value))
            s->playerName = value;
    }
    else if (key == "server_password")
    {
        if (Launcher_ValidPassword(value))
            s->serverPassword = value;
    }
    else if (key == "join_detect")
        ParseBool(value, &s->joinDetectMods);
    else if (key == "map")
    {
        for (int i = 0; i < kLauncherMapCount; ++i)
            if (value == Launcher_MapKey(i))
                s->map = i;
    }
    else if (key == "aimassist")
        ParseBool(value, &s->aimAssist);
    else if (key == "aim_slowdown")
        ParseBool(value, &s->aimSlowdown);
    else if (key == "aim_lockon")
        ParseBool(value, &s->aimLockon);
    else if (key == "aim_autoaim")
        ParseBool(value, &s->aimAutoaim);
    else if (key == "god")
        ParseBool(value, &s->god);
    else if (key == "zinfo")
        ParseBool(value, &s->tabInfo);
    else if (key == "start_points")
    {
        for (int i = 0; i < kLauncherStartPointCount; ++i)
            if (value == std::to_string(kLauncherStartPoints[i]))
                s->startPoints = kLauncherStartPoints[i];
    }
    else if (key == "start_perks")
    {
        // comma-separated names; unknown ones are skipped
        s->startPerks = 0;
        size_t pos = 0;
        while (pos <= value.size())
        {
            size_t end = value.find(',', pos);
            if (end == std::string::npos)
                end = value.size();
            const std::string name = Trim(value.substr(pos, end - pos));
            for (int i = 0; i < kLauncherPerkCount; ++i)
                if (name == kLauncherPerks[i].key)
                    s->startPerks |= 1u << i;
            pos = end + 1;
        }
    }
    else if (key == "backend")
    {
        for (int i = 0; i < LAUNCHER_BACKEND_COUNT; ++i)
            if (value == kBackendNames[i])
                s->backend = LauncherBackend(i);
    }
    else if (key == "start_power")
        ParseBool(value, &s->startPower);
    else if (key == "lan_auto")
        ParseBool(value, &s->lanAuto);
    else if (key == "join_bo2weapons")
        ParseBool(value, &s->joinBo2Weapons);
    else if (key == "dualwield")
        ParseBool(value, &s->dualWield);
    else if (key == "join_dualwield")
        ParseBool(value, &s->joinDualWield);
    else if (key == "start_pap")
        ParseBool(value, &s->startPap);
    else if (key == "far_respawn")
    {
        for (int i = 0; i < kLauncherFarRespawnCount; ++i)
            if (value == std::to_string(kLauncherFarRespawns[i]))
                s->farRespawn = kLauncherFarRespawns[i];
    }
    else if (key == "hitmarker")
        ParseBool(value, &s->hitmarker);
    else if (key == "unlimitedpap")
        ParseBool(value, &s->unlimitedPap);
    else if (key == "spawnrate")
    {
        for (int i = 0; i < kLauncherSpawnRateCount; ++i)
            if (value == std::to_string(kLauncherSpawnRates[i]))
                s->spawnRate = kLauncherSpawnRates[i];
    }
    else if (key == "spawnrate_rush")
        ParseBool(value, &s->spawnRush);
    else if (key == "resolution")
    {
        if (value == "480" || value == "540" || value == "720")
            s->height = std::atoi(value.c_str());
    }
    else if (key == "fsr1")
    {
        // menu.cfg before the upscaler choice; a later upscaler= line wins
        bool fsr1 = false;
        ParseBool(value, &fsr1);
        s->upscaler = fsr1 ? 1 : 0;
    }
    else if (key == "upscaler")
    {
        for (int i = 0; i < kLauncherUpscalerCount; ++i)
            if (value == kLauncherUpscalers[i].key)
                s->upscaler = i;
    }
    else if (key == "output")
    {
        if (value == "720" || value == "1080")
            s->output = std::atoi(value.c_str());
    }
    else if (key == "fsr_sharpness")
    {
        for (int i = 0; i < kLauncherFsrSharpnessCount; ++i)
            if (value == kLauncherFsrSharpness[i].key)
                s->fsrSharpness = i;
    }
    else if (key == "maxfps")
    {
        if (value == "30" || value == "60")
            s->maxFps = std::atoi(value.c_str());
    }
    else if (key == "shadows")
        ParseBool(value, &s->shadows);
    else if (key == "prop_distance")
    {
        for (int i = 0; i < kLauncherPropDistanceCount; ++i)
            if (value == kLauncherPropDistances[i].key)
                s->propDistance = i;
    }
    else if (key == "runinfo")
    {
        if (value == "0" || value == "1" || value == "2")
            s->runInfo = value[0] - '0';
    }
    else if (key == "fpscounter")
        ParseBool(value, &s->fpsCounter);
    else if (key.compare(0, 4, "pad_") == 0)
    {
        // checked as a whole once every line is read (Launcher_ParseSettings)
        const int control = PadIndex(key.substr(4));
        const int physical = PadIndex(value);
        if (control >= 0 && physical >= 0)
            s->pad.source[control] = (unsigned char)physical;
    }
    else if (key == "texfilter")
    {
        for (int i = 0; i < LAUNCHER_TEXFILTER_COUNT; ++i)
            if (value == kTexFilters[i].key)
                s->texFilter = LauncherTexFilter(i);
    }
}
} // namespace

LauncherSettings Launcher_ParseSettings(const std::string &text)
{
    LauncherSettings s;
    size_t pos = 0;
    while (pos < text.size())
    {
        size_t end = text.find('\n', pos);
        if (end == std::string::npos)
            end = text.size();
        const std::string line = text.substr(pos, end - pos);
        pos = end + 1;
        const size_t eq = line.find('=');
        if (eq != std::string::npos)
            Apply(&s, Trim(line.substr(0, eq)), Trim(line.substr(eq + 1)));
    }
    // A layout that gives two game controls one button would leave another without any (perhaps the menus' A).
    if (!Bo1_PadRemapValid(s.pad))
        Bo1_PadRemapIdentity(&s.pad);
    return s;
}

std::string Launcher_FormatSettings(const LauncherSettings &s)
{
    std::string out;
    out += std::string("mode=") + (s.join ? "join" : "solo") + "\n";
    out += "server=" + s.serverHost + "\n";
    out += "port=" + std::to_string(s.serverPort) + "\n";
    out += "name=" + s.playerName + "\n";
    out += "server_password=" + s.serverPassword + "\n";
    out += std::string("join_detect=") + (s.joinDetectMods ? "1" : "0") + "\n";
    out += "map=" + Launcher_MapKey(s.map) + "\n";
    out += std::string("aimassist=") + (s.aimAssist ? "1" : "0") + "\n";
    out += std::string("aim_slowdown=") + (s.aimSlowdown ? "1" : "0") + "\n";
    out += std::string("aim_lockon=") + (s.aimLockon ? "1" : "0") + "\n";
    out += std::string("aim_autoaim=") + (s.aimAutoaim ? "1" : "0") + "\n";
    out += std::string("god=") + (s.god ? "1" : "0") + "\n";
    out += std::string("zinfo=") + (s.tabInfo ? "1" : "0") + "\n";
    out += "start_points=" + std::to_string(s.startPoints) + "\n";
    out += "start_perks=" + Launcher_StartPerkList(s) + "\n";
    out += std::string("backend=") + kBackendNames[s.backend] + "\n";
    out += std::string("start_power=") + (s.startPower ? "1" : "0") + "\n";
    out += std::string("start_pap=") + (s.startPap ? "1" : "0") + "\n";
    out += std::string("lan_auto=") + (s.lanAuto ? "1" : "0") + "\n";
    out += std::string("join_bo2weapons=") + (s.joinBo2Weapons ? "1" : "0") + "\n";
    out += std::string("dualwield=") + (s.dualWield ? "1" : "0") + "\n";
    out += std::string("join_dualwield=") + (s.joinDualWield ? "1" : "0") + "\n";
    out += "far_respawn=" + std::to_string(s.farRespawn) + "\n";
    out += std::string("hitmarker=") + (s.hitmarker ? "1" : "0") + "\n";
    out += std::string("unlimitedpap=") + (s.unlimitedPap ? "1" : "0") + "\n";
    out += "spawnrate=" + std::to_string(s.spawnRate) + "\n";
    out += std::string("spawnrate_rush=") + (s.spawnRush ? "1" : "0") + "\n";
    out += "resolution=" + std::to_string(s.height) + "\n";
    out += std::string("upscaler=") + kLauncherUpscalers[s.upscaler].key + "\n";
    out += "output=" + std::to_string(s.output) + "\n";
    out += std::string("fsr_sharpness=") + kLauncherFsrSharpness[s.fsrSharpness].key + "\n";
    out += "maxfps=" + std::to_string(s.maxFps) + "\n";
    out += std::string("shadows=") + (s.shadows ? "1" : "0") + "\n";
    out += std::string("prop_distance=") + kLauncherPropDistances[s.propDistance].key + "\n";
    out += std::string("fpscounter=") + (s.fpsCounter ? "1" : "0") + "\n";
    out += "runinfo=" + std::to_string(s.runInfo) + "\n";
    out += std::string("texfilter=") + kTexFilters[s.texFilter].key + "\n";
    for (int i = 0; i < BO1_PAD_COUNT; ++i)
        out += std::string("pad_") + kPads[i].key + "=" + kPads[s.pad.source[i]].key + "\n";
    return out;
}

std::string Launcher_BuildLaunchLine(const LauncherSettings &s, const std::string &extra)
{
    const TexFilterInfo &filter = kTexFilters[s.texFilter];
    const bool join = s.join && Launcher_ValidServerHost(s.serverHost);
    std::string line = "+set bo1_zombies 1";
    // The three switches only act while bo1_aimassist is on (AimAssist_PlayerDisabledAutoAim), so they keep their
    // values when the assist is off and come back as they were.
    line += std::string(" +set bo1_aimassist ") + (s.aimAssist ? "1" : "0");
    line += std::string(" +set aim_slowdown_enabled ") + (s.aimSlowdown ? "1" : "0");
    line += std::string(" +set aim_lockon_enabled ") + (s.aimLockon ? "1" : "0");
    line += std::string(" +set aim_autoaim_enabled ") + (s.aimAutoaim ? "1" : "0");
    // Not the `god` command: it is a toggle that ClientSpawn clears. This dvar puts the god-mode bit back on every
    // playing client around each server frame (G_SP_HeadlessTestClientFrame).
    // Only a local server reads it: the dedicated server decides god mode for its players.
    line += std::string(" +set bo1_testclient_god ") + (s.god && !join ? "1" : "0");
    // The dedicated server stacks mods/zinfo for all its players itself (FS_ModStackNames), and decides its players'
    // start. Before the extra, so a launch_extra.cfg that sets its own fs_mods wins. mods/admin gives the start kit.
    const bool kit = !join && (s.startPoints > 0 || s.startPerks != 0 || s.startPower || s.startPap ||
                                s.farRespawn > 0);
    // A MapKit layout runs with fs_game mods/mapkit, which a fs_mods stack names first (ZmClient's solo_mod_flags).
    const LauncherMap &map = kLauncherMaps[s.map];
    const bool mapkit = !join && map.mapkit;
    if (mapkit)
        line += std::string(" +set fs_game mods/mapkit +set bo1_mod_mapkit ") + map.mapkit;
    // mods/dualwield needs a box: Dead Ops Arcade has none (ZmClient's bo2_weapons_available)
    const bool dual = !join && s.dualWield && s.dualWieldInstalled && strcmp(map.bsp, "zombietron") != 0;
    // mods/hitmarker, mods/unlimitedpap and mods/spawnrate: Dead Ops Arcade is not a round-based zombies map
    const bool zm = !join && strcmp(map.bsp, "zombietron") != 0;
    const bool hit = zm && s.hitmarker;
    const bool upap = zm && s.unlimitedPap && s.unlimitedPapInstalled;
    const bool rate = zm && s.spawnRate > 0;
    if (!join && (s.tabInfo || kit || dual || hit || upap || rate))
        line += std::string(" +set fs_mods") + (mapkit ? " mapkit" : "") + (s.tabInfo ? " zinfo" : "") +
                (kit ? " admin" : "") + (dual ? " dualwield" : "") + (hit ? " hitmarker" : "") +
                (upap ? " unlimitedpap" : "") + (rate ? " spawnrate" : "");
    if (rate)
        line += " +set spawnrate_mult " + std::to_string(s.spawnRate) + (s.spawnRush ? "" : " +set spawnrate_rush 0");
    if (mapkit && map.zone)
        // `set` takes the rest of its line as the value (ZmClient passes the zones the same way)
        line += std::string(" +set bo1_mod_zones ") + map.zone + (map.extraZone ? std::string(" ") + map.extraZone : "") +
                (map.fxZone ? std::string(" ") + map.fxZone : "") + " +set bo1_bspworld maps/" + map.zone +
                ".d3dbsp";
    if (kit && s.startPower)
        line += " +set zm_startpower 1";
    if (kit && s.startPap)
        line += " +set zm_startpap 1";
    if (kit && s.farRespawn > 0)
        line += " +set zm_farrespawn " + std::to_string(s.farRespawn);
    if (kit && s.startPoints > 0)
        line += " +set zm_startpoints " + std::to_string(s.startPoints);
    if (kit && s.startPerks != 0)
        line += " +set zm_startperks " + Launcher_StartPerkList(s);
    // The game runs windowed on the console (r_fullscreen 0), so r_customMode sizes its back buffer; the swapchain
    // takes that size and the console's compositor scales the frame to the screen. Arm ASR at 480p renders 856 wide,
    // a multiple of its 8x8 compute groups: at 854 its passes store past the right edge of their images, which Vulkan
    // drops and which corrupted Ryujinx's GPU command stream (docs/VULKAN.md, step 6, item 4).
    const bool asr = kLauncherUpscalers[s.upscaler].mode && std::string(kLauncherUpscalers[s.upscaler].mode) != "fsr1";
    line += std::string(" +set r_fullscreen 0 +set r_customMode ") +
            (s.height == 480 ? (asr ? "856x480" : "854x480") : s.height == 540 ? "960x540" : "1280x720");
    line += " +set com_maxfps " + std::to_string(s.maxFps);
    line += std::string(" +set sm_enable ") + (s.shadows ? "1" : "0");
    line += std::string(" +set r_lodScaleRigid ") + kLauncherPropDistances[s.propDistance].scale;
    line += std::string(" +set bo1_fpscounter ") + (s.fpsCounter ? "1" : "0");
    line += " +set bo1_runinfo " + std::to_string(s.runInfo);
    line += " +set r_texFilterAnisoMax " + std::to_string(filter.anisoMax);
    line += " +set r_texFilterMipMode " + std::to_string(filter.mipMode);
    if (join && Launcher_ValidPlayerName(s.playerName))
        line += " +set name " + s.playerName;
    if (join && Launcher_ValidPassword(s.serverPassword))
        line += " +set password " + s.serverPassword;
    if (join && s.serverModsKnown)
    {
        // what the server said its clients load (its fs_game, mods, zones, MapKit layout and world)
        if (!s.serverModArgs.empty())
            line += " " + s.serverModArgs;
    }
    else
    {
        // as ZmClient's join_bo2_weapons and join_dual_wield: fs_mods names the mods, so the engine loads their mod.ff
        // (DB_ListModZones)
        const bool joinBo2 = join && s.joinBo2Weapons && s.bo2WeaponsInstalled;
        const bool joinDual = join && s.joinDualWield && s.dualWieldInstalled;
        if (joinBo2 || joinDual)
            line += std::string(" +set fs_mods") + (joinBo2 ? " bo2weapons" : "") + (joinDual ? " dualwield" : "");
    }
    if (!extra.empty())
        line += " " + extra;
    if (join)
    {
        // The player typed the address, so a server beyond the LAN is meant. cl_autoConnect, not +connect: the menu's
        // own load undoes a connect from the command line, and it retries when the server is not up yet or goes away.
        line += " +set cl_allowWanConnect 1 +set cl_autoConnect " + Launcher_ServerAddress(s);
        return line;
    }
    line += " +devmap " + std::string(kLauncherMaps[s.map].bsp);
    return line;
}

std::vector<std::string> Launcher_UpscaleEnvironment(const LauncherSettings &s)
{
    const char *mode = kLauncherUpscalers[s.upscaler].mode;
    if (!mode || s.height >= 720)
        return {};
    return {std::string("BO1_UPSCALE=") + mode,
            std::string("BO1_UPSCALE_OUTPUT=") + (s.output == 1080 ? "1920x1080" : "1280x720"),
            std::string("BO1_UPSCALE_SHARPNESS=") + kLauncherFsrSharpness[s.fsrSharpness].stops};
}

bool Launcher_ValidServerHost(const std::string &host)
{
    if (host.empty() || host.size() > 63)
        return false;
    for (char c : host)
        if (!AddressChar(c))
            return false;
    return true;
}

bool Launcher_ParsePort(const std::string &text, int *port)
{
    if (text.empty() || text.size() > 5)
        return false;
    for (char c : text)
        if (c < '0' || c > '9')
            return false;
    const int value = std::atoi(text.c_str());
    if (value < 1 || value > 65535)
        return false;
    *port = value;
    return true;
}

std::string Launcher_StartPerkList(const LauncherSettings &s)
{
    std::string list;
    for (int i = 0; i < kLauncherPerkCount; ++i)
        if (s.startPerks & (1u << i))
            list += std::string(list.empty() ? "" : ",") + kLauncherPerks[i].key;
    return list;
}

std::string Launcher_ServerAddress(const LauncherSettings &s)
{
    return s.serverHost + ":" + std::to_string(s.serverPort);
}

bool Launcher_ValidPlayerName(const std::string &name)
{
    if (name.empty() || name.size() > 15)
        return false;
    for (char c : name)
        if (!AddressChar(c) && c != '_')
            return false;
    return true;
}

const char *Launcher_BackendName(LauncherBackend backend)
{
    return kBackendNames[backend];
}

const char *Launcher_TexFilterLabel(LauncherTexFilter filter)
{
    return kTexFilters[filter].label;
}

const char *Launcher_PadButtonLabel(int control)
{
    return control >= 0 && control < BO1_PAD_COUNT ? kPads[control].label : "?";
}

const char *Launcher_PadActionLabel(int control)
{
    return control >= 0 && control < BO1_PAD_COUNT ? kPads[control].action : "?";
}

bool Launcher_ValidPassword(const std::string &password)
{
    if (password.empty() || password.size() > 31)
        return false;
    for (char c : password)
        if (c <= ' ' || c == '"' || c == ';' || c == '+' || c == 127)
            return false;
    return true;
}

std::vector<std::string> Launcher_ServerModFiles(const std::string &fsMods, const std::string &zones,
                                                 const std::string &bspWorld)
{
    std::vector<std::string> out;
    const auto words = [](const std::string &text) {
        std::vector<std::string> list;
        size_t at = 0;
        while (at < text.size())
        {
            const size_t end = text.find(' ', at);
            const std::string word = text.substr(at, (end == std::string::npos ? text.size() : end) - at);
            if (!word.empty())
                list.push_back(word);
            if (end == std::string::npos)
                break;
            at = end + 1;
        }
        return list;
    };
    for (const std::string &mod : words(fsMods))
        if (mod == "bo2weapons" || mod == "dualwield")
            out.push_back("mods/" + mod + "/mod.ff");
    for (const std::string &zone : words(zones))
    {
        bool retail = false;
        for (int i = 0; i < kLauncherMapCount && !retail; ++i)
            retail = !kLauncherMaps[i].mapkit && zone == kLauncherMaps[i].bsp;
        if (!retail)
            out.push_back("usermaps/" + zone + "/" + zone + ".ff");
    }
    if (!bspWorld.empty())
        out.push_back("main/" + bspWorld);
    return out;
}
