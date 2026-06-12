# Syncthing setup

Syncthing keeps your wiki and user model in sync between the Pi and your Mac. Raw captures flow Pi → Mac; wiki edits and user model flow Mac → Pi.

## Install on Pi

```bash
sudo apt install syncthing
sudo systemctl enable syncthing@pi
sudo systemctl start syncthing@pi
```

## Access the Pi web UI via SSH tunnel

```bash
# On your Mac terminal:
ssh -L 8385:127.0.0.1:8384 pi@<your-pi-ip>
# Then open: http://localhost:8385
```

## Install on Mac

Download from [syncthing.net](https://syncthing.net) or:
```bash
brew install syncthing
brew services start syncthing
```

## Pair the devices

1. Open both web UIs
2. Add Remote Device — paste the Pi's Device ID into the Mac UI (and vice versa)
3. Accept the pairing request on each side

## Add folders

Create one shared folder for each of the following. Set the direction as noted.

| Folder | Pi path | Mac path | Direction |
|---|---|---|---|
| brain-raw | `<BRAIN_DIR>/raw` | `Brain/raw` | Pi → Mac (Send Only on Pi) |
| brain-wiki | `<BRAIN_DIR>/wiki` | `Brain/wiki` | Mac → Pi (Send Only on Mac) |
| brain-insights | `<BRAIN_DIR>/insights` | `Brain/insights` | Mac → Pi |
| brain-user | `<BRAIN_DIR>/user` | `Brain/user` | Mac → Pi |
| brain-guest-chats | `<BRAIN_DIR>/guest_chats` | `Brain/guest_chats` | Pi → Mac |

## Enable versioning (recommended)

For each folder on the Pi side, enable **Trash Can File Versioning** (30 days). This keeps deleted or overwritten files in `.stversions/` — useful if Cowork accidentally clobbers a wiki file.

In the Syncthing UI: Folder → Edit → Versioning → Trash Can → 30 days.
