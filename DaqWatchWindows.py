#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on March 26 6:33 PM 2022
Created in PyCharm
Created as STAR_DAQ_Watch/DaqWatchWindows.py

@author: Dylan Neff, Dylan
"""

from tkinter import Label, Button, Entry, LEFT, RIGHT, BOTTOM, TOP, Toplevel
from tkinter.ttk import Notebook, Frame


class ReadmeWindow(Toplevel):
    def __init__(self, root_window):
        super().__init__(master=root_window)
        self.title('DAQ Watch Readme')
        self.window_width, self.window_height = 600, 250
        self.geometry(f'{self.window_width}x{self.window_height}')
        self.readme = Label(self, anchor='e', justify=LEFT, font=('ariel', 12), wraplength=self.window_width * 0.9,
                            text='This program opens a browser and watches the DAQ Monitor webpage.\n'
                                 'Click "Start" to begin monitoring, "Stop" to end.\n'
                                 'The "Silence" button will mute all sounds until "Unsilence" is clicked.\n'
                                 'The "Chimes" button will toggle on/off the sound that indicates a detector that '
                                 'wasn\'t dead previously is now dead.\n'
                                 'The Set Parameters button opens a window in which various parameters can be altered. '
                                 'To make a change, set the desired parameter value in the text box and click the Set '
                                 'button. This will reset all parameter values to those shown in the window.\n'
                                 'The selenium webdriver this program runs on will be restarted after a run stops '
                                 'to deal with the driver instance continuously accumulating memory usage.\n'
                                 'Email Dylan Neff for issues: dneff@physics.ucla.edu')
        self.readme.pack(side=LEFT)


class ParametersWindow(Toplevel):
    def __init__(self, root_window, watch_gui=None, watcher=None):
        if watch_gui is None:
            return  # Need gui
        else:
            self.watch_gui = watch_gui
        if watcher is None:
            self.watch_gui.print_status('No DAQ Watcher is open?')
        else:
            self.watcher = watcher

        super().__init__(master=root_window)
        self.title('Set DAQ Watch Parameters')
        self.window_width, self.window_height = 650, 600
        self.geometry(f'{self.window_width}x{self.window_height}')
        self.tab_control = Notebook(self)

        self.tab_general = Frame(self.tab_control)
        self.tab_alarm_times = Frame(self.tab_control)

        self.tab_control.add(self.tab_general, text='General')
        self.tab_control.add(self.tab_alarm_times, text='Alarm Times')
        self.tab_control.pack(expand=1, fill='both')

        self.general_vars = {
            'run_start_buffer': 'min_run_time',
            'daq_hz_minimum': 'daq_hz_thresh',
            'run_duration_target': 'run_duration_min',
            'run_over_alarm_time': 'run_dur_alarm_time',
            'loop_sleep': 'refresh_sleep',
            'dead_threshold': 'dead_thresh',
        }

        self.general_descriptions = {
            'run_start_buffer': '(s) How long to wait at beginning of run before starting to watch DAQ',
            'daq_hz_minimum': '(Hz) Any total DAQ rate lower than this will sound alarm unless a '
                              'detector is dead',
            'run_duration_target': '(min) Run duration at which run stop reminder is played',
            'run_over_alarm_time': '(s) How long to keep playing run stop reminder alarm',
            'loop_sleep': '(s) How long program sleeps after checking daq. Page only updates every ~2s.',
            'dead_threshold': '(%) Threshold above which to consider detectors dead. ',
        }

        self.general_info = 'Set general parameters dealing with thresholds and times'
        self.alarm_time_info = 'Set alarm time for each detector. This is defined as the amount of time the detector ' \
                               'is dead before the alarm is sounded. All values in seconds.'

        self.alarm_time_desc = {det: 's' for det in self.watcher.alarm_times}

        self.general_entries = self.create_par_tab(self.tab_general, self.general_vars, self.general_info,
                                                   self.general_descriptions)

        self.alarm_time_entries = self.create_par_tab(self.tab_alarm_times, self.watcher.alarm_times,
                                                      self.alarm_time_info, self.alarm_time_desc, immute=False)

    def create_par_tab(self, tab, parameter_vars, info_text='', descriptions=None, immute=True):
        Label(tab, text=info_text, wraplength=self.window_width * 0.9, justify=LEFT).place(x=0, y=0)
        entries = {name: None for name in parameter_vars}
        pady, x_name, x_entry, x_desc = 35, 0, 130, 180
        y = 50
        for name, variable in parameter_vars.items():
            Label(tab, text=f'{name}:', width=17, anchor='e').place(x=x_name, y=y)
            entries[name] = Entry(tab, width=7)
            entries[name].place(x=x_entry, y=y+2)
            if immute:  # Looking at immutables, need to check from watcher
                var_val = getattr(self.watcher, variable)
            else:  # Looking at a mutable object, can read directly
                var_val = variable
            entries[name].insert(0, var_val)
            if descriptions:
                Label(tab, text=descriptions[name]).place(x=x_desc, y=y)
            y += pady

        Button(tab, text='Set', command=self.set_pars).place(x=x_desc+50, y=y + 5)

        return entries

    def set_pars(self):
        tabs = [{'vars': self.general_vars, 'entries': self.general_entries, 'immute': True},
                {'vars': self.watcher.alarm_times, 'entries': self.alarm_time_entries, 'immute': False}]

        for tab in tabs:
            for name in tab['vars']:  # All floats for now luckily
                entry = tab['entries'][name].get()
                if entry != '':
                    try:
                        if tab['immute']:  # Need to set in watcher
                            setattr(self.watcher, tab['vars'][name], float(entry))  # Set the value in watcher
                        else:  # Can set from object directly
                            tab['vars'][name] = float(entry)  # Set the value in watcher
                    except ValueError:
                        self.watch_gui(f'{name} set to {entry}, couldn\'t be converted to float. Ignoring.')

        self.watch_gui.print_status('\nParameters set')

        self.watcher.write_config()  # Have watcher write new values to config file to keep as default
