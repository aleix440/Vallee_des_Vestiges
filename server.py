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
# Valeurs de départ seulement : les provenances sont ensuite dans la base, modifiables par l'Animation.
PROVENANCES_SEED = {
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
# Écoles de magie (spells.json) ; leurs sorts sont dans la base, modifiables par l'Animation
with open(os.path.join(BASE_DIR, 'spells.json'), encoding='utf-8') as f:
    SCHOOL_META = [{k: v for k, v in s.items() if k != 'levels'} for s in json.load(f)]
SCHOOLS_BY_ID = {s['id']: s for s in SCHOOL_META}
# Contenu chargé depuis la base par reload_content()
PROVENANCES, MAGIC_SCHOOLS, SCHOOL_SPELLS, SPELL_INFO = {}, [], {}, {}
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

# Catégories d'affichage des compétences, remplies par des fichiers texte (une compétence par ligne,
# la 1re ligne du fichier est ignorée). Chaque compétence n'apparaît que dans une catégorie :
# celle de SKILL_CATEGORY_CHOICES si elle y est, sinon celle du 1er fichier qui la cite.
# Dans utilité.txt, la dernière lettre de la ligne donne la catégorie (ex. « Camouflage -u m » → Martial).
# Les compétences absentes des fichiers vont dans « Autres ».
SKILL_CATEGORIES = ["Martial", "Académique", "Économique"]
CATEGORY_FILES = [  # (fichier, catégorie ; None : dernière lettre de chaque ligne)
    ("martial.txt",  "Martial"),
    ("magie.txt",    "Académique"),
    ("utilité.txt",  None),
    ("craft.txt",    "Économique"),
    ("economie.txt", "Économique"),
]
CATEGORY_LETTERS = {"m": "Martial", "a": "Académique", "e": "Économique"}
OTHER_CATEGORY = "Autres"
# Catégorie retenue pour les compétences qui ont plusieurs étiquettes dans les fichiers, ou aucune
SKILL_CATEGORY_CHOICES = {
    "assommement":         "Martial",
    "entretiendarme":      "Économique",
    "ecrituredeparchemin": "Économique",
    "runisme":             "Académique",
    "druidisme":           "Académique",
    "medecine":            "Économique",
    "messe":               "Économique",
    "tatouage":            "Économique",
    "harmonisationalchimique": "Martial",
}
# Anciennes catégories (avant Martial / Académique / Économique)
OLD_CATEGORIES = {"Martial": "Martial", "Magie": "Académique", "Craft": "Économique", "Économie": "Économique"}
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

# Avantages et désavantages (p. 32-44), choisis une seule fois à la création (traits.json).
# Entre DISADVANTAGE_MIN et DISADVANTAGE_MAX points de désavantage ; les avantages coûtent au plus
# autant de points que les désavantages en donnent, les points restants sont perdus.
DISADVANTAGE_MIN = 3
DISADVANTAGE_MAX = 12
RUINED_TRAIT     = "d-ruiner"   # Ruiné : aucun avantage matériel
# La liste est rangée dans la base (table traits, modifiable par l'Animation), chargée par reload_content
TRAIT_KINDS      = ('avantage', 'desavantage')
TRAIT_CATEGORIES = ('Physique', 'Mental', 'Sociale', 'Matériel', 'Surnaturel')
TRAITS, TRAITS_BY_ID = [], {}

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

def owns_character(name):
    """Le personnage <name> appartient-il au compte connecté ?"""
    account = session.get('player')
    if not account:
        return False
    conn = get_db()
    row  = conn.execute('SELECT 1 FROM players WHERE name = ? AND account = ?', (name, account)).fetchone()
    conn.close()
    return row is not None

def require_player(f):
    """Le joueur connecté ne peut agir que sur les personnages de son compte."""
    @wraps(f)
    def decorated(name, *args, **kwargs):
        if not owns_character(name):
            return jsonify({'error': 'Non connecté'}), 401
        return f(name, *args, **kwargs)
    return decorated

def resolve_character(c, name):
    """Pour l'Animation : un nom de compte désigne son personnage actif, sinon <name> est l'identifiant
    d'un personnage. Renvoie l'identifiant du personnage ou None."""
    row = c.execute('SELECT name FROM players WHERE account = ? AND active = 1', (name,)).fetchone()
    if row:
        return row['name']
    row = c.execute('SELECT name FROM players WHERE name = ?', (name,)).fetchone()
    return row['name'] if row else None

def admin_target(f):
    """Route d'Animation /…/<name>/… : <name> (compte ou personnage) est remplacé par l'identifiant du personnage."""
    @wraps(f)
    def decorated(name, *args, **kwargs):
        conn = get_db()
        target = resolve_character(conn.cursor(), name)
        conn.close()
        if not target:
            return jsonify({'error': 'Joueur introuvable'}), 404
        return f(target, *args, **kwargs)
    return decorated

def character_label(row):
    """« Personnage (compte) » pour les messages de l'Animation."""
    return f"{row['character_name'] or row['name']} ({row['account']})"

def new_character_id(c):
    while True:
        cid = 'p' + secrets.token_hex(5)
        if not c.execute('SELECT 1 FROM players WHERE name = ?', (cid,)).fetchone():
            return cid

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
                   "provenance_languages TEXT NOT NULL DEFAULT '[]'", 'religion TEXT',
                   'traits TEXT',    # avantages/désavantages {id: coût}, NULL tant que non choisis
                   # Un compte (table accounts) a plusieurs personnages, un seul actif ; players.name est
                   # l'identifiant du personnage (le nom du compte pour les fiches d'avant les comptes)
                   'account TEXT', 'character_name TEXT', 'active INTEGER NOT NULL DEFAULT 0'):
        try:
            c.execute(f'ALTER TABLE players ADD COLUMN {column}')
        except Exception:
            pass
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        name          TEXT PRIMARY KEY,
        password_hash TEXT
    )''')
    # Fiches d'avant les comptes : chacune devient le personnage actif d'un compte du même nom
    for r in c.execute('SELECT name, password_hash FROM players WHERE account IS NULL').fetchall():
        c.execute('INSERT OR IGNORE INTO accounts (name, password_hash) VALUES (?, ?)', (r['name'], r['password_hash']))
        c.execute('UPDATE players SET account = ?, character_name = ?, active = 1 WHERE name = ?',
                  (r['name'], r['name'], r['name']))
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
    c.execute('''CREATE TABLE IF NOT EXISTS spells (
        id          TEXT PRIMARY KEY,
        school      TEXT    NOT NULL,
        level       INTEGER NOT NULL,
        position    INTEGER NOT NULL DEFAULT 0,
        name        TEXT    NOT NULL,
        type        TEXT    NOT NULL DEFAULT '',
        incantation TEXT    NOT NULL DEFAULT '',
        cible       TEXT    NOT NULL DEFAULT '',
        portee      TEXT    NOT NULL DEFAULT '',
        duree       TEXT    NOT NULL DEFAULT '',
        resistance  TEXT    NOT NULL DEFAULT '',
        description TEXT    NOT NULL DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS provenances (
        name     TEXT PRIMARY KEY,
        position INTEGER NOT NULL DEFAULT 0,
        data     TEXT    NOT NULL   -- JSON : skills, knowledges, language_choice, extra_free_weapons, notes
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS traits (
        id       TEXT PRIMARY KEY,
        position INTEGER NOT NULL DEFAULT 0,
        data     TEXT    NOT NULL   -- JSON : kind, category, name, costs, description, approval, requires, incompatible, stats
    )''')
    # Changements de contenu appliqués une seule fois : ensuite, la base (modifiable par l'Animation) fait foi
    c.execute('CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY)')
    done = {r['name'] for r in c.execute('SELECT name FROM migrations').fetchall()}
    for name, migrate in CONTENT_MIGRATIONS:
        if name not in done:
            migrate(c)
            c.execute('INSERT INTO migrations VALUES (?)', (name,))
    # L'ancienne « Tactiques militaires (1 pays) » est retirée si personne ne la possède
    c.execute('''DELETE FROM knowledges WHERE id = 'k_tactiques'
                 AND NOT EXISTS (SELECT 1 FROM player_knowledges WHERE knowledge_id = 'k_tactiques')''')
    conn.commit()
    reload_content(c)
    conn.close()

def seed_skills(c):
    """Arbre de compétences de référence (skills.json), pour une base neuve."""
    with open(os.path.join(BASE_DIR, 'skills.json'), encoding='utf-8') as f:
        base_skills = [(s['id'], s['branch'], s['name'], s['cost'], s['knowledge_cost'], s['desc'], s['prereq'],
                        s['sort_order']) for s in json.load(f)]
    c.executemany('''INSERT OR IGNORE INTO skills (id, branch, name, cost, knowledge_cost, desc, prereq, sort_order)
                     VALUES (?,?,?,?,?,?,?,?)''', base_skills + EXTRA_SKILLS)

def migrate_rules_2025(c):
    """Corrections de l'arbre selon le Livre des règles (armes, magie, religion…)."""
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

def migrate_categories(c):
    """La catégorie de chaque compétence (fichiers martial.txt, magie.txt…) est enregistrée dans la base."""
    placement, _ = load_skill_categories()
    for r in c.execute('SELECT id, name, branch FROM skills').fetchall():
        branch = placement.get(skill_key(r['name'])) or \
                 (r['branch'] if r['branch'] in SKILL_CATEGORIES else OTHER_CATEGORY)
        c.execute('UPDATE skills SET branch = ? WHERE id = ?', (branch, r['id']))

def migrate_three_categories(c):
    """Martial / Académique / Économique : les anciennes catégories sont renommées (en gardant les choix de
    l'Animation), les compétences d'Utilité et celles nommées dans SKILL_CATEGORY_CHOICES sont replacées."""
    placement, lettered = load_skill_categories()
    for r in c.execute('SELECT id, name, branch FROM skills').fetchall():
        key = skill_key(r['name'])
        if r['branch'] == 'Utilité' or key in lettered or key in SKILL_CATEGORY_CHOICES:
            branch = placement.get(key, OTHER_CATEGORY)
        else:
            branch = OLD_CATEGORIES.get(r['branch'], r['branch'] if r['branch'] in SKILL_CATEGORIES else OTHER_CATEGORY)
        c.execute('UPDATE skills SET branch = ? WHERE id = ?', (branch, r['id']))

def migrate_other_category(c):
    """Les compétences restées dans « Autres » (Médecine, Messe, Tatouage, Harmonisation alchimique) sont placées."""
    for r in c.execute('SELECT id, name FROM skills WHERE branch = ?', (OTHER_CATEGORY,)).fetchall():
        branch = SKILL_CATEGORY_CHOICES.get(skill_key(r['name']))
        if branch:
            c.execute('UPDATE skills SET branch = ? WHERE id = ?', (branch, r['id']))

def seed_spells(c):
    """Sorts du Règlement de magie (spells.json)."""
    with open(os.path.join(BASE_DIR, 'spells.json'), encoding='utf-8') as f:
        schools = json.load(f)
    c.executemany('''INSERT OR IGNORE INTO spells (id, school, level, position, name, type, incantation, cible,
                                                   portee, duree, resistance, description)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                  [(sp['id'], s['id'], int(lv), i, sp['name'], sp['type'], sp['incantation'], sp['cible'],
                    sp['portee'], sp['duree'], sp['resistance'], sp['description'])
                   for s in schools for lv, spells in s['levels'].items() for i, sp in enumerate(spells)])

def seed_provenances(c):
    c.executemany('INSERT OR IGNORE INTO provenances (name, position, data) VALUES (?, ?, ?)',
                  [(name, i, json.dumps(rules)) for i, (name, rules) in enumerate(PROVENANCES_SEED.items())])

def seed_traits(c):
    """Avantages et désavantages du Livre des règles (traits.json)."""
    with open(os.path.join(BASE_DIR, 'traits.json'), encoding='utf-8') as f:
        traits = json.load(f)
    c.executemany('INSERT OR IGNORE INTO traits (id, position, data) VALUES (?, ?, ?)',
                  [(t['id'], i, json.dumps({k: v for k, v in t.items() if k != 'id'})) for i, t in enumerate(traits)])

CONTENT_MIGRATIONS = [  # (nom, fonction), dans l'ordre ; chacune n'est appliquée qu'une fois par base
    ('competences-de-base', seed_skills),
    ('regles-2025',         migrate_rules_2025),
    ('categories',          migrate_categories),
    ('sorts',               seed_spells),
    ('provenances',         seed_provenances),
    ('avantages',           seed_traits),
    ('trois-categories',    migrate_three_categories),
    ('categorie-autres',    migrate_other_category),
]

def reload_content(c):
    """Recharge en mémoire sorts, provenances et avantages (au démarrage et après une modification par l'Animation)."""
    global PROVENANCES, MAGIC_SCHOOLS, SCHOOL_SPELLS, SPELL_INFO, TRAITS, TRAITS_BY_ID
    TRAITS = [{'id': r['id'], **json.loads(r['data'])}
              for r in c.execute('SELECT id, data FROM traits ORDER BY position, id').fetchall()]
    TRAITS_BY_ID = {t['id']: t for t in TRAITS}
    PROVENANCES = {r['name']: json.loads(r['data'])
                   for r in c.execute('SELECT name, data FROM provenances ORDER BY position, name').fetchall()}
    fields = ('id', 'name', 'type', 'incantation', 'cible', 'portee', 'duree', 'resistance', 'description')
    levels = {}
    for r in c.execute('SELECT * FROM spells ORDER BY school, level, position, name').fetchall():
        levels.setdefault(r['school'], {}).setdefault(str(r['level']), []).append({f: r[f] for f in fields})
    MAGIC_SCHOOLS = [{**s, 'levels': levels.get(s['id'], {})} for s in SCHOOL_META]
    SCHOOL_SPELLS = {(s['id'], int(lv)): [sp['id'] for sp in spells]
                     for s in MAGIC_SCHOOLS for lv, spells in s['levels'].items()}
    SPELL_INFO    = {sp: (school, level) for (school, level), spells in SCHOOL_SPELLS.items() for sp in spells}

# --- Servir le frontend ---
@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

# Documents de règles affichés dans les onglets du joueur (seuls ces fichiers sont servis)
RULE_DOCUMENTS = {
    'regles': 'Livre des règles 2025 v2.1 Copy.pdf',
    'magie':  'Règlement magie 2025.pdf',
}

# Documents remplacés par l'Animation (prioritaires sur ceux du dépôt git)
UPLOADED_DOCS_DIR = os.path.join(BASE_DIR, 'data', 'docs')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024   # taille maximale d'un document envoyé

@app.route('/docs/<doc>')
def serve_document(doc):
    if doc not in RULE_DOCUMENTS:
        return jsonify({'error': 'Document introuvable'}), 404
    if os.path.exists(os.path.join(UPLOADED_DOCS_DIR, f'{doc}.pdf')):
        return send_from_directory(UPLOADED_DOCS_DIR, f'{doc}.pdf', mimetype='application/pdf', max_age=0)
    return send_from_directory(BASE_DIR, RULE_DOCUMENTS[doc], mimetype='application/pdf', max_age=0)

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
    if c.execute('SELECT 1 FROM accounts WHERE name = ?', (name,)).fetchone():
        conn.close(); return jsonify({'error': 'Ce nom est déjà utilisé'}), 400
    c.execute('INSERT INTO accounts (name, password_hash) VALUES (?, ?)', (name, generate_password_hash(password)))
    create_character(c, name, 'Personnage 1')
    conn.commit()
    conn.close()
    session['player'] = name
    return jsonify({'name': name})

@app.route('/api/login', methods=['POST'])
def login():
    name, password = read_credentials()
    conn = get_db()
    c = conn.cursor()
    player = c.execute('SELECT password_hash FROM accounts WHERE name = ?', (name,)).fetchone()
    if not player:
        conn.close(); return jsonify({'error': 'Nom ou mot de passe incorrect'}), 401
    if player['password_hash'] is None:
        # Joueur créé avant les mots de passe : le premier mot de passe saisi devient le sien
        if (err := password_too_short(password)):
            conn.close(); return err
        c.execute('UPDATE accounts SET password_hash = ? WHERE name = ?', (generate_password_hash(password), name))
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
    """Compte connecté et liste de ses personnages."""
    account = session.get('player')
    if not account:
        return jsonify({'error': 'Non connecté'}), 401
    conn = get_db()
    characters = account_characters(conn.cursor(), account)
    conn.close()
    return jsonify({'account': account, 'characters': characters})

# --- Personnages du compte ---
def account_characters(c, account):
    return [{'id': r['name'], 'name': r['character_name'], 'race': r['race'], 'provenance': r['provenance'],
             'active': bool(r['active'])}
            for r in c.execute('SELECT name, character_name, race, provenance, active FROM players WHERE account = ? '
                               'ORDER BY rowid', (account,)).fetchall()]

def create_character(c, account, character_name):
    """Nouvelle fiche (9 XP, 3 Connaissance) ; elle est active si c'est la première du compte."""
    has_active = c.execute('SELECT 1 FROM players WHERE account = ? AND active = 1', (account,)).fetchone()
    cid = new_character_id(c)
    c.execute('INSERT INTO players (name, points, knowledge_points, account, character_name, active) '
              'VALUES (?, 9, 3, ?, ?, ?)', (cid, account, character_name, 0 if has_active else 1))
    return cid

def read_character_name():
    name = ((request.json or {}).get('name') or '').strip()
    return name[:60]

@app.route('/api/characters', methods=['POST'])
def add_character():
    account = session.get('player')
    if not account:
        return jsonify({'error': 'Non connecté'}), 401
    name = read_character_name()
    if not name:
        return jsonify({'error': 'Donnez un nom au personnage'}), 400
    conn = get_db()
    c    = conn.cursor()
    cid  = create_character(c, account, name)
    conn.commit()
    characters = account_characters(c, account)
    conn.close()
    return jsonify({'id': cid, 'characters': characters})

@app.route('/api/characters/<name>/activate', methods=['POST'])
@require_player
def activate_character(name):
    """Un seul personnage actif par compte : c'est lui qui reçoit les points distribués par l'Animation."""
    account = session['player']
    conn = get_db()
    c    = conn.cursor()
    c.execute('UPDATE players SET active = (name = ?) WHERE account = ?', (name, account))
    conn.commit()
    characters = account_characters(c, account)
    conn.close()
    return jsonify({'characters': characters})

@app.route('/api/characters/<name>/rename', methods=['POST'])
@require_player
def rename_character(name):
    new_name = read_character_name()
    if not new_name:
        return jsonify({'error': 'Donnez un nom au personnage'}), 400
    conn = get_db()
    c    = conn.cursor()
    c.execute('UPDATE players SET character_name = ? WHERE name = ?', (new_name, name))
    conn.commit()
    characters = account_characters(c, session['player'])
    conn.close()
    return jsonify({'characters': characters})

# --- Joueur ---
@app.route('/api/player/<name>', methods=['GET'])
def get_player(name):
    if is_admin():
        conn = get_db()
        target = resolve_character(conn.cursor(), name)
        conn.close()
        if not target:
            return jsonify({'error': 'Joueur introuvable'}), 404
        return get_player_data(target)
    if not owns_character(name):
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
    return jsonify({'name': name, 'account': player['account'], 'characterName': player['character_name'],
                    'active': bool(player['active']), 'points': player['points'],
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
    traits = json.loads(player['traits']) if player['traits'] is not None else None
    bonuses = [SKILL_STAT_BONUSES.get(s, {}) for s in skills] + \
              [TRAITS_BY_ID[t].get('stats', {}) for t in (traits or {}) if t in TRAITS_BY_ID]
    for bonus in bonuses:
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
            'religion': player['religion'], 'traits': traits,
            'talent': talent, 'armor': armor, 'armorImmunities': immunities,
            'pv': pv, 'pe': pe, 'armorPoints': armor_points}

def traits_error(traits):
    """Vérifie un choix d'avantages/désavantages {id: coût} ; renvoie un message d'erreur ou None."""
    if not isinstance(traits, dict):
        return 'Avantages et désavantages invalides'
    for tid, cost in traits.items():
        trait = TRAITS_BY_ID.get(tid)
        if not trait:
            return 'Avantage ou désavantage inconnu'
        if cost not in trait['costs']:
            return f'Coût invalide pour {trait["name"]}'
        if trait.get('requires') and not any(r in traits for r in trait['requires']):
            names = ' ou '.join(TRAITS_BY_ID[r]['name'] for r in trait['requires'] if r in TRAITS_BY_ID)
            return f'{trait["name"]} se prend avec {names}'
        for other in trait.get('incompatible', []):
            if other in traits:
                return f'{trait["name"]} est incompatible avec {TRAITS_BY_ID[other]["name"]}'
        if RUINED_TRAIT in traits and trait['kind'] == 'avantage' and trait['category'] == 'Matériel':
            return f'Un personnage ruiné ne peut pas prendre d\'avantage matériel ({trait["name"]})'
    malus = sum(c for t, c in traits.items() if TRAITS_BY_ID[t]['kind'] == 'desavantage')
    bonus = sum(c for t, c in traits.items() if TRAITS_BY_ID[t]['kind'] == 'avantage')
    if not DISADVANTAGE_MIN <= malus <= DISADVANTAGE_MAX:
        return f'Il faut entre {DISADVANTAGE_MIN} et {DISADVANTAGE_MAX} points de désavantage (vous en avez {malus})'
    if bonus > malus:
        return f'Vos avantages coûtent {bonus} points, mais vos désavantages n\'en donnent que {malus}'
    return None

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
    if 'traits' in allowed and 'traits' in data:
        # None remet à zéro : le joueur pourra choisir de nouveau
        if data['traits'] is not None and (err := traits_error(data['traits'])):
            return err
        updates['traits'] = None if data['traits'] is None else json.dumps(data['traits'])
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
        'traits':      TRAITS,
        'disadvantageMin': DISADVANTAGE_MIN, 'disadvantageMax': DISADVANTAGE_MAX, 'ruinedTrait': RUINED_TRAIT,
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

@app.route('/api/player/<name>/traits', methods=['POST'])
@require_player
def set_traits(name):
    """Avantages et désavantages : choisis une seule fois par le joueur, ensuite seule l'Animation peut les changer."""
    conn = get_db()
    c    = conn.cursor()
    if c.execute('SELECT traits FROM players WHERE name=?', (name,)).fetchone()['traits'] is not None:
        conn.close(); return jsonify({'error': 'Avantages et désavantages déjà choisis, demandez à l\'Animation'}), 400
    traits = (request.json or {}).get('traits')
    if traits is None:
        conn.close(); return jsonify({'error': 'Choisissez vos avantages et désavantages'}), 400
    if (err := update_character(c, name, {'traits': traits}, {'traits'})):
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
@admin_target
def admin_set_character(name):
    conn = get_db()
    c    = conn.cursor()
    if not c.execute('SELECT 1 FROM players WHERE name=?', (name,)).fetchone():
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    if (err := update_character(c, name, request.json or {}, {'race', 'provenance', 'humanBonus', 'armor', 'religion', 'traits'})):
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
    """({clé de compétence: catégorie}, clés placées par lettre) d'après les fichiers de catégories."""
    placement = dict(SKILL_CATEGORY_CHOICES)
    lettered  = set()
    for filename, category in CATEGORY_FILES:
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8-sig') as f:
            lines = [l.strip() for l in f.read().splitlines()[1:] if l.strip()]
        for line in lines:
            key = skill_key(re.split(r'\s+-', line)[0])
            if category is None:
                letter = CATEGORY_LETTERS.get(line.split()[-1].lstrip('-').lower())
                if not letter:
                    continue
                lettered.add(key)
                placement.setdefault(key, letter)
            else:
                placement.setdefault(key, category)
    return placement, lettered

def sort_name(name):
    """Ordre alphabétique sans accents, niveaux d'une même compétence regroupés."""
    base = unicodedata.normalize('NFD', re.sub(r'\s+[IVX]+$', '', name).lower())
    return ''.join(ch for ch in base if not unicodedata.combining(ch))

def skill_category_names():
    return SKILL_CATEGORIES + [OTHER_CATEGORY]

@app.route('/api/skills', methods=['GET'])
def get_skills():
    conn = get_db()
    rows = conn.execute('SELECT * FROM skills ORDER BY sort_order').fetchall()
    conn.close()
    order    = skill_category_names()
    branches = {name: [] for name in order}
    for r in rows:
        # La catégorie est enregistrée dans la base (migrate_categories, puis modifiable par l'Animation)
        branches[r['branch'] if r['branch'] in branches else OTHER_CATEGORY].append(r)
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

def read_skill_fields(c, data, skill_id=None):
    """Champs d'une compétence envoyés par l'Animation ; renvoie (champs, erreur)."""
    try:
        cost           = int(data.get('cost', 0) or 0)
        knowledge_cost = int(data.get('knowledge_cost', 0) or 0)
    except (TypeError, ValueError):
        return None, 'Coût invalide'
    fields = {'branch': data.get('branch') or OTHER_CATEGORY, 'name': (data.get('name') or '').strip(),
              'desc': (data.get('desc') or '').strip(), 'prereq': data.get('prereq') or None,
              'cost': cost, 'knowledge_cost': knowledge_cost}
    if not fields['name'] or not fields['desc']:
        return None, 'Le nom et la description sont obligatoires'
    if cost < 0 or knowledge_cost < 0:
        return None, 'Un coût ne peut pas être négatif'
    if fields['branch'] not in skill_category_names():
        return None, 'Catégorie inconnue'
    # Le prérequis doit exister et ne pas créer de boucle (A demande B qui demande A)
    prereq = fields['prereq']
    while prereq:
        if prereq == skill_id:
            return None, 'Ce prérequis créerait une boucle'
        row = c.execute('SELECT prereq FROM skills WHERE id = ?', (prereq,)).fetchone()
        if not row:
            return None, 'Prérequis introuvable'
        prereq = row['prereq']
    return fields, None

@app.route('/api/skills', methods=['POST'])
@require_admin
def add_skill():
    conn = get_db()
    c    = conn.cursor()
    fields, err = read_skill_fields(c, request.json or {})
    if err:
        conn.close(); return jsonify({'error': err}), 400
    if fields['cost'] == 0 and fields['knowledge_cost'] == 0:
        conn.close(); return jsonify({'error': 'Au moins un coût (XP ou Connaissance) doit être supérieur à 0'}), 400
    branch, name, cost, knowledge_cost, desc, prereq = (fields[k] for k in
                                                        ('branch', 'name', 'cost', 'knowledge_cost', 'desc', 'prereq'))
    max_order = c.execute('SELECT MAX(sort_order) FROM skills WHERE branch=?', (branch,)).fetchone()[0] or 0
    new_id    = branch[0].lower() + str(int(time.time()))
    c.execute('INSERT INTO skills (id, branch, name, cost, knowledge_cost, desc, prereq, sort_order) VALUES (?,?,?,?,?,?,?,?)',
              (new_id, branch, name, cost, knowledge_cost, desc, prereq, max_order + 1))
    conn.commit()
    conn.close()
    return jsonify({'id': new_id, 'branch': branch, 'name': name, 'cost': cost,
                    'knowledge_cost': knowledge_cost, 'desc': desc, 'prereq': prereq})

# --- Animation : modifier le contenu du jeu ---
# Compétences au fonctionnement particulier (achat par arme, par école, par sort) : modifiables, pas supprimables
SPECIAL_SKILLS = {WEAPON_SKILL, SPEC_SKILL, EXTRA_SPELL_SKILL, *MAGIC_SKILLS}

@app.route('/api/admin/skills/<skill_id>', methods=['POST'])
@require_admin
def admin_update_skill(skill_id):
    conn = get_db()
    c    = conn.cursor()
    if not c.execute('SELECT 1 FROM skills WHERE id = ?', (skill_id,)).fetchone():
        conn.close(); return jsonify({'error': 'Compétence introuvable'}), 404
    fields, err = read_skill_fields(c, request.json or {}, skill_id)
    if err:
        conn.close(); return jsonify({'error': err}), 400
    c.execute('''UPDATE skills SET branch = ?, name = ?, desc = ?, prereq = ?, cost = ?, knowledge_cost = ?
                 WHERE id = ?''', (*fields.values(), skill_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/skills/<skill_id>/delete', methods=['POST'])
@require_admin
def admin_delete_skill(skill_id):
    """Supprime une compétence ; les joueurs qui l'avaient achetée sont remboursés."""
    conn = get_db()
    c    = conn.cursor()
    skill = c.execute('SELECT * FROM skills WHERE id = ?', (skill_id,)).fetchone()
    if not skill:
        conn.close(); return jsonify({'error': 'Compétence introuvable'}), 404
    if skill_id in SPECIAL_SKILLS:
        conn.close(); return jsonify({'error': f'{skill["name"]} a un fonctionnement particulier : '
                                               'elle peut être modifiée mais pas supprimée'}), 400
    dependents = [r['name'] for r in c.execute('SELECT name FROM skills WHERE prereq = ?', (skill_id,)).fetchall()]
    if dependents:
        conn.close(); return jsonify({'error': 'Ces compétences l\'ont en prérequis, changez-les d\'abord : '
                                               + ', '.join(dependents)}), 400
    owners = [r['player_name'] for r in c.execute(
        'SELECT player_name FROM player_skills WHERE skill_id = ?', (skill_id,)).fetchall()]
    c.executemany('UPDATE players SET points = points + ?, knowledge_points = knowledge_points + ? WHERE name = ?',
                  [(skill['cost'], skill['knowledge_cost'], p) for p in owners])
    c.execute('DELETE FROM player_skills WHERE skill_id = ?', (skill_id,))
    c.execute('DELETE FROM skills WHERE id = ?', (skill_id,))
    # Elle n'est plus donnée par les provenances
    for prov, rules in PROVENANCES.items():
        if skill_id in rules.get('skills', []):
            rules = {**rules, 'skills': [s for s in rules['skills'] if s != skill_id]}
            c.execute('UPDATE provenances SET data = ? WHERE name = ?', (json.dumps(rules), prov))
    conn.commit()
    reload_content(c)
    labels = {r['name']: character_label(r) for r in c.execute('SELECT * FROM players').fetchall()}
    conn.close()
    return jsonify({'ok': True, 'refunded': [labels.get(o, o) for o in owners]})

SPELL_TEXT_FIELDS = ('name', 'type', 'incantation', 'cible', 'portee', 'duree', 'resistance', 'description')

@app.route('/api/admin/spells/<spell_id>', methods=['POST'])
@require_admin
def admin_update_spell(spell_id):
    data   = request.json or {}
    fields = {f: (data.get(f) or '').strip() for f in SPELL_TEXT_FIELDS}
    if not fields['name'] or not fields['description']:
        return jsonify({'error': 'Le nom et la description sont obligatoires'}), 400
    conn = get_db()
    c    = conn.cursor()
    c.execute(f'UPDATE spells SET {", ".join(f + " = ?" for f in fields)} WHERE id = ?', (*fields.values(), spell_id))
    if c.rowcount == 0:
        conn.close(); return jsonify({'error': 'Sort introuvable'}), 404
    conn.commit()
    reload_content(c)
    conn.close()
    return jsonify(MAGIC_SCHOOLS)

@app.route('/api/admin/spells/<spell_id>/delete', methods=['POST'])
@require_admin
def admin_delete_spell(spell_id):
    """Supprime un sort ; ceux achetés en sort supplémentaire sont remboursés (leur niveau en XP)."""
    conn = get_db()
    c    = conn.cursor()
    if not c.execute('SELECT 1 FROM spells WHERE id = ?', (spell_id,)).fetchone():
        conn.close(); return jsonify({'error': 'Sort introuvable'}), 404
    c.execute('''UPDATE players SET points = points + (SELECT level FROM player_spells
                                                       WHERE player_name = players.name AND spell = ?)
                 WHERE name IN (SELECT player_name FROM player_spells WHERE spell = ? AND extra = 1)''',
              (spell_id, spell_id))
    c.execute('DELETE FROM player_spells WHERE spell = ?', (spell_id,))
    c.execute('DELETE FROM spells WHERE id = ?', (spell_id,))
    conn.commit()
    reload_content(c)
    conn.close()
    return jsonify(MAGIC_SCHOOLS)

@app.route('/api/admin/provenances', methods=['POST'])
@require_admin
def admin_save_provenance():
    """Crée ou modifie une provenance ; un changement de nom suit chez les joueurs qui en proviennent."""
    data     = request.json or {}
    original = data.get('originalName')
    name     = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Le nom est obligatoire'}), 400
    if (name != original and name in PROVENANCES) or (original and original not in PROVENANCES):
        return jsonify({'error': 'Une provenance porte déjà ce nom' if name in PROVENANCES else 'Provenance introuvable'}), 400
    conn = get_db()
    c    = conn.cursor()
    skill_ids     = {r['id'] for r in c.execute('SELECT id FROM skills').fetchall()}
    knowledge_ids = {k[0] for k in KNOWLEDGES}
    skills, knowledges = data.get('skills') or [], data.get('knowledges') or []
    if any(s not in skill_ids for s in skills) or any(k not in knowledge_ids for k in knowledges):
        conn.close(); return jsonify({'error': 'Compétence ou connaissance inconnue'}), 400
    rules = {'skills': skills, 'knowledges': knowledges}
    try:
        if int(data.get('extraFreeWeapons') or 0) > 0:
            rules['extra_free_weapons'] = int(data['extraFreeWeapons'])
        choice = data.get('languageChoice')
        if choice and choice.get('options'):
            if any(k not in knowledge_ids for k in choice['options']) or not 0 < int(choice['count']) <= len(choice['options']):
                conn.close(); return jsonify({'error': 'Choix de langues invalide'}), 400
            rules['language_choice'] = [int(choice['count']), choice['options']]
    except (TypeError, ValueError, KeyError):
        conn.close(); return jsonify({'error': 'Valeur invalide'}), 400
    notes = [n.strip() for n in data.get('notes') or [] if n.strip()]
    if notes:
        rules['notes'] = notes
    if original:
        c.execute('UPDATE provenances SET name = ?, data = ? WHERE name = ?', (name, json.dumps(rules), original))
        c.execute('UPDATE players SET provenance = ? WHERE provenance = ?', (name, original))
    else:
        position = c.execute('SELECT COALESCE(MAX(position), 0) + 1 FROM provenances').fetchone()[0]
        c.execute('INSERT INTO provenances (name, position, data) VALUES (?, ?, ?)', (name, position, json.dumps(rules)))
    conn.commit()
    reload_content(c)
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/provenances/delete', methods=['POST'])
@require_admin
def admin_delete_provenance():
    name = (request.json or {}).get('name')
    conn = get_db()
    c    = conn.cursor()
    users = [character_label(r) for r in c.execute('SELECT * FROM players WHERE provenance = ?', (name,)).fetchall()]
    if users:
        conn.close(); return jsonify({'error': 'Des joueurs proviennent de cette provenance : ' + ', '.join(users)}), 400
    c.execute('DELETE FROM provenances WHERE name = ?', (name,))
    if c.rowcount == 0:
        conn.close(); return jsonify({'error': 'Provenance introuvable'}), 404
    conn.commit()
    reload_content(c)
    conn.close()
    return jsonify({'ok': True})

def read_trait_fields(data, trait_id=None):
    """Champs d'un avantage/désavantage envoyés par l'Animation ; renvoie (champs, erreur)."""
    name        = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    if not name or not description:
        return None, 'Le nom et la description sont obligatoires'
    if data.get('kind') not in TRAIT_KINDS:
        return None, 'Type invalide (avantage ou désavantage)'
    if data.get('category') not in TRAIT_CATEGORIES:
        return None, 'Catégorie inconnue'
    try:
        costs = sorted({int(c) for c in data.get('costs') or []})
        stats = {k: int(v) for k, v in (data.get('stats') or {}).items() if k in ('pv', 'pe') and int(v)}
    except (TypeError, ValueError):
        return None, 'Coût ou bonus invalide'
    if not costs or costs[0] <= 0:
        return None, 'Indiquez au moins un coût, chacun supérieur à 0'
    fields = {'kind': data['kind'], 'category': data['category'], 'name': name, 'costs': costs,
              'description': description}
    for key in ('requires', 'incompatible'):
        ids = list(dict.fromkeys(data.get(key) or []))
        if any(t not in TRAITS_BY_ID or t == trait_id for t in ids):
            return None, 'Avantage ou désavantage lié inconnu'
        if ids:
            fields[key] = ids
    if stats:
        fields['stats'] = stats
    if data.get('approval'):
        fields['approval'] = True
    return fields, None

@app.route('/api/admin/traits', methods=['POST'])
@require_admin
def admin_create_trait():
    fields, err = read_trait_fields(request.json or {})
    if err:
        return jsonify({'error': err}), 400
    base   = ('a-' if fields['kind'] == 'avantage' else 'd-') + (skill_key(fields['name']) or 'x')
    new_id = base
    while new_id in TRAITS_BY_ID:
        new_id = f'{base}-{int(time.time() * 1000) % 100000}'
    conn = get_db()
    c    = conn.cursor()
    position = c.execute('SELECT COALESCE(MAX(position), 0) + 1 FROM traits').fetchone()[0]
    c.execute('INSERT INTO traits (id, position, data) VALUES (?, ?, ?)', (new_id, position, json.dumps(fields)))
    conn.commit()
    reload_content(c)
    conn.close()
    return jsonify({'id': new_id})

@app.route('/api/admin/traits/<trait_id>', methods=['POST'])
@require_admin
def admin_update_trait(trait_id):
    """Modifie un avantage/désavantage ; les choix déjà faits par les joueurs sont conservés tels quels."""
    if trait_id not in TRAITS_BY_ID:
        return jsonify({'error': 'Avantage ou désavantage introuvable'}), 404
    fields, err = read_trait_fields(request.json or {}, trait_id)
    if err:
        return jsonify({'error': err}), 400
    conn = get_db()
    c    = conn.cursor()
    c.execute('UPDATE traits SET data = ? WHERE id = ?', (json.dumps(fields), trait_id))
    conn.commit()
    reload_content(c)
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/traits/<trait_id>/delete', methods=['POST'])
@require_admin
def admin_delete_trait(trait_id):
    """Supprime un avantage/désavantage qu'aucun joueur n'a choisi ; il est retiré des liens des autres."""
    if trait_id not in TRAITS_BY_ID:
        return jsonify({'error': 'Avantage ou désavantage introuvable'}), 404
    if trait_id == RUINED_TRAIT:
        return jsonify({'error': f'{TRAITS_BY_ID[trait_id]["name"]} a un fonctionnement particulier : '
                                 'il peut être modifié mais pas supprimé'}), 400
    conn = get_db()
    c    = conn.cursor()
    users = [character_label(r) for r in c.execute('SELECT * FROM players WHERE traits IS NOT NULL').fetchall()
             if trait_id in json.loads(r['traits'])]
    if users:
        conn.close(); return jsonify({'error': 'Ces joueurs l\'ont choisi, retirez-le d\'abord de leur fiche : '
                                               + ', '.join(users)}), 400
    for t in TRAITS:
        if trait_id in t.get('requires', []) + t.get('incompatible', []):
            data = {k: v for k, v in t.items() if k != 'id'}
            for key in ('requires', 'incompatible'):
                if key in data:
                    data[key] = [x for x in data[key] if x != trait_id]
                    if not data[key]:
                        del data[key]
            c.execute('UPDATE traits SET data = ? WHERE id = ?', (json.dumps(data), t['id']))
    c.execute('DELETE FROM traits WHERE id = ?', (trait_id,))
    conn.commit()
    reload_content(c)
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/docs/<doc>', methods=['POST'])
@require_admin
def admin_replace_document(doc):
    """Remplace un document de règles. Il est rangé dans data/docs (hors git) et remplace celui du dépôt."""
    if doc not in RULE_DOCUMENTS:
        return jsonify({'error': 'Document introuvable'}), 404
    upload = request.files.get('file')
    if not upload or upload.stream.read(5) != b'%PDF-':
        return jsonify({'error': 'Envoyez un fichier PDF'}), 400
    upload.stream.seek(0)
    os.makedirs(UPLOADED_DOCS_DIR, exist_ok=True)
    upload.save(os.path.join(UPLOADED_DOCS_DIR, f'{doc}.pdf'))
    return jsonify({'ok': True})

@app.route('/api/admin/player/<name>/remove-knowledge', methods=['POST'])
@require_admin
@admin_target
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
    """Un élément par compte : les points et compétences sont ceux du personnage actif."""
    conn   = get_db()
    c      = conn.cursor()
    result = []
    for a in c.execute('SELECT name FROM accounts ORDER BY name COLLATE NOCASE').fetchall():
        characters = account_characters(c, a['name'])
        active = c.execute('SELECT * FROM players WHERE account = ? AND active = 1', (a['name'],)).fetchone()
        skill_count = c.execute('SELECT COUNT(*) FROM player_skills WHERE player_name=?',
                                (active['name'],)).fetchone()[0] if active else 0
        result.append({'name': a['name'], 'character': active['character_name'] if active else None,
                       'points': active['points'] if active else 0,
                       'knowledgePoints': active['knowledge_points'] if active else 0,
                       'skillCount': skill_count, 'characters': characters})
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
    target = resolve_character(c, target)
    if not target:
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
    target = resolve_character(c, target)
    if not target:
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    c.execute('UPDATE players SET knowledge_points = knowledge_points + ? WHERE name=?', (int(amount), target))
    conn.commit()
    new_kp = c.execute('SELECT knowledge_points FROM players WHERE name=?', (target,)).fetchone()['knowledge_points']
    conn.close()
    return jsonify({'knowledgePoints': new_kp})

@app.route('/api/admin/distribute-knowledge', methods=['POST'])
@require_admin
def distribute_knowledge():
    """Donne des points de connaissance au personnage actif de chaque compte, SAUF les comptes de exclude."""
    amount  = int(request.json.get('amount', 1))
    exclude = set(request.json.get('exclude', []))
    conn = get_db()
    c    = conn.cursor()
    actives = c.execute('SELECT name, account FROM players WHERE active = 1').fetchall()
    updated = []
    for r in actives:
        if r['account'] not in exclude:
            c.execute('UPDATE players SET knowledge_points = knowledge_points + ? WHERE name=?', (amount, r['name']))
            updated.append(r['account'])
    conn.commit()
    conn.close()
    return jsonify({'updated': updated, 'skipped': list(exclude), 'count': len(updated)})

@app.route('/api/admin/distribute-xp', methods=['POST'])
@require_admin
def distribute_xp():
    """Donne des XP au personnage actif de chaque compte, SAUF les comptes de exclude."""
    amount  = int(request.json.get('amount', 2))
    exclude = set(request.json.get('exclude', []))
    conn = get_db()
    c    = conn.cursor()
    actives = c.execute('SELECT name, account FROM players WHERE active = 1').fetchall()
    updated = []
    for r in actives:
        if r['account'] not in exclude:
            c.execute('UPDATE players SET points = points + ? WHERE name=?', (amount, r['name']))
            updated.append(r['account'])
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
    if not c.execute('SELECT 1 FROM accounts WHERE name=?', (name,)).fetchone():
        conn.close(); return jsonify({'error': 'Joueur introuvable'}), 404
    c.execute('UPDATE accounts SET password_hash = ? WHERE name=?', (generate_password_hash(password), name))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/admin/reset/<name>', methods=['POST'])
@require_admin
@admin_target
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
