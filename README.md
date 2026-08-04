# Calltrainer

AI-powered phone conversation trainer that provides real-time analysis and behavioral feedback during simulated calls.

## Setup

1. Install Git
   - Download and install: https://git-scm.com/install/
   - Verify: open a new terminal and run `git --version`. It should print the installed Git version
   - Configure your identity (used for commits):
      - `git config --global user.name "Your Name"`
      - `git config --global user.email "your.mail@yourmail.com"`
   - Set up SSH for GitHub authentication:
     - Generate a key: `ssh-keygen -t ed25519 -C "your.mail@yourmail.com"`
     - Add the public key (`~/.ssh/id_ed25519.pub`) to your GitHub account under Settings → SSH and GPG keys
     - Open a terminal at your desired location and clone the repository: `git clone git@github.com:WIBWL/direkt-calltrainer.git`

2. Install Python 3.12.3 (64-bit): https://www.python.org/downloads/release/python-3123/
   - Verify: open a new terminal and run `python --version` (`python3 --version` for macOS). It should print the installed Python version

3. Install Docker Desktop
   - Windows: https://docs.docker.com/desktop/setup/install/windows-install/ (WSL2 backend recommended)
   - macOS: https://docs.docker.com/desktop/setup/install/mac-install/
   - Verify: open a new terminal and run `docker --version`. It should print the installed Docker version

4. Open the cloned `direkt-calltrainer` folder in VS Code

5. Create the virtual environment
   - In VS Code: `Strg+Shift+P`/`Cmd+Shift+P` → `Python: Create Environment` → select `venv` → choose Python 3.12.3
   - Check `requirements.txt` when VS Code asks which dependencies to install
   - VS Code creates a `.venv` folder in the project root and automatically sets it as the interpreter
   - Alternatively via terminal:
     - Windows: `python -m venv .venv`, then `.venv\Scripts\Activate.ps1`, then `pip install -r requirements.txt`
     - macOS: `python3 -m venv .venv`, then `source .venv/bin/activate`, then `pip install -r requirements.txt`
   - Verify: open a new terminal in VS Code. After ~1 second `(.venv)` should appear in front of the prompt, confirming the environment is active
 
6. Install the VS Code extensions `flake8` and `pylint`

7. Copy `.env.example` to `.env` and fill in your API key (`.env` is gitignored)


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
mkdocs serve
```

Läuft standardmäßig ebenfalls auf Port 8000 - App vorher stoppen, oder `mkdocs serve -a localhost:8001` verwenden, um den Port-Konflikt zu vermeiden.

## Lokale STT/TTS-Modelle einrichten

Das LLM (Dialoggenerierung) läuft über die gehostete EFRE-Direkt-Schnittstelle (`LLM_URL`/`LLM_API_KEY`/`LLM_MODEL` in `.env`) — dafür ist nichts zu installieren. STT (`openai/whisper-large-v3-turbo`) und TTS (`mistralai/Voxtral-4B-TTS-2603`) stellt EFRE-Direkt nicht bereit; die müssen lokal selbst gehostet werden (siehe ADR 0022).

**Voraussetzung:** eine NVIDIA-GPU. vLLM läuft unter Windows nicht offiziell nativ — der von vLLM selbst dokumentierte und unterstützte Weg ist WSL2 (Windows Subsystem for Linux). Prüfe zuerst, ob WSL2 schon eingerichtet ist:

```powershell
wsl --status
```

Falls nicht vorhanden: https://learn.microsoft.com/windows/wsl/install

1. **WSL/Ubuntu starten** (PowerShell oder Windows Terminal):
   ```powershell
   wsl
   ```
   GPU-Zugriff ist automatisch da (moderne NVIDIA-Windows-Treiber bringen GPU-Passthrough für WSL2 mit).

2. **GPU-Zugriff in WSL prüfen:**
   ```bash
   nvidia-smi
   ```
   Sollte dieselbe GPU wie unter Windows zeigen.

3. **Eigenes Python-Environment für vLLM anlegen** (nicht das Projekt-`.venv` — vLLM hat eigene, sehr spezifische Torch/CUDA-Abhängigkeiten, und braucht Python 3.12, das neuere Ubuntu-Versionen wie 26.04 nicht mehr per `apt` mitbringen). Dafür [uv](https://docs.astral.sh/uv/) nutzen, das die passende Python-Version selbst herunterlädt statt sich auf `apt` zu verlassen:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source $HOME/.local/bin/env
   uv venv ~/vllm-env --python 3.12
   source ~/vllm-env/bin/activate
   uv pip install "vllm[audio]" vllm-omni --upgrade
   ```

4. **Bei Hugging Face einloggen** (Voxtral ist ggf. lizenzgated):
   ```bash
   uv pip install huggingface_hub
   hf auth login
   ```
   Bei einem 403/Gated-Fehler beim ersten Start: auf https://huggingface.co/mistralai/Voxtral-4B-TTS-2603 einloggen und die Lizenz akzeptieren.

5. **STT-Server starten** (lädt beim ersten Start automatisch mehrere GB von Hugging Face herunter):
   ```bash
   vllm serve openai/whisper-large-v3-turbo --port 8025 --gpu-memory-utilization 0.8
   ```
   (vLLM erkennt Whisper-Modelle automatisch an der Architektur und aktiviert `/v1/audio/transcriptions` von selbst — kein `--task`/`--runner`-Flag nötig. `--gpu-memory-utilization` niedriger als den Default 0.92 setzen, sonst meckert vLLM, dass nicht genug freier VRAM übrig ist, weil Windows/andere Prozesse schon etwas belegen.)
   Test in einem zweiten WSL-Terminal: `curl http://localhost:8025/v1/models`

6. **TTS-Server starten** (neues WSL-Terminal, gleiches venv aktivieren):
   ```bash
   source ~/vllm-env/bin/activate
   VOXTRAL_YAML=$(python -c 'import vllm_omni, os; print(os.path.join(os.path.dirname(vllm_omni.__file__), "model_executor/stage_configs/voxtral_tts.yaml"))')
   vllm-omni serve mistralai/Voxtral-4B-TTS-2603 --omni --stage-configs-path "$VOXTRAL_YAML" --enforce-eager --port 8091 --gpu-memory-utilization 0.4
   ```
   Falls STT und TTS gleichzeitig laufen sollen, teilen sich beide den VRAM (bei 12 GB z. B. `0.4` je Prozess statt `0.8`) — sonst startet der zweite Server nicht, weil der erste schon zu viel reserviert hat.

7. **Backend starten** — läuft ganz normal unter Windows im Projekt-`.venv`. `STT_URL`/`TTS_URL` in `.env` zeigen schon auf `localhost:8025`/`localhost:8091`. Falls das Windows-Backend die WSL-Server nicht über `localhost` erreicht: WSL-IP verwenden statt `localhost`, ermittelbar mit `wsl hostname -I`.
