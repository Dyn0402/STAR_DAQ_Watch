#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on March 24 10:56 PM 2022
Created in PyCharm
Created as STAR_DAQ_Watch/installer.py

@author: Dylan Neff, Dylan
"""

import PyInstaller.__main__


PyInstaller.__main__.run([
    'main.py',
    '-y',
    '--noconsole',
    '-n daq_watch_v5',
    '--add-data=Alarm04.wav;.',
    '--add-data=chimes.wav;.',
    '--add-data=chord.wav;.',
    '--add-data=notify.wav;.',
    '--add-data=chromedriver_win.exe;.',
    '--add-data=geckodriver_win.exe;.',
])


def main():
    print('donzo')


if __name__ == '__main__':
    main()
