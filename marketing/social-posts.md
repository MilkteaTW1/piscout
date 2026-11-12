# 社群貼文草稿

每則都配一張圖或 GIF，連結放在最後（或第一則留言，視平台演算法）。

## Twitter / X（英文）

### X-1：問題開場
Booting a new Raspberry Pi usually means: open the router page, find the IP, open PuTTY, open a VNC viewer.

piscout does those in one Windows window: scan the LAN, click Connect, get a terminal and the Pi's desktop.

Free, MIT.
github.com/MilkteaTW1/piscout

📎 docs/demo.gif

### X-2：一個具體功能
The most common Raspberry Pi problem is a weak power supply, and the Pi rarely tells you.

piscout's health check reads `vcgencmd get_throttled`, temperature, SD card errors and failed services, then says in plain words what to fix. Read-only.

📎 健康檢查畫面截圖（需要補拍，見 issue #5 的方式）

### X-3：誠實的限制 + 邀請
Things piscout doesn't do yet:
- macOS / Linux GUI (there's a CLI scan)
- code-signed installer
- testing on anything but a Pi 3B

If you have a Pi 4, 5 or Zero 2 W, a 2-minute report helps a lot:
github.com/MilkteaTW1/piscout/issues/1

## Threads（繁體中文）

### T-1：開場介紹
每次插上一台新的樹莓派，都要先登入路由器找 IP、再開 PuTTY、再開 VNC。

我把這幾步做成一個 Windows 小程式 piscout：打開就掃區網，按「連線」就有終端機和樹莓派的桌面。免費、開源。

github.com/MilkteaTW1/piscout

📎 docs/demo.gif

### T-2：給新手
樹莓派常常莫名當機、卡頓，很多時候是電源不夠力，它不會跳出提醒。

piscout 的「健康檢查」會讀電壓、溫度、SD 卡錯誤、啟動失敗的服務，用白話告訴你該換電源還是加散熱片。只讀取，不改任何設定。

### T-3：擴充套件 + 徵求
想把樹莓派變成 NAS？在 piscout 裡按一下就裝好 Samba，也有 Docker、fail2ban、自動安全更新。

只用 apt 官方套件，執行前會列出每一步。移除時保留你的資料。

想要哪個套件可以來這裡提：github.com/MilkteaTW1/piscout/issues/23
