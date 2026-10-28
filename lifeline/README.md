# Lifeline - hospital disaster-recovery app

lifeline/
  frontend/lifeline-app.html   the whole web app (single file)
  backend/server.py            Python backend (no installs, Python 3.8+)  <- recommended
  backend/server.js            same backend in Node 18+ (alternative)
  lifeline-conversation.pdf    original notes

## Run (Python)
    cd backend
    python server.py            (Windows: py server.py)

Open http://localhost:3000 (laptop) or http://<laptop-ip>:3000 (phone on same Wi-Fi/hotspot).
In the app, paste that same address into "Real server URL". Done.

## Run (Node, alternative)
    cd backend
    node server.js

## Where data is saved
backend/records.json              every entry
backend/history/YYYY-MM-DD.json   one file per day

## API
GET /health | GET /records | POST /records | GET /history | GET / (the app)
Same id = update, never a duplicate. First-saved time never changes.
