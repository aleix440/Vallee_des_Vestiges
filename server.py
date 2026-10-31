from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import secrets
import sqlite3
import os
import re
import time
import unicodedata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'game.db')

# ─── CONFIGURATION (variables d'environnement sur le serveur) ───────────────
ADMIN_PASSWORD      = os.environ.get('ADMIN_PASSWORD', "animation2025")
HOST                = os.environ.get('HOST', '0.0.0.0')
PORT                = int(os.environ.get('PORT', 5000))
MIN_PASSWORD_LENGTH = 4
# ─────────────────────────────────────────────────────────────────────────────

def load_secret_key():
    """Clé de signature des sessions : SECRET_KEY si défini, sinon générée une fois et conservée dans data/."""
    if os.environ.get('SECRET_KEY'):
        return os.environ['SECRET_KEY']
    path = os.path.join(BASE_DIR, 'data', 'secret_key')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()

app = Flask(__name__)
app.secret_key = load_secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

# ─── LISTE DES CONNAISSANCES (Livre des règles 2025 v2.1) ────────────────────
KNOWLEDGES = [
    # Général
    ("k_anatomie_humain",       "Général",    "Anatomie — Humain",                    ""),
    ("k_anatomie_elfe",         "Général",    "Anatomie — Elfe",                      ""),
    ("k_anatomie_nain",         "Général",    "Anatomie — Nain",                      ""),
    ("k_anatomie_orc",          "Général",    "Anatomie — Orc",                       ""),
    ("k_anatomie_goblin",       "Général",    "Anatomie — Goblin",                    ""),
    ("k_anatomie_hafling",      "Général",    "Anatomie — Hafling",                   ""),
    ("k_anatomie_xuhatek",      "Général",    "Anatomie — Xuhatek",                   ""),
    ("k_anatomie_asheranti",    "Général",    "Anatomie — Asheranti",                 ""),
    ("k_animaux",               "Général",    "Animaux (3 espèces au choix)",         "Chaque point donne la connaissance de 3 espèces animales à choisir avec l'animation."),
    ("k_armes",                 "Général",    "Armes",                                ""),
    ("k_heraldisme",            "Général",    "Héraldisme",                           ""),
    ("k_legendes",              "Général",    "Légendes (1 par point)",               "Chaque point donne la connaissance d'une légende à choisir avec l'animation."),
    ("k_lois",                  "Général",    "Lois",                                 ""),
    ("k_mers",                  "Général",    "Mers",                                 ""),
    ("k_celebres",              "Général",    "Personnages célèbres",                 ""),
    ("k_prix",                  "Général",    "Prix du quotidien",                    ""),
    ("k_primes",                "Général",    "Primes",                               ""),
    # Nature
    ("k_bois",                  "Nature",     "Bois",                                 "Requis pour la compétence Menuiserie."),
    ("k_cuirs",                 "Nature",     "Cuirs",                                "Requis pour la compétence Maroquinerie."),
    ("k_plantes",               "Nature",     "Plantes",                              "Requis pour la compétence Botanique."),
    ("k_poisons",               "Nature",     "Poisons",                              "Requis pour la compétence Application de poison."),
    ("k_pierres",               "Nature",     "Pierres précieuses",                   ""),
    ("k_astrologie",            "Nature",     "Astrologie",                           ""),
    ("k_metaux",                "Nature",     "Métaux et alliages",                   "Requis pour la compétence Forge."),
    ("k_tissus",                "Nature",     "Tissus",                               ""),
    # Créatures
    ("k_cr_magiques",           "Créatures",  "Animaux magiques (3 par point)",       ""),
    ("k_cr_damnes",             "Créatures",  "Damnés (3 par point)",                 ""),
    ("k_cr_elementaires",       "Créatures",  "Élémentaires (3 par point)",           ""),
    ("k_cr_esprits",            "Créatures",  "Esprits (3 par point)",                ""),
    ("k_cr_feeriques",          "Créatures",  "Féeriques (3 par point)",              ""),
    ("k_cr_humanoides",         "Créatures",  "Humanoïdes (3 par point)",             ""),
    ("k_cr_necrophages",        "Créatures",  "Nécrophages (3 par point)",            ""),
    # Langues
    ("k_lang_elfique",          "Langues",    "Elfique",                              ""),
    ("k_lang_geofroy",          "Langues",    "Geofroy (Anglais)",                    ""),
    ("k_lang_karazim",          "Langues",    "Karazim (Allemand)",                   ""),
    ("k_lang_langelier",        "Langues",    "Langelier (Français)",                 ""),
    ("k_lang_tcheke",           "Langues",    "Tchéké (Espagnol)",                    ""),
    ("k_lang_yamalee",          "Langues",    "Yamalee (Arabe)",                      ""),
    ("k_lang_yashilovek",       "Langues",    "Yashilovek (Russe)",                   ""),
    # Pays
    ("k_pays_archipel",         "Pays",       "Archipels de Givre",                  ""),
    ("k_pays_aublanc",          "Pays",       "Aublanc",                             ""),
    ("k_pays_castello",         "Pays",       "Castello",                            ""),
    ("k_pays_chaufour",         "Pays",       "Chaufour",                            ""),
    ("k_pays_dulne",            "Pays",       "Empire de Dulne",                     ""),
    ("k_pays_eloria",           "Pays",       "Éloria",                              ""),
    ("k_pays_flotte",           "Pays",       "Flotte Asheranti",                    ""),
    ("k_pays_gonguldur",        "Pays",       "Gonguldur",                           ""),
    ("k_pays_grandes_plaines",  "Pays",       "Grandes Plaines",                     ""),
    ("k_pays_hulfenberg",       "Pays",       "Hulfenberg",                          ""),
    ("k_pays_lonniel",          "Pays",       "Lonniel",                             ""),
    ("k_pays_megorovie",        "Pays",       "Mégorovie",                           ""),
    ("k_pays_missely",          "Pays",       "Missely",                             ""),
    ("k_pays_ovaelanor",        "Pays",       "Ovaelanor",                           ""),
    ("k_pays_ratcheke",         "Pays",       "Ratchéké",                            ""),
    ("k_pays_sirrak",           "Pays",       "Sirrak",                              ""),
    ("k_pays_exiles",           "Pays",       "Terre des exilés",                    ""),
    # Religions
    ("k_rel_absolue",           "Religions",  "Culte de l'Absolue",                  ""),
    ("k_rel_anciens",           "Religions",  "Vénération des Anciens",              ""),
    ("k_rel_celestes",          "Religions",  "Voie des Célestes",                   ""),
    ("k_rel_damnes",            "Religions",  "Dévotion aux Empereurs Damnés",       ""),
    ("k_rel_dragon",            "Religions",  "Vénération du Grand-père Dragon",     ""),
    ("k_rel_henos",             "Religions",  "Dévotion aux Hénos",                  ""),
    ("k_rel_main",              "Religions",  "Main divine",                         ""),
    ("k_rel_voix",              "Religions",  "Secte de la Voix",                    ""),
    # Social
    ("k_groupes_criminels",     "Social",     "Groupes criminels",                   ""),
    ("k_marche_esclaves",       "Social",     "Marché d'esclaves",                   ""),
    ("k_drogues",               "Social",     "Drogues",                             ""),
    ("k_maladies",              "Social",     "Maladies",                            ""),
    ("k_maladies_mentales",     "Social",     "Maladies mentales",                   ""),
    # Magie & Militaire
    ("k_magie",                 "Magie",      "Magie",                               ""),
]
# Tactiques militaires : une connaissance par pays (17 pays, Livre des règles p. 81)
KNOWLEDGES += [
    ("k_tactiques_" + kid[len("k_pays_"):], "Militaire", f"Tactiques militaires — {name}", "")
    for kid, cat, name, _ in KNOWLEDGES if cat == "Pays"
]
KNOWLEDGE_MAX_LEVEL = 5
# Religions qu'un personnage peut prier (mêmes que les connaissances de religion) ; le joueur peut en changer.
# Prier une religion donne gratuitement 1 niveau de sa connaissance (p. 81), qui suit la religion si elle change.
RELIGION_KNOWLEDGES = {name: kid for kid, cat, name, _ in KNOWLEDGES if cat == "Religions"}
RELIGIONS = list(RELIGION_KNOWLEDGES)

# ─── PERSONNAGE (Livre des règles 2025 v2.1, p. 13-26) ───────────────────────
# Race : (points de vie, points d'esprit, talent)
RACES = {
    "Humain":    (6, 6, "Versatile : +1 pv ou +1 pe à la création de personnage."),
    "Elfe":      (8, 4, "Goût du sang : en goûtant du sang, détermine race, sexe, âge, malédiction, maladie ou poison."),
    "Demi-elfe": (6, 6, "Instinct de survie : 1× par événement, à l'agonie, peut se relever à 3 pv."),
    "Orc":       (7, 5, "Fureur : la 1re fois dans un cycle à 0 pv, se relève en rage 10 secondes, invincible."),
    "Demi-orc":  (6, 6, "Perfection de la race : à trouver en jeu."),
    "Nain":      (5, 7, "Vision des esprits : voit, entend et parle aux spectres, fantômes et esprits."),
    "Hafling":   (6, 6, "Immunité à la peur : Courage s'applique à la terreur, Courage +1."),
    "Goblin":    (5, 7, "Écholocation : immunisé aux effets d'aveuglement."),
    "Xuhatek":   (8, 8, "Armure naturelle : immunité aux dégâts physiques de 2 et moins, ne peut pas porter d'armure."),
    "Asheranti": (5, 7, "Magie innée : connaît un sort niveau 1 de feu, eau, air ou terre."),
}
# Avantages donnés gratuitement par la provenance (p. 19-26) :
# compétences (niveau I), connaissances (niveau 1) et avantages à appliquer par l'Animation.
# Il est impossible de provenir de l'Empire de Dulne ni de la Terre des exilés.
PROVENANCES = {
    "Archipels de Givre": {"skills": ["chasse1"],
                           "knowledges": ["k_lang_geofroy", "k_animaux", "k_astrologie"]},
    "Aublanc":            {"skills": ["lireerire1"],
                           "knowledges": ["k_lang_langelier", "k_heraldisme", "k_lois"]},
    "Castello":           {"knowledges": ["k_lang_geofroy", "k_heraldisme", "k_bois", "k_marche_esclaves"]},
    "Chaufour":           {"skills": ["fermier1"],
                           "knowledges": ["k_lang_langelier", "k_plantes", "k_animaux"]},
    "Éloria":             {"skills": ["technologie1"], "knowledges": ["k_lang_langelier"]},
    "Flotte Asheranti":   {"knowledges": ["k_mers", "k_prix"],
                           "language_choice": (2, ["k_lang_langelier", "k_lang_geofroy", "k_lang_yamalee", "k_lang_tcheke"])},
    "Gonguldur":          {"skills": ["technologie1"], "knowledges": ["k_lang_karazim"]},
    "Grandes Plaines":    {"skills": ["fouille1", "bandit1"],
                           "knowledges": ["k_lang_yashilovek", "k_animaux"]},
    "Hulfenberg":         {"skills": ["revenu1"],
                           "knowledges": ["k_lang_karazim", "k_prix", "k_heraldisme"]},
    "Lonniel":            {"skills": ["commerage1"],
                           "knowledges": ["k_lang_langelier", "k_legendes", "k_cr_magiques"]},
    "Mégorovie":          {"skills": ["fouille1", "denicheur1"],
                           "knowledges": ["k_lang_langelier", "k_heraldisme"]},
    "Missely":            {"skills": ["revenu1", "commerage1", "dissim1"], "knowledges": ["k_lang_langelier"]},
    "Ovaelanor":          {"skills": ["botanique1", "premiersoin1"],
                           "knowledges": ["k_lang_elfique", "k_plantes"]},
    "Ratchéké":           {"skills": ["denicheur1", "courage1"], "knowledges": ["k_lang_tcheke"],
                           "extra_free_weapons": 1},
    "Sirrak":             {"skills": ["volonte1"], "knowledges": ["k_lang_langelier", "k_pays_dulne"],
                           "extra_free_weapons": 1},
}

# Arme de prédilection : achetée une fois par catégorie d'arme (p. 45).
# La 1re catégorie est gratuite (+ extra_free_weapons de la provenance), les suivantes coûtent le prix de la compétence.
WEAPON_SKILL = "arme1"
WEAPONS = {
    "dague":    "Dague",
    "epee":     "Épée",
    "marteau":  "Marteau",
    "hache":    "Hache",
    "hast":     "Arme d'hast",
    "arc":      "Arc",
    "arbalete": "Arbalète",
}
WEAPON_SKILL_DESC = ("Choisissez une catégorie d'arme : au lieu d'infliger 1 dégât de base, elle en inflige 2. "
                     "La 1re catégorie est gratuite, chaque catégorie suivante coûte 1 XP.")
# Spécialisation d'arme (p. 79) : compétence séparée par catégorie d'arme de prédilection, jusqu'au niveau 3
SPEC_SKILL       = "specarm1"
SPEC_MAX_LEVEL   = 3
SPEC_SKILL_NAME  = "Spécialisation d'arme"
SPEC_SKILL_DESC  = ("Utilisez l'effet spécial d'une de vos armes de prédilection. Chaque catégorie se spécialise "
                    f"séparément, jusqu'au niveau {SPEC_MAX_LEVEL}.")
WEAPON_SPEC_EFFECTS = {
    "dague":    "1 coup rasoir par cycle par niveau",
    "epee":     "1 coup rasoir par cycle par niveau",
    "marteau":  "3× par cycle par niveau « repoussement 2 mètres »",
    "hache":    "1× par cycle par niveau « désarmement »",
    "hast":     "2× par cycle par niveau « jambette »",
    "arc":      "2 coups critique 6 par cycle par niveau",
    "arbalete": "1 coup critique 8 par cycle par niveau",
}
# Symbole de foi demande seulement de prier une religion, pas la Prêtrise
FAITH_SKILL      = "symboifoi1"
FAITH_SKILL_DESC = ("Pré-requis : prier une religion (à choisir dans la fiche Personnage). "
                    "Portez le symbole de votre religion (min 1 pied) : +2 PA se régénérant entre les combats.")
# Compétences qui exigent que le personnage prie une religion (p. 69, 72, 73, 79), avec leur description
RELIGION_SKILL_DESCS = {
    FAITH_SKILL: FAITH_SKILL_DESC,
    "messe1":    ("Pré-requis : Volonté et prier une religion (fiche Personnage). Messe de 10 min : jusqu'à 5 croyants "
                  "gagnent votre niveau de volonté pour résister à un effet pendant 1h."),
}
# La description de Prêtrise est dans MAGIC_SKILLS
SKILLS_REQUIRING_RELIGION = set(RELIGION_SKILL_DESCS) | {"pretrise1"}
# Prosélytisme est réservé aux prêtres : son prérequis Prêtrise n'était écrit que dans la description
PROSELYTISM_SKILL = "proselytisme1"
# Magie (Livre p. 57, 69, 74 ; Règlement magie). Les écoles et leurs sorts sont dans spells.json :
# « base » (École de magie), « advanced » (Magie avancée, combinaison de deux écoles de base)
# et « divine » (Prêtrise, une école par religion). Chaque école monte séparément jusqu'au niveau 5 ;
# à chaque niveau, le joueur choisit SPELLS_PER_LEVEL sorts parmi ceux du niveau (tous s'il y en a moins).
# Les niveaux 4 et 5 n'ont pas de sorts dans le règlement et demandent l'approbation d'un scénariste.
MAGIC_MAX_LEVEL  = 5
SPELLS_PER_LEVEL = 3
MAGIC_SKILLS = {  # compétence → (type d'école, nom, description)
    "ecomagie1":  ("base", "École de magie",
                   "Choisissez une école de magie (eau, air, terre, feu ou cœur) puis 3 sorts parmi les 5 du niveau. "
                   "Chaque école monte séparément ; les niveaux 4 et 5 demandent l'approbation d'un scénariste."),
    "ecoavance1": ("advanced", "Magie avancée",
                   "Combinez deux de vos écoles de base : Air+Eau=Glace, Air+Feu=Foudre, Air+Terre=Sable, "
                   "Feu+Terre=Métal, Eau+Terre=Plantes, Feu+Eau=Sang. Le niveau ne peut pas dépasser "
                   "celui des deux écoles requises. 3 sorts parmi les 5 du niveau."),
    "pretrise1":  ("divine", "Prêtrise/Cultisme",
                   "Pré-requis : prier une religion (fiche Personnage). Sorts divins de votre religion : "
                   "3 sorts parmi les 5 du niveau. Impossible d'avoir des sorts de plusieurs religions ; "
                   "les niveaux 4 et 5 demandent l'approbation d'un scénariste."),
}
MAGIC_SKILL = "ecomagie1"
# Sorts supplémentaires (p. 74) : un sort d'une école connue, de niveau au plus celui de l'école ; coûte son niveau en XP
EXTRA_SPELL_SKILL = "sortsupp1"
EXTRA_SPELL_DESC  = ("Apprenez un sort supplémentaire d'une école de magie ou de prêtrise que vous connaissez déjà, "
                     "d'un niveau que vous maîtrisez. Coût : le niveau du sort en XP. Peut être acheté plusieurs fois.")
INCANTATION_MAX_LENGTH = 3000
# Écriture de parchemin (p. 56) : Lecture/écriture (prérequis normal) et une école de magie OU la prêtrise
SCROLL_SKILL      = "ecrparch1"
SCROLL_SKILL_DESC = ("Pré-requis : Lecture/écriture et École de magie ou Prêtrise. Infusez un parchemin avec un sort "
                     "(coûte autant de pm que lancer le sort, réduit votre max jusqu'au prochain cycle). "
                     "Prend 2 min/niveau + 1 ressource tissu. Impossible pour les sorts rituels, passifs ou de concentration.")
SKILLS_REQUIRING_MAGIC = {SCROLL_SKILL}
with open(os.path.join(BASE_DIR, 'spells.json'), encoding='utf-8') as f:
    MAGIC_SCHOOLS = json.load(f)
SCHOOLS_BY_ID = {s['id']: s for s in MAGIC_SCHOOLS}
SCHOOL_SPELLS = {(s['id'], int(lv)): [sp['id'] for sp in spells]
                 for s in MAGIC_SCHOOLS for lv, spells in s['levels'].items()}
SPELL_INFO = {sp: (school, level) for (school, level), spells in SCHOOL_SPELLS.items() for sp in spells}
# Compétences qui exigent l'arme de prédilection dans l'une de ces catégories
SKILL_WEAPON_PREREQS = {
    "attsour1":  ["dague"],
    "brisbou1":  ["hache", "marteau"],
    "brismemb1": ["marteau"],
}

# Compétences du livre absentes de l'arbre initial (p. 77)
EXTRA_SKILLS = [
    ("technologie1", "Arts & Métiers", "Technologie I", 3, 0,
     "Utilisez, réparez et fabriquez les objets technologiques de base du quotidien (briquet, montre, appareil photo…) tant qu'ils sont décorum.",
     None, 100),
    ("technologie2", "Arts & Métiers", "Technologie II", 3, 0,
     "Accès aux technologies militaires : réparez, fabriquez et utilisez les armes à feu et leurs munitions. Demandez le document de technologie à l'animation.",
     "technologie1", 101),
]

# Catégories d'affichage des compétences : un fichier texte par catégorie, une compétence par ligne.
# La 1re ligne du fichier est ignorée (titre). Chaque compétence n'apparaît que dans une catégorie :
# celle de SKILL_CATEGORY_CHOICES si elle y est, sinon celle du 1er fichier qui la cite.
# Les étiquettes supplémentaires des fichiers (ex. « Assommement -m -u ») sont ignorées.
# Les compétences absentes des fichiers vont dans « Autres ».
SKILL_CATEGORIES = [  # (fichier, nom affiché, étiquette)
    ("martial.txt",  "Martial",  "m"),
    ("magie.txt",    "Magie",    "ma"),
    ("utilité.txt",  "Utilité",  "u"),
    ("craft.txt",    "Craft",    "c"),
    ("economie.txt", "Économie", "e"),
]
OTHER_CATEGORY = "Autres"
# Catégorie retenue pour les compétences qui ont plusieurs étiquettes dans les fichiers
SKILL_CATEGORY_CHOICES = {
    "assommement":         "Utilité",
    "entretiendarme":      "Craft",
    "inspiration":         "Utilité",
    "prestation":          "Magie",
    "ecrituredeparchemin": "Craft",
}
# Nom écrit dans les fichiers → nom de la compétence dans l'arbre, quand ils diffèrent
SKILL_NAME_ALIASES = {
    "symboldefoi":                  "symboledefoi",
    "sortssupplementaire":          "sortssupplementaires",
    "ecoledemagieavancee":          "magieavancee",
    "entrainementdefensifphalange": "entrainementdefensif",
    "entrainementoffensifassaut":   "entrainementoffensif",
    "maniementdesarmeslourdes":     "maniementarmeslourdes",
    "premiersoins":                 "premierssoins",
}

# Compétences qui augmentent les points de vie / d'esprit
SKILL_STAT_BONUSES = {
    "endurance1": {"pv": 3}, "endurance2": {"pv": 3},
    "eveil1":     {"pe": 3}, "eveil2":     {"pe": 3},
}

# Pièce d'armure : (nom, points par matériau cuir / maille / plaque / maximum)
ARMOR_PARTS = {
    "tete":            ("Tête",                (1,   2,   2,   3)),
    "torse":           ("Torse",               (1,   1.5, 2,   3)),
    "dos":             ("Dos",                 (1,   1.5, 2,   3)),
    "epaule_g":        ("Épaule gauche",       (0.5, 1,   1.5, 2)),
    "epaule_d":        ("Épaule droite",       (0.5, 1,   1.5, 2)),
    "avant_bras_g":    ("Avant-bras gauche",   (0.5, 1,   1.5, 2)),
    "avant_bras_d":    ("Avant-bras droit",    (0.5, 1,   1.5, 2)),
    "cuisses":         ("Cuisses",             (1,   1,   2,   3)),
    "tibia_g":         ("Tibia gauche",        (0.5, 1,   1.5, 2)),
    "tibia_d":         ("Tibia droit",         (0.5, 1,   1.5, 2)),
}
# Matériau : (nom, colonne du tableau, immunité aux dégâts de N et moins)
# Cuir + maille donne les bonus de la plaque, maille + plaque donne le maximum
ARMOR_MATERIALS = {
    "cuir":          ("Cuir",           0, 1),
    "maille":        ("Maille",         1, 2),
    "plaque":        ("Plaque",         2, 3),
    "cuir_maille":   ("Cuir + maille",  2, 2),
    "maille_plaque": ("Maille + plaque", 3, 3),
}
# ─────────────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-Admin-Key', '')
        if key != ADMIN_PASSWORD:
            return jsonify({'error': 'Mot de passe incorrect'}), 401
        return f(*args, **kwargs)
    return decorated

def is_admin():
    return request.headers.get('X-Admin-Key', '') == ADMIN_PASSWORD

def require_player(f):
    """Le joueur connecté ne peut agir que sur son propre compte."""
    @wraps(f)
    def decorated(name, *args, **kwargs):
        if session.get('player') != name:
            return jsonify({'error': 'Non connecté'}), 401
        return f(name, *args, **kwargs)
    return decorated

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        name              TEXT PRIMARY KEY,
        points            INTEGER DEFAULT 9,
        knowledge_points  INTEGER DEFAULT 3
    )''')
    # Migration : ajoute la colonne pour les BDs existantes
    try:
        c.execute('ALTER TABLE players ADD COLUMN knowledge_points INTEGER DEFAULT 3')
    except Exception:
        pass
    for column in ('password_hash TEXT', 'race TEXT', 'provenance TEXT',
                   'human_bonus TEXT', "armor TEXT NOT NULL DEFAULT '{}'",
                   "provenance_languages TEXT NOT NULL DEFAULT '[]'", 'religion TEXT'):
        try:
            c.execute(f'ALTER TABLE players ADD COLUMN {column}')
        except Exception:
            pass
    c.execute('''CREATE TABLE IF NOT EXISTS player_skills (
        player_name TEXT,
        skill_id    TEXT,
        PRIMARY KEY (player_name, skill_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS player_weapons (
        player_name TEXT NOT NULL,
        weapon      TEXT NOT NULL,
        PRIMARY KEY (player_name, weapon)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS player_magic_schools (
        player_name TEXT    NOT NULL,
        school      TEXT    NOT NULL,
        level       INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (player_name, school)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS player_spells (
        player_name TEXT    NOT NULL,
        spell       TEXT    NOT NULL,
        school      TEXT    NOT NULL,
        level       INTEGER NOT NULL,
        PRIMARY KEY (player_name, spell)
    )''')
    # extra : appris avec Sorts supplémentaires ; incantation : formule, rituel ou musique créée par le joueur
    for column in ('extra INTEGER NOT NULL DEFAULT 0', "incantation TEXT NOT NULL DEFAULT ''"):
        try:
            c.execute(f'ALTER TABLE player_spells ADD COLUMN {column}')
        except Exception:
            pass
    c.execute('''CREATE TABLE IF NOT EXISTS player_weapon_specs (
        player_name TEXT    NOT NULL,
        weapon      TEXT    NOT NULL,
        level       INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (player_name, weapon)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS skills (
        id             TEXT PRIMARY KEY,
        branch         TEXT    NOT NULL,
        name           TEXT    NOT NULL,
        cost           INTEGER NOT NULL DEFAULT 0,
        knowledge_cost INTEGER NOT NULL DEFAULT 0,
        desc           TEXT    NOT NULL,
        prereq         TEXT,
        sort_order     INTEGER DEFAULT 0
    )''')
    try:
        c.execute('ALTER TABLE skills ADD COLUMN knowledge_cost INTEGER NOT NULL DEFAULT 0')
    except Exception:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS knowledges (
        id          TEXT PRIMARY KEY,
        category    TEXT NOT NULL,
        name        TEXT NOT NULL,
        description TEXT DEFAULT ""
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS player_knowledges (
        player_name  TEXT NOT NULL,
        knowledge_id TEXT NOT NULL,
        level        INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (player_name, knowledge_id)
    )''')
    try:
        c.execute('ALTER TABLE player_knowledges ADD COLUMN level INTEGER NOT NULL DEFAULT 1')
    except Exception:
        pass
    # Synchronise la liste des connaissances avec KNOWLEDGES à chaque démarrage
    c.executemany('''INSERT INTO knowledges VALUES (?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET category=excluded.category, name=excluded.name,
                                                   description=excluded.description''', KNOWLEDGES)
    # Arbre de compétences de référence (skills.json) : ajouté s'il manque, par exemple sur une base neuve.
    # Les compétences déjà présentes, dont celles ajoutées par l'Animation, ne sont pas touchées.
    with open(os.path.join(BASE_DIR, 'skills.json'), encoding='utf-8') as f:
        base_skills = [(s['id'], s['branch'], s['name'], s['cost'], s['knowledge_cost'], s['desc'], s['prereq'],
                        s['sort_order']) for s in json.load(f)]
    c.executemany('''INSERT OR IGNORE INTO skills (id, branch, name, cost, knowledge_cost, desc, prereq, sort_order)
                     VALUES (?,?,?,?,?,?,?,?)''', base_skills + EXTRA_SKILLS)
    c.execute('UPDATE skills SET desc = ? WHERE id = ?', (WEAPON_SKILL_DESC, WEAPON_SKILL))
    # Les niveaux II et III de la spécialisation sont remplacés par des niveaux par catégorie d'arme
    c.execute('UPDATE skills SET name = ?, desc = ? WHERE id = ?', (SPEC_SKILL_NAME, SPEC_SKILL_DESC, SPEC_SKILL))
    c.execute('''DELETE FROM skills WHERE id IN ('specarm2', 'specarm3')
                 AND NOT EXISTS (SELECT 1 FROM player_skills WHERE skill_id IN ('specarm2', 'specarm3'))''')
    c.execute('UPDATE skills SET prereq = NULL WHERE id = ?', (FAITH_SKILL,))
    c.executemany('UPDATE skills SET desc = ? WHERE id = ?', [(d, sid) for sid, d in RELIGION_SKILL_DESCS.items()])
    c.execute("UPDATE skills SET prereq = 'pretrise1' WHERE id = ?", (PROSELYTISM_SKILL,))
    # Les niveaux II à V de la magie sont remplacés par des niveaux par école (niveaux non achetés seulement)
    for skill_id, (_, name, desc) in MAGIC_SKILLS.items():
        c.execute('UPDATE skills SET name = ?, desc = ? WHERE id = ?', (name, desc, skill_id))
        old_levels = [skill_id[:-1] + str(n) for n in range(2, 6)]
        marks = ','.join('?' * len(old_levels))
        c.execute(f'''DELETE FROM skills WHERE id IN ({marks})
                      AND NOT EXISTS (SELECT 1 FROM player_skills WHERE skill_id IN ({marks}))''', old_levels * 2)
    c.execute(f"UPDATE skills SET prereq = '{MAGIC_SKILL}' WHERE id = 'ecoavance1' AND prereq = 'ecomagie2'")
    # Sorts supplémentaires vaut pour la magie comme pour la prêtrise : l'école connue est vérifiée à l'achat
    c.execute('UPDATE skills SET desc = ?, prereq = NULL WHERE id = ?', (EXTRA_SPELL_DESC, EXTRA_SPELL_SKILL))
    c.execute("UPDATE skills SET desc = ?, prereq = 'lireerire1' WHERE id = ?", (SCROLL_SKILL_DESC, SCROLL_SKILL))
    # L'ancienne « Tactiques militaires (1 pays) » est retirée si personne ne la possède
    c.execute('''DELETE FROM knowledges WHERE id = 'k_tactiques'
                 AND NOT EXISTS (SELECT 1 FROM player_knowledges WHERE knowledge_id = 'k_tactiques')''')
    conn.commit()
    conn.close()

# --- Servir le frontend ---
@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

# --- Auth admin ---
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    password = request.json.get('password', '')
    if password == ADMIN_PASSWORD:
        return jsonify({'ok': True})
    return jsonify({'error': 'Mot de passe incorrect'}), 401

# --- Comptes joueurs ---
def read_credentials():
    data = request.json or {}
    return (data.get('name') or '').strip(), data.get('password') or ''

def password_too_short(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({'error': f'Le mot de passe doit faire au moins {MIN_PASSWORD_LENGTH} caractères'}), 400
    return None

@app.route('/api/register', methods=['POST'])
def register():
    name, password = read_credentials()
    if not name:
        return jsonify({'error': 'Nom requis'}), 400
    if (err := password_too_short(password)):
        return err
    conn = get_db()
    c = conn.cursor()
    if c.execute('SELECT 1 FROM players WHERE name = ?', (name,)).fetchone():
        conn.close(); return jsonify({'error': 'Ce nom est déjà utilisé'}), 400
    c.execute('INSERT INTO players (name, points, knowledge_points, password_hash) VALUES (?, 9, 3, ?)',
              (name, generate_password_hash(password)))
    conn.commit()
    conn.close()
    session['player'] = name
    return jsonify({'name': name})

@app.route('/api/login', methods=['POST'])
def login():
    name, password = read_credentials()
    conn = get_db()
    c = conn.cursor()
    player = c.execute('SELECT password_hash FROM players WHERE name = ?', (name,)).fetchone()
    if not player:
        conn.close(); return jsonify({'error': 'Nom ou mot de passe incorrect'}), 401
    if player['password_hash'] is None:
        # Joueur créé avant les comptes : le premier mot de passe saisi devient le sien
        if (err := password_too_short(password)):
            conn.close(); return err
        c.execute('UPDATE players SET password_hash = ? WHERE name = ?', (generate_password_hash(password), name))
        conn.commit()
    elif not check_password_hash(player['password_hash'], password):
        conn.close(); return jsonify({'error': 'Nom ou mot de passe incorrect'}), 401
    conn.close()
    session['player'] = name
    return jsonify({'name': name})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('player', None)
    return jsonify({'ok': True})

@app.route('/api/me', methods=['GET'])
def me():
    name = session.get('player')
    if not name:
        return jsonify({'error': 'Non connecté'}), 401
    return get_player_data(name)

# --- Joueur ---
@app.route('/api/player/<name>', methods=['GET'])
def get_player(name):
    if session.get('player') != name and not is_admin():
        return jsonify({'error': 'Non connecté'}), 401
    return get_player_data(name)

def get_player_data(name):
    conn = get_db()
    c = conn.cursor()
    player = c.execute('SELECT * FROM players WHERE name = ?', (name,)).fetchone()
    if not player:
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    skills  = player_skills(c, player)
    levels  = knowledge_levels(c, player)
    grants  = provenance_grants(player)
    weapons = weapon_status(c, player)
    conn.close()
    return jsonify({'name': name, 'points': player['points'],
                    'knowledgePoints': player['knowledge_points'],
                    'acquiredSkills': skills, **weapons, 'acquiredKnowledges': list(levels),
                    'knowledgeLevels': levels,
                    'provenanceSkills': grants['skills'], 'provenanceKnowledges': grants['knowledges'],
                    'religionKnowledges': religion_knowledges(player),
                    'character': {**character_sheet(player, skills), 'provenanceNotes': grants['notes'],
                                  'provenanceLanguages': json.loads(player['provenance_languages'] or '[]')}})

def provenance_grants(player):
    """Compétences, connaissances et notes données gratuitement par la provenance du joueur."""
    rules = PROVENANCES.get(player['provenance'], {})
    knowledges = list(rules.get('knowledges', []))
    if 'language_choice' in rules:
        _, choices = rules['language_choice']
        knowledges += [k for k in json.loads(player['provenance_languages'] or '[]') if k in choices]
    return {'skills': list(rules.get('skills', [])), 'knowledges': knowledges, 'notes': rules.get('notes', [])}

def player_skills(c, player):
    """Compétences achetées + compétences de provenance (+ arme de prédilection si au moins une catégorie)."""
    bought = [r['skill_id'] for r in c.execute(
        'SELECT skill_id FROM player_skills WHERE player_name = ?', (player['name'],)
    ).fetchall()]
    if player_weapons(c, player['name']) and WEAPON_SKILL not in bought:
        bought.append(WEAPON_SKILL)
    if weapon_specs(c, player['name']) and SPEC_SKILL not in bought:
        bought.append(SPEC_SKILL)
    # Une compétence de magie est acquise dès qu'une école de son type l'est
    kinds = {SCHOOLS_BY_ID[s]['kind'] for s in magic_schools(c, player['name']) if s in SCHOOLS_BY_ID}
    for skill_id, (kind, _, _) in MAGIC_SKILLS.items():
        if kind in kinds and skill_id not in bought:
            bought.append(skill_id)
    if any(s['extra'] for s in player_spells(c, player['name'])) and EXTRA_SPELL_SKILL not in bought:
        bought.append(EXTRA_SPELL_SKILL)
    return bought + [s for s in provenance_grants(player)['skills'] if s not in bought]

def player_weapons(c, name):
    return [r['weapon'] for r in c.execute(
        'SELECT weapon FROM player_weapons WHERE player_name = ?', (name,)).fetchall()]

def next_weapon_cost(c, player, weapons):
    """Gratuit tant que le joueur n'a pas épuisé ses catégories gratuites, sinon le prix de la compétence."""
    free = 1 + PROVENANCES.get(player['provenance'], {}).get('extra_free_weapons', 0)
    if len(weapons) < free:
        return 0
    return c.execute('SELECT cost FROM skills WHERE id = ?', (WEAPON_SKILL,)).fetchone()['cost']

def weapon_specs(c, name):
    """{catégorie d'arme: niveau de spécialisation}"""
    return {r['weapon']: r['level'] for r in c.execute(
        'SELECT weapon, level FROM player_weapon_specs WHERE player_name = ?', (name,)).fetchall()}

def magic_schools(c, name):
    """{école: niveau}"""
    return {r['school']: r['level'] for r in c.execute(
        'SELECT school, level FROM player_magic_schools WHERE player_name = ?', (name,)).fetchall()}

def player_spells(c, name):
    return [{'id': r['spell'], 'school': r['school'], 'level': r['level'],
             'extra': bool(r['extra']), 'incantation': r['incantation']} for r in c.execute(
        'SELECT * FROM player_spells WHERE player_name = ? ORDER BY school, level', (name,)).fetchall()]

def magic_school_error(player, schools, school_id, kind):
    """Raison pour laquelle le joueur ne peut pas monter cette école d'un niveau, ou None."""
    school = SCHOOLS_BY_ID.get(school_id)
    if not school or school['kind'] != kind:
        return 'Choisissez une école de magie'
    level = schools.get(school_id, 0) + 1
    if level > MAGIC_MAX_LEVEL:
        return f'Niveau maximum ({MAGIC_MAX_LEVEL}) déjà atteint'
    if kind == 'advanced':
        # Le niveau de l'école avancée ne peut pas dépasser celui de ses deux écoles de base
        if any(schools.get(r, 0) < level for r in school['requires']):
            names = ' et '.join(SCHOOLS_BY_ID[r]['name'] for r in school['requires'])
            return f'{school["name"]} niveau {level} demande {names} au niveau {level}'
    if kind == 'divine':
        if school['religion'] != player['religion']:
            return f'Ces sorts divins demandent de prier : {school["religion"]}'
        other = [s for s in schools if s != school_id and SCHOOLS_BY_ID.get(s, {}).get('kind') == 'divine']
        if other:
            return f'Vous avez déjà des sorts divins de {SCHOOLS_BY_ID[other[0]]["name"]}'
    return None

def weapon_status(c, player):
    """Armes, spécialisations, écoles de magie et sorts : tout ce que l'achat d'une compétence peut changer."""
    weapons = player_weapons(c, player['name'])
    return {'weapons': weapons, 'nextWeaponCost': next_weapon_cost(c, player, weapons),
            'weaponSpecs': weapon_specs(c, player['name']),
            'magicSchools': magic_schools(c, player['name']), 'spells': player_spells(c, player['name'])}

def character_sheet(player, skills):
    """Race, provenance, armure et totaux calculés de points de vie / d'esprit / d'armure."""
    race  = player['race']
    armor = json.loads(player['armor'] or '{}')
    pv, pe, talent = RACES.get(race, (0, 0, ''))
    if race == 'Humain' and player['human_bonus'] in ('pv', 'pe'):
        pv += player['human_bonus'] == 'pv'
        pe += player['human_bonus'] == 'pe'
    for skill_id in skills:
        bonus = SKILL_STAT_BONUSES.get(skill_id, {})
        pv += bonus.get('pv', 0)
        pe += bonus.get('pe', 0)
    armor_points = 0
    immunities   = {}
    if race != 'Xuhatek':
        for part, material in armor.items():
            if part in ARMOR_PARTS and material in ARMOR_MATERIALS:
                _, column, immunity = ARMOR_MATERIALS[material]
                armor_points += ARMOR_PARTS[part][1][column]
                immunities[part] = immunity
    return {'race': race, 'provenance': player['provenance'], 'humanBonus': player['human_bonus'],
            'religion': player['religion'],
            'talent': talent, 'armor': armor, 'armorImmunities': immunities,
            'pv': pv, 'pe': pe, 'armorPoints': armor_points}

def update_character(c, name, data, allowed):
    """Applique les champs de fiche autorisés ; renvoie un message d'erreur ou None."""
    updates = {}
    if 'race' in allowed and 'race' in data:
        if data['race'] not in RACES:
            return 'Race inconnue'
        updates['race'] = data['race']
    if 'provenance' in allowed and 'provenance' in data:
        if data['provenance'] not in PROVENANCES:
            return 'Provenance inconnue'
        updates['provenance'] = data['provenance']
        rules = PROVENANCES[data['provenance']]
        if 'language_choice' in rules:
            count, choices = rules['language_choice']
            languages = data.get('provenanceLanguages') or []
            if len(set(languages)) != count or any(k not in choices for k in languages):
                return f'Choisissez {count} langues différentes pour cette provenance'
            updates['provenance_languages'] = json.dumps(sorted(set(languages)))
        else:
            updates['provenance_languages'] = '[]'
    if 'humanBonus' in allowed and 'humanBonus' in data:
        if data['humanBonus'] not in ('pv', 'pe', None):
            return 'Bonus humain invalide (pv ou pe)'
        updates['human_bonus'] = data['humanBonus']
    if 'religion' in allowed and 'religion' in data:
        if data['religion'] not in RELIGIONS and data['religion'] is not None:
            return 'Religion inconnue'
        updates['religion'] = data['religion']
    if 'armor' in allowed and 'armor' in data:
        armor = data['armor'] or {}
        if any(p not in ARMOR_PARTS or m not in ARMOR_MATERIALS for p, m in armor.items()):
            return 'Pièce ou matériau d\'armure inconnu'
        updates['armor'] = json.dumps(armor)
    for column, value in updates.items():
        c.execute(f'UPDATE players SET {column} = ? WHERE name = ?', (value, name))
    return None

@app.route('/api/character-rules', methods=['GET'])
def character_rules():
    return jsonify({
        'races':       [{'name': n, 'pv': pv, 'pe': pe, 'talent': t} for n, (pv, pe, t) in RACES.items()],
        'provenances': [{'name': n, 'skills': r.get('skills', []), 'knowledges': r.get('knowledges', []),
                         'notes': r.get('notes', []), 'extraFreeWeapons': r.get('extra_free_weapons', 0),
                         'languageChoice': ({'count': r['language_choice'][0], 'options': r['language_choice'][1]}
                                            if 'language_choice' in r else None)}
                        for n, r in PROVENANCES.items()],
        'religions':   RELIGIONS,
        'armorParts':  [{'id': k, 'name': n, 'points': pts} for k, (n, pts) in ARMOR_PARTS.items()],
        'armorMaterials': [{'id': k, 'name': n, 'immunity': imm} for k, (n, _, imm) in ARMOR_MATERIALS.items()],
    })

@app.route('/api/player/<name>/character', methods=['POST'])
@require_player
def set_character(name):
    """Le joueur choisit sa race et sa provenance une seule fois ; ensuite seule l'Animation peut les changer."""
    data = request.json or {}
    conn = get_db()
    c    = conn.cursor()
    player = c.execute('SELECT race, provenance FROM players WHERE name=?', (name,)).fetchone()
    if player['race'] or player['provenance']:
        conn.close(); return jsonify({'error': 'Race et provenance déjà choisies, demandez à l\'Animation'}), 400
    if not data.get('race') or not data.get('provenance'):
        conn.close(); return jsonify({'error': 'Choisissez une race et une provenance'}), 400
    if data['race'] == 'Humain' and data.get('humanBonus') not in ('pv', 'pe'):
        conn.close(); return jsonify({'error': 'Un humain doit choisir +1 pv ou +1 pe'}), 400
    if (err := update_character(c, name, data, {'race', 'provenance', 'humanBonus', 'religion'})):
        conn.close(); return jsonify({'error': err}), 400
    conn.commit()
    conn.close()
    return get_player_data(name)

@app.route('/api/player/<name>/religion', methods=['POST'])
@require_player
def set_religion(name):
    """Contrairement à la race et la provenance, le joueur peut changer de religion quand il veut."""
    conn = get_db()
    c    = conn.cursor()
    if (err := update_character(c, name, {'religion': (request.json or {}).get('religion')}, {'religion'})):
        conn.close(); return jsonify({'error': err}), 400
    conn.commit()
    conn.close()
    return get_player_data(name)

@app.route('/api/admin/player/<name>/character', methods=['POST'])
@require_admin
def admin_set_character(name):
    conn = get_db()
    c    = conn.cursor()
    if not c.execute('SELECT 1 FROM players WHERE name=?', (name,)).fetchone():
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    if (err := update_character(c, name, request.json or {}, {'race', 'provenance', 'humanBonus', 'armor', 'religion'})):
        conn.close(); return jsonify({'error': err}), 400
    conn.commit()
    conn.close()
    return get_player_data(name)

def knowledge_levels(c, player):
    """{knowledge_id: niveau} : niveaux achetés + 1 niveau par connaissance de provenance."""
    levels = {r['knowledge_id']: r['level'] for r in c.execute(
        'SELECT knowledge_id, level FROM player_knowledges WHERE player_name = ?', (player['name'],)
    ).fetchall()}
    for kid in provenance_grants(player)['knowledges'] + religion_knowledges(player):
        levels[kid] = min(levels.get(kid, 0) + 1, KNOWLEDGE_MAX_LEVEL)
    return levels

def religion_knowledges(player):
    """Connaissance donnée gratuitement par la religion priée (liste vide sans religion)."""
    kid = RELIGION_KNOWLEDGES.get(player['religion'])
    return [kid] if kid else []

@app.route('/api/player/<name>/purchase', methods=['POST'])
@require_player
def purchase_skill(name):
    skill_id = request.json.get('skillId')
    conn = get_db()
    c = conn.cursor()
    player = c.execute('SELECT * FROM players WHERE name = ?', (name,)).fetchone()
    if not player:
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    skill = c.execute('SELECT * FROM skills WHERE id = ?', (skill_id,)).fetchone()
    if not skill:
        conn.close(); return jsonify({'error': 'Compétence introuvable'}), 404
    owned = player_skills(c, player)
    if skill_id == WEAPON_SKILL:
        return purchase_weapon(conn, player, request.json.get('weapon'))
    if skill_id == SPEC_SKILL:
        return purchase_spec(conn, player, skill['cost'], request.json.get('weapon'))
    if skill_id in SKILLS_REQUIRING_RELIGION and not player['religion']:
        conn.close(); return jsonify({'error': 'Prérequis manquant : prier une religion (fiche Personnage)'}), 400
    if skill['prereq'] and skill['prereq'] not in owned:
        conn.close(); return jsonify({'error': 'Prérequis manquant'}), 400
    if skill_id in SKILLS_REQUIRING_MAGIC and not magic_schools(c, name):
        conn.close(); return jsonify({'error': 'Prérequis manquant : École de magie ou Prêtrise'}), 400
    # Compétences achetables plusieurs fois : magie (par école) et sorts supplémentaires
    if skill_id in MAGIC_SKILLS:
        return purchase_magic(conn, player, skill['cost'], MAGIC_SKILLS[skill_id][0],
                              request.json.get('school'), request.json.get('spells') or [])
    if skill_id == EXTRA_SPELL_SKILL:
        return purchase_extra_spell(conn, player, request.json.get('spell'))
    if skill_id in owned:
        conn.close(); return jsonify({'error': 'Déjà acquise'}), 400
    weapon_prereq = SKILL_WEAPON_PREREQS.get(skill_id)
    if weapon_prereq and not set(weapon_prereq) & set(player_weapons(c, name)):
        conn.close()
        return jsonify({'error': 'Prérequis manquant : arme de prédilection ('
                                 + ' ou '.join(WEAPONS[w] for w in weapon_prereq) + ')'}), 400
    if skill['cost'] > 0 and player['points'] < skill['cost']:
        conn.close(); return jsonify({'error': 'Points XP insuffisants'}), 400
    if skill['knowledge_cost'] > 0 and player['knowledge_points'] < skill['knowledge_cost']:
        conn.close(); return jsonify({'error': 'Points de connaissance insuffisants'}), 400

    if skill['cost'] > 0:
        c.execute('UPDATE players SET points = points - ? WHERE name = ?', (skill['cost'], name))
    if skill['knowledge_cost'] > 0:
        c.execute('UPDATE players SET knowledge_points = knowledge_points - ? WHERE name = ?', (skill['knowledge_cost'], name))
    c.execute('INSERT INTO player_skills VALUES (?, ?)', (name, skill_id))
    conn.commit()
    return purchase_result(conn, name)

def purchase_weapon(conn, player, weapon):
    """Ajoute une catégorie d'arme de prédilection ; ferme la connexion."""
    c    = conn.cursor()
    name = player['name']
    if weapon not in WEAPONS:
        conn.close(); return jsonify({'error': 'Choisissez une catégorie d\'arme'}), 400
    weapons = player_weapons(c, name)
    if weapon in weapons:
        conn.close(); return jsonify({'error': 'Catégorie déjà acquise'}), 400
    cost = next_weapon_cost(c, player, weapons)
    if player['points'] < cost:
        conn.close(); return jsonify({'error': 'Points XP insuffisants'}), 400
    c.execute('UPDATE players SET points = points - ? WHERE name = ?', (cost, name))
    c.execute('INSERT INTO player_weapons VALUES (?, ?)', (name, weapon))
    conn.commit()
    return purchase_result(conn, name)

def purchase_spec(conn, player, cost, weapon):
    """Monte d'un niveau la spécialisation d'une arme de prédilection ; ferme la connexion."""
    c    = conn.cursor()
    name = player['name']
    if weapon not in player_weapons(c, name):
        conn.close(); return jsonify({'error': 'Choisissez une de vos armes de prédilection'}), 400
    if weapon_specs(c, name).get(weapon, 0) >= SPEC_MAX_LEVEL:
        conn.close(); return jsonify({'error': f'Niveau maximum ({SPEC_MAX_LEVEL}) déjà atteint'}), 400
    if player['points'] < cost:
        conn.close(); return jsonify({'error': 'Points XP insuffisants'}), 400
    c.execute('UPDATE players SET points = points - ? WHERE name = ?', (cost, name))
    c.execute('''INSERT INTO player_weapon_specs (player_name, weapon, level) VALUES (?, ?, 1)
                 ON CONFLICT(player_name, weapon) DO UPDATE SET level = level + 1''', (name, weapon))
    conn.commit()
    return purchase_result(conn, name)

def purchase_magic(conn, player, cost, kind, school, spells):
    """Ouvre une école (de base, avancée ou divine) ou la monte d'un niveau avec les sorts choisis ; ferme la connexion."""
    c       = conn.cursor()
    name    = player['name']
    schools = magic_schools(c, name)
    if (err := magic_school_error(player, schools, school, kind)):
        conn.close(); return jsonify({'error': err}), 400
    level = schools.get(school, 0) + 1
    # Un sort déjà appris en sort supplémentaire n'est pas proposé à nouveau
    known   = {s['id'] for s in player_spells(c, name)}
    choices = [s for s in SCHOOL_SPELLS.get((school, level), []) if s not in known]
    needed  = min(SPELLS_PER_LEVEL, len(choices))
    spells  = set(spells)
    if len(spells) != needed or not spells <= set(choices):
        conn.close(); return jsonify({'error': f'Choisissez {needed} sorts de niveau {level}'}), 400
    if player['points'] < cost:
        conn.close(); return jsonify({'error': 'Points XP insuffisants'}), 400
    c.execute('UPDATE players SET points = points - ? WHERE name = ?', (cost, name))
    c.execute('''INSERT INTO player_magic_schools (player_name, school, level) VALUES (?, ?, 1)
                 ON CONFLICT(player_name, school) DO UPDATE SET level = level + 1''', (name, school))
    c.executemany('INSERT INTO player_spells (player_name, spell, school, level) VALUES (?, ?, ?, ?)',
                  [(name, spell, school, level) for spell in spells])
    conn.commit()
    return purchase_result(conn, name)

def purchase_extra_spell(conn, player, spell):
    """Sort supplémentaire : un sort d'une école connue, d'un niveau maîtrisé ; coûte son niveau en XP."""
    c    = conn.cursor()
    name = player['name']
    if spell not in SPELL_INFO:
        conn.close(); return jsonify({'error': 'Choisissez un sort'}), 400
    school, level = SPELL_INFO[spell]
    if magic_schools(c, name).get(school, 0) < level:
        conn.close(); return jsonify({'error': 'Ce sort est d\'une école ou d\'un niveau que vous ne maîtrisez pas'}), 400
    if spell in {s['id'] for s in player_spells(c, name)}:
        conn.close(); return jsonify({'error': 'Sort déjà connu'}), 400
    if player['points'] < level:
        conn.close(); return jsonify({'error': 'Points XP insuffisants'}), 400
    c.execute('UPDATE players SET points = points - ? WHERE name = ?', (level, name))
    c.execute('INSERT INTO player_spells (player_name, spell, school, level, extra) VALUES (?, ?, ?, ?, 1)',
              (name, spell, school, level))
    conn.commit()
    return purchase_result(conn, name)

@app.route('/api/player/<name>/spell-incantation', methods=['POST'])
@require_player
def save_spell_incantation(name):
    """Le joueur écrit la formule, le rituel ou la musique qu'il a créé pour un de ses sorts."""
    data = request.json or {}
    text = (data.get('incantation') or '').strip()
    if len(text) > INCANTATION_MAX_LENGTH:
        return jsonify({'error': f'Incantation trop longue ({INCANTATION_MAX_LENGTH} caractères max)'}), 400
    conn = get_db()
    c    = conn.cursor()
    c.execute('UPDATE player_spells SET incantation = ? WHERE player_name = ? AND spell = ?',
              (text, name, data.get('spell')))
    if c.rowcount == 0:
        conn.close(); return jsonify({'error': 'Sort inconnu'}), 404
    conn.commit()
    spells = player_spells(c, name)
    conn.close()
    return jsonify({'spells': spells})

def purchase_result(conn, name):
    c          = conn.cursor()
    new_player = c.execute('SELECT * FROM players WHERE name=?', (name,)).fetchone()
    acquired   = player_skills(c, new_player)
    weapons    = weapon_status(c, new_player)
    conn.close()
    return jsonify({'points': new_player['points'], 'knowledgePoints': new_player['knowledge_points'],
                    'acquiredSkills': acquired, **weapons})

# --- Arbre de compétences ---
def skill_key(name):
    """Clé de comparaison d'un nom de compétence : sans niveau romain, accents, parenthèses ni ponctuation."""
    name = re.sub(r'\s+[IVX]+$', '', name.strip())
    name = re.sub(r'\(.*?\)', '', name)
    name = unicodedata.normalize('NFD', name.lower())
    key  = ''.join(ch for ch in name if ch.isalnum() and not unicodedata.combining(ch))
    return SKILL_NAME_ALIASES.get(key, key)

def load_skill_categories():
    """{clé de compétence: catégorie} d'après les fichiers de catégories."""
    placement = {}
    for filename, category, _ in SKILL_CATEGORIES:
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8-sig') as f:
            lines = [l.strip() for l in f.read().splitlines()[1:] if l.strip()]
        for line in lines:
            key = skill_key(re.split(r'\s+-', line)[0])
            placement.setdefault(key, SKILL_CATEGORY_CHOICES.get(key, category))
    return placement

def sort_name(name):
    """Ordre alphabétique sans accents, niveaux d'une même compétence regroupés."""
    base = unicodedata.normalize('NFD', re.sub(r'\s+[IVX]+$', '', name).lower())
    return ''.join(ch for ch in base if not unicodedata.combining(ch))

@app.route('/api/skills', methods=['GET'])
def get_skills():
    conn = get_db()
    rows = conn.execute('SELECT * FROM skills ORDER BY sort_order').fetchall()
    conn.close()
    placement = load_skill_categories()
    order     = [name for _, name, _ in SKILL_CATEGORIES] + [OTHER_CATEGORY]
    branches  = {name: [] for name in order}
    for r in rows:
        # Sans ligne dans les fichiers : la branche enregistrée si c'est une catégorie connue, sinon « Autres »
        b = placement.get(skill_key(r['name'])) \
            or (r['branch'] if r['branch'] in branches else OTHER_CATEGORY)
        branches[b].append(r)
    return jsonify([{'branchName': b,
                     'skills': [skill_json(r) for r in sorted(branches[b], key=lambda r: (sort_name(r['name']), r['sort_order']))]}
                    for b in order if branches[b]])

def skill_json(r):
    skill = {'id': r['id'], 'name': r['name'], 'cost': r['cost'],
             'knowledge_cost': r['knowledge_cost'],
             'desc': r['desc'], 'prereq': r['prereq'],
             'weaponPrereq': SKILL_WEAPON_PREREQS.get(r['id']),
             'requiresReligion': r['id'] in SKILLS_REQUIRING_RELIGION,
             'requiresMagic': r['id'] in SKILLS_REQUIRING_MAGIC}
    if r['id'] == WEAPON_SKILL:
        skill['weaponChoices'] = WEAPONS
    if r['id'] == SPEC_SKILL:
        skill.update(weaponNames=WEAPONS, specEffects=WEAPON_SPEC_EFFECTS, maxLevel=SPEC_MAX_LEVEL)
    if r['id'] in MAGIC_SKILLS:
        skill.update(magicKind=MAGIC_SKILLS[r['id']][0], maxLevel=MAGIC_MAX_LEVEL, spellsPerLevel=SPELLS_PER_LEVEL)
    if r['id'] == EXTRA_SPELL_SKILL:
        skill['extraSpell'] = True
    return skill

@app.route('/api/spells', methods=['GET'])
def get_spells():
    return jsonify(MAGIC_SCHOOLS)

@app.route('/api/knowledges', methods=['GET'])
def get_knowledges():
    conn = get_db()
    rows = conn.execute('SELECT * FROM knowledges ORDER BY category, name').fetchall()
    conn.close()
    cats = {}
    for r in rows:
        cat = r['category']
        if cat not in cats:
            cats[cat] = []
        cats[cat].append({'id': r['id'], 'name': r['name'], 'description': r['description']})
    return jsonify([{'category': k, 'knowledges': v} for k, v in cats.items()])

@app.route('/api/player/<name>/buy-knowledge', methods=['POST'])
@require_player
def buy_knowledge(name):
    knowledge_id = request.json.get('knowledgeId')
    conn = get_db()
    c = conn.cursor()
    player = c.execute('SELECT * FROM players WHERE name = ?', (name,)).fetchone()
    if not player:
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    knowledge = c.execute('SELECT * FROM knowledges WHERE id = ?', (knowledge_id,)).fetchone()
    if not knowledge:
        conn.close(); return jsonify({'error': 'Connaissance introuvable'}), 404
    if knowledge_levels(c, player).get(knowledge_id, 0) >= KNOWLEDGE_MAX_LEVEL:
        conn.close(); return jsonify({'error': f'Niveau maximum ({KNOWLEDGE_MAX_LEVEL}) déjà atteint'}), 400
    if player['knowledge_points'] < 1:
        conn.close(); return jsonify({'error': 'Points de connaissance insuffisants'}), 400
    c.execute('UPDATE players SET knowledge_points = knowledge_points - 1 WHERE name = ?', (name,))
    c.execute('''INSERT INTO player_knowledges (player_name, knowledge_id, level) VALUES (?, ?, 1)
                 ON CONFLICT(player_name, knowledge_id) DO UPDATE SET level = level + 1''', (name, knowledge_id))
    conn.commit()
    player = c.execute('SELECT * FROM players WHERE name=?', (name,)).fetchone()
    levels = knowledge_levels(c, player)
    conn.close()
    return jsonify({'knowledgePoints': player['knowledge_points'], 'acquiredKnowledges': list(levels), 'knowledgeLevels': levels})

@app.route('/api/skills', methods=['POST'])
@require_admin
def add_skill():
    data           = request.json
    branch         = data.get('branch', 'Combat')
    name           = data.get('name', '').strip()
    cost           = int(data.get('cost', 0) or 0)
    knowledge_cost = int(data.get('knowledge_cost', 0) or 0)
    desc           = data.get('desc', '').strip()
    prereq         = data.get('prereq') or None
    if not name or not desc:
        return jsonify({'error': 'Champs manquants'}), 400
    if cost == 0 and knowledge_cost == 0:
        return jsonify({'error': 'Au moins un coût (XP ou Connaissance) doit être supérieur à 0'}), 400
    conn = get_db()
    c    = conn.cursor()
    max_order = c.execute('SELECT MAX(sort_order) FROM skills WHERE branch=?', (branch,)).fetchone()[0] or 0
    new_id    = branch[0].lower() + str(int(time.time()))
    c.execute('INSERT INTO skills (id, branch, name, cost, knowledge_cost, desc, prereq, sort_order) VALUES (?,?,?,?,?,?,?,?)',
              (new_id, branch, name, cost, knowledge_cost, desc, prereq, max_order + 1))
    conn.commit()
    conn.close()
    return jsonify({'id': new_id, 'branch': branch, 'name': name, 'cost': cost,
                    'knowledge_cost': knowledge_cost, 'desc': desc, 'prereq': prereq})

@app.route('/api/admin/player/<name>/remove-knowledge', methods=['POST'])
@require_admin
def admin_remove_knowledge(name):
    knowledge_id = request.json.get('knowledgeId')
    refund       = bool(request.json.get('refund', True))
    conn = get_db()
    c    = conn.cursor()
    if not c.execute('SELECT 1 FROM players WHERE name=?', (name,)).fetchone():
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    if not c.execute('SELECT 1 FROM player_knowledges WHERE player_name=? AND knowledge_id=?', (name, knowledge_id)).fetchone():
        # Les niveaux donnés par la provenance ne s'annulent pas : changez la provenance
        conn.close(); return jsonify({'error': 'Aucun niveau acheté pour cette connaissance'}), 400
    # Retire un seul niveau ; la connaissance disparaît quand elle tombe à 0
    c.execute('UPDATE player_knowledges SET level = level - 1 WHERE player_name=? AND knowledge_id=?', (name, knowledge_id))
    c.execute('DELETE FROM player_knowledges WHERE player_name=? AND knowledge_id=? AND level <= 0', (name, knowledge_id))
    if refund:
        c.execute('UPDATE players SET knowledge_points = knowledge_points + 1 WHERE name=?', (name,))
    conn.commit()
    player = c.execute('SELECT * FROM players WHERE name=?', (name,)).fetchone()
    levels = knowledge_levels(c, player)
    conn.close()
    return jsonify({'knowledgePoints': player['knowledge_points'], 'acquiredKnowledges': list(levels), 'knowledgeLevels': levels})

# --- Admin : joueurs ---
@app.route('/api/admin/players', methods=['GET'])
@require_admin
def get_all_players():
    conn    = get_db()
    players = conn.execute('SELECT * FROM players ORDER BY name').fetchall()
    result  = []
    for p in players:
        skill_count = conn.execute(
            'SELECT COUNT(*) FROM player_skills WHERE player_name=?', (p['name'],)
        ).fetchone()[0]
        result.append({'name': p['name'], 'points': p['points'],
                       'knowledgePoints': p['knowledge_points'], 'skillCount': skill_count})
    conn.close()
    return jsonify(result)

@app.route('/api/admin/give-points', methods=['POST'])
@require_admin
def give_points():
    target = request.json.get('player', '').strip()
    amount = request.json.get('amount')
    if not target or amount is None:
        return jsonify({'error': 'Champs manquants'}), 400
    conn = get_db()
    c    = conn.cursor()
    if not c.execute('SELECT 1 FROM players WHERE name=?', (target,)).fetchone():
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    c.execute('UPDATE players SET points = points + ? WHERE name=?', (int(amount), target))
    conn.commit()
    new_points = c.execute('SELECT points FROM players WHERE name=?', (target,)).fetchone()['points']
    conn.close()
    return jsonify({'points': new_points})

@app.route('/api/admin/give-knowledge', methods=['POST'])
@require_admin
def give_knowledge():
    target = request.json.get('player', '').strip()
    amount = request.json.get('amount')
    if not target or amount is None:
        return jsonify({'error': 'Champs manquants'}), 400
    conn = get_db()
    c    = conn.cursor()
    if not c.execute('SELECT 1 FROM players WHERE name=?', (target,)).fetchone():
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    c.execute('UPDATE players SET knowledge_points = knowledge_points + ? WHERE name=?', (int(amount), target))
    conn.commit()
    new_kp = c.execute('SELECT knowledge_points FROM players WHERE name=?', (target,)).fetchone()['knowledge_points']
    conn.close()
    return jsonify({'knowledgePoints': new_kp})

@app.route('/api/admin/distribute-knowledge', methods=['POST'])
@require_admin
def distribute_knowledge():
    """Donne des points de connaissance à TOUS les joueurs SAUF ceux dans la liste exclude."""
    amount  = int(request.json.get('amount', 1))
    exclude = set(request.json.get('exclude', []))
    conn = get_db()
    c    = conn.cursor()
    players = [r['name'] for r in c.execute('SELECT name FROM players').fetchall()]
    updated = []
    for name in players:
        if name not in exclude:
            c.execute('UPDATE players SET knowledge_points = knowledge_points + ? WHERE name=?', (amount, name))
            updated.append(name)
    conn.commit()
    conn.close()
    return jsonify({'updated': updated, 'skipped': list(exclude), 'count': len(updated)})

@app.route('/api/admin/distribute-xp', methods=['POST'])
@require_admin
def distribute_xp():
    """Donne des XP à TOUS les joueurs SAUF ceux dans la liste exclude."""
    amount  = int(request.json.get('amount', 2))
    exclude = set(request.json.get('exclude', []))
    conn = get_db()
    c    = conn.cursor()
    players = [r['name'] for r in c.execute('SELECT name FROM players').fetchall()]
    updated = []
    for name in players:
        if name not in exclude:
            c.execute('UPDATE players SET points = points + ? WHERE name=?', (amount, name))
            updated.append(name)
    conn.commit()
    conn.close()
    return jsonify({'updated': updated, 'skipped': list(exclude), 'count': len(updated)})

@app.route('/api/admin/player/<name>/set-password', methods=['POST'])
@require_admin
def admin_set_password(name):
    """Pour un joueur qui a oublié son mot de passe."""
    password = (request.json or {}).get('password') or ''
    if (err := password_too_short(password)):
        return err
    conn = get_db()
    c    = conn.cursor()
    if not c.execute('SELECT 1 FROM players WHERE name=?', (name,)).fetchone():
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    c.execute('UPDATE players SET password_hash = ? WHERE name=?', (generate_password_hash(password), name))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/reset/<name>', methods=['POST'])
@require_admin
def reset_player(name):
    conn = get_db()
    c    = conn.cursor()
    c.execute('UPDATE players SET points = 9, knowledge_points = 3 WHERE name=?', (name,))
    c.execute('DELETE FROM player_skills WHERE player_name=?', (name,))
    c.execute('DELETE FROM player_weapons WHERE player_name=?', (name,))
    c.execute('DELETE FROM player_weapon_specs WHERE player_name=?', (name,))
    c.execute('DELETE FROM player_magic_schools WHERE player_name=?', (name,))
    c.execute('DELETE FROM player_spells WHERE player_name=?', (name,))
    c.execute('DELETE FROM player_knowledges WHERE player_name=?', (name,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# Initialisée à l'import pour fonctionner aussi derrière waitress-serve / gunicorn
init_db()

if __name__ == '__main__':
    from waitress import serve
    print(f"\n  GN Skill Tree — ouvrez http://localhost:{PORT} dans le navigateur")
    if 'ADMIN_PASSWORD' not in os.environ:
        print("  ATTENTION : mot de passe Animation par défaut, définissez ADMIN_PASSWORD sur le serveur.")
    print()
    serve(app, host=HOST, port=PORT)
