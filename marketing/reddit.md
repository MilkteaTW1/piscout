# Reddit 草稿

發文前：
- 讀兩個版的最新規則（自我推廣比例、是否限定特定日子或 flair）。規則常改，以版上當下寫的為準
- 兩篇不要同一天發，間隔幾天，內容也不要一樣
- 附 `docs/demo.gif`，並說明它是模擬裝置錄的
- 發完前幾個小時要在線上回留言
- 已有的 `docs/reddit-draft.md` 寫了 Korean，實際沒有韓文，別用那段

---

## r/raspberry_pi

**Flair**：Show-and-Tell（或版上對應的）

**Title**
I made a free Windows app that finds the Pis on my network and opens SSH and the desktop in one window

**Body**

I set up Pis often enough that the routine got old: router admin page to find the IP, PuTTY, a VNC viewer, then later figuring out why one keeps rebooting. So I wrote piscout.

What it does:

- Scans your /24 on launch and marks Pis by MAC prefix and mDNS name. If AP isolation hides it, type `raspberrypi.local`
- SSH terminal in the window, with command and path suggestions as you type
- Remote desktop through the same SSH login (starts wayvnc bound to 127.0.0.1 on the Pi, stops it when you close). Needs the Wayland desktop, so Lite and old X11 images won't work
- Health check: under-voltage and throttling from `vcgencmd get_throttled`, temperature, SD card errors in dmesg, full disk, failed services, clock sync. Read-only, plain-language advice
- Quick setup for I2C / SPI / NTP / expand filesystem, from a fixed list
- Drag files onto the terminal and they land in the shell's current folder
- Overview of several Pis with batch reboot / apt upgrade
- Flash an SD card with the official images, picked for your model

Tested on a Pi 3 Model B with Bookworm. I don't own a 4, 5 or Zero 2 W, so if you try it on one, I'd like to know whether detection and the desktop tab work (issue #1 has a short template).

Limits: Windows only for the GUI, installer not code-signed (SmartScreen warns), and the remote re-image feature is off by default because it bricked a card during my own testing. The README explains that incident.

MIT licensed: https://github.com/MilkteaTW1/piscout

---

## r/selfhosted

**角度**：r/selfhosted 關心的是「我的服務跑在 Pi 上，怎麼管」，以及隱私／不靠雲端。piscout 本身是桌面程式，不是 self-hosted 服務，標題和內文第一段就講清楚，避免被說離題。

**Title**
A Windows app for managing the Raspberry Pis that run my self-hosted stuff (local only, no account)

**Body**

Not a server you host, so tell me if this is off-topic: it's a desktop app for looking after the Pis that run Samba, Pi-hole, Docker and so on, without a cloud dashboard or an account.

The parts that might matter here:

- **Local only.** The app's web UI binds to 127.0.0.1 with a per-launch random token. Saved logins are encrypted with Windows DPAPI. The only outbound request is a GitHub release check, and you can switch it off
- **Add-ons from a fixed list.** Samba share, Docker, fail2ban, unattended-upgrades. Each one is an apt-only script you can read in `piscout/addons.py`. No `curl | bash`, no third-party apt repos, safe to run twice, and removing keeps your data. The UI can only pick an add-on and install/remove; it cannot send arbitrary commands
- **Fleet overview.** Temperature, load, memory and disk for every Pi, plus batch reboot and `apt upgrade`
- **Health check.** Under-voltage, throttling, SD card I/O errors, failed systemd units, NTP sync. SD card wear is the usual way a Pi server dies, so this is the part I use most
- **MCP server** (`python -m piscout.mcp`) if you want an AI assistant to run commands on a Pi using the saved login without seeing the password

Honest limits: Windows GUI only, unsigned installer, SSH host keys are trusted on first use (fine on a home LAN, not beyond it), tested only on a Pi 3B.

https://github.com/MilkteaTW1/piscout (MIT). If there's an add-on you'd want, the list is open: issue #23.
