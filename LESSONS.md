# Router Mode (Mantra): lessons

- 15.11.2026: before building a switcher, read the router: the MR110 in Wireless Router Mode already has an LTE backup
  (`lteBackupEnable=1`). Staying in that mode beats switching modes: no reboots, and it works when the Mac is away.
- 15.11.2026: "physical link Up" on the router's port means only the dongle's carrier; the phone serves nothing until
  Android's Ethernet tethering is switched on (`dumpsys ethernet`: Tethered interface requests 0, eth0 without IPv4).
- 15.11.2026: the MR firmware's /cgi/getParm answers without a login only with a `Referer: http://192.168.1.1/` header
  (403 without it); this one uses the older RSA-512 + AES login (TPLinkMRClient), not the ECC one.
- 15.11.2026: Android shell cannot `ip link show eth0` by name on the Nothing (netlink request denied); `ip link` works.

## Lesson: hover card and pipes (16.11.2026)
Poll the mouse (macOS draws a status item once per display, only one copy owns the button, so a tracking area misses the other display). The panel needs `titleVisibility = .hidden` for the one-title guard. A non-activating NSPanel at statusBar+1 never takes focus. Pipes for text items: attributed title; for icon items: pipedIcon + rightPipe; for view items: drawPipes or PipesView.
