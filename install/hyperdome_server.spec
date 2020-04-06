# -*- mode: python -*-

import platform
p = platform.system()

version = open('share/version.txt').read().strip()

a = Analysis(
    ['scripts/cli.py'],
    pathex=['.'],
    binaries=None,
    datas=[
        ('../share/version.txt', 'share'),
        ('../share/wordlist.txt', 'share'),
        ('../share/torrc_template', 'share'),
        ('../share/torrc_template-obfs4', 'share'),
        ('../share/torrc_template-meek_lite_azure', 'share'),
        ('../share/images/*', 'share/images'),
        ('../share/static/*', 'share/static'),
        ('../share/locale/*', 'share/locale'),
        ('../share/templates/*', 'share/templates'),
        ('../share/static/css/*', 'share/static/css'),
        ('../share/static/img/*', 'share/static/img'),
        ('../install/licenses/*', 'licenses')
    ],
    hiddenimports=["pkg_resources.py2_warn"],
    hookspath=[],
    runtime_hooks=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None)

pyz = PYZ(
    a.pure, a.zipped_data,
    cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='hyperdome_server',
    debug=False,
    strip=False,
    upx=True,
    console=True, icon='hyperdome_logo.ico')

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='hyperdome_server')

if p == 'Darwin':
    app = BUNDLE(
        coll,
        name='Hyperdome_server.app',
        icon='install/hyperdome.icns',
        bundle_identifier='com.arades.hyperdome_server',
        info_plist={
            'CFBundleShortVersionString': version,
            'NSHighResolutionCapable': 'True'
        }
    )
