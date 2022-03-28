#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on March 24 10:51 PM 2022
Created in PyCharm
Created as STAR_DAQ_Watch/DaqWatchGUI.py

@author: Dylan Neff, Dylan
"""

import tkinter as tk
from tkinter import scrolledtext, Label, Button, Entry, LEFT, Toplevel

from time import sleep
from threading import Thread

from DaqWatcher import DaqWatcher
from DaqWatchWindows import ParametersWindow, ReadmeWindow


class DaqWatchGUI:
    def __init__(self):
        self.window = None
        self.set_window()

        self.status_text = scrolledtext.ScrolledText(self.window, wrap=tk.WORD, width=59, height=10)
        self.status_text.place(x=10, y=100)

        self.start_button = Button(self.window, text='Start', command=self.start_click)
        self.start_button.place(x=10, y=10)
        self.stop_button = Button(self.window, text='Stop', bg='red', fg='white', command=self.stop_click)
        self.stop_button.place(x=10, y=50)
        self.silence_button = Button(self.window, text='Silence', bg='blue', fg='white', command=self.silence_click)
        self.silence_button.place(x=80, y=10)
        self.chimes_button = Button(self.window, text='Chimes Are On', bg='green', fg='white',
                                    command=self.chimes_click)
        self.chimes_button.place(x=80, y=50)
        self.readme_button = Button(self.window, text='Readme')
        self.readme_button.bind('<Button>', lambda e: ReadmeWindow(self.window))
        self.readme_button.place(x=205, y=10)
        self.parameters_button = Button(self.window, text='Set Parameters')
        self.parameters_button.bind('<Button>', lambda e: ParametersWindow(self.window))
        self.parameters_button.place(x=205, y=50)
        # self.readme = Label(self.window, anchor='e', justify=LEFT,
        #                     text='This program opens a firefox browser and watches the DAQ Monitor webpage.\n'
        #                          'Click "Start" to begin monitoring, "Stop" to end.\n'
        #                          'The "Silence" button will mute all sounds until "Unsilence" is clicked.\n'
        #                          'The "Chimes" button will toggle on/off the sound immediately indicating a '
        #                          'detector is dead.\n'
        #                          'The selenium webdriver this program runs on will be restarted after a run stops \n'
        #                          'to deal with the driver instance continuously accumulating memory usage.')
        # self.readme.place(x=205, y=0)
        # self.silence_time_entry = Entry(self.window, width=5)
        # self.silence_time_entry.place(x=140, y=12)

        self.status_max_lines = 5000  # Number of lines at which to clear status text
        self.status_keep_lines = 500  # How many lines to keep when clearing status

        self.silence_time = 0.1  # min  How long to silence

        self.watcher = DaqWatcher()
        self.watcher.gui = self

        self.window.mainloop()

    def set_window(self):
        self.window = tk.Tk()
        self.window.title('DAQ Watch')
        self.window.geometry('500x300')

    def start_click(self):
        if self.watcher.is_alive():
            self.print_status('Watcher instance already live!')
        else:
            daq_watch_thread = Thread(target=self.watcher.start)
            daq_watch_thread.start()
            self.stop_button.configure(bg='#F0F0F0', fg='black')
            self.start_button.configure(bg='green', fg='white')
            sleep(0.1)  # Don't let user click again before watcher.is_alive() has a chance to change state

    def stop_click(self):
        if self.watcher.is_alive():
            stop_thread = Thread(target=self.watcher.stop)
            stop_thread.start()
            self.stop_button.configure(bg='red', fg='white')
            self.start_button.configure(bg='#F0F0F0', fg='black')
        else:
            self.print_status('No live watchers to stop!')
        sleep(0.1)  # Don't let user click again before watcher.is_alive() has a chance to change state

    def silence_click(self):  # Need to indicate persistently on GUI whether silenced or not. Ideally button color.
        if self.watcher.silent:
            self.watcher.unsilence()
            if not self.watcher.silent:
                self.silence_button.configure(text='Silence', bg='blue', fg='white')
        else:
            # entry = self.silence_time_entry.get()
            # if entry != '':
            #     try:
            #         self.watcher.silence_duration = float(entry)
            #     except ValueError:
            #         self.print_status('Bad entry for silence time. Need a float.')
            self.watcher.silence()
            if self.watcher.silent:
                self.silence_button.configure(text='Unsilence', bg='yellow', fg='black')
            # unsilence_thread = Thread(target=timer_func(self.watcher.unsilence, self.silence_time * 60))
            # unsilence_thread.start()  # not working. Google best way to set timer on tkinter
            # self.window.after(self.silence_time * 60 * 1000, self.watcher.unsilence)
        sleep(0.1)  # Don't let user click again till state switched

    def chimes_click(self):
        if self.watcher.dead_chime:
            self.watcher.dead_chime = False
            self.chimes_button.configure(text='Chimes Are Off', bg='red')
        else:
            self.watcher.dead_chime = True
            self.chimes_button.configure(text='Chimes Are On', bg='green')

    def print_status(self, status):
        if self.status_text is not None:
            go_to_end = self.status_text.yview()[-1] == 1.0
            self.status_text.insert(tk.INSERT, f'\n{status}')
            if go_to_end:
                self.status_text.see('end')
            self.window.update()
            lines = int(self.status_text.index('end-1c').split('.')[0])
            if lines > self.status_max_lines:
                self.clear_status()

    def clear_status(self):
        if self.status_text is not None:
            text = self.status_text.get('1.0', tk.END)
            text = '\n'.join(text.split('\n')[-self.status_keep_lines:])
            self.status_text.delete('1.0', tk.END)
            self.print_status(text)
