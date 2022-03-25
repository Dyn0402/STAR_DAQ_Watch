#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on March 21 2:22 AM 2022
Created in PyCharm
Created as STAR_DAQ_Watch/main

@author: Dylan Neff, Dyn04
"""

from tkinter import filedialog as fd
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext, Label, Button, Entry

from time import sleep
from threading import Thread

from DaqWatcher import DaqWatcher


class DaqWatchGUI:
    def __init__(self):
        self.window = None
        self.set_window()

        self.status_text = scrolledtext.ScrolledText(self.window, wrap=tk.WORD, width=80, height=10)
        self.status_text.grid(column=2, row=2, pady=10, padx=10)

        Button(self.window, text='Start', command=self.start_click).grid(column=0, row=0, pady=10, padx=10)
        Button(self.window, text='Stop', command=self.stop_click).grid(column=1, row=0, pady=10, padx=10)
        self.silence_button = Button(self.window, text='Silence', bg='blue', fg='white', command=self.silence_click)
        self.silence_button.grid(column=0, row=1, pady=10, padx=10)
        self.chimes_button = Button(self.window, text='Chimes On', bg='green', fg='white', command=self.chimes_click)
        self.silence_time_entry = Entry(self.window, width=5)
        self.silence_time_entry.grid(column=1, row=1, pady=10, padx=10)

        self.clear_status_interval = 5 * 60  # s How often to clear status
        self.status_clear_keep_lines = 50  # How many lines to keep when clearing status

        self.silence_time = 0.1  # min  How long to silence

        self.watcher = DaqWatcher()
        self.watcher.gui = self

        self.window.mainloop()

    def set_window(self):
        self.window = tk.Tk()
        self.window.title('DAQ Watch')
        self.window.geometry('1000x600')

    def start_click(self):
        if self.watcher.is_alive():
            self.print_status('Watcher instance already live!')
        else:
            daq_watch_thread = Thread(target=self.watcher.start)
            daq_watch_thread.start()
            sleep(0.1)  # Don't let user click again before watcher.is_alive() has a chance to change state

    def stop_click(self):
        if self.watcher.is_alive():
            stop_thread = Thread(target=self.watcher.stop)
            stop_thread.start()
        else:
            self.print_status('No live watchers to stop!')
        sleep(0.1)  # Don't let user click again before watcher.is_alive() has a chance to change state

    def silence_click(self):  # Need to indicate persistently on GUI whether silenced or not. Ideally button color.
        if self.watcher.silent:
            self.watcher.unsilence()
            # sleep(0.1)
            if not self.watcher.silent:
                self.silence_button.configure(text='Silence', bg='blue', fg='white')
        else:
            entry = self.silence_time_entry.get()
            if entry != '':
                try:
                    self.watcher.silence_duration = float(entry)
                except ValueError:
                    self.print_status('Bad entry for silence time. Need a float.')
            self.watcher.silence()
            # sleep(0.1)
            if self.watcher.silent:
                self.silence_button.configure(text='Unsilence', bg='yellow', fg='black')
            # unsilence_thread = Thread(target=timer_func(self.watcher.unsilence, self.silence_time * 60))
            # unsilence_thread.start()  # not working. Google best way to set timer on tkinter
            # self.window.after(self.silence_time * 60 * 1000, self.watcher.unsilence)
        sleep(0.1)  # Don't let user click again till state switched

    def chimes_click(self):
        pass

    def print_status(self, status):
        if self.status_text is not None:
            self.status_text.insert(tk.INSERT, f'\n{status}')
            self.status_text.see('end')
            self.window.update()

    def clear_status(self):
        if self.status_text is not None:
            text = self.status_text.get('1.0', tk.END)
            text = '\n'.join(text.split('\n')[-self.status_clear_keep_lines:])
            self.status_text.delete('1.0', tk.END)
            self.print_status(text)
        clear_status_thread = Thread(target=timer_func(self.clear_status, self.clear_status_interval))
        clear_status_thread.start()  # Probably not working
        # self.window.after(self.clear_status_interval, self.clear_status())  # Recursively clear status window on timer.


def timer_func(func, time, **args):
    sleep(time)
    func(args)


def main():
    # set_watch()
    test = DaqWatchGUI()
    print('donzo')


def set_watch():
    watcher = DaqWatcher()
    window = tk.Tk()
    watcher.window = window
    window.title('DAQ Watch')
    window.geometry('1000x600')
    # Label(window, text='Data File Path: ').grid(column=0, row=0)
    status_text = scrolledtext.ScrolledText(window, wrap=tk.WORD, width=80, height=10)
    status_text.grid(column=2, row=2, pady=10, padx=10)
    watcher.status_out = status_text
    # status_text.configure()
    Button(window, text='Start', command=watcher.start_click).grid(column=0, row=0, pady=10, padx=10)
    Button(window, text='Stop', command=watcher.stop).grid(column=1, row=0, pady=10, padx=10)
    Button(window, text='Silence', command=watcher.silence).grid(column=0, row=1, pady=10, padx=10)
    watcher.silence_entry = Entry(window, width=5).grid(column=1, row=1, pady=10, padx=10)
    # lbl_file_path = Label(window, text=plotter.path)
    # lbl_file_path.grid(column=1, row=0)
    # plotter.lbl_file_path = lbl_file_path
    # Button(window, text='Select File Path Via GUI', command=plotter.gui_file_select).grid(column=5, row=0)
    # Button(window, text='Plot Ring Dts', command=plotter.plot_dt_ring).grid(column=1, row=1)
    # Button(window, text='Plot Ring Streaks', command=plotter.plot_ring_streaks).grid(column=1, row=8)
    # Button(window, text='Plot 1D Histograms', command=plotter.plot_1d_hists).grid(column=2, row=1)
    # Button(window, text='Plot 2D Histograms', command=plotter.plot_2d_hists).grid(column=3, row=1)
    # Label(window, text='Binning of 1D Histograms (ADC channels/bin): ').grid(column=0, row=2)
    # lbl_1d_binning_val = Label(window, text=plotter.binning_1d)
    # lbl_1d_binning_val.grid(column=3, row=2)
    # plotter.lbl_1d_binning = lbl_1d_binning_val
    # entry_1d_bins = Entry(window, width=10)
    # entry_1d_bins.grid(column=2, row=2)
    # plotter.entry_1d_binning = entry_1d_bins
    # Button(window, text='Set Bin Num', command=plotter.gui_1d_bins).grid(column=5, row=2)
    # Label(window, text='Gaussian Fit Detector: ').grid(column=0, row=3)
    # combo_fit_detector = ttk.Combobox(window)
    # combo_fit_detector['values'] = ('None', 'Fixed', 'Abel', 'Baker', 'Cain')
    # combo_fit_detector.current(0)
    # combo_fit_detector.grid(column=1, row=3)
    # Label(window, text='Left Bound: ').grid(column=1, row=4)
    # entry_curve_fit_leftb = Entry(window, width=10)
    # entry_curve_fit_leftb.grid(column=2, row=4)
    # Label(window, text='Right Bound: ').grid(column=3, row=4)
    # entry_curve_fit_rightb = Entry(window, width=10)
    # entry_curve_fit_rightb.grid(column=4, row=4)
    # plotter.set_fit_entries(combo_fit_detector, entry_curve_fit_leftb, entry_curve_fit_rightb)
    # Button(window, text='Fit Range', command=plotter.set_fit).grid(column=5, row=4)
    # var_y_zoom = IntVar()
    # Checkbutton(window, text='Zoom in past pedestal on y-axis', variable=var_y_zoom).grid(column=1, row=5)
    # plotter.y_zoom = var_y_zoom
    # lbl_status = Label(window, text='')
    # lbl_status.grid(column=0, row=8)
    # plotter.lbl_status = lbl_status
    window.mainloop()


if __name__ == '__main__':
    main()
