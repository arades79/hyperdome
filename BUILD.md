# Building OnionShare

Start by getting the source code:

```sh
git clone https://github.com/arades79/hyperdome.git
cd hyperdome
```

Hyperdome uses poetry for running development scripts and managing dependencies. You can read about poetry and it's reccomended method of installation at https://python-poetry.org/docs/ however the easiest method is simply typing `python3 -m pip install --user poetry` into a terminal.

## Linux

Install the needed dependencies from your distro's package manager (names may not be exact):
* python3
* python3-pip
* python3-flask
* python3-stem
* python3-pyqt5
* python3-cryptography
* python3-socks
* tor
* obfs4proxy
* python3-pytest


 open a terminal and type `poetry install` in the hyperdome directory to get and setup all of the package dependencies.

After that you can try both the CLI and the GUI version of Hyperdome:

```sh
poetry run hyperdome_server --debug
poetry run hyperdome_client --debug
```

You can also build binary version of the applications with `build_generic.sh`
This build and resulting binary have only been verified on Manjaro at this point.

There also exists `build_deb.sh` and `build_rpm.sh` scripts, but these haven't been verified, and aren't guaranteed to work out of the box.

## Mac OS X

*WARNING:*
 MacOS builds have not yet been tested for Hyperdome! All instructions below are from the upstream project. You should only try to build/run hyperdome on MacOS if you know your way around python development and MacOS packaging.

Install Xcode from the Mac App Store. Once it's installed, run it for the first time to set it up. Also, run this to make sure command line tools are installed: `xcode-select --install`. And finally, open Xcode, go to Preferences > Locations, and make sure under Command Line Tools you select an installed version from the dropdown. (This is required for installing Qt5.)

Download and install Python 3.8.2 from https://www.python.org/downloads/release/python-382/.

You may also need to run the command `/Applications/Python\ 3.8/Install\ Certificates.command` to update Python 3.6's internal certificate store. Otherwise, you may find that fetching the Tor Browser .dmg file fails later due to a certificate validation error.

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

#### Building PyInstaller

If you want to build an app bundle, you'll need to use PyInstaller. Recently there has been issues with installing PyInstaller using pip, so here's how to build it from source. First, make sure you don't have PyInstaller currently installed:

```sh
pip3 uninstall PyInstaller
```

Change to a folder where you keep source code, and clone the PyInstaller git repo:

```sh
git clone https://github.com/pyinstaller/pyinstaller.git
```

Verify the v3.4 git tag:

```sh
cd pyinstaller
gpg --keyserver hkps://keyserver.ubuntu.com:443 --recv-key 0xD4AD8B9C167B757C4F08E8777B752811BF773B65
git tag -v v3.4
```

It should say `Good signature from "Hartmut Goebel <h.goebel@goebel-consult.de>`. If it verified successfully, checkout the tag:

```sh
git checkout v3.4
```

And compile the bootloader, following [these instructions](https://pyinstaller.readthedocs.io/en/stable/bootloader-building.html#building-for-mac-os-x). To compile, run this:

```sh
cd bootloader
python3 waf distclean all --target-arch=64bit
```

Finally, install the PyInstaller module into your local site-packages:

```sh
cd ..
python3 setup.py install
```

#### To build the app bundle

```sh
install/build_osx.sh
```

Now you should have `dist/OnionShare.app`.

#### To codesign and build a pkg for distribution

```sh
install/build_osx.sh --release
```

Now you should have `dist/OnionShare.pkg`.

## Windows

### Setting up your dev environment

Download Python 3.8.2 or higher from whichever source you prefer. If your windows instalation is up-to-date the easiest way is to type `python` into a command prompt, which will take you to a windows store page.

Install  Qt 5.14 or higher from https://www.qt.io/download-open-source/. You don't need everything the installer tries to give you, just the most recent Qt core library and the build tools for MSVC.

open a terminal and type `poetry install` in the hyperdome directory to get and setup all of the package dependencies.


You'll also need an up-to-date version of tor browser for the application to use its underlying tor proxy. You can get tor browser from https://torproject.org

You now have all the requirements to build and run hyperdome and hyperdome server, run them in your development environments with:
```
poetry run hyperdome_server --debug
poetry run hyperdome_client --debug
```

#### If you want to build a .exe

These instructions include adding folders to the path in Windows. To do this, go to Start and type "advanced system settings", and open "View advanced system settings" in the Control Panel. Click Environment Variables. Under "System variables" double-click on Path. From there you can add and remove folders that are available in the PATH.

Download and install the 32-bit [Visual C++ Redistributable for Visual Studio 2015](https://www.microsoft.com/en-US/download/details.aspx?id=48145). I downloaded `vc_redist.x86.exe`.

Download and install 7-Zip from http://www.7-zip.org/download.html. I downloaded `7z1805.exe`.

Download and install the standalone [Windows 10 SDK](https://dev.windows.com/en-us/downloads/windows-10-sdk). Note that you may not need this if you already have Visual Studio.

Add the following directories to the path:

* `C:\Program Files (x86)\Windows Kits\10\bin\10.0.17763.0\x86`
* `C:\Program Files (x86)\Windows Kits\10\Redist\10.0.17763.0\ucrt\DLLs\x86`
* `C:\Users\user\AppData\Local\Programs\Python\Python37-32\Lib\site-packages\PyQt5\Qt\bin`
* `C:\Program Files (x86)\7-Zip`

#### If you want the .exe to not get falsely flagged as malicious by anti-virus software

OnionShare uses PyInstaller to turn the python source code into Windows executable `.exe` file. Apparently, malware developers also use PyInstaller, and some anti-virus vendors have included snippets of PyInstaller code in their virus definitions. To avoid this, you have to compile the Windows PyInstaller bootloader yourself instead of using the pre-compiled one that comes with PyInstaller.

(If you don't care about this, you can install PyInstaller with `pip install PyInstaller==3.4`.)

Here's how to compile the PyInstaller bootloader:

Download and install [Microsoft Build Tools for Visual Studio 2017](https://www.visualstudio.com/downloads/#build-tools-for-visual-studio-2017). I downloaded `vs_buildtools.exe`. In the installer, check the box next to "Visual C++ build tools". Click "Individual components", and under "Compilers, build tools and runtimes", check "Windows Universal CRT SDK". Then click install. When installation is done, you may have to reboot your computer.

Then, enable the 32-bit Visual C++ Toolset on the Command Line like this:

```
cd "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Auxiliary\Build"
vcvars32.bat
```

Make sure you have a new enough `setuptools`:

```
pip install setuptools==40.6.3
```

Now make sure you don't have PyInstaller installed from pip:

```
pip uninstall PyInstaller
rmdir C:\Users\user\AppData\Local\Programs\Python\Python37-32\Lib\site-packages\PyInstaller /S
```

Change to a folder where you keep source code, and clone the PyInstaller git repo:

```
git clone https://github.com/pyinstaller/pyinstaller.git
```

To verify the git tag, you first need the signing key's PGP key, which means you need `gpg`. If you installed git from git-scm.com, you can run this from Git Bash:

```
gpg --keyserver hkps://keyserver.ubuntu.com:443 --recv-key 0xD4AD8B9C167B757C4F08E8777B752811BF773B65
```

And now verify the tag:

```
cd pyinstaller
git tag -v v3.4
```

It should say `Good signature from "Hartmut Goebel <h.goebel@goebel-consult.de>`. If it verified successfully, checkout the tag:

```
git checkout v3.4
```

And compile the bootloader, following [these instructions](https://pythonhosted.org/PyInstaller/bootloader-building.html). To compile, run this:

```
cd bootloader
python waf distclean all --target-arch=32bit --msvc_targets=x86
```

Finally, install the PyInstaller module into your local site-packages:

```
cd ..
python setup.py install
```

Now the next time you use PyInstaller to build OnionShare, the `.exe` file should not be flagged as malicious by anti-virus.

### To make a .exe:

* go to the `install` directory and run `build_exe.bat`, inside the `dist` directory there will be folders for `hyperdome_server` and `hyperdome` for the server and client respectively, run the `hyperdome_server.exe` (along with any command line parameters if needed) for running a server on your local machine, and run `hyperdome.exe` to start the hyperdome client.

