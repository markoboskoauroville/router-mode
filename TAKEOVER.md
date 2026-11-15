# Router Mode (Mantra): takeover

**v1** (15.11.2026) · repository markoboskoauroville/router-mode (public, not promoted: no README, no description).
The TP-Link TL-MR110-Outdoor (4G outdoor router, http://192.168.1.1, firmware 1.0.0 0.9.1 Build 241202, SSID "mantra")
gets its internet either from its SIM or from a cable in its port. At home the Nothing phone (USB Ethernet dongle +
Android Ethernet tethering) feeds that port; the router is the local network where every device sees the others.

## The design (15.11.2026)

- The router stays in **Wireless Router Mode** (`SYS_MODE mode=ETH`) for good. Its own **LTE backup**
  (`lteBackupEnable=1`) carries the house on the SIM whenever the cable connection `ipoe_1_d` has no lease: no reboot,
  and it works while the Mac is away. (Proven 15.11.2026: tethering off, cable link Up but Disconnected, LTE Connected,
  the house online.) The hand back from SIM to cable once tethering is on is **not yet proven** (test pending).
- **3G/4G Router Mode** (`mode=LTE`) = SIM only. Switching the mode reboots the router (1-2 min offline): manual only.
- The watcher never switches. It warns (macOS notification + the menu bar in orange) when the SIM carries for more than
  5 min while the Nothing is home (its eth0 dongle link up): Ethernet tethering is then probably off.

## The pieces

| File | What |
|---|---|
| `routermode.py` | the client (tplinkrouterc6u's TPLinkMRClient in `.venv`), `status`, `tether`, `state`, `daemon`, `set` |
| `bin/routermode` | the command on the PATH (`~/.local/bin/routermode` links here), runs the venv Python with `-I` |
| `launchd/com.mantra.routermode.plist`, `agent.sh load|unload|status` | the watcher LaunchAgent (KeepAlive, `routermode daemon`) |
| `app/` (`App.swift`, `main.swift`, `Updater.swift`), `build.sh`, `.github/workflows/build.yml` | the menu-bar app, built only by GitHub Actions |

- **Login**: RSA key from `POST /cgi/getParm` (`nn`, `ee`, `seq`, no login needed), `cgi/login?data&sign`, the TokenID
  from `/`, then AES-encrypted `/cgi_gdpr` acts (`[OID#stack#pstack]i,n` lines). The password comes from
  `~/Downloads/API/tp-link-password.txt` (one line), never printed, masked in errors. The app never reads it.
- **Reads**: `SYS_MODE` (mode, lteBackupEnable), `WAN_COMMON_INTF_CFG` (physicalLinkStatus per Ethernet/LTE),
  `WAN_IP_CONN` (`ipoe_1_d` = cable, `LTE` = SIM: connectionStatus), `WAN_LTE_INTF_CFG` (dailyFlow, totalStatistics:
  bytes), `LTE_NET_STATUS` (sigLevel). IMEI/IMSI attributes are never requested.
- **The phone**: adb (USB serial or wireless 100.67.149.40:5555). `ip link` lists eth0 (shell may not run `ip link show
  eth0` by name: "request send failed: Permission denied"), `dumpsys ethernet` → "Tethered interface requests: N".
  Wireless adb works over Tailscale anywhere, so "phone home" = the dongle's eth0 link up, not adb reachable.
- **The watcher** reads every 60 s with one login kept; a failed read drops the session and waits 10 min before logging
  in again (one router session at a time: a login throws out Chrome's admin tab and router-sms). State:
  `~/Library/Application Support/router-mode/state.json`; log `~/Library/Logs/router-mode.log` (every change of the
  carrying line, warnings, manual sets).
- **The app** reads state.json every 15 s: title `PHONE · 120 MB` (normal) or `SIM · 120 MB` (orange); menu: the two
  status lines, the warning, Use phone internet, Use SIM only (both confirm, both reboot), Open router page (Chrome
  Profile 15), Check for updates, Quit. Every item is an NSMenuItem with its AX label. Updater kit (Latest vN).
- **Queen**: groq_ai_studio queen_skills/router-mode.md + qwen_app/router_mode.py (local, $0): "router status", "use
  phone", "use SIM" (asks first, switches only on "yes, use sim|phone").

## Install (Mac, no compile)

    gh release download --repo markoboskoauroville/router-mode --pattern app.zip -D /tmp/rm --clobber
    ditto -x -k /tmp/rm/app.zip /Applications && codesign --force -s "Mantra Apps" "/Applications/Router Mode (Mantra).app"

## Never proven

- `routermode set` (the SYS_MODE write + reboot): the one real switch test waits for Marko watching.
- The LTE backup giving the house back to the cable when tethering comes on; the failover time when the dongle is pulled.
- The router's own detection: `detectionMode=0` (link/lease based; `IPV4Ping` 0.0.0.0). A cable that has a lease but no
  internet behind it (phone without data) may not fail over.
