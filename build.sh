#!/bin/sh
# build.sh: Router Mode (Mantra).app. Run ONLY by GitHub Actions (.github/workflows/build.yml), never on the Mac.
# The version is VERSION in app/App.swift. SIGN=- on GitHub (ad hoc); the Mac re-signs "Mantra Apps" at install.
set -e
cd "$(dirname "$0")"
V=$(sed -n 's/^let VERSION = \([0-9]*\)/\1/p' app/App.swift)
APP="build/Router Mode (Mantra).app"
rm -rf "$APP"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -swift-version 5 -o "$APP/Contents/MacOS/RouterMode" app/*.swift
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Router Mode (Mantra)</string>
<key>CFBundleDisplayName</key><string>Router Mode (Mantra)</string>
<key>CFBundleIdentifier</key><string>community.auroville.routermode</string>
<key>CFBundleExecutable</key><string>RouterMode</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>$V</string>
<key>CFBundleVersion</key><string>$V</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>LSUIElement</key><true/>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PL
codesign --force -s "${SIGN:-Mantra Apps}" "$APP"
echo "built $APP (v$V)"
