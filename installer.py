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


def main():
    version_name = 'daq_watch_v8'
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
    shutil.copy('./watcher_config.ini', f'./dist/{version_name}/watcher_config.ini')
    shutil.copytree('./audio_files', f'./dist/{version_name}/audio_files')
    shutil.copytree('./drivers', f'./dist/{version_name}/drivers')

    print('donzo')


if __name__ == '__main__':
    main()
