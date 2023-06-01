#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on March 24 10:56 PM 2022
Created in PyCharm
Created as STAR_DAQ_Watch/installer.py

@author: Dylan Neff, Dylan
"""

import PyInstaller.__main__
import shutil
import os


def main():
    # Using pyinstaller 5.11.0
    version_name = 'daq_watch_v9'
    PyInstaller.__main__.run([
        'main.py',
        '-y',
        '--noconsole',
        f'-n {version_name}',
    ])

    try:
        shutil.rmtree(f'./dist/{version_name}')
    except FileNotFoundError:
        pass
    shutil.move(f'./dist/ {version_name}', f'./dist/{version_name}')  # Get rid of pyinstaller weird space
    if os.path.exists('./watcher_config.ini'):
        shutil.copy('./watcher_config.ini', f'./dist/{version_name}/watcher_config.ini')
    shutil.copytree('./audio_files', f'./dist/{version_name}/audio_files')

    print('donzo')


if __name__ == '__main__':
    main()
