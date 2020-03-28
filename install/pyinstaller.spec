# -*- mode: python -*-

import platform
p = platform.system()

version = open('share/version.txt').read().strip()

a = Analysis(
    ['scripts/hyperdome_client.py'],
    pathex=['.'],
    binaries=None,
    datas=[
        ('../share/version.txt', 'share'),
        ('../share/wordlist.txt', 'share'),
        ('../share/torrc_template', 'share'),
        ('../share/torrc_template-obfs4', 'share'),
        ('../share/torrc_template-meek_lite_azure', 'share'),
        ('../share/images/*', 'share/images'),
        ('../share/locale/*', 'share/locale'),
        ('../share/static/*', 'share/static'),
        ('../share/templates/*', 'share/templates'),
        ('../share/static/css/*', 'share/static/css'),
        ('../share/static/img/*', 'share/static/img'),
        ('../share/static/js/*', 'share/static/js'),
        ('../install/licenses/*', 'licenses')
    ],
    hiddenimports=[],
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
    name='hyperdome',
    debug=False,
    strip=False,
    upx=True,
    console=False)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='hyperdome')

if p == 'Darwin':
    app = BUNDLE(
        coll,
        name='Hyperdome.app',
        icon='install/hyperdome.icns',
        bundle_identifier='com.arades.hyperdome',
        info_plist={
            'CFBundleShortVersionString': version,
            'NSHighResolutionCapable': 'True'
        }
    )
