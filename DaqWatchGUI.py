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
        self.readme_button = Button(self.window, text='Readme', command=self.readme_click)
        # self.readme_button.bind('<Button>', lambda e: ReadmeWindow(self.window))
        self.readme_button.place(x=205, y=10)
        self.parameters_button = Button(self.window, text='Set Parameters', command=self.parameters_click)
        # self.parameters_button.bind('<Button>', lambda e: ParametersWindow(self.window))
        self.parameters_button.place(x=205, y=50)

        # self.test_button = Button(self.window, text='TEST', command=self.test_click)
        # self.test_button.place(x=280, y=10)

        self.status_max_lines = 5000  # Number of lines at which to clear status text
        self.status_keep_lines = 500  # How many lines to keep when clearing status

        # self.silence_time = 0.1  # min  How long to silence

        self.readme_window = None
        self.parameters_window = None

        self.watcher = DaqWatcher(self)

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

    def readme_click(self):
        if self.readme_window is not None and self.readme_window.winfo_exists():
            self.readme_window.state('normal')
            self.readme_window.focus_set()
        else:
            self.readme_window = ReadmeWindow(self.window)

    def parameters_click(self):
        if self.parameters_window is not None and self.parameters_window.winfo_exists():
            self.parameters_window.state('normal')
            self.parameters_window.focus_set()
        else:
            self.parameters_window = ParametersWindow(self.window, self, self.watcher)

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

    def test_click(self):
        if self.test_button is not None and self.watcher is not None:
            test_thread = Thread(target=self.watcher.test)
            test_thread.start()
