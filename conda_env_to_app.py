#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import fileinput
import glob
import logging
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import time
import tokenize
from datetime import date
from pathlib import Path
import tempfile
import argparse

import dmgbuild
import magic
import six

# Improved logging setup
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MacAppBuilder:
    """Class to encapsulate Mac app building functionality"""
    
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.config = {}
        self.load_config()
        self.validate_config()
        
    def load_config(self):
        """Load configuration from settings file"""
        try:
            encoding = 'utf-8'
            with open(self.config_file_path, 'rb') as fp:
                try:
                    encoding = tokenize.detect_encoding(fp.readline)[0]
                except SyntaxError:
                    pass
            
            # Use a safer approach to load config
            config_globals = {}
            with open(self.config_file_path, 'r', encoding=encoding) as fp:
                exec(compile(fp.read(), self.config_file_path, 'exec'), config_globals)
            
            # Extract configuration variables
            self.config = {k: v for k, v in config_globals.items() 
                          if not k.startswith('__')}
            
        except IOError as e:
            logger.error(f"Could not read app config file: {e}")
            sys.exit(1)
    
    def validate_config(self):
        """Validate required configuration variables"""
        required_vars = [
            'APP_NAME', 'OUTPUT_FOLDER', 'VERSION', 
            'AUTHOR', 'CONDA_ENV_PATH', 'ENTRY_SCRIPT', 'IDENTIFIER'
        ]
        
        missing = [var for var in required_vars if var not in self.config]
        if missing:
            logger.error(f"Missing required configuration variables: {', '.join(missing)}")
            sys.exit(1)
        
        # Expand paths
        self.config['CONDA_ENV_PATH'] = os.path.expanduser(self.config['CONDA_ENV_PATH'])
        self.config['OUTPUT_FOLDER'] = os.path.expanduser(self.config['OUTPUT_FOLDER'])
        
        # Validate conda environment exists
        if not os.path.exists(self.config['CONDA_ENV_PATH']):
            logger.error(f"Conda environment not found at: {self.config['CONDA_ENV_PATH']}")
            sys.exit(1)
        
        # Set up derived paths
        self.app_file = os.path.join(self.config['OUTPUT_FOLDER'], 
                                    self.config['APP_NAME'] + '.app')
        self.macos_dir = os.path.join(self.app_file, 'Contents/MacOS')
        self.resource_dir = os.path.join(self.app_file, 'Contents/Resources')
        self.app_script = os.path.join(self.macos_dir, self.config['APP_NAME'])
    
    def find_and_replace(self, path, search, replace, exclusions=None):
        """Improved find and replace with better error handling"""
        if exclusions is None:
            exclusions = []
        
        processed_files = 0
        failed_files = []
        
        for root, _, files in os.walk(path):
            # Check exclusions
            if any(excl in root for excl in exclusions):
                continue
            
            logger.debug(f'Scanning {root}')
            
            for f in files:
                full_path = os.path.join(root, f)
                
                try:
                    # Use file command instead of python-magic for better reliability
                    result = subprocess.run(['file', '--mime-type', full_path], 
                                          capture_output=True, text=True)
                    mime_type = result.stdout.strip().split(': ')[-1]
                    
                    # Only process text files
                    if not mime_type.startswith('text/'):
                        continue
                    
                    # Read and replace
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as file:
                        content = file.read()
                    
                    if search in content:
                        new_content = content.replace(search, replace)
                        with open(full_path, 'w', encoding='utf-8') as file:
                            file.write(new_content)
                        processed_files += 1
                        
                except Exception as e:
                    logger.warning(f'Unable to process {full_path}: {e}')
                    failed_files.append(full_path)
        
        logger.info(f"Processed {processed_files} files, {len(failed_files)} failures")
        return processed_files, failed_files
    
    def create_app(self, clear=True):
        """Main method to create the app bundle"""
        if os.path.exists(self.app_file):
            if not clear:
                logger.info("Skipping app creation")
                return False
            logger.info("Removing previous app")
            shutil.rmtree(self.app_file)
        
        logger.info("Creating app bundle...")
        start_time = time.time()
        
        # try:
        self.create_app_structure()
        self.copy_conda_env()
        self.copy_icon()
        self.create_plist()
        self.create_launcher_script()
        self.fix_paths()
        self.cleanup_bundle()
        self.code_sign()
        
        elapsed = time.time() - start_time
        logger.info(f"App creation completed in {elapsed:.1f} seconds")
        return True
            
        # except Exception as e:
            # logger.error(f"App creation failed: {e}")
            # if os.path.exists(self.app_file):
                # shutil.rmtree(self.app_file)
            # raise
    
    def create_app_structure(self):
        """Create the basic app bundle structure"""
        logger.info("Creating app structure")
        os.makedirs(self.macos_dir, exist_ok=True)
        os.makedirs(self.resource_dir, exist_ok=True)
    
    def create_launcher_script(self):
        """Create improved launcher script"""
        logger.info("Creating launcher script")
        
        launcher_content = '''#!/usr/bin/env bash
# Get the directory of this script
DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" && pwd )"
CONTENTS_DIR="$(dirname "$DIR")"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

# Set up environment
export PATH="$RESOURCES_DIR/bin:$PATH"
export PYTHONHOME="$RESOURCES_DIR"
export PYTHONNOUSERSITE=1

# Disable user site-packages to ensure isolation
export PYTHONUSERBASE=/dev/null

# Launch the application
exec "$RESOURCES_DIR/bin/python" "$RESOURCES_DIR/bin/{entry_script}" "$@"
'''.format(entry_script=self.config['ENTRY_SCRIPT'])
        
        with open(self.app_script, 'w') as f:
            f.write(launcher_content)
        
        # Make executable
        os.chmod(self.app_script, 0o755)
    
    def copy_conda_env(self):
        """Copy conda environment with progress indication"""
        logger.info("Copying Anaconda environment (this may take a while)...")
        
        # If specific folders are defined, copy only those
        if 'CONDA_FOLDERS' in self.config:
            for folder in self.config['CONDA_FOLDERS']:
                src = os.path.join(self.config['CONDA_ENV_PATH'], folder)
                dst = os.path.join(self.resource_dir, folder)
                if os.path.exists(src):
                    shutil.copytree(src, dst, symlinks=True)
        else:
            # Copy entire environment
            shutil.copytree(self.config['CONDA_ENV_PATH'], self.resource_dir,
                            symlinks=True, dirs_exist_ok=True)
    
    def cleanup_bundle(self):
        """Remove unnecessary files from bundle"""
        logger.info("Cleaning up bundle...")
        
        # Default exclusions
        default_exclusions = [
            '*.pyc',
            '__pycache__',
            '.DS_Store',
            'include/',
            'share/doc/',
            'share/man/',
            'conda-meta/',
            'pkgs/',
        ]
        
        exclusions = self.config.get('CONDA_EXCLUDE_FILES', []) + default_exclusions
        
        for pattern in exclusions:
            for path in Path(self.resource_dir).rglob(pattern):
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    logger.debug(f"Removed: {path}")
                except Exception as e:
                    logger.warning(f"Could not remove {path}: {e}")
    
    def fix_paths(self):
        """Fix hardcoded paths in the bundle"""
        app_path = os.path.join('/Applications', self.config['APP_NAME'] + '.app', 
                               'Contents', 'Resources')
        logger.info(f"Replacing {self.config['CONDA_ENV_PATH']} with {app_path}")
        
        self.find_and_replace(
            self.resource_dir,
            self.config['CONDA_ENV_PATH'],
            app_path,
            exclusions=['site-packages', 'doc', 'Resources/lib/python']
        )
    
    def copy_icon(self):
        """Copy icon file if specified"""
        if 'ICON_PATH' not in self.config:
            return
        
        icon_path = os.path.expanduser(self.config['ICON_PATH'])
        if not os.path.exists(icon_path):
            logger.warning(f"Icon file not found: {icon_path}")
            return
        
        logger.info("Copying icon file")
        icon_filename = os.path.basename(icon_path)
        shutil.copy(icon_path, os.path.join(self.resource_dir, icon_filename))
    
    def create_plist(self):
        """Create Info.plist with improved structure"""
        logger.info("Creating Info.plist")
        
        info_plist = {
            'CFBundleDevelopmentRegion': 'en',
            'CFBundleExecutable': self.config['APP_NAME'],
            'CFBundleIdentifier': self.config['IDENTIFIER'],
            'CFBundleInfoDictionaryVersion': '6.0',
            'CFBundleName': self.config['APP_NAME'],
            'CFBundleDisplayName': self.config['APP_NAME'],
            'CFBundlePackageType': 'APPL',
            'CFBundleVersion': self.config.get('LONG_VERSION', self.config['VERSION']),
            'CFBundleShortVersionString': self.config['VERSION'],
            'CFBundleSignature': '????',
            'LSMinimumSystemVersion': '10.9.0',
            'LSUIElement': False,
            'NSHighResolutionCapable': True,
            'NSSupportsAutomaticGraphicsSwitching': True,
            'NSHumanReadableCopyright': f'© {date.today().year} {self.config["AUTHOR"]}',
        }
        
        # Add icon if present
        if 'ICON_PATH' in self.config:
            info_plist['CFBundleIconFile'] = os.path.basename(self.config['ICON_PATH'])
        
        # Add file associations if specified
        if 'APP_SUPPORTED_FILES' in self.config:
            info_plist.update(self.config['APP_SUPPORTED_FILES'])
        
        # Add additional plist entries if specified
        if 'PLIST_ADDITIONS' in self.config:
            info_plist.update(self.config['PLIST_ADDITIONS'])
        
        plist_path = os.path.join(self.app_file, 'Contents', 'Info.plist')
        with open(plist_path, 'wb') as f:
            plistlib.dump(info_plist, f)
    
    def code_sign(self):
        """Attempt to code sign the app"""
        if not self.config.get('CODE_SIGN', False):
            return
        
        logger.info("Code signing app...")
        identity = self.config.get('SIGNING_IDENTITY', '-')  # '-' for ad-hoc signing
        
        try:
            subprocess.run([
                'codesign', '--force', '--deep', '--sign', identity, self.app_file
            ], check=True)
            logger.info("Code signing successful")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Code signing failed: {e}")
    
    def create_dmg(self, clear=True):
        """Create DMG with improved error handling"""
        dmg_filename = self.config.get('DMG_FILE', self.config['APP_NAME'] + '.dmg')
        dmg_path = os.path.join(self.config['OUTPUT_FOLDER'], dmg_filename)
        
        if clear and os.path.exists(dmg_path):
            os.remove(dmg_path)
        
        logger.info("Creating DMG...")
        
        # Calculate size
        app_size_bytes = sum(f.stat().st_size for f in Path(self.app_file).rglob('*'))
        dmg_size = str(int(app_size_bytes * 1.3 / 1024 / 1024)) + 'M'
        
        dmg_config = {
            'filename': dmg_path,
            'volume_name': self.config['APP_NAME'],
            'size': dmg_size,
            'files': [self.app_file],
            'symlinks': {'Applications': '/Applications'},
            'format': self.config.get('DMG_FORMAT', 'UDZO'),  # UDZO = compressed
        }
        
        # Add optional DMG configuration
        for key in ['badge_icon', 'background', 'icon_size', 'icon_locations', 'window_rect']:
            config_key = 'DMG_' + key.upper()
            if config_key in self.config:
                dmg_config[key] = self.config[config_key]
        
        # Create temporary settings file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("# -*- coding: utf-8 -*-\n")
            for key, value in dmg_config.items():
                if isinstance(value, str):
                    f.write(f'{key} = "{value}"\n')
                else:
                    f.write(f'{key} = {value}\n')
            temp_settings = f.name
        
        try:
            dmgbuild.build_dmg(dmg_path, self.config['APP_NAME'], 
                             settings_file=temp_settings)
            logger.info(f"DMG created: {dmg_path}")
        finally:
            os.unlink(temp_settings)


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description='Build macOS app bundles from Anaconda environments'
    )
    parser.add_argument('config', help='Path to settings.py configuration file')
    parser.add_argument('--clear', action='store_true',
                        help='Clear current source folder and DMG if they exists')
    parser.add_argument('--build', action='store_true',
                        help='Builds the source folder for the dmg')
    parser.add_argument('--dmg', action='store_true', 
                       help='Also create a DMG disk image')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Build the app
    builder = MacAppBuilder(args.config)
    
    if args.build:
        if builder.create_app(args.clear):
            logger.info("App bundle created successfully!")
        
    if args.dmg:
        builder.create_dmg(args.clear)
    
    logger.info("Done! 🎉")

if __name__ == "__main__":
    main()