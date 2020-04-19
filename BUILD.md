# Building Hyperdome

Start by getting the source code:

```sh
git clone https://github.com/arades79/hyperdome.git
cd hyperdome
```

Hyperdome uses poetry for running development scripts and managing dependencies. You can read about poetry and it's reccomended method of installation at https://python-poetry.org/docs/ however the easiest method is simply typing `python3 -m pip install --user poetry` into a terminal.

you'll also need Tor browser installed and running before trying to launch hyperdome. Get the latest version at https://torproject.org/

## Linux

Install the needed dependencies from your distro's package manager (names may not be exact):
* python3
* python3-pip
* python3-flask
* python3-stem
* python3-pyqt5
* python3-cryptography
* python3-socks
* python3-sqlalchemy
* tor
* obfs4proxy
* python3-pytest


open a terminal and type `poetry install` in the hyperdome directory to get and setup all of the package dependencies.

#### fixing installation errors
Depending on your distro, you may recieve errors when installing due to mismatched python versions, in this case install:
* python3.8
* python3.8-venv

Then activate a python specific venv to use in poetry with `poetry env use python3.8`.

Poetry venv's use the system python's version of pip, so it's likely this will start out of date, update it with `poetry run pip install --upgrade pip`
Then try running `poetry install` again.

#### using hyperdome once installed
After that you can try both the CLI and the GUI version of Hyperdome:

```sh
poetry run hyperdome_server --debug
poetry run hyperdome_client --debug
```

### building binaries

make sure the .sh scripts in the install directory have execution permissions: `chmod +x install/*.sh`
then run the build: `build_generic.sh`
This build and resulting binary have only been verified on Manjaro at this point.

There also exists `build_deb.sh` and `build_rpm.sh` scripts, but these haven't been verified, and aren't guaranteed to work out of the box.

## Mac OS X

*WARNING:*
 MacOS builds have not yet been tested for Hyperdome! All instructions below are from the upstream project. You should only try to build/run hyperdome on MacOS if you know your way around python development and MacOS packaging.

Install Xcode from the Mac App Store. Once it's installed, run it for the first time to set it up. Also, run this to make sure command line tools are installed: `xcode-select --install`. And finally, open Xcode, go to Preferences > Locations, and make sure under Command Line Tools you select an installed version from the dropdown. (This is required for installing Qt5.)

Download and install Python 3.8.2 from https://www.python.org/downloads/release/python-382/.

You may also need to run the command `/Applications/Python\ 3.8/Install\ Certificates.command` to update Python's internal certificate store. Otherwise, you may find that fetching the Tor Browser .dmg file fails later due to a certificate validation error.

Install Qt 5.14 or later from https://www.qt.io/download-open-source/. I downloaded `qt-unified-mac-x64-3.0.6-online.dmg`. In the installer, you can skip making an account, and all you need is `Qt` > `Qt 5.14` > `macOS`.

open a terminal and type `poetry install` in the hyperdome directory to get and setup all of the package dependencies.

```sh
poetry install
```

#### You can run both the server and client of hyperdome without building a bundle

```sh
poetry run hyperdome_server --debug
poetry run hyperdome_client --debug
```


#### To build the app bundle

```sh
install/build_osx.sh
```

Now you should have `dist/Hyperdome.app`.

#### To codesign and build a pkg for distribution

```sh
install/build_osx.sh --release
```

Now you should have `dist/Hyperdome.pkg`.

## Windows

### Setting up your dev environment

Download Python 3.8.2 or higher from whichever source you prefer. If your windows instalation is up-to-date the easiest way is to type `python` into a command prompt, which will take you to a windows store page.

Install  Qt 5.14 or higher from https://www.qt.io/download-open-source/. You don't need everything the installer tries to give you, just the most recent Qt core library and the build tools for MSVC.

open a terminal and type `poetry install` in the hyperdome directory to get and setup all of the package dependencies.

You now have all the requirements to build and run hyperdome and hyperdome server, run them in your development environments with:
```
poetry run hyperdome_server --debug
poetry run hyperdome_client --debug
```

#### If you want to build a .exe

These instructions include adding folders to the path in Windows. To do this, go to Start and type "advanced system settings", and open "View advanced system settings" in the Control Panel. Click Environment Variables. Under "System variables" double-click on Path. From there you can add and remove folders that are available in the PATH.

Download and install the 32-bit [Visual C++ Redistributable for Visual Studio 2015](https://www.microsoft.com/en-US/download/details.aspx?id=48145). I downloaded `vc_redist.x86.exe`.

Download and install the standalone [Windows 10 SDK](https://dev.windows.com/en-us/downloads/windows-10-sdk). Note that you may not need this if you already have Visual Studio.

Add the following directories to the path:

* `C:\Program Files (x86)\Windows Kits\10\bin\10.0.17763.0\x86`
* `C:\Program Files (x86)\Windows Kits\10\Redist\10.0.17763.0\ucrt\DLLs\x86`
* `C:\Users\user\AppData\Local\Programs\Python\Python37-32\Lib\site-packages\PyQt5\Qt\bin`
* `C:\Program Files (x86)\7-Zip`


#### To make a .exe:

* go to the `install` directory and run `build_exe.bat`, inside the `dist` directory there will be folders for `hyperdome_server` and `hyperdome` for the server and client respectively, run the `hyperdome_server.exe` (along with any command line parameters if needed) for running a server on your local machine, and run `hyperdome.exe` to start the hyperdome client.

