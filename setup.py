"""
py2app build script for 3GP Converter.

Usage:
    pip install py2app
    python setup.py py2app

The resulting .app will be in ./dist/
"""
from setuptools import setup

APP = ["convert_3gp.py"]
DATA_FILES = ["logo_header.png"]
OPTIONS = {
    "argv_emulation": False,
    "semi_standalone": False,
    "iconfile": "AppIcon.icns",
    "packages": [],
    "plist": {
        "CFBundleName": "3GP Converter",
        "CFBundleDisplayName": "3GP Converter",
        "CFBundleIdentifier": "com.local.threegpconverter",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,   # respect system dark mode
        "LSMinimumSystemVersion": "12.0",
    },
}

setup(
    name="3GP Converter",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
