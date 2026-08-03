# Calltrainer

AI-powered phone conversation trainer that provides real-time analysis and behavioral feedback during simulated calls.

## Setup

1. `.env.example` nach `.env` kopieren und API-Key eintragen. `.env` ist gitignored.

## Starten (Docker)

```powershell
docker compose up --build
```

Läuft auf `http://localhost:8000`.


## Frontend (React + TypeScript)

`docker compose up --build` baut das Frontend automatisch mit (Multi-Stage-Dockerfile). Für lokale Frontend-Entwicklung ohne Docker:

```powershell
cd frontend
npm install
npm run dev
```

Läuft auf `http://localhost:5173` und ruft die API über `VITE_API_URL` (aus `.env`, Standard `http://localhost:8000`) auf — dafür muss das Backend separat laufen (siehe unten), CORS für `localhost:5173` ist im Backend schon erlaubt.

## App ohne echten API-Key testen

Solange kein gültiger `LLM_API_KEY` vorhanden ist, kann die Pipeline gegen einen lokalen Mock-Server statt gegen `llm.efre-direkt.de` getestet werden.

Terminal 1:

```powershell
python scripts/mock_llm_server.py
```

Terminal 2:

```powershell
$env:LLM_URL = "http://localhost:9000"
uvicorn backend.app:app --reload
```

Damit läuft nur die API auf `http://localhost:8000` (ohne gebautes Frontend). Für die volle Oberfläche zusätzlich `npm run dev` im `frontend/`-Ordner starten (siehe oben) und `http://localhost:5173` öffnen — dort eine Audiodatei hochladen liefert die Testantworten aus dem Mock zurück statt echter Ergebnisse.

**Wichtig:** Die App liest `.env` nur beim Start ein. Nach Änderungen an `.env` (z. B. echten API-Key eintragen) muss der laufende Prozess neu gestartet werden, damit die neuen Werte greifen.

## Doku-Seite ansehen (arc42 + ADRs)

```powershell
pip install -r requirements-docs.txt
mkdocs serve
```

Läuft standardmäßig ebenfalls auf Port 8000 - App vorher stoppen, oder `mkdocs serve -a localhost:8001` verwenden, um den Port-Konflikt zu vermeiden.
