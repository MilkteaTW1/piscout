## piscout v0.1.16

Windows desktop tool for Raspberry Pi on your LAN: auto-discovery, built-in SSH terminal, remote desktop, overview and batch actions, SD card flashing, multilingual UI (中文 / English / हिन्दी / اردو / العربية / বাংলা / Español, more welcome).

### What changed since v0.1.15
A maintenance release: fixes and hardening, no new features.
- **Terminal and remote desktop connections** now only accept requests from piscout's own window (same host and port). Before, the check that blocks other web pages ran for normal requests but not for these connections; they were still protected by a one-time token.
- **Adding a Pi by name** no longer fails with a server error for malformed names such as `a..b`; you get the usual "not found" message.
- **Status bubble**: if something other than the piscout agent answers on port 8765, it is reported as "agent not responding" instead of a server error.
- **Dropped files**: if the final step of an upload fails, the half-written `.piscout-part` file is removed from the Pi and you see an error instead of a server error.
- If the Pi drops the SSH connection right after login, the terminal now closes that connection instead of leaving it open.
- 46 new API tests, a lint check in CI, a CONTRIBUTING guide, and first-connection steps in the README.

### Download
`piscout-setup.exe`. Verify it with `piscout-setup.exe.sha256`.

> It is not **code-signed**, so Windows SmartScreen may warn: *More info → Run anyway*.
> It is built by GitHub Actions from this repository's source at the tagged commit.

Not verified on real hardware: macOS and Linux scanning.

---

## 繁體中文
相較 v0.1.15（維護版，只有修正，沒有新功能）：
- **終端機與遠端桌面連線**現在只接受 piscout 自己視窗（同主機、同 port）發起的連線。以前擋掉其他網頁的檢查只套用在一般請求上，這兩種連線靠一次性 token 保護。
- **用名稱新增樹莓派**：輸入 `a..b` 這類格式錯誤的名稱時，不再出現伺服器錯誤，改顯示一般的「找不到」訊息。
- **狀態泡泡**：8765 port 上回應的不是 piscout agent 時，顯示「agent 沒有回應」，不再是伺服器錯誤。
- **拖曳傳檔**：上傳最後一步失敗時，會刪掉樹莓派上寫到一半的 `.piscout-part` 檔，並顯示錯誤訊息。
- 樹莓派在登入後立刻切斷 SSH 時，終端機會把那條連線關掉，不再留著。
- 新增 46 個 API 測試、CI 加上 lint 檢查、CONTRIBUTING 說明、README 加上第一次連線的步驟。

檔案沒有簽章，SmartScreen 可能警告，按「其他資訊 → 仍要執行」。
