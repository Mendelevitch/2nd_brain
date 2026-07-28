# Setting up on Windows

Windows replaces the Mac in this setup. It handles three things:
1. **Cowork** — runs the automated wiki-processing routines (daily translate, weekly digest, etc.)
2. **Syncthing** — keeps your Brain folder in sync with the Pi
3. **Ollama** (optional, if you have a GPU) — runs local AI models for `/local` mode in the chat bot

---

## Part 1: Brain folder + Cowork

### Create the Brain folder structure

Open PowerShell and run:

```powershell
$brain = "$env:USERPROFILE\Brain"
@("raw","wiki","archive","insights","user","guest_chats","chats","projects","prompts") | ForEach-Object {
    New-Item -ItemType Directory -Force -Path "$brain\$_"
}
Write-Host "Brain folder created at $brain"
```

### Copy Cowork prompts

From the cloned repo:

```powershell
$repo = "C:\path\to\2nd-brain"   # wherever you cloned the repo
$brain = "$env:USERPROFILE\Brain"
Copy-Item "$repo\prompts\*" "$brain\prompts\" -Recurse -Force
Copy-Item "$repo\templates\*" "$brain\templates\" -Recurse -Force
```

### Install Cowork

Download and install [Cowork](https://cowork.ai) for Windows.

Open Cowork, point it at your Brain folder (`~/Brain`), and run `templates/setup-cowork-routines.md` once — this creates all the scheduled routines (daily translate, weekly digest, planning).

### Create your user model

Run `templates/onboarding-cowork.md` in Cowork — it interviews you and creates `user/user-model.md` and seeds your wiki.

---

## Part 2: Syncthing (sync Brain with Pi)

Syncthing keeps your Brain folder on Windows in sync with the Pi.

### Install Syncthing on Windows

Download from [syncthing.net](https://syncthing.net) — use the Windows installer. It runs as a tray app.

Open the web UI at `http://localhost:8384`.

### Add the Pi as a remote device

1. On the Pi, get the Device ID: `syncthing --device-id`
2. In Windows Syncthing UI: **Add Remote Device** → paste the Pi's Device ID
3. On the Pi's Syncthing UI, accept the connection from Windows

### Set up shared folders

| Folder | Windows path | Pi path | Direction |
|--------|-------------|---------|-----------|
| brain-raw | `~/Brain/raw` | `/brain/raw` | Pi → Windows |
| brain-wiki | `~/Brain/wiki` | `/brain/wiki` | Windows → Pi |
| brain-insights | `~/Brain/insights` | `/brain/insights` | Windows → Pi |
| brain-user | `~/Brain/user` | `/brain/user` | Windows → Pi |
| brain-guest-chats | `~/Brain/guest_chats` | `/brain/guest_chats` | Pi → Windows |

In Syncthing, "Send Only" = that side is the source; "Receive Only" = that side receives.

See [docs/setup-syncthing.md](setup-syncthing.md) for the full Syncthing guide.

---

## Part 3: Local GPU (optional)

If you have a Windows machine with a decent GPU, you can route chat bot responses to a local model via `/local` mode. This keeps conversations private and avoids API costs for heavy usage.

The setup has two parts:
1. **Ollama on Windows** — runs the local model
2. **Wake-on-LAN** (optional) — lets the Pi wake your Windows machine remotely

---

## 1. Install Ollama on Windows

Download and install from [ollama.com](https://ollama.com).

### Allow network access

By default Ollama only listens on `localhost`. To make it reachable from the Pi, you need to set an environment variable:

1. Open **System Properties → Advanced → Environment Variables**
2. Under **System variables**, click **New**:
   - Name: `OLLAMA_HOST`
   - Value: `0.0.0.0`
3. Click OK. Restart Ollama (or reboot).

Verify it's accessible from another machine:
```
curl http://<windows-ip>:11434/api/tags
```

### Pull a model

```
ollama pull gemma4:12b
```

Other options that fit in 12–16 GB VRAM:
- `gemma4:12b` — fast, good for conversation
- `qwen3:14b` — strong reasoning, supports tool calling
- `llama3.3:70b-q4` — if you have 24+ GB VRAM

---

## 2. Open Windows Firewall

Allow inbound connections on port 11434:

```powershell
New-NetFirewallRule -DisplayName "Ollama" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow
```

Or via GUI: Windows Defender Firewall → Advanced Settings → Inbound Rules → New Rule → Port → TCP 11434.

---

## 3. Configure the Pi

In your `config.py` on the Pi:

```python
OLLAMA_HOST  = "192.168.1.x"   # your Windows machine's local IP
OLLAMA_PORT  = 11434
OLLAMA_MODEL = "gemma4:12b"
WINDOWS_MAC  = ""               # fill in for Wake-on-LAN (see below)
```

Find your Windows IP: `ipconfig` → look for IPv4 Address under your active adapter.

---

## 4. Wake-on-LAN (optional)

Wake-on-LAN lets the Pi send a magic packet to boot your Windows machine when you use `/local`. You can then keep the PC off when not in use.

### Enable WoL in Windows

1. Open **Device Manager → Network Adapters**
2. Right-click your ethernet adapter → **Properties → Power Management**
3. Enable: **Allow this device to wake the computer** and **Only allow a magic packet to wake the computer**
4. Also enable in BIOS/UEFI: look for **Wake on LAN** or **Power On By PCI-E** under power settings

### Get your MAC address

```
ipconfig /all
```

Look for **Physical Address** next to your ethernet adapter (format: `AA-BB-CC-DD-EE-FF`).

Add it to `config.py`:
```python
WINDOWS_MAC = "AA:BB:CC:DD:EE:FF"   # use colons, not dashes
```

Install the WoL library on the Pi:
```bash
pip3 install wakeonlan --break-system-packages
```

### Test WoL from the Pi

```python
import wakeonlan
wakeonlan.send_magic_packet("AA:BB:CC:DD:EE:FF")
```

---

## 5. Using /local in the chat bot

Once configured:

- Type `/local` in your Telegram chat with the bot
- The bot checks if Ollama is reachable. If not, it sends a WoL packet and waits up to 90 seconds for the machine to boot.
- Responses come from your local model instead of Claude.
- `/local` is a toggle — type it again to switch back to cloud.

The local model has access to the same web search tools as cloud mode (via `/browse` or auto-detected keywords like "поищи", "search for", etc.).

---

## Notes

- The Pi and Windows machine need to be on the same network, or connected via a VPN (e.g. Tailscale).
- With Tailscale, use the Tailscale IP of the Windows machine as `OLLAMA_HOST`.
- WoL only works over ethernet (not Wi-Fi) and only on the local network — not over Tailscale.
- Restart the chat bot after editing `config.py`: `sudo systemctl restart mind-bot`
