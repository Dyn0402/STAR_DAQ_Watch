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

from DaqWatcher import DaqWatcher


class DaqWatchGUI:
    def __init__(self):
        self.window = self.set_window()

        self.status_text = scrolledtext.ScrolledText(self.window, wrap=tk.WORD, width=80, height=10)\
            .grid(column=2, row=2, pady=10, padx=10)

        Button(self.window, text='Start', command=self.start_click).grid(column=0, row=0, pady=10, padx=10)
        Button(self.window, text='Stop', command=self.stop_click).grid(column=1, row=0, pady=10, padx=10)
        Button(self.window, text='Silence', command=self.silence_click).grid(column=0, row=1, pady=10, padx=10)
        # watcher.silence_entry = Entry(window, width=5).grid(column=1, row=1, pady=10, padx=10)

        self.watcher = DaqWatcher()

    def start_click(self):
        if self.watcher.is_alive():
            self.print_status('Watcher instance already live!')
        else:
            pass

    def stop_click(self):
        if self.watcher.is_alive():
            # self.watcher_live = False  # Try to stop next click here, update status on watcher stop if fail?
            self.print_status('Stopping...')
        else:
            self.print_status('No live watchers to stop!')

    def silene_click(self):
        pass

    def print_status(self, status):
        if self.status_out is not None:
            self.status_out.insert(tk.INSERT, f'\n{status}')
            self.status_out.see('end')
            self.window.update()


def set_window():
    window = tk.Tk()
    window.title('DAQ Watch')
    window.geometry('1000x600')
    return window


def main():
    set_watch()


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
    print('donzo')


if __name__ == '__main__':
    main()
