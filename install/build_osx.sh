#!/bin/bash

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"
cd $ROOT

# deleting dist
echo Deleting dist folder
rm -rf $ROOT/dist &>/dev/null 2>&1

# build the .app
echo Building OnionShare.app
pyinstaller $ROOT/install/pyinstaller.spec
# TODO: download and bundle tor
# python3 $ROOT/install/get-tor-osx.py

if [ "$1" = "--release" ]; then
  mkdir -p dist
  APP_PATH="$ROOT/dist/Hyperdome.app"
  PKG_PATH="$ROOT/dist/Hyperdome.pkg"
  IDENTITY_NAME_APPLICATION="Developer ID Application: Skyelar Craver"
  IDENTITY_NAME_INSTALLER="Developer ID Installer: Skyelar Craver"
  ENTITLEMENTS_CHILD_PATH="$ROOT/install/macos_sandbox/child.plist"
  ENTITLEMENTS_PARENT_PATH="$ROOT/install/macos_sandbox/parent.plist"

  echo "Codesigning the app bundle"
  codesign --deep -s "$IDENTITY_NAME_APPLICATION" -f --entitlements "$ENTITLEMENTS_CHILD_PATH" "$APP_PATH"
  codesign -s "$IDENTITY_NAME_APPLICATION" -f --entitlements "$ENTITLEMENTS_PARENT_PATH" "$APP_PATH"

  echo "Creating an installer"
  productbuild --sign "$IDENTITY_NAME_INSTALLER" --component "$APP_PATH" /Applications "$PKG_PATH"

  echo "Cleaning up"
  rm -rf "$APP_PATH"

  echo "All done, your installer is in: $PKG_PATH"
fi
