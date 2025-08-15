# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import re
import shutil
import json
from pathlib import Path

# ===============================================================================
# General settings applicable to all apps
# ===============================================================================

# Get the current user's home directory
HOME = Path.home()

# Name of the app
APP_NAME = "OpenSesame"
# The short version string
# In this script, this value is overwritten later, because the value of OpenSesame
# is automatically retrieved from its source code.
VERSION = "4.1.0"
# The website in reversed order (domain first, etc.)
IDENTIFIER = "nl.cogsci.osdoc"
# The author of this package
AUTHOR = "Sebastiaan Mathôt"

# Full path to the anaconda environment folder to package
# Using expanduser to handle ~ and Path for cross-platform compatibility
CONDA_ENV_PATH = str(HOME / "miniconda3/envs/opensesame")

# Alternative: If you want to use conda's current environment:
# import subprocess
# CONDA_ENV_PATH = subprocess.check_output(['conda', 'info', '--base']).decode().strip()

# Folders to include from Anaconda environment, if omitted everything will be copied
# CONDA_FOLDERS = ["lib", "bin", "share", "qsci", "ssl", "translations"]

# Paths of files and folders to remove from the copied anaconda environment,
# relative to the environment's root.
CONDA_EXCLUDE_FILES = [
    'bin/*.app',
    'bin/*.prl',
    'bin/qmake',
    'bin/2to3*',
    'bin/autopoint',
    'conda-meta',
    'include',
    'lib/*.prl',
    'lib/pkg-config',
    'org.freedesktop.dbus-session.plist'
]

# Exclude unnecessary translation files
CONDA_EXCLUDE_FILES += [f'translations/{x}' for x in [
    'assistant*', 'designer*', 'linguist*', 'qt_*', 'qtbase*', 'qtconnectivity*', 
    'qtdeclarative*', 'qtlocation*', 'qtmultimedia*', 'qtquickcontrols*', 
    'qtscript*', 'qtserialport*', 'qtwebsockets*', 'qtxmlpatterns*'
]]

# Path to resources - assumes script is run from the build scripts directory
# You can adjust this path based on your project structure
BUILD_SCRIPTS_DIR = Path.cwd()  # Current working directory
RESOURCES_DIR = BUILD_SCRIPTS_DIR / "opensesame_resources"

# Path to the icon of the app
ICON_PATH = str(RESOURCES_DIR / "opensesame.icns")

# The entry script of the application in the environment's bin folder
ENTRY_SCRIPT = "opensesame"

# Folder to place created APP and DMG in
OUTPUT_FOLDER = str(BUILD_SCRIPTS_DIR)

# Alternative: Put output on Desktop
# OUTPUT_FOLDER = str(HOME / "Desktop")

# Information about file types that the app can handle
APP_SUPPORTED_FILES = {
    "CFBundleDocumentTypes": [
        {
            'CFBundleTypeName': "OpenSesame experiment",
            'CFBundleTypeRole': "Editor",
            'LSHandlerRank': "Owner",
            'CFBundleTypeIconFile': os.path.basename(ICON_PATH),
            'LSItemContentTypes': ["nl.cogsci.osdoc.osexp"],
            'NSExportableTypes': ["nl.cogsci.osdoc.osexp"]
        }
    ],
    "UTExportedTypeDeclarations": [
        {
            'UTTypeConformsTo': ['org.gnu.gnu-zip-archive'],
            'UTTypeDescription': "OpenSesame experiment",
            'UTTypeIdentifier': "nl.cogsci.osdoc.osexp",
            'UTTypeTagSpecification': {
                'public.filename-extension': 'osexp',
                'public.mime-type': 'application/gzip'
            }
        }
    ]
}

# Placed here to not let linter go crazy. Will be overwritten by main program
RESOURCE_DIR = ""

# ===== Settings specific to dmgbuild =====

# Create a DMG template name, so version can be overwritten if it can be
# determined from the OS libraries.
os_dmg_template = 'opensesame_{}-py313-macos-x64-1.dmg'

# Name of the DMG file that will be created in OUTPUT_FOLDER
DMG_FILE = os_dmg_template.format(VERSION)

# DMG format (UDZO = compressed)
DMG_FORMAT = 'UDZO'

# Locations of shortcuts in DMG window
DMG_ICON_LOCATIONS = {
    APP_NAME + '.app': (5, 452),
    'Applications': (200, 450)
}

# Size of DMG window when mounted
DMG_WINDOW_RECT = ((300, 200), (358, 570))

# Size of icons in DMG
DMG_ICON_SIZE = 80

# Background of DMG file
DMG_BACKGROUND = str(RESOURCES_DIR / "instructions.png")

# ===============================================================================
# Extra settings and functions specific to OpenSesame (Remove for other apps)
# ===============================================================================

LOCAL_LIB_FOLDER = "/usr/local/lib"

# Try to obtain OpenSesame version from OpenSesame source
# Note: Updated to use Python 3.13 path
os_metadata_file = os.path.join(CONDA_ENV_PATH, 'lib', 'python3.13',
                               'site-packages', 'libopensesame', 'metadata.py')

# Auto-detect Python version if needed
if not os.path.exists(os_metadata_file):
    # Try to find the correct Python version
    lib_path = Path(CONDA_ENV_PATH) / 'lib'
    python_dirs = [d for d in lib_path.iterdir() if d.is_dir() and d.name.startswith('python')]
    if python_dirs:
        python_version = python_dirs[0].name
        os_metadata_file = str(lib_path / python_version / 'site-packages' / 'libopensesame' / 'metadata.py')

try:
    with open(os_metadata_file, 'r') as fp:
        metadata = fp.read()
except Exception as e:
    print(f"Could not read OpenSesame version from metadata: {e}")
else:
    version_match = re.search(r"(?<=__version__)\s*=\s*u?'(.*)'", metadata)
    if version_match:
        VERSION = version_match.group(1)

    codename_match = re.search(r"(?<=codename)\s*=\s*u?'(.*)'", metadata)
    if codename_match:
        codename = codename_match.group(1)
        LONG_VERSION = f"{VERSION} {codename}"
    else:
        LONG_VERSION = VERSION

    # Overwrite name of the DMG file that will be created in OUTPUT_FOLDER
    DMG_FILE = os_dmg_template.format(VERSION)

    print(f"Creating app for {APP_NAME} {LONG_VERSION}")


def extra():
    """Called after copying conda env to perform OpenSesame-specific modifications"""
    # Copy the opensesame entry script to a file with the .py extension
    # otherwise multiprocessing doesn't work
    copy_opensesame_with_py_ext()
    # Create qt.conf files, to enable Qt to find all libraries inside the app
    compose_qtconf()
    # Fix some hardcoded conda paths
    fix_paths()


def fix_paths():
    """Fix hardcoded paths in Jupyter kernel configuration"""
    kernel_json = os.path.join(
        RESOURCE_DIR, 'share', 'jupyter', 'kernels', 'python3', 'kernel.json')
    if os.path.exists(kernel_json):
        print('Fixing kernel.json')
        with open(kernel_json, 'r') as fp:
            kernelCfg = json.load(fp)
            kernelCfg['argv'][0] = 'python'
        with open(kernel_json, 'w+') as fp:
            json.dump(kernelCfg, fp, indent=2)


def compose_qtconf():
    """Create qt.conf files to help Qt find resources within the app bundle
    
    The QtWebEngineProcess uses its own qt.conf and ignores the general one,
    so a separate one is created for QtWebEngineProcess in the libexec dir.
    """
    qtconf = os.path.join(RESOURCE_DIR, 'bin', 'qt.conf')
    qtconf_wep = os.path.join(RESOURCE_DIR, 'libexec', 'qt.conf')

    contents = """[Paths]
Prefix = ..
Binaries = bin
Libraries = lib
Headers = include/qt
Plugins = plugins
Translations = translations
"""

    contents_wep = """[Paths]
Prefix = ..
Translations = translations
"""

    with open(qtconf, "w+") as f:
        f.write(contents)

    # Create libexec directory if it doesn't exist
    os.makedirs(os.path.dirname(qtconf_wep), exist_ok=True)
    with open(qtconf_wep, "w+") as f:
        f.write(contents_wep)


def copy_opensesame_with_py_ext():
    """Copy bin/opensesame to bin/opensesame.py to enable multiprocessing"""
    try:
        shutil.copy(
            os.path.join(RESOURCE_DIR, 'bin', ENTRY_SCRIPT),
            os.path.join(RESOURCE_DIR, 'bin', ENTRY_SCRIPT + '.py')
        )
    except IOError as e:
        print(f"Could not copy opensesame to opensesame.py: {e}")


def cleanup_conda():
    """Remove unnecessary files from the conda environment (currently unused)"""
    try:
        folders = [
            os.path.join(RESOURCE_DIR, 'translations'),
        ]
        for folder in folders:
            if os.path.exists(folder):
                shutil.rmtree(folder)
    except IOError as e:
        print(f"Error during cleanup: {e}")