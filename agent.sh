#!/bin/sh
# agent.sh load|unload|status : the watcher LaunchAgent
P="$HOME/Library/LaunchAgents/com.mantra.routermode.plist"
case "$1" in
  load)   cp "$(dirname "$0")/launchd/com.mantra.routermode.plist" "$P"; launchctl bootout gui/$(id -u)/com.mantra.routermode 2>/dev/null; launchctl bootstrap gui/$(id -u) "$P" && echo loaded ;;
  unload) launchctl bootout gui/$(id -u)/com.mantra.routermode && rm -f "$P" && echo unloaded ;;
  *)      launchctl print gui/$(id -u)/com.mantra.routermode 2>/dev/null | grep -E "state|pid" | head -3 ;;
esac
