import datetime
import glob
import json
import os
import pathlib
import shutil
import sys
import time
import py_compile

import requests.certs
from cx_Freeze import setup, Executable

from buildtools import cython_setup

# ----
# TOGGLE WHAT GETS BUILT HERE
CYTHONIZE_HEARTBROKEN = True
BUILD_HEARTBROKEN = True
BUILD_UPDATER = False
# ----


BUILD_PATH = './build/heartbroken_win/' if sys.platform == 'win32' else './build/heartbroken_linux/'
BUILD_PATH = pathlib.Path(BUILD_PATH).absolute()


def insert_secrets():
    print('Injecting secrets...')

    with open('secrets.json') as f:
        secrets = json.loads(f.read())

    client_id = secrets['client_id']
    token_url = secrets['token_url']

    shutil.copy2('./libs/tokenhandler.py', './libs/tokenhandler.bak')
    with open('./libs/tokenhandler.py') as f:
        source = f.read()

    os.remove('./libs/tokenhandler.py')

    source = source.replace('{inject_client_id}', client_id, 1).replace('{inject_token_url}', token_url, 1)
    with open('./libs/tokenhandler.py', 'w') as f:
        f.write(source)

    print('Secrets injected')


def restore_nosecrets_file():
    print('Removing secrets...')
    os.remove('./libs/tokenhandler.py')
    shutil.copy2('./libs/tokenhandler.bak', './libs/tokenhandler.py')
    os.remove('./libs/tokenhandler.bak')
    print('Secrets removed')


def cythonize_heartbroken(target_packages):
    cython_setup.run_cython(['.'] + target_packages)

    for src_dir, _, files in os.walk('./heartbroken'):
        dst_dir = src_dir.replace('heartbroken', '', 1)

        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)

        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.exists(dst_file):
                os.remove(dst_file)
            try:
                shutil.copy(src_file, dst_dir)
            except FileNotFoundError:
                print(f'WARN: shutil couldn\'t find {src_file}')


def rmtree(pth: pathlib.Path):
    for sub in pth.iterdir():
        if sub.is_dir():
            rmtree(sub)
        else:
            sub.unlink()

    while True:
        try:
            pth.rmdir()
            break
        except OSError:  # Folder not yet empty, wait for OS to catch up
            time.sleep(.05)


def copy_requirements():
    if sys.platform == 'win32':
        try:
            shutil.copy('build/heartbroken_win/lib/VCRUNTIME140.dll', 'build/heartbroken_win/')
        except FileNotFoundError:
            print('WARN: Could not find VCRUNTIME140.dll in build/heartbroken_win/lib')


def main():
    # Cleanup .pyc caches
    for path in glob.glob('./**/__pycache__', recursive=True):
        path = os.path.abspath(path)

        try:
            shutil.rmtree(os.path.abspath(path))

        except PermissionError:
            print('Warning: __pycache__ cleanup failed due to running Python process')
            print('This probably won\'t cause issues, but you\'ll be sorry if it does!')

    # ----
    # Grab the secrets from secrets.json and inject them into the file
    insert_secrets()

    TARGET_PACKAGES = ['libs']

    if CYTHONIZE_HEARTBROKEN:
        cythonize_heartbroken(TARGET_PACKAGES)

    TARGET_DIRECTORIES = ['./' + package for package in TARGET_PACKAGES]
    sys.path.extend(TARGET_DIRECTORIES)

    build_options = {
        'build_exe': {
            'build_exe': BUILD_PATH,
            #'namespace_packages': [ ],

            # Remove package paths from tracebacks
            'replace_paths': [('C:/Users/under/Desktop/', '\\'),
                              ('C:/Python/Python38/Lib/site-packages/cx_Freeze/initscripts/', '\\initscripts\\'),
                              ('C:/Python/Python38/', '\\runtime\\'),
                              ('*', '\\')],

            "includes": [ ],

            'bin_includes': [ ],

            'include_files': [('./resources/heartbroken.ico', './resources/heartbroken.ico'),
                              ('./resources/heartbroken-paused.ico', './resources/heartbroken-paused.ico'),
                              (requests.certs.where(), 'lib/cacert.pem')
                              ],

            'packages': TARGET_PACKAGES + [
                'ctypes', 'datetime', 'http.server', 'json', 'multiprocessing', 'os', 'queue', 'sqlite3', 'sys', 'time', 'typing', 'urllib.parse', 'webbrowser',
                'encodings', 'encodings.cp949', 'encodings.utf_8', 'encodings.ascii',
                'pkg_resources._vendor', 'requests', 'requests_oauthlib',
                'pywintypes', 'win32api', 'win32con', 'win32gui_struct', 'win32gui'
            ],

            'excludes': [
                'tkinter', 'cProfile', 'profile', 'pdb', 'pydoc', 'doctest', 'cryptography', #'cryptography.hazmat.bindings._openssl', 'cryptography.hazmat.bindings._rust',
                'Cython', 'zodbpickle', 'lib2to3', 'unittest', 'asyncio', 'jinja2', 'ctypes.test'
            ],

            # cx_freeze includes JRE DLLs for unknown reasons
            'bin_excludes': glob.glob('C:/Program Files/Eclipse Adoptium/**/*.dll', recursive=True),

            'zip_include_packages': '*',
            'zip_exclude_packages': [ ],

            'include_msvcr': True,
            'optimize': 2,
        }
    }

    if sys.platform == 'win32':
        executables = [Executable('heartbroken.py',
                                  target_name='heartbroken.exe',
                                  icon='resources/heartbroken.ico')
                       ]

        build_options['build_exe']['packages'].append('win32api')

    else:
        executables = [Executable('heartbroken.py',
                                  target_name='heartbroken',
                                  icon='resources/heartbroken.ico')
                       ]

    if BUILD_HEARTBROKEN:
        print('\n=====\nBuilding Heartbroken...\n')
        setup(name='Heartbroken',
              version='2.0.0',
              description='Heartbroken - Dislike for Spotify',
              options=build_options,
              executables=executables
        )

    """
    if BUILD_UPDATER:
        print('\n=====\nBuilding Updater...\n')
        setup(name='updater',
              version='2.0.0',
              description='Heartbroken updater',
              executables=[Executable('updater.py')],
              options={
                'build_exe': {
                    'build_exe': BUILD_PATH / 'updater',
                    'packages': [ ],
                    'include_files': [(requests.certs.where(), 'lib/cacert.pem')],
                    # 'zip_include_packages': '*',
                    # 'zip_exclude_packages': [],

                    'excludes': ['tkinter'],

                    # Remove package paths from tracebacks
                    # 'replace_paths': [('*', '/')],

                    'include_msvcr': True
                }
            }
        )
    """

    # ----
    copy_requirements()

    # ----
    
    cython_setup.cleanup_pyd()

    print(f'\nBuild of Heartbroken completed at {datetime.datetime.now().strftime("%I:%M%p on %m/%d (%A)")}')


if __name__ == '__main__':
    try:
        main()
    except Exception as ex:
        raise
    finally:
        cython_setup.cleanup_pyd()  # Clean up .pyd/.so's alongside .py's leftover from build
        restore_nosecrets_file()    # Replace real keys with placeholders
