# piscout

[![ci](https://github.com/MilkteaTW1/piscout/actions/workflows/ci.yml/badge.svg)](https://github.com/MilkteaTW1/piscout/actions/workflows/ci.yml) [![release](https://img.shields.io/github/v/release/MilkteaTW1/piscout)](https://github.com/MilkteaTW1/piscout/releases) [![license](https://img.shields.io/github/license/MilkteaTW1/piscout)](LICENSE) ![platform](https://img.shields.io/badge/platform-Windows-0078D6)

**English** · [繁體中文](#繁體中文)

**[⬇ Download piscout-setup.exe | 下載安裝程式](https://github.com/MilkteaTW1/piscout/releases/latest/download/piscout-setup.exe)** (Windows, free, MIT)

Website: [inkacuity.com/projects/piscout](https://inkacuity.com/projects/piscout) · 專案介紹頁

> **Find and manage your Raspberry Pis from one Windows window.**
> Scan the network, open an SSH terminal, see the desktop, check temperature and load of every Pi.
> No router admin page, no separate tools.

`raspberry-pi` `raspberry-pi-os` `network-scanner` `lan-discovery` `fleet-management`
`ssh-terminal` `remote-desktop` `vnc` `sd-card` `flasher` `imager` `netboot` `pxe`
`mdns` `fastapi` `pywebview` `windows` `desktop-app`

![piscout demo: scan, connect, built-in terminal](docs/demo.gif)

![piscout features: scan, terminal suggestions, drag-and-drop, flashing, MCP](docs/promo.gif)

<sub>[Watch the 18-second overview video](docs/promo.mp4) (animated, not a screen recording)</sub>

<sub>Recorded with a simulated device and shell (`PISCOUT_DEMO=1`, see [docs/DEMO.md](docs/DEMO.md)); no real Raspberry Pi appears in it.</sub>

## What you get

Tested on a real Raspberry Pi 3 Model B (Raspberry Pi OS Bookworm):

- **Find** – scans the LAN on launch and recognizes Raspberry Pis, no IP hunting
- **Add by hand** – if the scan cannot see your Pi (router AP isolation, another subnet), type its IP or name (`raspberrypi.local`) and connect directly; only private-network addresses are accepted
- **Add-ons** – turn a Pi into a NAS (Samba), install Docker, fail2ban or automatic security updates in one click; official apt packages only, and you see exactly what will happen before it runs
- **Connect** – click *Connect*, enter the login, and get an SSH terminal inside the app
- **See the desktop** – view and control the Pi's desktop through the SSH tunnel
- **Always-on status bubble** – a small panel in the top-right corner shows the Pi's temperature, load, memory, disk and uptime; the agent is installed automatically after the first connection, and you can collapse or drag the bubble anywhere
- **Health check in plain words** – on the *System info* tab: under-voltage (the #1 beginner problem), overheating, SD card errors, full disk, low memory, failed services, wrong clock, each with advice. Read-only
- **Quick setup** – one click to enable I2C / SPI and time sync, install common tools (htop, git, tree, ncdu, curl) or expand the filesystem. Only a fixed list of actions, nothing arbitrary
- **Suggestions while you type** – the terminal shows a VS Code-style popup with commands, files and folders as you type; Up/Down to choose, Tab to accept, Esc to close
- **Fast start** – the Pis seen last time appear immediately and the scan runs in the background
- **Drag and drop files** – drop files onto the window while connected: on the terminal tab they go to the shell's current folder, on the remote desktop tab to the Pi's Desktop folder. Existing files are never overwritten (`name (1).ext`). Folders are not supported yet
- **Manage several** – temperature / load / memory of every Pi at a glance; reboot, shut down or update several at once
- **Remembers you** – logins are encrypted with Windows DPAPI and the model is detected automatically
- **Multilingual** – ships with 中文 / English, follows the system language, switchable at any time. **Adding a language needs no code**: drop a JSON file into `piscout/static/locales/` ([how](docs/TRANSLATING.md))

Also included, **use with care**:

- **SD card flashing** from this computer, official Raspberry Pi OS images verified with SHA-256, with a recommended OS for your model. Tested on real hardware: flashed a Raspberry Pi 3 Model B, it booted and the configured login worked
- **Remote re-imaging (advanced, off by default)** – write a new OS to a Pi's own SD card without taking it out. It has real risks and a documented incident, read [Known risks](#known-risks) first

It is an early version, see [Status](#status-and-roadmap) for exactly what is verified.

## Screenshots

| Devices | Flash OS (recommended image per model) |
|---|---|
| ![Devices tab](docs/devices.png) | ![Flash OS tab](docs/flash.png) |

The Devices screenshot uses the simulated device; the Flash OS screenshot uses the real official OS list.

## Usage

Download `piscout-setup.exe` from [Releases](../../releases) and run it: it installs per user (no administrator
rights), adds a Start menu entry and an optional desktop shortcut, and the installer follows your Windows language.
Prefer no installer? Build `piscout.exe` yourself, see below.
When a newer release is published, the app tells you and updates itself with one click (*Update now*, checksum
verified). Turn the check off with *Don't remind me* or `PISCOUT_NO_UPDATE_CHECK=1`; see [PRIVACY](docs/PRIVACY.md).
Normal use (scanning, terminal, remote desktop, overview) does **not** need administrator rights.
Only *local SD card flashing* does, and the app offers a "Restart as administrator" button when
you get there. The file is not code-signed, so SmartScreen may warn you ("More info → Run anyway").

A **winget** package has been submitted and is under review ([microsoft/winget-pkgs#451835](https://github.com/microsoft/winget-pkgs/pull/451835)); until it is merged, install from Releases. Microsoft Store packaging is prepared in [`packaging/`](packaging/). The exe is not code-signed yet, hence the SmartScreen prompt.

**Remote re-imaging requires a Pi that still boots and has SSH enabled.** A completely
blank SD card cannot be seen on the network by any software; flash it once from this
computer, after which it can be re-imaged remotely.

How remote re-imaging works:

1. The PC downloads the official image and writes the boot settings straight into the image's boot partition while decompressing
2. `dd`, `dash` and `sha256sum` (with their libraries) are copied into the Pi's RAM (`/dev/shm`), so nothing depends on the SD card that is about to be overwritten
3. The image is streamed over SSH to the boot disk
4. The first part is read back and hashed; **the Pi only reboots if it matches**

> Overwriting the disk of a running system is inherently risky. If power or the network
> drops mid-write, the card will not boot and must be re-flashed from a computer.

## Run from source

Requires Python 3.9+, Windows 10/11 (WebView2 is built in on Windows 11).

```bash
git clone https://github.com/<your-account>/piscout.git
cd piscout
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_gui.py
```

Build the app: `pip install pyinstaller` then `build.bat` (the result is the folder `dist\piscout`). Run tests: `pytest`.

### Scan from the command line (Windows, macOS, Linux)

```bash
python -m piscout scan                       # Raspberry Pis on this machine's /24
python -m piscout scan --network 10.0.0.0/24 --all --json
```

It needs only Python 3.9+ and the `piscout` folder (no pip packages; `zeroconf`, if installed, adds host names). It sweeps port 22, then reads the ARP table (`arp -a`, or `ip neigh` on Linux systems without `arp`). It does not need administrator rights.

### Add-ons

The *Add-ons* section of a Pi's info page installs and removes common services. Each add-on is a fixed entry in [`piscout/addons.py`](piscout/addons.py): the screen can only pick *which* one and *install/remove*, it never sends free-form commands. Scripts use apt packages only (no `curl | bash`), can be run again safely, and removing an add-on keeps your data. Installing needs the Pi's sudo, so log in with the password (or a key plus passwordless sudo, except the NAS add-on which needs the password to create the Samba account).

To add your own, append one dict to `CATALOG` (`id`, `title`, `desc`, `steps`, `ports`, `check`, `install`, `remove`, `after`) and add the English text to `locales/en.json`; the field list is documented at the top of `addons.py`.

## How it differs from other tools

| Tool | Discovery | Terminal | Remote desktop | Flash | Re-image without removing the card |
|---|---|---|---|---|---|
| [Raspberry Pi Imager](https://github.com/raspberrypi/rpi-imager) | | | | local SD card | |
| Angry IP Scanner / nmap scripts | IP list only | | | | |
| Raspberry Pi Connect | | | cloud, account needed | | |
| **piscout** | ✓ | ✓ | ✓ | ✓ | ✓ |

piscout does not replace Imager. Imager writes an image to a card; piscout handles what
comes after the card is already in the Pi: find it, log in, see its screen, change its OS.

## Known risks

### Remote re-imaging can leave a card unbootable

This happened during the first real-hardware test, so it is documented here on purpose.

**What happened.** The app was closed while the image was still streaming to the Pi. The card was left partly overwritten. The Pi kept running from memory for a while (ping, the agent and VNC still answered) but every new SSH connection was dropped immediately, and after a power cycle it never came back on the network. The only fix was to re-flash the card from a computer with a card reader.

**Why it can happen.** Remote re-imaging overwrites the disk of a system that is running. Anything that interrupts the transfer (closing the app, the computer sleeping, a network or power drop) leaves a half-written card, and a Pi in that state cannot be repaired remotely.

**What the app does about it now**

- Remote re-imaging is an **advanced feature, off by default**. It is only enabled after you tick the switch on the *Flash OS* tab, and the backend refuses the request without that confirmation
- You must also confirm that you have a card reader or a spare SD card
- The computer is kept awake during the transfer and SSH keep-alive is enabled
- The image checksum is verified before anything is written, the first part of the card is read back and hashed, and **the Pi only reboots if it matches**
- If a failure happens after writing started, the app says the card needs to be re-flashed from a computer

**What you should do.** Use it only with a card reader or spare card within reach, on stable power, ideally with the PC on Ethernet and plugged in. Do not close the app until it reports success. If you do not have a reader, use *An SD card inserted in this computer* instead.

### Other things to know

- A completely blank card cannot be reached over the network by any software
- SSH host keys are trusted on first use (see Security notes)
- Remote desktop starts an unauthenticated VNC bound to `127.0.0.1` on the Pi while a session is open

## FAQ

**How do I find the IP address of a Raspberry Pi on my network from Windows?**
Open piscout; it scans your /24 on launch and flags Raspberry Pis by MAC prefix and mDNS name.

**Can I get an SSH terminal and a remote desktop for my Pi in one app?**
Yes. After logging in, the terminal (xterm.js) and the desktop (noVNC over an SSH tunnel) are tabs in the same window. The desktop needs Raspberry Pi OS with the Wayland desktop (wayvnc); Lite has no desktop.

**Can I reinstall Raspberry Pi OS without taking the SD card out?**
Yes, if the Pi still boots and SSH is enabled: piscout streams the official image over SSH to the Pi's own boot disk and verifies it before rebooting. It cannot help a blank card that has never booted; flash that one once from your computer.

**How does it choose which OS to install?**
It reads the model (from `/proc/device-tree/model` after login) and picks the matching official image: the 64-bit desktop edition for Pi 3 and newer, the 32-bit edition for older boards, or the Lite edition if you choose a terminal-only setup. It refuses an image the board cannot run.

**Is it a replacement for Raspberry Pi Imager?**
No. Use Imager to write a card in your computer. piscout is for managing Pis that are already on the network, and also includes a local flasher for convenience.

**Does it work on Linux or macOS?**
The app and the local flasher are Windows-only. The LAN scan also runs on Linux and macOS as a command-line tool with only the Python standard library: `python -m piscout scan` (see "Scan from the command line" below). The terminal and remote-flash modules are plain Python and could be ported.

**Is it safe to expose?**
It binds to `127.0.0.1` only. Do not publish its port. See the security notes above.

## Security notes

- The UI service binds to `127.0.0.1` only; API calls need a per-launch random token, and terminal/desktop sessions use one-time tokens
- Passwords are stored with Windows DPAPI (bound to your Windows account and PC)
- SSH host keys are accepted on first use (`AutoAddPolicy`); harden this if you use it beyond a home LAN
- Remote desktop starts an unauthenticated VNC bound to `127.0.0.1` on the Pi, reachable only through the SSH tunnel, and stops it when the session closes
- Boot-settings passwords are stored hashed; the Wi-Fi password is plain text in the boot partition (format limitation)
- Only private IPs are accepted; images are only downloaded from Raspberry Pi domains
- Only scan networks you own

## Let an AI assistant use your Pis (MCP)

piscout includes a tiny MCP server (standard library only) so an AI assistant can list your Pis and run commands on them.
Logins come from piscout's saved logins, the assistant never sees the password, and only private LAN addresses are accepted.
Output is trimmed to keep token use low.

```json
{ "mcpServers": { "piscout": { "command": "C:\path\to\piscout.exe", "args": ["--mcp"] } } }
```

(From source: `"command": "python", "args": ["-m", "piscout.mcp"]`.)

Tools: `pi_list` (scan the LAN), `pi_run` (run a shell command) and `pi_health` (read-only health check). Save a login for the Pi in piscout first.
Only enable this for assistants you trust: they can run any command as that user.

## Translations

![Translation status per language](docs/i18n-status.svg)

Regenerate the chart with `python tools/i18n_status.py` after a locale changes.

piscout ships with 中文 and English. **Adding a language needs no code**: it is a single JSON file in
`piscout/static/locales/`. Run `python tools/i18n_check.py --new ja 日本語` to get a template, fill it in (anything
left empty shows English), check it with `python tools/i18n_check.py`, and open a pull request.
The same file also translates the Windows installer (`installer` section; the installer follows the user's Windows
language, and Inno Setup's built-in languages need only 3 short texts). Full guide: [docs/TRANSLATING.md](docs/TRANSLATING.md). **Help wanted:** [add your language (#11)](https://github.com/MilkteaTW1/piscout/issues/11).

## Need something custom?

Custom features, integrations or setup help are available. See [墨鋒 Inkacuity](https://inkacuity.com/projects/piscout) or email [ink@inkacuity.com](mailto:ink@inkacuity.com).

## Status and roadmap

**Tested on real hardware** (Raspberry Pi 3 Model B Rev 1.2, Raspberry Pi OS Debian 12 "Bookworm"):

| Feature | Result |
|---|---|
| LAN scan and Raspberry Pi detection | works |
| SSH login, system info, agent install, overview | works |
| Built-in terminal (run commands) | works (tested by the author) |
| Remote desktop (wayvnc through the SSH tunnel) | works (tested by the author) |
| Drag-and-drop upload into the terminal's current folder | works (tested by the author) |
| Typing suggestions popup in the terminal | works (tested by the author) |
| Local SD card flashing (download, write, read-back verify, boot settings) | works: the Pi booted and the configured user could log in |

**Tested without a real device:** image pre-processing and boot-settings injection (also run against the real
Raspberry Pi OS 64-bit image: source SHA-256 verified, `user-data` written into the boot partition), the Pi-side
write script's flow and verification (simulated locally), unit tests.

Have a different model or OS version? Please [report a compatibility result](../../issues/new/choose); it makes this table better.

**Not yet verified on real hardware:** a completed remote write (the first real attempt was interrupted, see Known risks). Local SD flashing was verified on a Raspberry Pi 3 Model B only; other models are covered by the official image list but untested.

- [ ] Validate the remaining items on real devices and publish the results per model
- [ ] Network install (netboot) for blank cards: works out of the box on Pi 3B+, needs a one-time bootloader change on Pi 4/5
- [ ] Remote desktop for X11 / RealVNC systems
- [ ] SSH host-key pinning
- [ ] Linux / macOS local flashing

---

*piscout is an independent open-source project. It is not affiliated with, endorsed by or sponsored by Raspberry Pi Ltd. Raspberry Pi is a trademark of Raspberry Pi Ltd.*

---

<a id="繁體中文"></a>

# piscout（繁體中文）

[English](#piscout) · **繁體中文**

> Raspberry Pi 區網管理工具：自動掃描、內建 SSH 終端機、遠端桌面、遠端重灌系統。
> A Windows desktop tool to discover, SSH into, view the desktop of, and re-image Raspberry Pis on your LAN.

> **在 Windows 的一個視窗裡，找到並管理你的樹莓派。**
> 掃描網路、開 SSH 終端機、看桌面、一次看多台的溫度與負載，不用翻路由器後台，也不用裝一堆工具。

`raspberry-pi` `raspberry-pi-os` `network-scanner` `lan-discovery` `fleet-management`
`ssh-terminal` `remote-desktop` `vnc` `sd-card` `flasher` `imager` `netboot` `pxe`
`mdns` `fastapi` `pywebview` `windows` `desktop-app`

![piscout 示範：掃描、連線、內建終端機](docs/demo.gif)

![piscout 功能總覽：掃描、補齊選單、拖曳傳檔、燒錄、MCP](docs/promo.gif)

<sub>[觀看 18 秒功能總覽影片](docs/promo.mp4)（動畫，不是螢幕錄影）</sub>

<sub>示範影片使用模擬的裝置與終端機錄製（`PISCOUT_DEMO=1`，說明見 [docs/DEMO.md](docs/DEMO.md)），畫面中沒有真實的樹莓派。</sub>

## 你會得到什麼

已在真實的 Raspberry Pi 3 Model B（Raspberry Pi OS Bookworm）上測試：

- **找到**：一打開就掃區網並辨識樹莓派，不用再找 IP
- **連線**：點「連線」輸入帳密，直接在程式裡開 SSH 終端機
- **看桌面**：經 SSH 通道查看並操作樹莓派的桌面
- **常駐狀態泡泡**：右上角的小面板隨時顯示樹莓派的溫度、負載、記憶體、磁碟與開機時間；第一次連線後會自動安裝 agent，泡泡可以收合，也能拖到畫面任何位置
- **白話健康檢查**：在「系統資訊」分頁，檢查電源不足（新手最常見的問題）、過熱、SD 卡錯誤、磁碟快滿、記憶體不足、服務啟動失敗、時間不準，並附上建議；只讀取，不改任何東西
- **一鍵快速設定**：一鍵開啟 I2C / SPI 與時間同步、安裝常用工具（htop、git、tree、ncdu、curl）、擴展檔案系統；只提供固定清單裡的動作，不能執行任意指令
- **擴充套件**：一鍵把樹莓派變成 NAS（Samba）、裝 Docker、fail2ban 或自動安全更新；只用 apt 官方套件，執行前會先列出要做什麼
- **輸入時的補齊選單**：在終端機打字時，像 VS Code 一樣跳出指令、檔案、資料夾的候選；上下鍵選、Tab 接受、Esc 關閉
- **啟動很快**：一打開就先顯示上次的樹莓派，掃描在背景進行
- **拖曳傳檔**：連線後把檔案拖進視窗，在終端機分頁會傳到 shell 目前所在的資料夾，在遠端桌面分頁會傳到樹莓派的桌面資料夾；同名檔案不會被覆蓋（自動改成 `名稱 (1).副檔名`）；目前不支援整個資料夾
- **管理多台**：一眼看到每台的溫度、負載、記憶體，並可批次重開機、關機、更新套件
- **記住帳密**：以 Windows DPAPI 加密儲存，並自動偵測型號
- **多語言介面**：內建中文 / English，自動偵測系統語言，也可手動切換。**新增語言不用改程式**：把一個 JSON 檔放進 `piscout/static/locales/` 即可（[做法](docs/TRANSLATING.md)）

另外也有，**請小心使用**：

- **SD 卡燒錄**：把官方 Raspberry Pi OS（SHA-256 校驗）燒到插在這台電腦上的 SD 卡，並依型號給出建議。已在真機測試：燒錄 Raspberry Pi 3 Model B 後可開機，並能用設定的帳號登入
- **遠端重灌（進階功能，預設關閉）**：SD 卡不用拔，直接把新系統寫進 Pi 的卡。有實際風險，也發生過事故，請先看[已知風險](#已知風險)

目前是早期版本，確切驗證了哪些，請看「驗證狀況與還沒做的」。

## 使用

到 [Releases](../../releases) 下載 `piscout-setup.exe` 執行即可：安裝在你自己的帳號下（不需要系統管理員權限），
會建立開始功能表項目與可選的桌面捷徑，安裝畫面會跟著你的 Windows 語言。
不想安裝也可以依下方「從原始碼執行」自行打包單檔 `piscout.exe`。
有新版本發佈時，程式會提醒你，按「立即更新」就在程式裡自動更新（會核對 SHA-256）。可選「不再提醒」或設定 `PISCOUT_NO_UPDATE_CHECK=1` 關閉，詳見 [隱私權政策](docs/PRIVACY.md)。
一般使用（掃描、終端機、遠端桌面、總覽）不需要系統管理員權限；只有「本機燒錄」寫入 SD 卡時，才會請你以系統管理員身分重新啟動。

> 檔案沒有簽章，SmartScreen 可能警告，按「其他資訊 → 仍要執行」。

**winget** 套件已送出審核（[microsoft/winget-pkgs#451835](https://github.com/microsoft/winget-pkgs/pull/451835)），合併之前請從 Releases 下載；Microsoft Store 的上架素材已備妥於 [`packaging/`](packaging/)。目前尚未簽章，所以會看到 SmartScreen 提示。

### 連線、終端機、遠端桌面

開啟後會自動掃描。找到的樹莓派按「連線」，輸入帳號密碼，就會在程式裡開出終端機。
上方可以切換：

- **終端機**：完整的 xterm，支援縮放視窗
- **遠端桌面**：在 Pi 上啟動只監聽 `127.0.0.1` 的 wayvnc，再經 SSH 通道轉到程式裡顯示。
  需要 Raspberry Pi OS 桌面版（Wayland），Lite 版沒有桌面所以不行
- **系統資訊**：型號、溫度、記憶體、磁碟，並可安裝監控用的 agent

勾選「記住」時，帳密會以 Windows DPAPI 加密存在這台電腦（只有同一個 Windows 帳號解得開）；沒勾就只存在這個視窗的記憶體裡，關閉連線就沒了。可以用「清除已存帳密」全部刪除。

### 遠端重灌（SD 卡留在 Pi 上）

1. 到「燒錄系統」，選區網裡的樹莓派，填它**目前**的登入帳密
2. 按「讀取這台的型號與系統」，會自動選對型號並顯示最佳建議
3. 設定重灌後的主機名稱、帳號、密碼、Wi-Fi
4. 按兩次「開始燒錄」（第一次只是確認），等 10–30 分鐘，Pi 會自己重新開機

**前提：Pi 必須還開得起來、而且開著 SSH。** 完全空白的 SD 卡在網路上根本看不到，
沒有任何軟體能遠端連上它。這種情況請改用「插在這台電腦上的 SD 卡」。

運作方式：

1. 電腦端下載官方映像，解壓縮時把開機設定直接寫進映像裡的 boot 分割區
2. 把 `dd`、`dash`、`sha256sum` 連同函式庫複製到 Pi 的記憶體（`/dev/shm`），
   之後只用記憶體裡的程式，不再依賴會被覆蓋的 SD 卡
3. 映像串流經 SSH 寫入 Pi 的開機磁碟
4. 讀回前段資料算 SHA-256，**一致才重新開機**；不一致就停下來並報錯

> 這是在「正在執行的系統」上覆寫它自己的磁碟，天生有風險。寫到一半斷電或斷網，
> 那張卡就開不了機，得拔下來用電腦重燒。請在穩定的電源與網路下進行。

### 本機燒錄

「燒錄系統」選「插在這台電腦上的 SD 卡」。只列出 USB/SD 類的可移除磁碟，
不會列出系統碟，也不會列出超過 512 GB 的磁碟。

### 擴充套件

樹莓派資訊頁裡的「擴充套件」可以一鍵安裝、移除常見服務。每一個都是 [`piscout/addons.py`](piscout/addons.py) 裡寫死的項目：畫面只能選「哪一個」和「安裝 / 移除」，不會送任意指令。腳本只用 apt 的官方套件（不跑 `curl | bash`），可以重複執行，移除時不會刪你的資料。安裝需要樹莓派的 sudo，所以請用密碼登入（用金鑰登入也可以，但要這個帳號 sudo 不需密碼；NAS 要用密碼來建立 Samba 帳號，一定要密碼登入）。

想加自己的：在 `CATALOG` 加一筆（`id`、`title`、`desc`、`steps`、`ports`、`check`、`install`、`remove`、`after`），再把英文寫進 `locales/en.json`；欄位說明在 `addons.py` 開頭。

## 和其他工具的差別

| 工具 | 掃描 | 內建終端機 | 遠端桌面 | 燒錄 | 遠端重灌（不拔卡） |
|---|---|---|---|---|---|
| [Raspberry Pi Imager](https://github.com/raspberrypi/rpi-imager)（官方） | | | | 本機 SD 卡 | |
| Angry IP Scanner、各種 nmap 腳本 | ✓ 只列 IP | | | | |
| [LabLink](https://github.com/X9X0/LabLink) 等 Pi 掃描工具 | ✓ | | | | |
| Raspberry Pi Connect（官方） | | | ✓ 需帳號、走雲端 | | |
| **piscout** | ✓ | ✓ | ✓ | ✓ | ✓ |

piscout 不是要取代 Imager：Imager 是把映像寫進一張卡，piscout 處理的是「卡已經在
Pi 上」之後的事——找到它、連進去、看畫面、換系統。網路開機安裝（netboot）的相關
專案可以參考 [pipxe](https://github.com/ipxe/pipxe)、
[rpi-pxe-server](https://github.com/beta-tester/install-pxe-server)，
這部分 piscout 還在規劃中。

## 已知風險

### 遠端重灌可能讓卡變成開不了機

這件事在第一次真機測試時發生了，所以刻意寫在這裡。

**發生了什麼。** 映像還在傳輸時程式被關掉，卡被覆寫到一半。樹莓派有一段時間還靠記憶體運作
（ping、agent、VNC 都還有回應），但每個新的 SSH 連線都被立刻切斷，重新通電後再也沒有回到網路上。
唯一的解法是把卡拿到有讀卡機的電腦上重燒。

**為什麼會這樣。** 遠端重灌是在「執行中」的系統上覆寫它自己的磁碟。任何中斷（關閉程式、電腦睡眠、
斷網、斷電）都會留下寫了一半的卡，而且這種狀態無法從遠端修復。

**現在程式做了哪些防護**

- 遠端重灌是**進階功能，預設關閉**，要在「燒錄系統」頁勾選開關才會啟用；後端沒有收到確認也會拒絕
- 還必須確認你有讀卡機或備用的 SD 卡
- 傳輸期間禁止電腦睡眠，並啟用 SSH 保持連線
- 寫入前先校驗映像，寫完讀回前段資料算 SHA-256，**一致才會重新開機**
- 如果在開始寫入之後失敗，會明確提示這張卡要拿到電腦上重燒

**你該怎麼做。** 只在讀卡機或備用卡就在手邊、電源穩定的時候使用，最好電腦接網路線並插著電源。
程式回報成功之前不要關掉它。沒有讀卡機的話，請改用「插在這台電腦上的 SD 卡」。

### 其他要注意的

- 完全空白的卡在網路上看不到，沒有任何軟體能遠端連上它
- SSH 的 host key 是「第一次連線就信任」（見安全注意事項）
- 開著遠端桌面連線時，Pi 上會有一個只聽 `127.0.0.1`、沒有密碼的 VNC

## 常見問題

**Windows 上怎麼找到區網裡樹莓派的 IP？**
打開 piscout 就會自動掃描 /24 網段，用 MAC 前綴與 mDNS 名稱標出樹莓派。

**能在同一個程式裡開 SSH 終端機和遠端桌面嗎？**
可以。登入後終端機（xterm.js）和桌面（noVNC，走 SSH 通道）是同一個視窗的分頁。
遠端桌面需要 Raspberry Pi OS 桌面版（Wayland / wayvnc），Lite 沒有桌面。

**不拔 SD 卡可以重灌系統嗎？**
可以，前提是 Pi 還開得起來而且開著 SSH：piscout 會把官方映像經 SSH 串流寫進 Pi 自己的
開機磁碟，並在重新開機前校驗。**從未開機過的空白卡做不到**，那種卡請先在電腦上燒一次。

**它怎麼決定要裝哪個系統？**
登入後讀取 `/proc/device-tree/model` 得知型號，挑對應的官方映像：Pi 3 以後建議 64 位元桌面版，
更舊的板子用 32 位元版，選精簡用途就推薦 Lite。板子跑不起來的映像會直接拒絕。

**能取代 Raspberry Pi Imager 嗎？**
不能。Imager 負責把卡寫好；piscout 負責卡已經在 Pi 上之後的管理，也附了方便的本機燒錄。

**支援 Linux / macOS 嗎？**
視窗版和本機燒錄只支援 Windows。區網掃描另外可以在 Linux、macOS 用命令列執行，只需要 Python 標準函式庫：`python -m piscout scan`（見英文版「Scan from the command line」）。終端機、遠端重灌都是純 Python，之後可以移植。

## 從原始碼執行

需要 Python 3.9 以上、Windows 10/11（需要 WebView2，Win11 內建）。

```bash
git clone https://github.com/<你的帳號>/piscout.git
cd piscout
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_gui.py
```

本機燒錄寫入 SD 卡需要系統管理員權限；程式會在需要時提供「以系統管理員身分重新啟動」按鈕。

打包成 exe：

```bash
pip install pyinstaller
build.bat
```

## 專案結構

```
run_gui.py            # 桌面版入口
build.bat             # PyInstaller 打包
piscout/
├── gui.py            # 原生視窗（pywebview）+ 只聽 127.0.0.1 的本機服務
├── app.py            # FastAPI：API、終端機與桌面的 WebSocket
├── scanner.py        # 區網掃描、ARP 解析、mDNS
├── remote.py         # SSH 連線、啟動遠端桌面、安裝 agent
├── remoteflash.py    # 遠端重灌
├── addons.py         # 擴充套件清單與安裝腳本（NAS、Docker……）
├── flasher.py        # 映像清單、型號建議、本機燒錄、開機設定
├── agent/agent.py    # 會被推到 Pi 上的小程式（只用標準函式庫）
└── static/           # 介面；vendor/ 內是 xterm.js 與 noVNC
tests/
```

跑測試：`pytest`

## 注意事項

- 介面服務只綁 `127.0.0.1`，並使用一次性 token 建立終端機/桌面連線
- SSH 的 host key 目前是「第一次連線就接受」，家用網路還好，正式環境請自己改
  （`remote.py` 的 `AutoAddPolicy`）
- 遠端桌面會在 Pi 上開一個**無密碼、只聽本機**的 VNC，因為只能經由 SSH 通道連到，
  所以安全性等同 SSH；關閉連線時會把它停掉
- 開機設定裡的密碼只寫雜湊值；Wi-Fi 密碼因為格式限制會以明文寫在 boot 分割區
- API 只接受私有網段的 IP；映像只下載樹莓派官方網域
- 只掃自己的網路

## 讓 AI 助手操作你的樹莓派（MCP）

piscout 內附一個很小的 MCP 伺服器（只用標準函式庫），讓 AI 助手可以列出樹莓派並在上面執行指令。
帳密取自 piscout 已儲存的登入，AI 看不到密碼，也只接受區網內的私有位址。輸出會被截短以節省 token。

```json
{ "mcpServers": { "piscout": { "command": "C:\path\to\piscout.exe", "args": ["--mcp"] } } }
```

(From source: `"command": "python", "args": ["-m", "piscout.mcp"]`.)

工具：`pi_list`（掃描區網）、`pi_run`（執行 shell 指令）、`pi_health`（唯讀的健康檢查）。請先在 piscout 裡儲存該台樹莓派的帳密。
只在你信任的 AI 助手上啟用：它能以該帳號執行任何指令。

## 翻譯

piscout 目前有中文和 English。**新增語言不用寫程式**，只要在 `piscout/static/locales/` 放一個 JSON 檔：
執行 `python tools/i18n_check.py --new ja 日本語` 產生範本，填上翻譯（留空的會顯示英文），用
`python tools/i18n_check.py` 檢查後送 PR。同一個檔案也能翻譯 Windows 安裝程式（`installer` 區塊，安裝畫面會跟著使用者的 Windows 語言；Inno Setup 內建的語言只要翻 3 句）。完整說明見 [docs/TRANSLATING.md](docs/TRANSLATING.md)。
**徵求幫手：**[新增你的語言（#11）](https://github.com/MilkteaTW1/piscout/issues/11)。

## 需要客製？

想要專屬功能、整合或部署協助？歡迎找我，詳情請見 [墨鋒 Inkacuity](https://inkacuity.com/projects/piscout)，或寄信到 [ink@inkacuity.com](mailto:ink@inkacuity.com)。

## 驗證狀況與還沒做的

**已在真機實測**（Raspberry Pi 3 Model B Rev 1.2、Raspberry Pi OS Debian 12「Bookworm」）：區網掃描與 Pi 辨識、
SSH 登入與系統資訊、agent 安裝與總覽、內建終端機（可實際執行指令）、遠端桌面（經 SSH 通道的 wayvnc）、拖曳傳檔到終端機目前資料夾、輸入補齊選單、本機 SD 卡燒錄（燒完開機並以設定的帳號登入），皆由作者測試。

**未用真機測試的部分**：映像預處理與開機設定寫入（含用真實的 Raspberry Pi OS 64 位元映像跑過：來源 SHA-256 校驗通過、`user-data` 已寫入 boot 分割區）、
Pi 端寫入腳本的流程與校驗邏輯（用本機模擬）、單元測試。

**還沒在真機上實測**：遠端重灌的完整寫入（第一次真機嘗試中途被中斷，見「已知風險」）。本機燒錄只在 Raspberry Pi 3 Model B 上驗證過，其他型號尚未測試。

你用的是別的型號或系統版本嗎？歡迎[回報相容性結果](../../issues/new/choose)。
Pi 專屬的部分（記憶體內執行環境、sysrq 重開機、wayvnc）是依文件寫的，
第一次實機測試很可能需要微調。

- [ ] 實機驗證以上三項，並補上各型號的測試結果
- [ ] 遠端桌面支援 X11 / RealVNC 的舊系統
- [ ] SSH key 登入的介面（後端已支援，前端還沒接）
- [ ] Linux / macOS 的本機燒錄
- [ ] 空白 Pi 用 PXE / 網路開機安裝

## 已知問題

- Windows 防火牆有時會擋掉 mDNS，主機名稱會是空的，但 IP 與 MAC 判斷正常
- 掃描只做 IPv4，而且只掃 /24
- 用了 USB 網卡等非原廠網卡，MAC 前綴會對不上
- 本機燒錄後 Windows 可能會跳出「需要格式化磁碟」，**不要格式化**，直接關掉

---

*piscout 是獨立的開源專案，與 Raspberry Pi Ltd 無關，也未獲其認可或贊助。Raspberry Pi 是 Raspberry Pi Ltd 的商標。*
