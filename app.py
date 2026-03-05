from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import random
import socket as _socket

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mossy-hollow-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ── In-memory store ──────────────────────────────────────────────────
rooms        = {}          # room_name -> [msg, ...]
msg_counter  = {}          # room_name -> int
room_members = {}          # room_name -> {sid: username}
online_users = {}          # sid -> username

DEFAULT_ROOMS = [
    {"name": "general",   "color": "#3d6b45", "pinned": True}
]
ROOM_META = {r["name"]: r for r in DEFAULT_ROOMS}

def init_room(name):
    if name not in rooms:
        rooms[name]        = []
        msg_counter[name]  = 0
        room_members[name] = {}

for r in DEFAULT_ROOMS:
    init_room(r["name"])
    


def now_time():
    return datetime.now().strftime("%I:%M %p")

def get_local_ip():
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── Routes ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    room_list = []
    for r in DEFAULT_ROOMS:
        msgs = rooms.get(r["name"], [])
        last = msgs[-1] if msgs else None
        room_list.append({
            **r,
            "last_sender":  last["sender"] if last else "",
            "last_preview": (last["text"][:36] + "…") if last and len(last["text"]) > 36
                            else (last["text"] if last else ""),
            "last_time":    last["time"] if last else "",
            "member_count": len(room_members.get(r["name"], {})),
        })
    return render_template('index.html', rooms=room_list)


# ── Socket events ────────────────────────────────────────────────────

@socketio.on('set_username')
def on_set_username(data):
    username = data.get('username', '').strip()[:24]
    if not username:
        emit('username_error', {'msg': 'Name cannot be empty.'})
        return
    online_users[request.sid] = username
    emit('username_ok', {'username': username})

@socketio.on('join')
def on_join(data):
    room     = data['room']
    username = online_users.get(request.sid, 'Anonymous')
    join_room(room)
    init_room(room)
    room_members[room][request.sid] = username
    meta = ROOM_META.get(room, {})

    emit('room_data', {
        'room':     room,
        'color':    meta.get('color', '#3d6b45'),
        'members':  list(room_members[room].values()),
        'messages': rooms.get(room, []),
        'my_sid':   request.sid,
    })

    emit('member_update', {
        'room':    room,
        'members': list(room_members[room].values()),
    }, to=room, include_self=False)

@socketio.on('leave')
def on_leave(data):
    room     = data['room']
    leave_room(room)
    if room in room_members:
        room_members[room].pop(request.sid, None)
    emit('member_update', {
        'room':    room,
        'members': list(room_members.get(room, {}).values()),
    }, to=room)

@socketio.on('disconnect')
def on_disconnect():
    username = online_users.pop(request.sid, 'Anonymous')
    for room in list(room_members.keys()):
        if request.sid in room_members[room]:
            room_members[room].pop(request.sid)
            emit('member_update', {
                'room':    room,
                'members': list(room_members[room].values()),
            }, to=room)

@socketio.on('send_message')
def handle_message(data):
    room     = data['room']
    text     = data['text'].strip()
    username = online_users.get(request.sid, 'Anonymous')
    if not text:
        return

    init_room(room)
    msg_counter[room] += 1
    msg = {
        "id":       msg_counter[room],
        "sender":   username,
        "text":     text,
        "time":     now_time(),
        "reply_to": data.get('reply_to'),
    }
    rooms[room].append(msg)
    emit('new_message', {'room': room, 'message': msg}, to=room)

@socketio.on('typing')
def handle_typing(data):
    username = online_users.get(request.sid, 'Anonymous')
    emit('typing', {
        'room':   data['room'],
        'user':   username,
        'active': data.get('active', False),
    }, to=data['room'], include_self=False)

@socketio.on('create_room')
def handle_create_room(data):
    name = data['name'].strip().lower().replace(' ', '-')
    if not name or name in ROOM_META:
        emit('room_error', {'msg': 'Room already exists or invalid name.'})
        return
    colors = ['#3d6b45','#4a7c5a','#8b6a3e','#c47a5a','#6b8c6b','#5a7a8a','#7a6b8c','#8c7a5a']
    color = random.choice(colors)
    ROOM_META[name] = {"name": name, "color": color, "pinned": False}
    DEFAULT_ROOMS.append(ROOM_META[name])
    init_room(name)
    emit('room_created', {'room': ROOM_META[name]}, broadcast=True)

@socketio.on('delete_room')
def handle_delete_room(data):
    name = data['name']
    if name not in ROOM_META:
        return
    del ROOM_META[name]
    DEFAULT_ROOMS[:] = [r for r in DEFAULT_ROOMS if r['name'] != name]
    rooms.pop(name, None)
    msg_counter.pop(name, None)
    room_members.pop(name, None)
    emit('room_deleted', {'name': name}, broadcast=True)


if __name__ == '__main__':
    ip   = get_local_ip()
    port = 5000
    print("\n" + "=" * 54)
    print("  🌿  Mossy Chat — LAN mode")
    print(f"\n  Your machine  →  http://localhost:{port}")
    print(f"  Your friends  →  http://{ip}:{port}")
    print("\n  Share the second URL with everyone in your lab.")
    print("  Make sure you're all on the same Wi-Fi / network.")
    print("=" * 54 + "\n")
    socketio.run(app, host='0.0.0.0', port=port,debug=False, allow_unsafe_werkzeug=True)
