#!/usr/bin/env python3
"""routermode: read and switch the operation mode of the TP-Link TL-MR110-Outdoor (192.168.1.1).

  routermode status [--json]      mode (SIM = 3G/4G Router Mode, PHONE = Wireless Router Mode), WAN links, SIM data
  routermode tether [--json]      is the Nothing's Ethernet tethering up (over adb)
  routermode set sim|phone --yes  write SYS_MODE (manual tool only; NOT yet proven; the router reboots)
  routermode daemon               the watcher (LaunchAgent com.mantra.routermode): every 60 s, reports only
  routermode state [--json]       the watcher's last state (no router login)

The design (15.11.2026): the router stays in Wireless Router Mode (ETH) for good; its own LTE backup
(lteBackupEnable=1) carries the house on the SIM when the phone cable has no internet, with no reboot,
also when the Mac is away. The watcher never switches; it warns when the SIM carries > 5 min while the
Nothing is home (eth0 dongle link up) - Ethernet tethering is then probably off.

Login: tplinkrouterc6u's TPLinkMRClient (RSA key from /cgi/getParm + AES /cgi_gdpr), in ./.venv.
The password is read from ~/Downloads/API/tp-link-password.txt and never printed or logged.
"""
import json, os, re, subprocess, sys

HOST = 'http://192.168.1.1'
PWFILE = os.path.expanduser('~/Downloads/API/tp-link-password.txt')
ADB = os.path.expanduser('~/Library/Android/sdk/platform-tools/adb')
NOTHING = ['0005534BC000140', '100.67.149.40:5555']
MODES = {'LTE': 'SIM', 'ETH': 'PHONE'}


STATE_DIR = os.path.expanduser('~/Library/Application Support/router-mode')
STATE = os.path.join(STATE_DIR, 'state.json')
LOG = os.path.expanduser('~/Library/Logs/router-mode.log')
INTERVAL = 60
WARN_AFTER = 300        # SIM carrying while the phone is home, seconds
KICK_BACKOFF = 600      # our session was taken (Chrome / router-sms logged in): wait before logging in again


def log(msg):
    import datetime
    with open(LOG, 'a') as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def client():
    from tplinkrouterc6u import TPLinkMRClient
    pw = open(PWFILE).read().strip()
    c = TPLinkMRClient(HOST, pw)
    c.authorize()
    return c


def rows(res):
    return res if isinstance(res, list) else [res]


def status(c=None):
    c = c or client()
    A = c.ActItem
    _, sysmode = c.req_act([A(A.GET, 'SYS_MODE', attrs=['mode', 'lteBackupEnable'])])
    _, links = c.req_act([A(A.GL, 'WAN_COMMON_INTF_CFG', attrs=['WANAccessType', 'physicalLinkStatus'])])
    _, conns = c.req_act([A(A.GL, 'WAN_IP_CONN', attrs=['name', 'connectionStatus', 'externalIPAddress'])])
    _, lte = c.req_act([A(A.GL, 'WAN_LTE_INTF_CFG', attrs=['totalStatistics', 'dailyFlow', 'curRxSpeed', 'curTxSpeed'])])
    _, net = c.req_act([A(A.GL, 'LTE_NET_STATUS', attrs=['sigLevel', 'connStat', 'netType', 'smsUnreadCount'])])
    link = {r.get('WANAccessType'): r.get('physicalLinkStatus') for r in rows(links)}
    conn = {r.get('name'): (r.get('connectionStatus'), r.get('externalIPAddress')) for r in rows(conns)}
    eth = conn.get('ipoe_1_d', ('?', ''))
    sim = conn.get('LTE', ('?', ''))
    lte_row = rows(lte)[-1] if rows(lte) else {}
    net_row = rows(net)[-1] if rows(net) else {}
    mode = sysmode.get('mode', '?')
    via = 'cable' if eth[0] == 'Connected' else ('SIM' if sim[0] == 'Connected' else 'none')
    return {
        'mode': MODES.get(mode, mode), 'raw_mode': mode,
        'lte_backup': sysmode.get('lteBackupEnable') == '1',
        'cable_link': link.get('Ethernet'), 'cable_internet': eth[0] == 'Connected',
        'sim_internet': sim[0] == 'Connected', 'internet_via': via,
        'sim_total_mb': round(float(lte_row.get('totalStatistics') or 0) / 1e6, 1),
        'sim_today_mb': round(float(lte_row.get('dailyFlow') or 0) / 1e6, 1),
        'signal': net_row.get('sigLevel'),
    }


def tether():
    """The Nothing's eth0: present, link up, and in tethered state (a 192.168/10.x address served to the router)."""
    out = {'adb': None, 'eth0': False, 'link_up': False, 'tethering': False}
    for serial in NOTHING:
        try:
            r = subprocess.run([ADB, '-s', serial, 'shell',
                                'ip -4 addr 2>/dev/null | grep -A2 " eth0:"; echo ===; ip link 2>/dev/null | grep " eth0:"; echo ===;'
                                ' dumpsys ethernet | grep -E "Tethered interface requests"'],
                               capture_output=True, text=True, timeout=8)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode != 0:
            continue
        out['adb'] = serial
        addr, link, eth = (r.stdout.split('===') + ['', '', ''])[:3]
        out['eth0'] = 'eth0' in link
        out['link_up'] = 'LOWER_UP' in link
        m = re.search(r'Tethered interface requests:\s*(\d+)', eth)
        out['tethering'] = bool(re.search(r'inet \d', addr)) and bool(m and int(m.group(1)) > 0)
        break
    return out


def set_mode(target):
    want = {'sim': 'LTE', 'phone': 'ETH'}[target]
    c = client()
    A = c.ActItem
    c.req_act([A(A.SET, 'SYS_MODE', attrs=[f'mode={want}'])])
    try:
        c.reboot()   # the web page reboots after a mode change
    except Exception:
        pass
    return want


def notify(title, text):
    subprocess.run(['osascript', '-e', f'display notification {json.dumps(text)} with title {json.dumps(title)}'],
                   capture_output=True, timeout=10)


def write_state(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, STATE)


def daemon():
    import time
    c, sim_since, warned, last_via, kicked_at = None, None, False, None, 0
    log('daemon start')
    while True:
        now = time.time()
        st = {'time': int(now), 'ok': False}
        try:
            if c is None:
                if now - kicked_at < KICK_BACKOFF:
                    raise RuntimeError(f'waiting {int(KICK_BACKOFF - (now - kicked_at))} s before logging in again')
                c = client()
                log('login')
            try:
                st.update(status(c))
            except Exception:
                # session gone (another login took it, or the router rebooted): one fresh login, else back off
                c = None
                kicked_at = now
                raise
            st['ok'] = True
        except Exception as e:
            st['error'] = str(e)[-300:]
        t = tether()
        st['phone'] = t
        st['phone_home'] = bool(t['eth0'] and t['link_up'])
        if st['ok']:
            via = st['internet_via']
            if via != last_via:
                log(f"internet via {via} (mode {st['mode']}, cable link {st['cable_link']}, phone home {st['phone_home']},"
                    f" tethering {t['tethering']}, SIM today {st['sim_today_mb']} MB)")
                last_via = via
            if via == 'SIM' and st['phone_home']:
                sim_since = sim_since or now
            else:
                sim_since, warned = None, False
            st['sim_since'] = int(sim_since) if sim_since else None
            st['warning'] = None
            if sim_since and now - sim_since >= WARN_AFTER:
                st['warning'] = 'The house is on the SIM while the Nothing is home: switch Ethernet tethering on.'
                if not warned:
                    notify('Router Mode (Mantra)', st['warning'])
                    log('WARN ' + st['warning'])
                    warned = True
        else:
            log('read failed: ' + st.get('error', ''))
        write_state(st)
        time.sleep(INTERVAL)


def main(a):
    js = '--json' in a
    a = [x for x in a if x != '--json']
    cmd = a[0] if a else 'status'
    if cmd == 'status':
        s = status()
        print(json.dumps(s) if js else
              f"mode {s['mode']} · internet via {s['internet_via']} · cable link {s['cable_link']}"
              f" · LTE backup {'on' if s['lte_backup'] else 'off'} · SIM total {s['sim_total_mb']} MB, today {s['sim_today_mb']} MB")
    elif cmd == 'state':
        try:
            st = json.load(open(STATE))
        except OSError:
            sys.exit('no state yet (is the watcher running? routermode daemon)')
        if js:
            print(json.dumps(st))
        elif st.get('ok'):
            import time
            print(f"{'PHONE cable' if st['internet_via'] == 'cable' else 'SIM backup' if st['internet_via'] == 'SIM' else 'NO internet'}"
                  f" · mode {st['mode']} · SIM today {st['sim_today_mb']} MB · phone {'home' if st['phone_home'] else 'away'}"
                  f" · tethering {'on' if st['phone']['tethering'] else 'off'} · {int(time.time() - st['time'])} s ago"
                  + (f"\nWARNING: {st['warning']}" if st.get('warning') else ''))
        else:
            print('router not read: ' + st.get('error', '?'))
    elif cmd == 'daemon':
        daemon()
    elif cmd == 'tether':
        t = tether()
        print(json.dumps(t) if js else
              f"adb {t['adb'] or 'absent'} · eth0 {'yes' if t['eth0'] else 'no'} · link {'up' if t['link_up'] else 'down'}"
              f" · Ethernet tethering {'ON' if t['tethering'] else 'off'}")
    elif cmd == 'set' and len(a) > 1 and a[1] in ('sim', 'phone'):
        if '--yes' not in a:
            sys.exit('refused: a switch reboots the router (1-2 min without internet); add --yes')
        log(f'MANUAL set {a[1]}')
        print('written', set_mode(a[1]), '- router rebooting')
    else:
        print(__doc__)


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception as e:
        msg = str(e)
        try:
            msg = msg.replace(open(PWFILE).read().strip(), '***')
        except OSError:
            pass
        sys.exit(f'routermode: {msg[:300]}')
