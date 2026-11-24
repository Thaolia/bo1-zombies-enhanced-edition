"""The texts the views show to explain a key or a setting (French: the players' language)."""

MODE_LABELS = {
    "solo": "Solo (hors ligne)",
    "join": "Rejoindre un serveur",
    "host": "Serveur local + le rejoindre",
}
MODE_HELP = {
    "solo": "Une partie seul sur ce PC, réglée dans la vue Solo (F3) : map, mods, horde, difficulté.",
    "join": "Rejoindre un serveur dédié (LAN ou internet), choisi dans la vue Serveurs (F2). Le serveur décide de "
            "la map, des mods et du god mode ; ZmClient lui demande ce qu'il faut charger.",
    "host": "Démarre le serveur dédié de ce dossier (comme ZmAdmin, qui peut ensuite l'administrer) avec la partie "
            "de la vue Solo (F3), puis le jeu, qui le rejoint dès qu'il a chargé sa map. D'autres joueurs du réseau "
            "peuvent venir.",
}
WINDOW_LABELS = {"borderless": "Sans bordure (plein écran fenêtré)", "window": "Fenêtre", "fullscreen": "Plein écran"}
TRISTATE_LABELS = {"": "réglage du jeu", "1": "oui", "0": "non"}
SPLIT_LABELS = {"off": "non", "kbm_pad": "clavier/souris + manette", "pad_pad": "deux manettes"}
SPLIT_HELP = {
    "off": "un seul joueur sur ce PC",
    "kbm_pad": "joueur 1 au clavier et à la souris, joueur 2 à la première manette",
    "pad_pad": "joueur 1 à la première manette, joueur 2 à la deuxième",
}
SPLIT_LAYOUT_LABELS = {"side": "côte à côte", "stack": "l'un au-dessus de l'autre"}
SPLIT_LAYOUT_HELP = {
    "side": "joueur 1 à gauche, joueur 2 à droite : chacun une moitié de l'écran, en hauteur",
    "stack": "joueur 1 en haut, joueur 2 en bas : chacun une moitié de l'écran, en largeur",
}
DIFFICULTY_LABELS = {0: "Normal", 1: "Nightmare", 2: "Hell"}

SPAWN_RATE_HELP = {
    0: "le rythme du jeu d'origine",
    2: "deux fois plus vite, pauses courtes entre les manches",
    3: "trois fois plus vite (le réglage du mod)",
    5: "cinq fois plus vite",
    10: "dix fois plus vite : la manche sort presque d'un coup",
}

ROW_HELP = {
    "mode": "Comment jouer. Entrée : choisir.",
    "map": "La map de la partie solo. Les maps « Mapkit » sont construites par le mod mapkit sur une map de base.",
    "server": "Le serveur à rejoindre : adresse, port et mot de passe des joueurs (g_password, vide s'il n'en a "
              "pas). La vue Serveurs (F2) liste les favoris et ceux du réseau local.",
    "name": "Votre nom sur les serveurs (1 à 15 lettres, chiffres, « _ », « - », « . »). Vide : celui de "
            "config.cfg.",
    "god": "Invincible (bo1_testclient_god : le jeu remet le god mode à chaque image). Solo seulement : un serveur "
           "décide pour ses joueurs.",
    "zinfo": "En tenant Tab, les zombies en vie et ceux qui restent dans la manche s'affichent à gauche (mod zinfo).",
    "noperks": "Pas de machines à atouts (mod noperks). Le Pack-a-Punch et la boîte restent.",
    "quickrestart": "Après la fin de partie, R relance la même map avec les mêmes réglages.",
    "hitmarker": "Un X au centre de l'écran à chaque zombie touché (mod hitmarker) : blanc au corps, orange à la "
                 "tête, rouge pour le coup qui tue. « hitmarker 0 » dans la console le cache.",
    "unlimited_pap": "Le Pack-a-Punch reprend une arme déjà améliorée, autant de fois qu'on veut : chaque passage "
                     "double le prix (5 000, 10 000, 20 000...) et les dégâts (mod unlimitedpap). Les munitions de "
                     "réserve ne doublent pas. Son script est écrit depuis vos propres zones "
                     "(tools/unlimitedpap/make_perks.py, que les paquets lancent).",
    "spawn_rate": "Les zombies de chaque manche apparaissent plus vite, et la pause entre deux manches passe de 12 s à "
                  "3 s (mod spawnrate). Nombre, santé et vitesse des zombies restent ceux du jeu. "
                  "« spawnrate_mult » dans la console change la vitesse en jeu.",
    "spawn_rush": "Avec l'apparition plus rapide : chaque zombie court jusqu'à sa barricade, puis reprend la vitesse "
                  "de sa manche (spawnrate_rush).",
    "start_points": "Les points de chaque joueur à son arrivée sur la map, au lieu des 500 du jeu (mod admin, "
                    "zm_startpoints). Solo seulement : un serveur décide pour ses joueurs.",
    "start_power": "Le courant est mis à l'arrivée du premier joueur (mod admin, zm_startpower) : les machines, le "
                   "Pack-a-Punch et les portes électriques marchent tout de suite. Sans effet sur une map sans courant.",
    "start_pap": "Un Pack-a-Punch toujours allumé, posé au centre des points de départ des joueurs (mod admin, "
                 "zm_startpap). Il fait aussi marcher celui de la map sans courant, et en donne un aux maps qui n'en ont "
                 "pas (Nacht der Untoten).",
    "far_respawn": "Un zombie plus loin que cette distance de tous les joueurs (unités de zm_where) et qu'aucun ne "
                   "voit est remplacé par un autre, qui apparaît près des joueurs (mod admin, zm_farrespawn ; le jeu "
                   "le fait sur Moon à 1500). Pas les chiens ni les boss, ni un zombie blessé.",
    "start_perk": "Un atout donné gratuitement à l'arrivée sur la map (mod admin, zm_startperks). Seulement s'il a "
                  "sa machine sur cette map : Kino et Five n'ont que Juggernog, Quick Revive, Speed Cola et Double "
                  "Tap.",
    "horde": "Mod horde : beaucoup de zombies à la fois ; la manche suivante commence quand le dernier zombie de la "
             "manche est apparu.",
    "horde_max": "Zombies en même temps (24 à 1024). Au-delà de 300 c'est lourd : le jeu active ses options de "
                 "performance (comme le lanceur .hta).",
    "horde_round": "La manche de départ (1 : normal).",
    "horde_napalm": "Zombies napalm (de Shangri-La). Kino et Five seulement (fichiers de spawn du mod horde).",
    "horde_sonic": "Zombies hurleurs (shriekers, de Shangri-La). Kino et Five seulement.",
    "horde_spawn_all": "Les zombies sortent de toutes les fenêtres des zones ouvertes, pas seulement près de vous.",
    "horde_unjam": "Un zombie coincé dans la foule traverse les autres pendant 1,5 s.",
    "horde_clear_round": "La manche suivante n'arrive que quand tous les zombies sont morts (sinon : dès que le "
                         "dernier est apparu, les vivants restent).",
    "difficulty": "Nightmare : George, un astronaute, des zombies napalm et hurleurs, des chiens... dès la manche 1. "
                  "Hell : plusieurs de chaque à la fois. Kino et Five seulement ; charge trois maps de plus (démarrage "
                  "plus lent).",
    "bo2_weapons": "Les armes de Black Ops II (HAMR, AN-94, DSR-50, Ray Gun Mark II...) et leur version Pack-a-Punch, "
                   "dans la boîte (mod bo2weapons). Leur mod.ff se construit depuis votre propre Black Ops II "
                   "(docs/BO2_WEAPONS.md) et se pose dans mods/bo2weapons/. Les armes au mur restent celles de la "
                   "map. Un joueur qui rejoint un serveur avec ces armes doit avoir le même mod.ff (vue Jouer, mode "
                   "Rejoindre : « Armes de Black Ops II »).",
    "dual_wield": "Le Pack-a-Punch double le Ray Gun (deux Ray Guns) et le Thundergun (« Zeus and Hera ») (mod "
                  "dualwield, réglages dualwield_pap et dualwield_ppsh). Leur mod.ff se construit depuis les zones de "
                  "votre jeu, ou depuis votre copie du mod « Relaxing Dual Wield » : il double alors aussi le PPSh "
                  "(« The Grim Reapers ») et met le PPSh-41 dans la boîte (mods/dualwield/README.md). Se cumule avec "
                  "les armes de Black Ops II.",
    "join_dual_wield": "À cocher pour rejoindre un serveur qui a les armes doublées (mod dualwield) : le jeu charge "
                       "alors le même mods/dualwield/mod.ff. Sans lui, l'entrée sur ce serveur échoue en nommant "
                       "l'arme qui manque.",
    "join_detect_mods": "Au lancement, ZmClient demande au serveur ce qu'il charge (ses mods, ses zones, la carte "
                        "importée et son monde BSP), avec le mot de passe joueur s'il en a un, et le jeu charge la "
                        "même chose. Un serveur plus ancien ne répond pas, et un serveur protégé ne répond qu'au bon "
                        "mot de passe : les deux cases ci-dessous servent alors.",
    "join_bo2_weapons": "À cocher pour rejoindre un serveur qui a les armes de Black Ops II (mod bo2weapons) : le jeu "
                        "charge alors le même mods/bo2weapons/mod.ff. Sans lui, l'entrée sur ce serveur échoue "
                        "et le jeu revient au menu avec un message (arme manquante).",
    "window": "Sans bordure : une fenêtre de la taille de l'écran (comme Play.bat). Fenêtre : la taille ci-dessous. "
              "Plein écran : à la résolution ci-dessous.",
    "window_size": "La résolution en Fenêtre (taille de la fenêtre) et en Plein écran (mode de l'écran ; une taille "
                   "que l'écran ne propose pas revient à celle du jeu), LARGEURxHAUTEUR. Aussi dans Config du jeu "
                   "(F5). Sans effet en Sans bordure.",
    "run_info": "Les réglages qui changent une partie et un hash SHA-512 du programme et des zones chargées "
                "(bo1_runinfo), en bas de l'écran de chargement, ou aussi dans un coin pendant la partie, pour un "
                "stream ou un speedrun. Le hash complet est aussi écrit dans console_mp.log (ligne runinfo:).",
    "gfx_api": "Le moteur de rendu : Direct3D 9 (Windows) ou OpenGL (Linux) par défaut, ou Vulkan "
               "(r_mod_gfxApi sous Windows, BO1_GFX_BACKEND sous Linux). Au prochain lancement.",
    "fsr": "Avec Vulkan seulement (r_mod_upscale) : le jeu rend plus petit que la fenêtre puis l'agrandit en gardant "
           "les contours nets (FSR 1.0 ou Arm ASR, voir la ligne suivante). Le HUD reste à la taille de la fenêtre. "
           "Plus de FPS sur un GPU limité (Intel). Au prochain lancement.",
    "upscaler": "Comment l'image est agrandie (r_mod_upscaler) : FSR 1.0 d'AMD, image par image, ou Arm ASR, qui "
                "accumule les images successives pour retrouver les détails fins (plus net, un peu plus coûteux, de "
                "légères traînées possibles sur ce qui bouge). Si le GPU n'a pas ce qu'il faut pour ASR, le jeu prend "
                "FSR 1.0 (ligne « upscale » du journal). Au prochain lancement.",
    "fsr_sharpness": "Le renforcement des contours après l'agrandissement (r_mod_upscaleSharpness) : « forte » est le "
                     "réglage d'AMD ; « douce » ou « faible » si l'image paraît granuleuse.",
    "fps_counter": "Le petit compteur d'images par seconde du portage, en haut à gauche.",
    "scene_models": "Les modèles que le jeu dessine par image (r_mod_sceneModels ; 1024 dans le jeu d'origine). Une map "
                    "importée par Mapkit en a bien plus (Nuketown : 2 096 props) : à 1024 les plus lointains manquent "
                    "(l'horloge de la tour vue de la rue). 4096 les dessine tous et agrandit d'autant la réserve "
                    "d'éclairage des modèles. Utile surtout pour les maps importées.",
    "aim_assist": "Aide à la visée à la manette (bo1_aimassist). Les trois réglages suivants n'agissent que si elle "
                  "est active. « réglage du jeu » : rien n'est forcé.",
    "aim_slowdown": "La visée ralentit sur un zombie.",
    "aim_lockon": "La visée suit un zombie qui bouge.",
    "aim_autoaim": "La visée saute vers un zombie en visant (ADS).",
    "host_game": "Le serveur local joue la partie réglée dans la vue Solo (F3) : sa map (les maps de Black Ops II "
                 "importées comprises), la horde, la difficulté, zinfo, noperks, le hit marker, le Pack-a-Punch "
                 "illimité, la vitesse d'apparition, le kit de départ, les armes de Black Ops II et les armes "
                 "doublées. Le jeu charge ensuite ce qu'il faut pour le rejoindre. Entrée : vue Solo.",
    "host_port": "Le port UDP du serveur local (3074 par défaut ; le port + 1 reçoit les logs des clients). Ouvrez-"
                 "les dans le pare-feu pour des joueurs d'autres machines.",
    "host_password": "Le mot de passe rcon du serveur local, partagé avec ZmAdmin (son fichier servers.json) : "
                     "ZmAdmin administre le serveur que ZmClient a lancé.",
    "split": "Deux joueurs sur ce PC : deux fenêtres du jeu se partagent l'écran principal et rejoignent le même "
             "serveur (mode Serveur local, ou Rejoindre). Pas en Solo : choisir « Serveur local + le rejoindre ». "
             "La fenêtre de la manette lit sa manette même quand l'autre a le focus, ignore clavier et souris, et ne "
             "prend jamais le focus : le clavier reste à l'autre fenêtre (après un Alt+Tab, un clic dessus le rend).",
    "split_layout": "Comment les deux fenêtres se partagent l'écran principal.",
    "split_sound2": "Le son de la fenêtre du joueur 2. Les deux fenêtres jouent la même partie : avec les deux, chaque "
                    "son est entendu deux fois (non par défaut).",
    "name2": "Le nom du joueur 2 (1 à 15 lettres, chiffres, « _ », « - », « . »). Vide : Joueur2. Sa config, son "
             "profil et son journal sont dans le dossier split2/ du jeu.",
}

BO2_WEAPON_HELP = {
    0: "les armes de la map seulement",
    1: "les armes de Black Ops II s'ajoutent à celles de la map (bo2weapons_box 0)",
    2: "la boîte ne donne plus que les armes de Black Ops II, plus les armes spéciales de la map : Ray Gun, "
       "Thundergun, Wunderwaffe, singe, Gersh... (bo2weapons_box 1)",
    3: "la boîte ne donne plus que les armes de Black Ops II (bo2weapons_box 2)",
}

VIEW_HELP = {
    "play": [
        "Jouer : choisir comment jouer, puis lancer.",
        "Haut/Bas    choisir une ligne ; Entrée, Espace ou double-clic : la modifier",
        "L           lancer le jeu (et le serveur local en mode Serveur local ; les deux fenêtres en écran partagé)",
        "S           arrêter le jeu lancé par ZmClient (les deux fenêtres en écran partagé)",
        "K           arrêter le serveur local",
        "La ligne de commande exacte est affichée en bas. Les réglages sont gardés dans profile.json (dossier de "
        "configuration de ZmClient).",
    ],
    "servers": [
        "Serveurs : vos favoris et les serveurs du réseau local, interrogés toutes les 3 secondes (getstatus).",
        "Entrée      rejoindre le serveur choisi (double-clic aussi)",
        "a           ajouter un favori        e  modifier        x  retirer",
        "f           ajouter le serveur du réseau choisi aux favoris",
        "r           interroger maintenant",
        "Un serveur du réseau est trouvé par broadcast sur les ports 3074 à 3083 ; un serveur sur internet doit être "
        "ajouté à la main (son adresse et son port). Le mot de passe d'un favori est celui des joueurs (g_password), "
        "pas le rcon.",
    ],
    "solo": [
        "Solo : la partie hors ligne. Les options grisées ne s'appliquent pas à la map choisie (la raison est "
        "affichée en bas).",
        "Haut/Bas    choisir ; Entrée, Espace ou double-clic : modifier",
        "Les drapeaux de mods sont ceux de tools/mod-launcher.hta (horde_flags.js, nightmare_flags.js), à "
        "l'identique.",
    ],
    "launch": [
        "Lancement : ce que ZmClient ajoute à la ligne de commande dans tous les modes.",
        "Haut/Bas    choisir ; Entrée, Espace ou double-clic : modifier",
        "La ligne de commande gagne sur config.cfg pour ces réglages.",
    ],
    "config": [
        "Config du jeu : players/config.cfg du dossier, le fichier que le jeu écrit en quittant. ZmClient lance le "
        "jeu avec bo1_mod_sharedconfig 1 : un seul fichier pour tous les mods.",
        "Haut/Bas    choisir ; Entrée ou double-clic : modifier (marqué *)",
        "Ctrl+S      sauvegarder (rien n'est écrit avant) ;  u  annuler les modifications",
        "n           modifier un autre dvar du fichier (son nom, puis sa valeur)",
        "b           touches : changer ou retirer une commande liée (bind)",
        "r           relire le fichier",
        "Le jeu réécrit config.cfg en quittant : ZmClient refuse de sauvegarder pendant qu'il tourne.",
        "La ligne Résolution est celle de la vue Lancement (F4), pas une ligne de config.cfg : le jeu la reçoit en "
        "ligne de commande (r_mode en Plein écran, r_customMode en Fenêtre) ; en Sans bordure il prend la taille de "
        "l'écran. Modifiée ici, elle est enregistrée tout de suite.",
    ],
    "extra": [
        "Dvars libres : des commandes ajoutées à la ligne de commande, avant la map ou la connexion.",
        "a           ajouter une ligne : un dvar connu dans la liste (avec son explication), ou une commande libre",
        "e           modifier          x  retirer          Espace  activer / désactiver",
        "La colonne Description explique les dvars que ZmClient connaît (ceux du portage surtout) ; le texte complet "
        "de la ligne choisie s'affiche sous les boutons.",
        "Chaque ligne devient une commande « +ligne ». Pas de « + » dans une ligne : le jeu coupe sa ligne de "
        "commande à chaque « + », et n'en lit que 63.",
    ],
    "setup": [
        "Installation : les fichiers du jeu, depuis votre installation de Call of Duty: Black Ops (Steam).",
        "Copie localization.txt, main/*.iwd et main/video/, puis convertit les zones zombies avec le ffconv du "
        "paquet (environ 6 minutes ; il écrit aussi shaders.pack), puis compile shaders.pack en shaders.spv pour "
        "Vulkan avec glslang (5 à 15 minutes selon le processeur ; glslang est dans les paquets Windows et "
        "Linux, sinon celui du système : glslang-tools). Votre installation n'est jamais modifiée.",
        "c           choisir l'installation : trouvée dans les bibliothèques Steam, en parcourant les dossiers "
        "(flèches, Entrée pour ouvrir, Retour arrière pour remonter, Espace pour choisir ; une installation est "
        "marquée « Black Ops »), ou en tapant le chemin",
        "v           avec ou sans les vidéos      z  avec ou sans la conversion des zones",
        "s           avec ou sans les shaders Vulkan (refaits seulement s'ils manquent ou sont plus anciens que "
        "shaders.pack)",
        "i           installer          Échap  annuler une installation en cours",
        "Un fichier déjà copié (même taille, même date) n'est pas recopié. Si ffconv échoue, les zones précédentes "
        "restent. Sans glslang, tout le reste s'installe et le jeu garde son rendu habituel. Journal : "
        "main/zmclient_setup.log.",
    ],
    "log": [
        "Journal : le console_mp.log du jeu lancé, en direct.",
        "/           filtrer       Espace  pause       PgPréc/PgSuiv, molette : défiler       Fin  dernières lignes",
    ],
}

GLOBAL_HELP = [
    "F1 Jouer  F2 Serveurs  F3 Solo  F4 Lancement  F5 Config du jeu  F6 Dvars libres  F7 Installation  F8 Journal",
    "Tab / Maj+Tab   vue suivante / précédente",
    "?  ou F9    cette aide                q  ou F10   quitter",
    "Souris      clic : choisir un onglet, une ligne ou un bouton ; double-clic : modifier ou exécuter la ligne ; "
    "molette : défiler. Pour sélectionner du texte dans le terminal, tenir Maj (ou lancer zmclient --no-mouse).",
]

RUN_INFO_LABELS = {0: "non", 1: "au chargement", 2: "chargement + en jeu"}
GFX_API_LABELS = {"default": "Direct3D 9 (Windows) / OpenGL (Linux)", "vulkan": "Vulkan"}
FSR_LABELS = {"off": "non", "ultra": "Ultra qualité (x1,3)", "quality": "Qualité (x1,5)",
              "balanced": "Équilibré (x1,7)", "performance": "Performance (x2)",
              "native": "Natif (anti-aliasing ASR)", "ssaa_1.5x": "Suréchantillonnage x1,5 (SSAA)",
              "ssaa_2x": "Suréchantillonnage x2 (SSAA)"}
FSR_HELP = {
    "off": "Le jeu rend à la taille de la fenêtre.",
    "ultra": "Rendu à 77 % de la fenêtre puis agrandi par FSR 1.0 : presque aucune perte.",
    "quality": "Rendu aux deux tiers de la fenêtre (1280x720 pour 1920x1080).",
    "balanced": "Rendu à 59 % de la fenêtre.",
    "performance": "Rendu à la moitié de la fenêtre : le plus rapide, le plus flou.",
    "native": "Rendu à la taille de la fenêtre, Arm ASR sert d'anti-aliasing (bords lisses, pas de gain de FPS). "
              "Choisir une méthode Arm ASR à la ligne suivante : avec FSR 1.0, rien ne change.",
    "ssaa_1.5x": "Rendu à 1,5 fois la fenêtre sur chaque côté (2880x1620 pour 1920x1080), puis réduit : "
                 "bords lisses et détails fins stables, mais 2,25 fois plus de pixels à dessiner.",
    "ssaa_2x": "Rendu au double de la fenêtre sur chaque côté (3840x2160 pour 1920x1080), puis réduit : "
               "la meilleure image, 4 fois plus de pixels à dessiner. Pour les cartes graphiques puissantes.",
}
FSR_SHARPNESS_LABELS = {0.0: "maximum", 0.2: "forte (défaut AMD)", 0.5: "moyenne", 1.0: "douce", 2.0: "faible"}
UPSCALER_LABELS = {"fsr1": "FSR 1.0", "asr_quality": "Arm ASR qualité", "asr_balanced": "Arm ASR équilibré",
                   "asr_performance": "Arm ASR performance"}
UPSCALER_HELP = {
    "fsr1": "FSR 1.0 d'AMD : chaque image est agrandie seule. Le plus léger.",
    "asr_quality": "Arm ASR (temporel) avec ses shaders les plus fins : la meilleure image.",
    "asr_balanced": "Arm ASR avec des shaders allégés : presque la même image, un peu plus rapide.",
    "asr_performance": "Arm ASR avec ses shaders les plus rapides : un peu moins fin.",
}
GFX_API_HELP = {
    "default": "Le rendu habituel : le Direct3D 9 de Windows, OpenGL sous Linux.",
    "vulkan": "Le rendu par Vulkan (Windows 64 bits, Linux). Il lui faut shaders.spv à côté du programme ; sans lui, "
              "ou sans pilote Vulkan, le jeu revient au rendu habituel (Windows) et le dit dans console_mp.log.",
}
