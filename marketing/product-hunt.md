# Product Hunt 上架草稿

## Name
piscout

## Tagline（60 字元以內，挑一個）
1. Find, SSH into and manage your Raspberry Pis from Windows（57）
2. Every Raspberry Pi on your LAN, one Windows window（50）
3. Stop hunting for your Raspberry Pi's IP address（47）

建議用 1：說清楚是什麼、給誰、在哪個平台。

## Topics
Developer Tools · Open Source · Hardware · Windows

## Description（260 字元以內）

piscout scans your network, finds your Raspberry Pis and opens an SSH terminal or the Pi's desktop in the same window. It also checks power and SD card health, installs Samba or Docker from a fixed list, and flashes SD cards. Free, MIT, Windows.

（245 字元，貼上前用 PH 的計數再確認一次）

## Links
- Website: https://inkacuity.com/projects/piscout
- GitHub: https://github.com/MilkteaTW1/piscout
- Download: https://github.com/MilkteaTW1/piscout/releases/latest/download/piscout-setup.exe

## Gallery（順序）
1. `docs/demo.gif`：掃描 → 連線 → 終端機（第一張決定點擊率，用動的）
2. `docs/devices.png`：裝置清單
3. `docs/terminal.png`：終端機與補齊選單
4. `docs/features.png`：功能一覽
5. `docs/flash.png`：依型號推薦映像
6. 影片：依 `demo-video-script.md` 錄的 45 秒版本（或先用 `docs/promo.mp4`）

注意：demo.gif 是用模擬裝置錄的（`PISCOUT_DEMO=1`）。在說明或留言裡講一句，不要讓人以為是真機畫面。

## 首則 maker comment

Hi everyone, I made piscout.

Every time I set up a Raspberry Pi I ended up doing the same things: log into the router to find its IP, open PuTTY, open a VNC viewer, and later wonder why it keeps rebooting (it was the power supply). piscout puts those steps in one Windows window:

- It scans your /24 on launch and marks the Pis by MAC prefix and mDNS name. If your router isolates Wi-Fi clients, you can type `raspberrypi.local` instead.
- Connect opens an SSH terminal (xterm.js) with command and path suggestions. The desktop tab tunnels wayvnc over the same SSH login, so nothing new is exposed on your network.
- The health check reads `vcgencmd get_throttled`, temperature, disk, SD card errors in dmesg and failed services, and says in plain words what to fix.
- Add-ons install Samba, Docker, fail2ban or unattended-upgrades. They are a fixed list of apt-only scripts; the UI cannot send arbitrary commands.

Things I want to be upfront about:

- The GUI is Windows only. There is a cross-platform command-line scan (`python -m piscout scan`).
- The installer is not code-signed yet, so SmartScreen will warn you.
- I have only tested on a Raspberry Pi 3 Model B with Bookworm. Issue #1 collects reports from other models.
- Remote re-imaging (writing a new OS to a running Pi's own SD card) is off by default. During my first real test it left a card unbootable after I closed the app mid-transfer. The README documents what happened and what changed.

It binds to 127.0.0.1 only, logins are encrypted with Windows DPAPI, and the only outbound request is the GitHub release check, which you can turn off.

I would like to hear which Pi model you tried and what broke.

## 上架當天
- 台灣時間 15:00–16:00 上架（PH 以太平洋時間 00:01 換日），整天回留言
- 先準備好幾個常見問題的答案：為什麼不支援 Mac、跟 Raspberry Pi Connect 差在哪、為什麼沒簽章
