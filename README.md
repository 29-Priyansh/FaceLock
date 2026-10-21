# FaceLock

Locks Windows (same as Win+L) when the webcam stops seeing **your** face.
Runs from the system tray until you shut down, restart or sign out. Works offline.

## Use it

1. Double-click `dist\FaceLock\FaceLock.exe` (make a desktop shortcut to it).
   No console window opens; a padlock icon appears in the tray.
2. First run opens **Enroll**: press Start and follow the five head-pose prompts (~10 s).
3. Then run tray -> **Improve face recognition...** (~70 s) a few times: once now, and again
   in other lighting (evening, lamp on/off), with/without glasses, in another seat. Each run
   only adds what your profile does not know yet, and shows how many samples were new.
4. Right-click the tray icon for everything else.

| Tray colour | Meaning |
|---|---|
| green | You are recognised |
| amber | Countdown running |
| grey | Paused / locked / screen off |
| red | Not enrolled, or camera in use by another app |

### Behaviour
- **Your face recognised** anywhere in the frame, at any angle your profile covers (other
  people in view are ignored) -> stays unlocked. Identity is decided by your face data only.
- **Looking away** (keyboard, phone, side monitor, head turned) -> still recognised, as long
  as the camera can see part of your face *and* you have scanned that angle with
  **Improve face recognition**. Faces are detected on the full 640x480 frame with a
  permissive detector setting, so turned and tilted faces are found.
- **You not recognised** -> one quick re-check (so a single missed frame does nothing),
  then a small "Locking in 10" box appears bottom-right -> Windows locks at 0. Being
  recognised again cancels it. The box never takes keyboard focus.
- **Developer mode** (on by default, Settings) adds a *Cancel* button that pauses monitoring
  for 5 minutes.
- **Another app uses the camera** (Teams, Zoom, Camera app...) -> FaceLock steps aside,
  does not lock, and resumes automatically once the camera is free.
- **Locked / screen off / sleep / hibernate** -> camera fully released, no CPU used.
  Monitoring resumes after you unlock.
- FaceLock never asks Windows to stay awake, so sleep and screen-off timers work as normal.

### Tray menu
Pause (5 min / 30 min / 1 h / until resumed), Resume, **Improve face recognition**,
Enroll face (start over), Delete face data, Diagnostics (live preview: green box = you,
red = not recognised, with scores, CPU, RAM), Settings, Open log folder, Quit.

### Improve face recognition
A guided ~75 s session: look straight, **slowly** turn your head all the way left and right,
keyboard/phone, up and lean back, far left/right edges, chin on hand, then move naturally for
20 s. The live box is **green** when the current angle is already recognised and **amber**
while it is being learned. Keep turning slowly through amber angles: each new sample links
to the previous one, so the profile grows outward step by step. Scanning uses exactly the
monitor's face detector, so every angle captured here is recognised afterwards. Every 0.3 s a
face sample is taken and:
- **kept** if it is new (not > 0.93 similar to anything already in the profile),
- **skipped as already known** if the profile already covers that pose,
- **rejected** if it does not look like you (< 0.30 similar to your profile and this
  session's samples) - this keeps other people out of your profile.

Run it as often as you like. The profile holds up to 400 samples; beyond that the most
redundant ones are dropped. Enroll (start over) replaces everything.

### Settings (`%LOCALAPPDATA%\FaceLock\config.json`)
| Key | Default | |
|---|---|---|
| `lock_after_s` | 10 | countdown length |
| `sample_interval_s` | 3 | time between checks while you are present |
| `match_threshold` | 0.363 | SFace cosine similarity; raise to be stricter |
| `camera_index` | 0 | |
| `dev_mode` | true | Cancel button on the countdown |
| `cancel_pause_min` | 5 | |

## How it works

- **Camera**: this laptop's webcam cannot be streamed by two apps at once (tested), so
  FaceLock never holds it open while you are present. Every 3 s it opens the camera with
  DirectShow (~0.2 s), reads 1-2 frames and releases it. During the countdown it keeps the
  camera open (max 10 s) so it notices you quickly. Before every grab it checks the Windows
  camera-usage registry (`ConsentStore\webcam`) and stays away if another app is streaming.
  The camera LED therefore blinks briefly every few seconds; that is expected.
- **Models** (OpenCV Zoo, bundled, run on CPU, single-threaded):
  YuNet face detector (MIT, 0.2 MB, ~23 ms per 640x480 frame) and SFace recogniser
  (Apache-2.0, 37 MB, ~13 ms per face) on an i7-10850H. Every detected face is compared with
  every sample in your profile; the best similarity >= `match_threshold` means "you".
- **Lock**: `LockWorkStation()`. Lock/unlock, display on/off, suspend/resume and shutdown
  arrive through a hidden window (`WTSRegisterSessionNotification`,
  `RegisterPowerSettingNotification`, `WM_POWERBROADCAST`). The lock state is also polled every
  2 s as a safety net.
- **Data**: `%LOCALAPPDATA%\FaceLock\profile.bin` holds only face *embeddings* (128 numbers
  per sample, about 20 samples), encrypted with Windows DPAPI for your account. No images
  are ever saved. Nothing is sent over the network.

## Measured on this laptop (Dell Precision 7550, Windows 11 26300)

| | Result |
|---|---|
| CPU while present (3 s interval) | ~0.5 % of the machine (30 s headless run) |
| Memory | ~150 MB working set (headless run); more while the Enroll/Diagnostics window is open |
| Install folder | 168 MB (OpenCV 71 MB + SFace model 37 MB make up most of it) |
| Detection + recognition | 4 ms + 13 ms per frame |
| Camera open (DirectShow) | ~0.2 s |

Re-measure on your own runs with `tools\bench.py` (see below).

## Known limitations (read these)

- **No liveness detection.** A photo or video of you held up to the camera within the
  10 s countdown could keep the laptop unlocked. The IR camera is not reachable through
  OpenCV on this hardware, so this was not built. Once Windows is locked, only Windows
  sign-in can unlock it; FaceLock never unlocks anything.
- **A face that is not visible cannot be recognised.** Looking away works when the camera
  still sees part of your face (side view, looking down, chin on hand) and you have scanned
  that angle. Turning your back to the camera, a full side profile beyond what the detector
  can find, or a hand/cup covering most of the face counts as "not recognised". The
  countdown then starts after the quick re-check, and seeing you again within the 10 s
  cancels it. Diagnostics shows live which angles are green.
- **No auto-lock while another app has the camera** (e.g. during a video call), by design.
  Windows' own screen-timeout lock still applies.
- **Camera unplugged or failing** is treated the same way (paused, not locked).
- Lookalikes or relatives might score above the threshold. Check scores in Diagnostics
  and raise `match_threshold` if needed.
- DPAPI protects the profile from other Windows accounts and offline copies, not from
  malware running as you. A tampered profile is rejected (FaceLock never fails open).
- Windows Hello is not used: there is no supported API that lets an app run continuous
  identity checks against Hello.

## Develop / build

```powershell
.venv\Scripts\python -m facelock --debug    # run from source (log also printed to the console)
.venv\Scripts\python -m pytest tests        # unit tests
powershell -ExecutionPolicy Bypass -File build.ps1   # -> dist\FaceLock\FaceLock.exe
.venv\Scripts\python tools\camera_probe.py  # camera indices, open latency, model timings
.venv\Scripts\python tools\bench.py --minutes 10 --label present   # CPU/RAM of a running FaceLock
```

Requires Windows 10 1809+ / Windows 11, x64. The build needs the python.org Python 3.11
(not conda: conda's numpy/MKL inflates the exe). Note: `opencv-python-headless` 4.13
lacks the MSMF backend, so the full `opencv-python` wheel is used.

Log: `%LOCALAPPDATA%\FaceLock\facelock.log` (1 MB, rotated).
To remove all data: tray -> Delete face data, then delete `%LOCALAPPDATA%\FaceLock`.
