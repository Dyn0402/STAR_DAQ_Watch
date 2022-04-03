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

from sys import platform
import os
import subprocess
from time import sleep
from threading import Thread

from DaqWatcher import DaqWatcher
from DaqWatchWindows import ParametersWindow, ReadmeWindow


class DaqWatchGUI:
    def __init__(self):
        self.window = None
        self.set_window()

        self.status_text = scrolledtext.ScrolledText(self.window, wrap=tk.WORD, width=59, height=10, font=('ariel', 10))
        self.status_text.place(x=10, y=100)

        self.start_stop_button = Button(self.window, text='Start', font=('arial', 15), command=self.start_click)
        self.start_stop_button.place(x=10, y=28)
        self.silence_button = Button(self.window, text='Silence', font=('arial', 10), bg='blue', fg='white',
                                     command=self.silence_click)
        self.silence_button.place(x=120, y=10)
        self.chimes_button = Button(self.window, text='Chimes Are On', font=('arial', 10), bg='green', fg='white',
                                    command=self.chimes_click)
        self.chimes_button.place(x=120, y=50)
        self.readme_button = Button(self.window, text='Readme', font=('arial', 10), command=self.readme_click)
        self.readme_button.place(x=400, y=10)
        self.parameters_button = Button(self.window, text='Set Parameters', font=('arial', 10),
                                        command=self.parameters_click)
        self.parameters_button.place(x=250, y=50)
        self.trigger_screenshots_button = Button(self.window, text='Trigger Screenshots', font=('arial', 10),
                                                 command=self.trigger_screenshots_click)
        self.trigger_screenshots_button.place(x=225, y=10)

        self.status_max_lines = 10000  # Number of lines at which to clear status text
        self.status_keep_lines = 1000  # How many lines to keep when clearing status
        self.click_sleep = 0.1  # s How long to sleep after a click to keep things safe
        self.check_watcher_sleep = 0.1  # s How long to wait before updating GUI button colors

        self.readme_window = None
        self.parameters_window = None

        self.watcher = DaqWatcher(self)

        self.check_watcher_thread = Thread(target=self.check_watcher_loop, daemon=True)
        self.check_watcher_thread.start()

        self.window.protocol('WM_DELETE_WINDOW', self.on_close)

        self.window.mainloop()

    def set_window(self):
        self.window = tk.Tk()
        self.window.title('DAQ Watch')
        self.window.geometry('500x300')

    def check_watcher_loop(self):
        while self.window.winfo_exists():
            self.check_watcher()
            sleep(self.check_watcher_sleep)
        self.check_watcher_thread.raise_exception()
        self.check_watcher_thread.join()

    def check_watcher(self):
        watcher_live = self.watcher.is_alive()
        if watcher_live == 'starting':
            self.start_stop_button.configure(bg='yellow', fg='black', text='Starting', command=self.empty_click)
        elif watcher_live == 'stopping':
            self.start_stop_button.configure(bg='yellow', fg='black', text='Stopping', command=self.empty_click)
        elif watcher_live:
            self.start_stop_button.configure(bg='red', fg='white', text='Stop', command=self.stop_click)
        else:
            self.start_stop_button.configure(bg='green', fg='white', text='Start', command=self.start_click)

        if self.watcher.silent:
            self.silence_button.configure(text='Unsilence', bg='yellow', fg='black')
        else:
            self.silence_button.configure(text='Silence', bg='blue', fg='white')

        if self.watcher.dead_chime:
            self.chimes_button.configure(text='Chimes Are On', bg='green')
        else:
            self.chimes_button.configure(text='Chimes Are Off', bg='red')

    def start_click(self):
        if self.watcher.is_alive():
            self.print_status('Watcher instance already live!')
        else:
            daq_watch_thread = Thread(target=self.watcher.start, daemon=True)
            daq_watch_thread.start()
            self.check_watcher()
            sleep(self.click_sleep)  # Don't let user click again before watcher.is_alive() has a chance to change state

    def stop_click(self):
        if self.watcher.is_alive():
            stop_thread = Thread(target=self.watcher.stop, daemon=True)
            stop_thread.start()
        else:
            self.print_status('No live watchers to stop!')
        self.check_watcher()
        sleep(self.click_sleep)  # Don't let user click again before watcher.is_alive() has a chance to change state

    def silence_click(self):  # Need to indicate persistently on GUI whether silenced or not. Ideally button color.
        if self.watcher.silent:
            self.watcher.unsilence()
        else:
            self.watcher.silence()
        self.check_watcher()
        sleep(self.click_sleep)  # Don't let user click again till state switched

    def chimes_click(self):
        if self.watcher.dead_chime:
            self.watcher.dead_chime = False
            self.chimes_button.configure(text='Chimes Are Off', bg='red')
        else:
            self.watcher.dead_chime = True
            self.chimes_button.configure(text='Chimes Are On', bg='green')
        sleep(self.click_sleep)  # Don't let user click again till state switched

    def readme_click(self):
        if self.readme_window is not None and self.readme_window.winfo_exists():
            self.readme_window.state('normal')
            self.readme_window.focus_set()
        else:
            self.readme_window = ReadmeWindow(self.window)
        sleep(self.click_sleep)  # Don't let user click again till state switched

    def trigger_screenshots_click(self):
        """
        Open directory containing dead trigger screenshots
        :return:
        """
        path = os.path.abspath(self.watcher.screenshot_path)
        if not os.path.exists(path):
            self.print_status(f'Trigger Screenshot path doesn\'t exist, maybe no screenshots yet?\n{path}')
        else:
            if platform == 'darwin':
                subprocess.Popen(['open', '-R', os.path.abspath(self.watcher.screenshot_path)])
            elif 'win' in platform:
                os.startfile(os.path.abspath(self.watcher.screenshot_path))
            else:
                subprocess.Popen(['xdg-open', os.path.abspath(self.watcher.screenshot_path)])

    def parameters_click(self):
        if self.parameters_window is not None and self.parameters_window.winfo_exists():
            self.parameters_window.state('normal')
            self.parameters_window.focus_set()
        else:
            self.parameters_window = ParametersWindow(self.window, self, self.watcher)
        sleep(self.click_sleep)  # Don't let user click again till state switched

    def empty_click(self):
        pass  # It seems like making command=None just reverts to last command. This is workaround.

    def print_status(self, status):
        if self.status_text is not None:
            go_to_end = self.status_text.yview()[-1] == 1.0
            self.status_text.insert(tk.END, f'\n{status}')
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

    def on_close(self):
        self.window.destroy()
        self.window = None
        self.status_text = None  # Make sure everybody knows root window is dead, don't try to write anything else
        if self.watcher.is_alive():
            stop_thread = Thread(target=self.watcher.stop, daemon=True, args=(True,))
            stop_thread.start()
        while self.watcher.is_alive():  # Keep main thread alive long enough for daemonic stop threads to kill driver
            sleep(0.1)
