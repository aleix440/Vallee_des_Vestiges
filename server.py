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
        points            INTEGER DEFAULT 10,
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
        id         TEXT PRIMARY KEY,
        branch     TEXT    NOT NULL,
        name       TEXT    NOT NULL,
        cost       INTEGER NOT NULL,
        desc       TEXT    NOT NULL,
        prereq     TEXT,
        sort_order INTEGER DEFAULT 0
    )''')
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
        c.execute('INSERT INTO players (name, points, knowledge_points) VALUES (?, 10, 3)', (name,))
        conn.commit()
        player = c.execute('SELECT * FROM players WHERE name = ?', (name,)).fetchone()
    skills = [r['skill_id'] for r in c.execute(
        'SELECT skill_id FROM player_skills WHERE player_name = ?', (name,)
    ).fetchall()]
    conn.close()
    return jsonify({'name': name, 'points': player['points'],
                    'knowledgePoints': player['knowledge_points'], 'acquiredSkills': skills})

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
    if player['points'] < skill['cost']:
        conn.close(); return jsonify({'error': 'Points insuffisants'}), 400
    if skill['prereq'] and not c.execute(
        'SELECT 1 FROM player_skills WHERE player_name=? AND skill_id=?', (name, skill['prereq'])
    ).fetchone():
        conn.close(); return jsonify({'error': 'Prérequis manquant'}), 400

    c.execute('UPDATE players SET points = points - ? WHERE name = ?', (skill['cost'], name))
    c.execute('INSERT INTO player_skills VALUES (?, ?)', (name, skill_id))
    conn.commit()
    new_points = c.execute('SELECT points FROM players WHERE name=?', (name,)).fetchone()['points']
    acquired   = [r['skill_id'] for r in c.execute(
        'SELECT skill_id FROM player_skills WHERE player_name=?', (name,)
    ).fetchall()]
    conn.close()
    return jsonify({'points': new_points, 'acquiredSkills': acquired})

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
                             'desc': r['desc'], 'prereq': r['prereq']})
    return jsonify([{'branchName': k, 'skills': v} for k, v in branches.items()])

@app.route('/api/skills', methods=['POST'])
@require_admin
def add_skill():
    data   = request.json
    branch = data.get('branch', 'Combat')
    name   = data.get('name', '').strip()
    cost   = data.get('cost')
    desc   = data.get('desc', '').strip()
    prereq = data.get('prereq') or None
    if not name or cost is None or not desc:
        return jsonify({'error': 'Champs manquants'}), 400
    conn = get_db()
    c    = conn.cursor()
    max_order = c.execute('SELECT MAX(sort_order) FROM skills WHERE branch=?', (branch,)).fetchone()[0] or 0
    new_id    = branch[0].lower() + str(int(time.time()))
    c.execute('INSERT INTO skills VALUES (?,?,?,?,?,?,?)',
              (new_id, branch, name, cost, desc, prereq, max_order + 1))
    conn.commit()
    conn.close()
    return jsonify({'id': new_id, 'branch': branch, 'name': name, 'cost': cost,
                    'desc': desc, 'prereq': prereq})

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
        c.execute('INSERT INTO players (name, points) VALUES (?, ?)', (target, 10 + int(amount)))
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
        c.execute('INSERT INTO players (name, points, knowledge_points) VALUES (?, 10, ?)', (target, 3 + int(amount)))
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
    c.execute('UPDATE players SET points = 10, knowledge_points = 3 WHERE name=?', (name,))
    c.execute('DELETE FROM player_skills WHERE player_name=?', (name,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

if __name__ == '__main__':
    init_db()
    print("\n  GN Skill Tree — http://localhost:5000")
    print(f"  Mot de passe Animation : {ADMIN_PASSWORD}\n")
    app.run(debug=True, port=5000)
