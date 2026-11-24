"""What the Free dvars view knows of the dvars a player may add: a short line for its Description column and a longer
text under the list. Each text follows the dvar's registration in src/ (its description and limits); the tests check
that every name here is still a quoted string in src/."""

# name: (short, long). Names as the engine registers them; lookups ignore case, as the engine does.
KNOWN = {
    "bo1_netlog": (
        "Envoie le log du jeu au serveur rejoint",
        "1 (défaut) : le jeu envoie son console log au serveur qu'il rejoint (port du serveur + 1), qui l'écrit dans "
        "ses logs/. 0 : rien n'est envoyé."),
    "bo1_logserver": (
        "Serveur qui reçoit le log (host[:port])",
        "L'adresse host[:port] du port de jeu du serveur à qui envoyer le log (il le reçoit sur port + 1). Vide : le "
        "serveur de cl_autoConnect."),
    "r_shaderWarming": (
        "Préchauffe les shaders au chargement (long)",
        "1 : au premier rendu d'une map, le jeu dessine une fois chaque passe éclairée pour que le pilote compile ses "
        "shaders d'avance (moins de saccades ensuite). L'image se fige longtemps à ce moment (2 minutes et plus sur un "
        "portable). 0 par défaut ; la vue Lancement a cette option (« Préchauffage des shaders ») et la donne à chaque "
        "lancement."),
    "bo1_frameperf": (
        "Profileur : log des images plus lentes que N ms",
        "« set bo1_frameperf 200 » : le jeu écrit une ligne BO1_FRAMEHITCH pour chaque image de plus de 200 ms et une "
        "ligne BO1_FRAMEPERF de statistiques (fps, percentiles) toutes les 5 s, dans console_mp.log. Lu seulement sur "
        "la ligne de commande."),
    "bo1_fpscounter": (
        "Compteur FPS du portage (haut droite)",
        "1 : compteur d'images par seconde (et niveau de batterie) en haut à droite. La vue Lancement a aussi cette "
        "option."),
    "bo1_runinfo": (
        "Réglages + hash du programme (speedrun)",
        "1 : les réglages de la partie et le hash du programme et des zones sur l'écran de chargement ; 2 : aussi "
        "pendant la partie ; 0 : rien. La vue Lancement a aussi cette option."),
    "bo1_mod_fov": (
        "Champ de vision pour tous les modes",
        "0 : celui du jeu ; 65 à 120 : plus large. Gardé dans players/bo1_shared.cfg (la vue Config du jeu a aussi ce "
        "réglage)."),
    "bo1_quitOnDisconnect": (
        "Quitter le jeu depuis le menu pause",
        "1 (défaut, toutes les plateformes) : la commande disconnect (« Quitter » du menu pause) ferme le jeu au lieu "
        "de revenir au menu. La vue Config du jeu a aussi ce réglage."),
    "bo1_autoquit": (
        "Quitter tout seul après N ms",
        "Le jeu se ferme N millisecondes après son démarrage (0 : jamais). Pour des tests chronométrés."),
    "bo1_dvardump": (
        "Liste tous les dvars en quittant (bo1_autoquit)",
        "1 : quand bo1_autoquit ferme le jeu, il écrit chaque dvar (type, drapeaux, valeur par défaut et actuelle) "
        "dans console_mp.log."),
    "bo1_audio": (
        "Log de chaque son joué (mesure)",
        "1 : chaque demande de son (alias, entité, position, résultat) est écrite dans le log. Mesure seulement, "
        "verbeux."),
    "bo1_aimassist": (
        "Aide à la visée à la manette",
        "1 : ralentissement et accroche de la visée à la manette (absents du jeu PC d'origine). La vue Lancement a "
        "aussi cette option."),
    "bo1_mod_lazymodels": (
        "Charge les décors des zones ajoutées à la demande",
        "1 (défaut) : les modèles (décor) d'une zone de bo1_mod_zones ne sont reliés que quand quelque chose s'en "
        "sert : chargement plus court des maps importées."),
    "bo1_mod_ailod": (
        "Zombies lointains animés moins souvent",
        "1 : un zombie loin de tous les joueurs met à jour son animation de course toutes les 0,2 s au lieu de chaque "
        "image (moins de CPU avec beaucoup de zombies)."),
    "bo1_mod_maxactors": (
        "Places d'IA (32 d'origine, 1024 au plus)",
        "Le nombre de zombies que la partie peut avoir en même temps (32 dans le jeu d'origine, jusqu'à 1024). Lu au "
        "démarrage d'une map ; la horde le règle elle-même."),
    "bo1_mod_tabinfo": (
        "Zombies en vie / restants avec le tableau Tab",
        "1 : le nombre de zombies en vie et restants dans la manche s'affiche à côté du tableau des scores (mods/zinfo "
        "le met)."),
    "bo1_mod_pcore": (
        "CPU hybrides : threads sur les cœurs P",
        "1 : thread du serveur sur les cœurs performance et priorité au-dessus de la normale ; 2 : aussi les threads "
        "du client. Sans effet sur un CPU non hybride."),
    "bo1_mod_priority": (
        "Priorité du processus (0, 1, 2)",
        "1 : priorité au-dessus de la normale (processus et thread principal) ; 2 : priorité haute ; 0 : celle du "
        "lancement (défaut d'un client)."),
    "r_mod_sceneModels": (
        "Modèles dessinés par image (1024 d'origine)",
        "Le plafond de modèles dessinés par image (1024 d'origine, jusqu'à 4096) : plus de décor au loin sur les "
        "maps importées. La vue Lancement a aussi ce réglage."),
    "r_mod_modelLightingEntries": (
        "Éclairage des modèles : entrées réservées",
        "Le nombre d'entrées d'éclairage dynamique des modèles réservées au démarrage (0 : celui du jeu, jusqu'à "
        "5120). ZmClient le monte déjà avec les modèles par image."),
    "r_mod_skinCacheMB": (
        "Cache des modèles animés, en Mo (8 d'origine)",
        "La taille en Mo de chaque cache de sommets des modèles animés (8 d'origine, jusqu'à 256) : utile avec "
        "beaucoup de zombies à l'écran."),
    "r_mod_fxElems": (
        "Éléments d'effets à la fois (2048 d'origine)",
        "Le nombre d'éléments d'effets (particules) vivants en même temps (2048 d'origine, jusqu'à 4096), lu au "
        "chargement de la map."),
    "r_mod_gfxEnts": (
        "Modèles spéciaux par image (256 d'origine)",
        "Les zombies, corps et l'arme en main dessinés par image (256 d'origine, jusqu'à 2048) : à monter avec une "
        "grosse horde."),
    "r_mod_drawStats": (
        "Log des draw calls toutes les N images",
        "Toutes les N images, le jeu écrit ses draw calls par technique et type de surface (lignes drawstats:) ; "
        "0 : jamais. Mesure seulement."),
    "r_mod_scsShare": (
        "Partage des constantes de shader identiques",
        "1 : les modèles aux constantes de shader identiques partagent un des 128 emplacements de l'image (0 "
        "d'origine)."),
    "cl_allowWanConnect": (
        "Autorise les serveurs hors du réseau local",
        "1 : connect et cl_autoConnect acceptent aussi une adresse hors du réseau local (Internet). 0 par défaut."),
    "cl_autoConnect": (
        "Serveur rejoint dès le menu (et après coupure)",
        "L'adresse host[:port] d'un serveur que le jeu rejoint dès que le menu est prêt, et de nouveau chaque fois "
        "qu'il revient au menu. La vue Serveurs le fait déjà."),
    "com_maxfps": (
        "FPS maximum (0 : sans limite)",
        "Limite d'images par seconde (85 par défaut, 0 : sans limite, 1000 au plus). La vue Config du jeu a aussi ce "
        "réglage."),
    "r_fog": (
        "Brouillard (0 : désactivé)",
        "0 : pas de brouillard (on voit plus loin, l'ambiance change). Défaut 1."),
    "r_vsync": (
        "Synchronisation verticale",
        "1 : pas de déchirure d'image, FPS limités à la fréquence de l'écran. La vue Config du jeu a aussi ce réglage."),
    "developer": (
        "Mode développeur (messages en plus)",
        "1 ou 2 : active les systèmes de développement (plus de messages et de vérifications dans le log)."),
    "logfile": (
        "Écriture du console_mp.log",
        "0 : pas de fichier de log ; 1 : écriture en arrière-plan (défaut) ; 2 : chaque ligne écrite tout de suite "
        "(plus lent, mais rien de perdu si le jeu plante)."),
    "cg_fov": (
        "Champ de vision du jeu (65 d'origine)",
        "L'angle de vue en degrés (65 par défaut). bo1_mod_fov le règle pour tous les modes."),
    "r_borderlessRect": (
        "Sans bordure : part de l'écran occupée",
        "Avec Sans bordure : « x,y,l,h » en fractions de l'écran (ex. 0,0,0.5,1 : moitié gauche) ; vide : tout "
        "l'écran. L'écran partagé le règle lui-même."),
}

_BY_LOWER = {name.lower(): name for name in KNOWN}
_SET_WORDS = ("set", "seta", "sets", "setu")


def dvar_of(text):
    """The dvar a free command line sets ("set r_fog 0" -> "r_fog"), or its first word."""
    words = text.split()
    if not words:
        return ""
    if words[0].lower() in _SET_WORDS and len(words) > 1:
        return words[1]
    return words[0]


def describe(text):
    """(short, long) for a free command line's dvar, or ("", "") when unknown."""
    name = _BY_LOWER.get(dvar_of(text).lower())
    return KNOWN[name] if name else ("", "")
