# app.py
import os
import random
import uuid
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# --- 게임 모델 (간단화) ---
BLOCK_TYPES = [
    {"type":"small","size":1,"weight":1,"center":0},
    {"type":"rect","size":2,"weight":2,"center":0},
    {"type":"long","size":3,"weight":3,"center":1},
    {"type":"wide","size":2,"weight":2,"center":-1},
]

GAMES = {}  # game_id -> state

def new_game(num_players=2, rounds=8):
    gid = str(uuid.uuid4())[:8]
    players = [{"id":i,"name":f"P{i+1}","tower":[], "tokens":0} for i in range(num_players)]
    state = {
        "id": gid,
        "players": players,
        "round": 0,
        "max_rounds": rounds,
        "deck": create_deck(),
        "log": []
    }
    GAMES[gid] = state
    return state

def create_deck():
    deck = []
    for _ in range(6):
        for b in BLOCK_TYPES:
            deck.append(b.copy())
    random.shuffle(deck)
    return deck

def draw_card(state):
    if not state["deck"]:
        state["deck"] = create_deck()
    return state["deck"].pop()

def compute_instability(tower):
    if not tower: return 0
    s = 0
    for b in tower:
        s += b["weight"] * abs(b["center"])
    return round(s / len(tower), 2)

def place_block(state, player_id, block):
    player = state["players"][player_id]
    player["tower"].append(block)
    instability = compute_instability(player["tower"])
    if instability > 3:
        player["tokens"] += 1
        state["log"].append(f"{player['name']} gained instability token (total {player['tokens']})")
    else:
        state["log"].append(f"{player['name']} placed block safely")
    return {"instability": instability, "tokens": player["tokens"]}

# --- 간단 UI ---
INDEX_HTML = """
<!doctype html>
<html>
<head><meta charset="utf-8"><title>균형의 탑</title>
<style>body{font-family:system-ui;margin:20px}button{margin:4px;padding:8px}#board{display:flex;gap:16px;margin-top:12px}.player{border:1px solid #ccc;padding:8px;width:180px}.log{white-space:pre-wrap;background:#f4f4f4;padding:8px;margin-top:12px}</style>
</head>
<body>
<h3>균형의 탑 - 프로토타입</h3>
<label>플레이어 수: <input id="players" type="number" value="2" min="2" max="6"></label>
<button onclick="newGame()">새 게임</button>
<button onclick="nextRound()">자동 한 라운드</button>
<div id="board"></div>
<div class="log" id="log"></div>
<script>
let game=null;
async function newGame(){
  const p = parseInt(document.getElementById('players').value)||2;
  const res = await fetch('/api/new_game',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({num_players:p})});
  game = await res.json(); render();
}
async function nextRound(){
  if(!game){ alert('새 게임 생성'); return; }
  for(let i=0;i<game.players.length;i++){
    await fetch('/api/draw/'+game.id+'/'+i);
    await fetch('/api/place/'+game.id+'/'+i, {method:'POST',headers:{'Content-Type':'application/json'}, body: JSON.stringify({})});
  }
  const st = await fetch('/api/state/'+game.id);
  game = await st.json(); render();
}
function render(){
  const b = document.getElementById('board'); b.innerHTML='';
  game.players.forEach(p=>{
    const d=document.createElement('div'); d.className='player';
    d.innerHTML=`<strong>${p.name}</strong><div>타워:${p.tower.length}층</div><div>불안정토큰:${p.tokens}</div><div>스코어:${p.tower.length - p.tokens}</div><pre>${JSON.stringify(p.tower,null,2)}</pre>`;
    b.appendChild(d);
  });
  document.getElementById('log').innerText = game.log.join("\\n");
}
</script>
</body></html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/api/new_game", methods=["POST"])
def api_new():
    data = request.get_json() or {}
    num = int(data.get("num_players",2))
    g = new_game(num_players=num)
    return jsonify(g)

@app.route("/api/state/<gid>")
def api_state(gid):
    s = GAMES.get(gid)
    if not s: return jsonify({"error":"no game"}),404
    return jsonify(s)

@app.route("/api/draw/<gid>/<int:pid>")
def api_draw(gid,pid):
    s = GAMES.get(gid)
    if not s: return jsonify({"error":"no game"}),404
    card = draw_card(s)
    return jsonify(card)

@app.route("/api/place/<gid>/<int:pid>", methods=["POST"])
def api_place(gid,pid):
    s = GAMES.get(gid)
    if not s: return jsonify({"error":"no game"}),404
    # 클라이언트가 보낸 블록이 없으면 서버에서 자동으로 draw한 블록을 사용
    data = request.get_json() or {}
    block = data if data else draw_card(s)
    res = place_block(s, pid, block)
    return jsonify(res)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
