#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on March 21 2:22 AM 2022
Created in PyCharm
Created as STAR_DAQ_Watch/main

Dependencies: Selenium 4.1.3, simpleaudio 1.0.4, pydub 0.25.1, time, datetime, sys.platform
libasound2-dev on linux

Script to monitor STAR online DAQ Monitor webpage using selenium package. In an infinite loop, page is refreshed and
each detector dead time is read out. If any is close above some threshold value (~90%) the detector is considered dead.
If a new detector is dead, soft chime will sound to indicate if chime option is true. If a detector is dead for a
longer period of time as defined in set_alarm_times, a louder and persistent alarm will sound. This alarm stays on
until no detectors are found to be dead.
Selenium webdrivers will accumulate memory until closed. Now restart webdriver after each run to fix this issue.

@author: Dylan Neff, Dyn04
"""

from DaqWatchGUI import DaqWatchGUI


def main():
    DaqWatchGUI()
    print('donzo')


if __name__ == '__main__':
    main()
