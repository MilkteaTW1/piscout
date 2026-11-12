# piscout 推廣草稿（未發布）

這個資料夾只放草稿，沒有任何東西已經貼出去。發之前請自己讀過、改成你的口氣。

| 檔案 | 內容 |
|---|---|
| [product-hunt.md](product-hunt.md) | Product Hunt：名稱、tagline、描述、首則 maker comment、圖庫順序 |
| [social-posts.md](social-posts.md) | Twitter/X 3 則（英文）、Threads 3 則（繁中） |
| [reddit.md](reddit.md) | r/raspberry_pi、r/selfhosted 各一篇 |
| [demo-video-script.md](demo-video-script.md) | 45 秒 demo 影片分鏡與旁白 |

## 寫文案時可以引用的事實（都查得到出處）

- Windows 桌面程式，免費、MIT 授權，目前 v0.1.15
- 實機測過：Raspberry Pi 3 Model B、Raspberry Pi OS Bookworm（掃描、連線、燒錄後開機登入）
- 功能：區網掃描辨識樹莓派、內建 SSH 終端機（有輸入補齊）、經 SSH 通道的遠端桌面（wayvnc + noVNC）、拖曳傳檔、多台總覽與批次重開機／更新、白話健康檢查、固定清單的快速設定、擴充套件（Samba NAS、Docker、fail2ban、自動安全更新，只用 apt 官方套件）、本機 SD 卡燒錄、遠端重灌（進階、預設關閉）、MCP 伺服器
- 介面語言：English、中文、Español、हिन्दी、العربية、اردو、বাংলা（7 種）
- 安全：服務只綁 127.0.0.1、每次啟動隨機 API token、帳密用 Windows DPAPI 加密、只接受私有網段 IP
- 不收集資料；唯一的對外連線是查 GitHub release（可關）
- 誠實的限制：只有 Windows GUI；exe 沒有程式碼簽章，SmartScreen 會警告；winget 還在審核；遠端重灌在第一次實測時把一張卡弄到開不了機（README「Known risks」有寫）

## 不要寫的

- 「Korean」：目前沒有韓文語系檔（`docs/reddit-draft.md` 裡寫了，發之前要拿掉）
- 「支援所有樹莓派型號」：只在 Pi 3B 實測過
- 「安全無虞」「一鍵搞定一切」這類保證
