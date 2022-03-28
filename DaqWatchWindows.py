#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on March 26 6:33 PM 2022
Created in PyCharm
Created as STAR_DAQ_Watch/DaqWatchWindows.py

@author: Dylan Neff, Dylan
"""

import tkinter as tk
from tkinter import scrolledtext, Label, Button, Entry, LEFT, Toplevel
from tkinter.ttk import Notebook, Frame


class ReadmeWindow(Toplevel):
    def __init__(self, root_window=None):
        super().__init__(master=root_window)
        self.title('DAQ Watch Readme')
        self.geometry('800x200')
        self.readme = Label(self, anchor='e', justify=LEFT,
                            text='This program opens a firefox browser and watches the DAQ Monitor webpage.\n'
                                 'Click "Start" to begin monitoring, "Stop" to end.\n'
                                 'The "Silence" button will mute all sounds until "Unsilence" is clicked.\n'
                                 'The "Chimes" button will toggle on/off the sound immediately indicating a '
                                 'detector is dead.\n'
                                 'The selenium webdriver this program runs on will be restarted after a run stops \n'
                                 'to deal with the driver instance continuously accumulating memory usage.')
        self.readme.pack()


class ParametersWindow(Toplevel):
    def __init__(self, watch_gui=None, watcher=None):
        if watch_gui is None:
            return  # Need gui
        elif watcher is None:
            watch_gui.print_status('No DAQ Watcher is ')
        super().__init__(master=root_window)
        self.title('Set DAQ Watch Parameters')
        self.geometry('400x400')
        self.tab_control = Notebook(self)

        self.tab_general = Frame(self.tab_control)
        self.tab_dead_timers = Frame(self.tab_control)

        self.tab_control.add(self.tab_general, text='General')
        self.tab_control.add(self.tab_dead_timers, text='Dead Timers')
        self.tab_control.pack(expand=1, fill='both')

    def create_par_tab(self, tab, *vals):
        pass
