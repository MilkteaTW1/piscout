# Demo 影片腳本（約 45 秒）

用途：Product Hunt 圖庫、X、Threads、README。1920×1080 錄製，另外裁一份 1080×1080 給社群。

## 錄影前準備
- 用**真的樹莓派**錄（現有的 demo.gif 是模擬的；PH 和 Reddit 的觀眾會問）。Pi 3B、Bookworm 桌面版、已開 SSH
- 清空 vault（「清除已存帳密」），讓畫面從「第一次連線」開始
- Windows 改英文介面、縮放 100%、關掉通知
- 樹莓派桌面放一個好認的桌布，切到遠端桌面時才看得出差別
- 先準備一個小檔案（例如 `notes.txt`）放在 Windows 桌面，拿來拖曳

## 分鏡

| 時間 | 畫面 | 旁白／字幕（英文，同時燒中文字幕） |
|---|---|---|
| 0–4s | Windows 桌面，雙擊 piscout 圖示，視窗打開，開始掃描 | "This is piscout. It finds the Raspberry Pis on your network." |
| 4–9s | 掃描結果出現，樹莓派出現並帶著 Raspberry Pi 標籤；滑鼠停在型號標籤上 | "No router page, no IP hunting." |
| 9–15s | 按 Connect，輸入 pi / 密碼，勾 Remember，送出；終端機出現 | "Click Connect, log in, and you get a terminal." |
| 15–20s | 輸入 `sudo apt up`，補齊選單跳出，按 Tab 接受 | "It suggests commands and paths as you type." |
| 20–25s | 把 `notes.txt` 拖進終端機，輸入 `ls` 看到檔案 | "Drop a file in, and it lands in the current folder." |
| 25–31s | 切到 Remote desktop 分頁，樹莓派桌面出現，點一下開始選單 | "The Pi's desktop, over the same SSH login." |
| 31–38s | 切到 System info，跑健康檢查，結果列出（最好有一項 warn，例如曾經電壓不足） | "The health check tells you about power, heat and SD card problems, in plain words." |
| 38–42s | 切到 Overview，看到多台（沒有第二台就跳過這段，影片縮成 40 秒） | "And keeps an eye on all of them." |
| 42–45s | 結尾卡：piscout 標誌、`github.com/MilkteaTW1/piscout`、"Free · MIT · Windows" | "piscout. Free and open source." |

## 剪輯
- 輸入密碼那幾格要打馬賽克或加速跳過
- 等待（掃描、SSH 登入、桌面啟動）加速 2–4 倍，畫面角落標 "2×"，不要直接剪掉讓人以為是瞬間完成
- 背景音樂小聲，旁白可以省略，只留字幕（社群影片多半靜音播放）
- 不放「最強」「革命性」這類字

## 不要錄進去的
- 遠端重灌：有風險、預設關閉，放在宣傳影片裡會讓人以為是主要功能
- 真實的區網 IP 以外的個人資訊（Wi-Fi 名稱、路由器型號、其他裝置的主機名稱）
