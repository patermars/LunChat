from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import random
import socket as _socket
import os
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mossy-hollow-secret'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', max_http_buffer_size=16 * 1024 * 1024)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ── In-memory store ──────────────────────────────────────────────────
rooms        = {}          # room_name -> [msg, ...]
msg_counter  = {}          # room_name -> int
room_members = {}          # room_name -> {sid: username}
online_users = {}          # sid -> username
room_notepads = {}         # room_name -> {"content": str, "updated_by": str, "updated_at": str, "revision": int}
room_polls = {}            # room_name -> {poll_id: {question, options: [{text, votes: [username]}], created_by, created_at}}

DEFAULT_ROOMS = [
    {"name": "general",   "color": "#3d6b45", "pinned": True}
]
ROOM_META = {r["name"]: r for r in DEFAULT_ROOMS}

def init_room(name):
    if name not in rooms:
        rooms[name]        = []
        msg_counter[name]  = 0
        room_members[name] = {}
    if name not in room_notepads:
        room_notepads[name] = {
            "content": "",
            "updated_by": "",
            "updated_at": "",
            "revision": 0,
        }

def member_payload(room):
    members = room_members.get(room, {})
    return [{"sid": sid, "username": username} for sid, username in members.items()]

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

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


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

    members = member_payload(room)
    emit('room_data', {
        'room':     room,
        'color':    meta.get('color', '#3d6b45'),
        'members':  [m["username"] for m in members],
        'member_info': members,
        'messages': rooms.get(room, []),
        'notepad': room_notepads.get(room, {
            "content": "",
            "updated_by": "",
            "updated_at": "",
            "revision": 0,
        }),
        'my_sid':   request.sid,
    })

    emit('member_update', {
        'room':    room,
        'members': [m["username"] for m in members],
        'member_info': members,
    }, to=room, include_self=False)

@socketio.on('leave')
def on_leave(data):
    room     = data['room']
    leave_room(room)
    if room in room_members:
        room_members[room].pop(request.sid, None)
    members = member_payload(room)
    emit('member_update', {
        'room':    room,
        'members': [m["username"] for m in members],
        'member_info': members,
    }, to=room)

@socketio.on('disconnect')
def on_disconnect():
    username = online_users.pop(request.sid, 'Anonymous')
    for room in list(room_members.keys()):
        if request.sid in room_members[room]:
            room_members[room].pop(request.sid)
            members = member_payload(room)
            emit('member_update', {
                'room':    room,
                'members': [m["username"] for m in members],
                'member_info': members,
            }, to=room)

@socketio.on('ping_user')
def handle_ping_user(data):
    target_sid = (data or {}).get('to')
    room = (data or {}).get('room')
    if not target_sid or target_sid == request.sid:
        return
    if room:
        members = room_members.get(room, {})
        if request.sid not in members or target_sid not in members:
            return
    from_user = online_users.get(request.sid, 'Anonymous')
    emit('ping_received', {
        'from': from_user,
        'room': room,
        'time': now_time(),
    }, to=target_sid)

@socketio.on('send_message')
def handle_message(data):
    room     = data['room']
    text     = data['text'].strip()
    username = online_users.get(request.sid, 'Anonymous')
    file_data = data.get('file')
    
    if not text and not file_data:
        return

    init_room(room)
    msg_counter[room] += 1
    msg = {
        "id":       msg_counter[room],
        "sender":   username,
        "text":     text,
        "time":     now_time(),
        "reply_to": data.get('reply_to'),
        "edited":   False,
        "timestamp": datetime.now().isoformat()
    }
    
    if file_data:
        filename = f"{msg_counter[room]}_{file_data['name']}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(file_data['data'].split(',')[1]))
        msg['file'] = {'name': file_data['name'], 'url': f'/uploads/{filename}', 'size': file_data['size']}
    
    rooms[room].append(msg)
    emit('new_message', {'room': room, 'message': msg}, to=room)

@socketio.on('edit_message')
def handle_edit_message(data):
    room = data['room']
    msg_id = data['id']
    new_text = data['text'].strip()
    username = online_users.get(request.sid, 'Anonymous')
    
    if not new_text or room not in rooms:
        return

    msg = next((m for m in rooms[room] if m['id'] == msg_id), None)
    
    if not msg:
        return

    is_owner = msg['sender'] == username
    msg_time = datetime.fromisoformat(msg['timestamp'])
    is_recent = (datetime.now() - msg_time).total_seconds() < 900

    if is_owner and is_recent:
        msg['text'] = new_text
        msg['time'] = now_time()
        msg['edited'] = True
        is_latest = bool(rooms[room]) and rooms[room][-1]['id'] == msg['id']
        emit('message_edited', {'room': room, 'message': msg, 'is_latest': is_latest}, to=room)
    else:
        emit('edit_error', {'msg': 'Cannot edit this message.'}, room=request.sid)

@socketio.on('typing')
def handle_typing(data):
    username = online_users.get(request.sid, 'Anonymous')
    emit('typing', {
        'room':   data['room'],
        'user':   username,
        'active': data.get('active', False),
    }, to=data['room'], include_self=False)

@socketio.on('notepad_update')
def handle_notepad_update(data):
    room = (data or {}).get('room', '').strip()
    content = (data or {}).get('content', '')

    if not room or not isinstance(content, str):
        return
    if room not in room_members or request.sid not in room_members[room]:
        return

    init_room(room)
    existing = room_notepads.get(room, {})
    next_revision = int(existing.get('revision', 0)) + 1
    payload = {
        'room': room,
        'content': content[:20000],
        'updated_by': online_users.get(request.sid, 'Anonymous'),
        'updated_at': now_time(),
        'revision': next_revision,
        'sid': request.sid,
    }
    room_notepads[room] = {
        'content': payload['content'],
        'updated_by': payload['updated_by'],
        'updated_at': payload['updated_at'],
        'revision': payload['revision'],
    }
    emit('notepad_updated', payload, to=room)

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

@socketio.on('create_poll')
def handle_create_poll(data):
    room = data.get('room')
    question = data.get('question', '').strip()
    options = data.get('options', [])
    if not room or not question or len(options) < 2:
        return
    init_room(room)
    if room not in room_polls:
        room_polls[room] = {}
    poll_id = len(room_polls[room]) + 1
    room_polls[room][poll_id] = {
        'id': poll_id,
        'question': question,
        'options': [{'text': opt, 'votes': []} for opt in options],
        'created_by': online_users.get(request.sid, 'Anonymous'),
        'created_at': now_time()
    }
    emit('poll_created', {'room': room, 'poll': room_polls[room][poll_id]}, to=room)

@socketio.on('vote_poll')
def handle_vote_poll(data):
    room = data.get('room')
    poll_id = data.get('poll_id')
    option_idx = data.get('option_idx')
    username = online_users.get(request.sid, 'Anonymous')
    if room not in room_polls or poll_id not in room_polls[room]:
        return
    poll = room_polls[room][poll_id]
    for opt in poll['options']:
        if username in opt['votes']:
            opt['votes'].remove(username)
    if 0 <= option_idx < len(poll['options']):
        poll['options'][option_idx]['votes'].append(username)
    emit('poll_updated', {'room': room, 'poll': poll}, to=room)

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
    room_notepads.pop(name, None)
    room_polls.pop(name, None)
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
