from flask import Flask, request, jsonify, send_from_directory
from functools import wraps
import sqlite3
import os
import time

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'game.db')

# ─── MOT DE PASSE DE L'ANIMATION (changez-le ici) ───────────────────────────
ADMIN_PASSWORD = "animation2025"
# ─────────────────────────────────────────────────────────────────────────────

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
    ("k_tactiques",             "Militaire",  "Tactiques militaires (1 pays)",        "1 pays au choix avec l'animation."),
]
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
    c.execute('''CREATE TABLE IF NOT EXISTS player_skills (
        player_name TEXT,
        skill_id    TEXT,
        PRIMARY KEY (player_name, skill_id)
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
        PRIMARY KEY (player_name, knowledge_id)
    )''')
    if not c.execute('SELECT 1 FROM knowledges LIMIT 1').fetchone():
        c.executemany('INSERT INTO knowledges VALUES (?,?,?,?)', KNOWLEDGES)
    conn.commit()
    conn.close()

# --- Servir le frontend ---
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# --- Auth admin ---
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    password = request.json.get('password', '')
    if password == ADMIN_PASSWORD:
        return jsonify({'ok': True})
    return jsonify({'error': 'Mot de passe incorrect'}), 401

# --- Joueur ---
@app.route('/api/player/<name>', methods=['GET'])
def get_player(name):
    conn = get_db()
    c = conn.cursor()
    player = c.execute('SELECT * FROM players WHERE name = ?', (name,)).fetchone()
    if not player:
        c.execute('INSERT INTO players (name, points, knowledge_points) VALUES (?, 9, 3)', (name,))
        conn.commit()
        player = c.execute('SELECT * FROM players WHERE name = ?', (name,)).fetchone()
    skills = [r['skill_id'] for r in c.execute(
        'SELECT skill_id FROM player_skills WHERE player_name = ?', (name,)
    ).fetchall()]
    knowledges = [r['knowledge_id'] for r in c.execute(
        'SELECT knowledge_id FROM player_knowledges WHERE player_name = ?', (name,)
    ).fetchall()]
    conn.close()
    return jsonify({'name': name, 'points': player['points'],
                    'knowledgePoints': player['knowledge_points'],
                    'acquiredSkills': skills, 'acquiredKnowledges': knowledges})

@app.route('/api/player/<name>/purchase', methods=['POST'])
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
    if c.execute('SELECT 1 FROM player_skills WHERE player_name=? AND skill_id=?', (name, skill_id)).fetchone():
        conn.close(); return jsonify({'error': 'Déjà acquise'}), 400
    if skill['cost'] > 0 and player['points'] < skill['cost']:
        conn.close(); return jsonify({'error': 'Points XP insuffisants'}), 400
    if skill['knowledge_cost'] > 0 and player['knowledge_points'] < skill['knowledge_cost']:
        conn.close(); return jsonify({'error': 'Points de connaissance insuffisants'}), 400
    if skill['prereq'] and not c.execute(
        'SELECT 1 FROM player_skills WHERE player_name=? AND skill_id=?', (name, skill['prereq'])
    ).fetchone():
        conn.close(); return jsonify({'error': 'Prérequis manquant'}), 400

    if skill['cost'] > 0:
        c.execute('UPDATE players SET points = points - ? WHERE name = ?', (skill['cost'], name))
    if skill['knowledge_cost'] > 0:
        c.execute('UPDATE players SET knowledge_points = knowledge_points - ? WHERE name = ?', (skill['knowledge_cost'], name))
    c.execute('INSERT INTO player_skills VALUES (?, ?)', (name, skill_id))
    conn.commit()
    new_player = c.execute('SELECT points, knowledge_points FROM players WHERE name=?', (name,)).fetchone()
    acquired   = [r['skill_id'] for r in c.execute(
        'SELECT skill_id FROM player_skills WHERE player_name=?', (name,)
    ).fetchall()]
    conn.close()
    return jsonify({'points': new_player['points'], 'knowledgePoints': new_player['knowledge_points'], 'acquiredSkills': acquired})

# --- Arbre de compétences ---
@app.route('/api/skills', methods=['GET'])
def get_skills():
    conn = get_db()
    rows = conn.execute('SELECT * FROM skills ORDER BY branch, sort_order').fetchall()
    conn.close()
    branches = {}
    for r in rows:
        b = r['branch']
        if b not in branches:
            branches[b] = []
        branches[b].append({'id': r['id'], 'name': r['name'], 'cost': r['cost'],
                             'knowledge_cost': r['knowledge_cost'],
                             'desc': r['desc'], 'prereq': r['prereq']})
    return jsonify([{'branchName': k, 'skills': v} for k, v in branches.items()])

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
    if c.execute('SELECT 1 FROM player_knowledges WHERE player_name=? AND knowledge_id=?', (name, knowledge_id)).fetchone():
        conn.close(); return jsonify({'error': 'Connaissance déjà acquise'}), 400
    if player['knowledge_points'] < 1:
        conn.close(); return jsonify({'error': 'Points de connaissance insuffisants'}), 400
    c.execute('UPDATE players SET knowledge_points = knowledge_points - 1 WHERE name = ?', (name,))
    c.execute('INSERT INTO player_knowledges VALUES (?, ?)', (name, knowledge_id))
    conn.commit()
    new_kp   = c.execute('SELECT knowledge_points FROM players WHERE name=?', (name,)).fetchone()['knowledge_points']
    acquired = [r['knowledge_id'] for r in c.execute(
        'SELECT knowledge_id FROM player_knowledges WHERE player_name=?', (name,)
    ).fetchall()]
    conn.close()
    return jsonify({'knowledgePoints': new_kp, 'acquiredKnowledges': acquired})

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
        conn.close(); return jsonify({'error': 'Connaissance non acquise par ce joueur'}), 400
    c.execute('DELETE FROM player_knowledges WHERE player_name=? AND knowledge_id=?', (name, knowledge_id))
    if refund:
        c.execute('UPDATE players SET knowledge_points = knowledge_points + 1 WHERE name=?', (name,))
    conn.commit()
    new_kp   = c.execute('SELECT knowledge_points FROM players WHERE name=?', (name,)).fetchone()['knowledge_points']
    acquired = [r['knowledge_id'] for r in c.execute(
        'SELECT knowledge_id FROM player_knowledges WHERE player_name=?', (name,)
    ).fetchall()]
    conn.close()
    return jsonify({'knowledgePoints': new_kp, 'acquiredKnowledges': acquired})

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
        c.execute('INSERT INTO players (name, points) VALUES (?, ?)', (target, 9 + int(amount)))
    else:
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
        c.execute('INSERT INTO players (name, points, knowledge_points) VALUES (?, 9, ?)', (target, 3 + int(amount)))
    else:
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

@app.route('/api/admin/reset/<name>', methods=['POST'])
@require_admin
def reset_player(name):
    conn = get_db()
    c    = conn.cursor()
    c.execute('UPDATE players SET points = 9, knowledge_points = 3 WHERE name=?', (name,))
    c.execute('DELETE FROM player_skills WHERE player_name=?', (name,))
    c.execute('DELETE FROM player_knowledges WHERE player_name=?', (name,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

if __name__ == '__main__':
    init_db()
    print("\n  GN Skill Tree — http://localhost:5000")
    print(f"  Mot de passe Animation : {ADMIN_PASSWORD}\n")
    app.run(debug=True, port=5000)
