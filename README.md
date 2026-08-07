# Calltrainer

AI-powered phone conversation trainer that provides real-time analysis and behavioral feedback during simulated calls.

## 1. Setup

1. Install Git
   - Download and install: https://git-scm.com/install/
   - Verify: open a new terminal and run `git --version`. It should print the installed Git version.
   - Configure your identity (used for commits):
     - `git config --global user.name "Your Name"`
     - `git config --global user.email "your.mail@yourmail.com"`
   - Set up SSH for GitHub authentication:
     - Generate a key: `ssh-keygen -t ed25519 -C "your.mail@yourmail.com"`
     - Add the public key (`~/.ssh/id_ed25519.pub`) to your GitHub account under Settings → SSH and GPG keys
     - Open a terminal at your desired location and clone the repository: `git clone git@github.com:WIBWL/direkt-calltrainer.git`

2. Install Python 3.12.3 (64-bit): https://www.python.org/downloads/release/python-3123/
   - Verify: open a new terminal and run `python --version` (`python3 --version` on macOS). It should print the installed Python version.

3. Install Docker Desktop
   - Windows: https://docs.docker.com/desktop/setup/install/windows-install/ (WSL2 backend recommended)
   - macOS: https://docs.docker.com/desktop/setup/install/mac-install/
   - Verify: open a new terminal and run `docker --version`. It should print the installed Docker version.

4. Open the cloned `direkt-calltrainer` folder in VS Code.

5. Create the Python virtual environment (used for the backend)
   - In VS Code: `Ctrl+Shift+P`/`Cmd+Shift+P` → `Python: Create Environment` → select `venv` → choose Python 3.12.3
   - Check `requirements.txt` when VS Code asks which dependencies to install
   - VS Code creates a `.venv` folder in the project root and automatically sets it as the interpreter
   - Alternatively via terminal:
     - Windows: `python -m venv .venv`, then `.venv\Scripts\Activate.ps1`, then `pip install -r requirements.txt`
     - macOS: `python3 -m venv .venv`, then `source .venv/bin/activate`, then `pip install -r requirements.txt`
   - Verify: open a new terminal in VS Code. After ~1 second, `(.venv)` should appear in front of the prompt, confirming the environment is active.

6. Install the VS Code extensions `flake8` and `pylint`.

7. Copy `.env.example` to `.env` and fill in the real values (`LLM_API_KEY`, etc.) — `.env` is gitignored, never commit it.

## 2. Local STT/TTS model servers (GPU required)

The LLM (dialogue generation) runs against the hosted EFRE-Direkt gateway (`LLM_URL`/`LLM_API_KEY`/`LLM_MODEL` in `.env`) — nothing to install for that. STT (`openai/whisper-large-v3-turbo`) and TTS (`mistralai/Voxtral-4B-TTS-2603`) are not provided by EFRE-Direkt; they must be self-hosted locally (see ADR 0022). This section is only needed if you want to run the full pipeline — you can skip it if you're only working on the frontend, or testing against the mock server (section 3.3).

**Requirement:** an NVIDIA GPU. vLLM has no official native Windows support — the path vLLM itself documents and supports is WSL2 (Windows Subsystem for Linux). Check first whether WSL2 is already set up:

```powershell
wsl --status
```

If not installed: https://learn.microsoft.com/windows/wsl/install

1. **Start WSL/Ubuntu** (PowerShell or Windows Terminal):
   ```powershell
   wsl
   ```
   GPU access works out of the box (modern NVIDIA Windows drivers include GPU passthrough for WSL2).

2. **Verify GPU access inside WSL:**
   ```bash
   nvidia-smi
   ```
   Should show the same GPU as under Windows.

3. **Create a dedicated Python environment for vLLM** (not the project's `.venv` — vLLM has its own, very specific Torch/CUDA dependencies, and needs Python 3.12, which newer Ubuntu releases like 26.04 no longer ship via `apt`). Use [uv](https://docs.astral.sh/uv/) instead, which downloads the right Python version itself rather than relying on `apt`:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source $HOME/.local/bin/env
   uv venv ~/vllm-env --python 3.12
   source ~/vllm-env/bin/activate
   uv pip install "vllm[audio]" vllm-omni --upgrade
   ```

4. **Install a C compiler and the CUDA toolkit** (vLLM compiles kernels at runtime via Triton, which needs `gcc` and `nvcc` — neither is preinstalled on a fresh WSL Ubuntu):
   ```bash
   sudo apt update && sudo apt install -y build-essential
   ```
   Find the CUDA toolkit version matching your installed Torch (`python -c 'import torch; print(torch.version.cuda)'` in the activated venv — `13.0` for us), then:
   ```bash
   wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
   sudo dpkg -i cuda-keyring_1.1-1_all.deb
   sudo apt-get update
   apt search cuda-toolkit 2>/dev/null | grep cuda-toolkit-13   # find the exact version matching your Torch CUDA version
   sudo apt-get -y install cuda-toolkit-13-0                    # adjust the version number as needed
   ```
   **Important:** install only the `-toolkit` package, not `cuda`/`cuda-drivers` — those try to install a Linux GPU driver inside WSL2, which conflicts with the passed-through Windows driver.

   `nvcc` is now installed but not on PATH — add it permanently (in any WSL terminal that was already open, run `source ~/.bashrc` once to pick it up):
   ```bash
   echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
   echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
   source ~/.bashrc
   nvcc --version   # should now print a version number
   ```

5. **Log in to Hugging Face** (Voxtral may be license-gated):
   ```bash
   uv pip install huggingface_hub
   hf auth login
   ```
   On a 403/gated error at first startup: log in at https://huggingface.co/mistralai/Voxtral-4B-TTS-2603 and accept the license.

6. **Start the STT server** (downloads several GB from Hugging Face automatically on first run):
   ```bash
   VLLM_USE_V2_MODEL_RUNNER=0 vllm serve openai/whisper-large-v3-turbo --port 8025 --gpu-memory-utilization 0.25
   ```
   - vLLM recognizes Whisper models automatically by their architecture and enables `/v1/audio/transcriptions` on its own — no `--task`/`--runner` flag needed.
   - `--gpu-memory-utilization` is the fraction of **total** VRAM this process reserves for itself (not just what's currently free) — pick values so STT and TTS together stay under ~90%. `0.25` is enough for Whisper (much smaller than Voxtral) and leaves room for the TTS server.
   - `VLLM_USE_V2_MODEL_RUNNER=0` is required because vLLM's newer "Model Runner V2" needs UVA (Unified Virtual Addressing) internally, which isn't available under WSL2 (`RuntimeError: UVA is not available`) — vLLM deliberately disables pinned memory under WSL2, which disables UVA along with it.

   Test from a second WSL terminal: `curl http://localhost:8025/v1/models`

7. **Start the TTS server** (new WSL terminal, activate the same venv):
   ```bash
   source ~/vllm-env/bin/activate
   VOXTRAL_YAML=$(python -c 'import vllm_omni, os; print(os.path.join(os.path.dirname(vllm_omni.__file__), "deploy/voxtral_tts.yaml"))' | tail -1)
   VLLM_USE_V2_MODEL_RUNNER=0 vllm-omni serve mistralai/Voxtral-4B-TTS-2603 --omni --stage-configs-path "$VOXTRAL_YAML" --enforce-eager --port 8091 --gpu-memory-utilization 0.6
   ```
   (`| tail -1` is needed because `import vllm_omni` prints INFO log lines automatically, which otherwise end up inside `$VOXTRAL_YAML` and break the path — only the last line is the actual `print()` output.)

   `0.25` (STT) + `0.6` (TTS) = `0.85` of the total 12 GB VRAM, which works for us running both servers at once on an RTX 4070. Adjust for less VRAM or a different GPU — `0.4`/`0.4` was too little for TTS alone for us (`ValueError: No available memory for the cache blocks`).

   Valid `voice` presets for this model (if you want to change `TTS_VOICE` in `.env`): `ar_male, casual_female, casual_male, cheerful_female, de_female, de_male, es_female, es_male, fr_female, fr_male, hi_female, hi_male, it_female, it_male, neutral_female, neutral_male, nl_female, nl_male, pt_female, pt_male`.

Both servers only run for as long as their terminal stays open — restart them each session, same as the backend below. `STT_URL`/`TTS_URL` in `.env` already point at `localhost:8025`/`localhost:8091`. If the Windows-side backend can't reach the WSL servers via `localhost`, use the WSL IP instead, found with `wsl hostname -I`.

## 3. Running the app

### 3.1 Docker (simplest, full stack)

```powershell
docker compose up --build
```

Builds the frontend too (multi-stage Dockerfile) and serves everything on `http://localhost:8000`. Note: this does not start the local STT/TTS model servers from section 2 — those still need to run separately if you want the full pipeline.

### 3.2 Local development (backend + frontend separately, with hot reload)

Backend:

```powershell
$env:PYTHONUTF8 = "1"
uvicorn backend.app:app --reload
```

`PYTHONUTF8` avoids garbled umlauts in the console (German text like "Gespräch" would otherwise show as "Gespr�ch" — a Windows console encoding quirk, not a data bug). The backend reads `.env` only at startup; restart it after changing `.env`.

Frontend (separate terminal):

```powershell
cd frontend
npm install   # first time only
npm run dev
```

Runs on `http://localhost:5173` and calls the API via `VITE_API_URL` (from `.env`, default `http://localhost:8000`) — the backend must be running separately for this to work. CORS for `localhost:5173` is already allowed in the backend.

### 3.3 Testing without a real LLM_API_KEY

While no valid `LLM_API_KEY` is available, the pipeline can be tested against a local mock server instead of `llm.efre-direkt.de`.

Terminal 1:

```powershell
python scripts/mock_llm_server.py
```

Terminal 2:

```powershell
$env:LLM_URL = "http://localhost:9000"
uvicorn backend.app:app --reload
```

This runs only the API on `http://localhost:8000` (no built frontend). For the full UI, also start `npm run dev` in `frontend/` (see 3.2) and open `http://localhost:5173` — uploading an audio file there returns the mock's fixed test values instead of real results. Once you have real credentials in `.env`, don't set `$env:LLM_URL` anymore — it would override `.env` and point the app back at the (likely not running) mock server.

### 3.4 Docs site (arc42 + ADRs)

```powershell
mkdocs serve
```

Also runs on port 8000 by default — stop the app first, or use `mkdocs serve -a localhost:8001` to avoid the port clash.
