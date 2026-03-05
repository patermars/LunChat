# 🌿 LunChat

**Real-time LAN chat for labs and classrooms**

A lightweight, feature-rich chat application for instant messaging over local networks. Perfect for computer labs, classrooms, or any shared workspace.

## ✨ Features

- 💬 **Real-time messaging** with Socket.IO
- 📁 **File sharing** (drag & drop support)
- 📝 **Collaborative notepad** per room
- 📊 **Live polls** with instant results
- 🔔 **User pinging** with visual/audio alerts
- ✏️ **Message editing** (within 15 minutes)
- 💬 **Reply to messages** with threading
- 🏠 **Multiple chat rooms** with custom creation
- 👥 **Live member list** showing who's online
- 🎨 **Clean, modern UI** with smooth animations

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/LunChat.git
cd LunChat

# Install dependencies
pip install flask flask-socketio

# Run the server
python app.py
```

### Usage

1. Start the server on one machine
2. Share the displayed LAN URL with others on the same network
3. Everyone opens the URL in their browser
4. Enter your name and start chatting!

**Example:**
```
Your machine  →  http://localhost:5000
Your friends  →  http://{ip_address}:5000
```

## 🛠️ Tech Stack

- **Backend:** Flask, Flask-SocketIO
- **Frontend:** Vanilla JavaScript, Socket.IO client
- **Styling:** Custom CSS with modern design

## 📂 Project Structure

```
LunChat/
├── app.py              # Flask server & Socket.IO handlers
├── templates/
│   └── index.html      # Frontend UI
├── uploads/            # File attachments storage
└── roast.txt          # Bot responses (optional)
```

## 🤖 Features in Detail

- **RoastBot:** An AI companion that occasionally responds to messages
- **Typing indicators:** See when others are typing
- **Message receipts:** Know when your messages are delivered
- **Room management:** Create, join, and delete rooms
- **Kick users:** Room moderators can remove disruptive users
- **Persistent usernames:** Remembers your name across sessions

## 📝 License

See [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions welcome! Feel free to open issues or submit pull requests.

---

**Made for seamless LAN communication** 🌿
