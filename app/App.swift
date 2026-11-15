// Router Mode (Mantra): a menu-bar item for the TP-Link TL-MR110-Outdoor.
// It shows which line carries the house (PHONE cable, or SIM backup) and the SIM megabytes of today, read from the
// watcher's file ~/Library/Application Support/router-mode/state.json (LaunchAgent com.mantra.routermode, the
// command `routermode`). The app never holds the router password: a switch runs `routermode set phone|sim --yes`.
import AppKit

let VERSION = 1
let APP_NAME = "Router Mode (Mantra)"

let home = FileManager.default.homeDirectoryForCurrentUser.path
let stateFile = home + "/Library/Application Support/router-mode/state.json"
let routermode = home + "/Developer/ROUTER_MODE/bin/routermode"

struct State {
    var ok = false, via = "", mode = "", simToday = 0.0, phoneHome = false, tethering = false
    var warning: String? = nil, error: String? = nil, age = 0

    static func read() -> State? {
        guard let d = FileManager.default.contents(atPath: stateFile),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return nil }
        var s = State()
        s.ok = j["ok"] as? Bool ?? false
        s.via = j["internet_via"] as? String ?? ""
        s.mode = j["mode"] as? String ?? ""
        s.simToday = (j["sim_today_mb"] as? NSNumber)?.doubleValue ?? 0
        s.phoneHome = j["phone_home"] as? Bool ?? false
        s.tethering = (j["phone"] as? [String: Any])?["tethering"] as? Bool ?? false
        s.warning = j["warning"] as? String
        s.error = j["error"] as? String
        s.age = Int(Date().timeIntervalSince1970) - ((j["time"] as? NSNumber)?.intValue ?? 0)
        return s
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let menu = NSMenu()
    let line1 = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    let line2 = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    let warn = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    var busy: String? = nil

    func applicationDidFinishLaunching(_ n: Notification) {
        item.button?.setAccessibilityLabel(APP_NAME)
        menu.delegate = self
        menu.autoenablesItems = false
        for l in [line1, line2, warn] { l.isEnabled = false; menu.addItem(l) }
        menu.addItem(.separator())
        add("Use phone internet", #selector(usePhone))
        add("Use SIM only", #selector(useSim))
        add("Open router page", #selector(openRouter))
        menu.addItem(.separator())
        add("Check for updates", #selector(checkUpdates))
        add("Quit", #selector(quit), key: "q")
        item.menu = menu
        refresh()
        Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in self?.refresh() }
        Updater.checkAtStart()
    }

    func add(_ title: String, _ sel: Selector, key: String = "") {
        let m = NSMenuItem(title: title, action: sel, keyEquivalent: key)
        m.target = self
        m.setAccessibilityLabel(title)
        menu.addItem(m)
    }

    func menuWillOpen(_ m: NSMenu) { refresh() }

    func refresh() {
        guard let s = State.read() else {
            setTitle("ROUTER ?", warning: true)
            line1.title = "No reading yet: the watcher (com.mantra.routermode) is not running"
            line2.title = ""; warn.isHidden = true
            return
        }
        let mb = s.simToday >= 1000 ? String(format: "%.1f GB", s.simToday / 1000) : "\(Int(s.simToday)) MB"
        if let b = busy {
            setTitle(b, warning: true)
        } else if !s.ok || s.age > 300 {
            setTitle("ROUTER ?", warning: true)
        } else {
            let name = s.via == "cable" ? "PHONE" : s.via == "SIM" ? "SIM" : "NO NET"
            setTitle("\(name) · \(mb)", warning: s.via != "cable")
        }
        let where_ = s.via == "cable" ? "Internet from the phone cable" :
                     s.via == "SIM" ? (s.mode == "SIM" ? "Internet from the SIM (SIM only mode)" : "Internet from the SIM backup") :
                     "No internet"
        line1.title = s.ok ? "\(where_) · SIM today \(mb)" : "Router not read: \(String((s.error ?? "?").suffix(80)))"
        line2.title = "Phone \(s.phoneHome ? "home" : "away") · Ethernet tethering \(s.tethering ? "on" : "off") · read \(s.age) s ago"
        warn.title = "⚠︎ " + (s.warning ?? "")
        warn.isHidden = s.warning == nil
    }

    func setTitle(_ t: String, warning: Bool) {
        guard let b = item.button else { return }
        b.attributedTitle = NSAttributedString(string: t, attributes: [
            .font: NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .medium),
            .foregroundColor: warning ? NSColor.systemOrange : NSColor.labelColor])
        b.setAccessibilityValue(t)
    }

    func confirm(_ title: String, _ text: String) -> Bool {
        NSApp.activate(ignoringOtherApps: true)
        let a = NSAlert()
        a.messageText = title
        a.informativeText = text
        a.addButton(withTitle: "Switch and reboot")
        a.addButton(withTitle: "Cancel")
        return a.runModal() == .alertFirstButtonReturn
    }

    func switchTo(_ target: String, label: String) {
        busy = label
        refresh()
        DispatchQueue.global().async {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: routermode)
            p.arguments = ["set", target, "--yes"]
            let pipe = Pipe(); p.standardOutput = pipe; p.standardError = pipe
            var out = ""
            do { try p.run(); p.waitUntilExit()
                 out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? "" }
            catch { out = "could not run routermode: \(error.localizedDescription)" }
            let ok = p.terminationStatus == 0
            DispatchQueue.main.asyncAfter(deadline: .now() + (ok ? 120 : 0)) {
                self.busy = nil
                self.refresh()
            }
            if !ok { DispatchQueue.main.async {
                let a = NSAlert(); a.messageText = APP_NAME; a.informativeText = out; a.runModal() } }
        }
    }

    @objc func usePhone() {
        if let s = State.read(), s.ok, s.mode == "PHONE" {
            let a = NSAlert(); a.messageText = "Already in phone mode (Wireless Router Mode)"
            a.informativeText = s.via == "cable" ? "The house is on the phone cable." :
                "The router is waiting for the phone cable; the SIM backup carries meanwhile. Switch Ethernet tethering on in the Nothing (Settings → Network → Hotspot & tethering)."
            NSApp.activate(ignoringOtherApps: true); a.runModal(); return
        }
        if confirm("Use phone internet?", "The router changes to Wireless Router Mode and reboots: the whole house is offline for 1 to 2 minutes. Its SIM stays as the automatic backup.") {
            switchTo("phone", label: "REBOOTING")
        }
    }

    @objc func useSim() {
        if confirm("Use the SIM only?", "The router changes to 3G/4G Router Mode and reboots: the whole house is offline for 1 to 2 minutes. The phone cable is then not used at all, until you choose Use phone internet.") {
            switchTo("sim", label: "REBOOTING")
        }
    }

    @objc func openRouter() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        p.arguments = ["-na", "Google Chrome", "--args", "--profile-directory=Profile 15", "http://192.168.1.1/"]
        try? p.run()
    }

    @objc func checkUpdates() { Updater.checkAtStart(delay: 0, manual: true) }
    @objc func quit() { NSApp.terminate(nil) }
}

