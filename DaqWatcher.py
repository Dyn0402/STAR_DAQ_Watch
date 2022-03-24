#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on March 21 3:18 AM 2022
Created in PyCharm
Created as STAR_DAQ_Watch/DaqWatcher

@author: Dylan Neff, Dyn04
"""

from sys import platform
from time import sleep
from datetime import datetime as dt, timedelta

import selenium.common.exceptions
from selenium.common.exceptions import WebDriverException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from pydub import AudioSegment
from pydub.playback import play, _play_with_simpleaudio

from threading import Thread


class DaqWatcher:
    def __init__(self):
        self.min_run_time = 60  # s If run not this old, don't check dead time yet
        self.run_stop_messages = 10  # Number of messages to check from most recent for a run stop
        self.run_end_window = 60  # s Consider run stopped if message no more than this old
        self.daq_hz_thresh = 1  # Hz If ALL DAQ Hz less than this, sound alarm (beam loss)
        self.dead_chime = True  # If True play chime immediately after any detector goes dead,
        # else just alarm for extended dead

        self.silent = False  # Silence all alarms if true

        self.run_duration_min = 30 * 60  # s How long run should go for.
        self.run_duration_max = self.run_duration_min + 20  # s When to stop notifying that run is too long.

        self.refresh_sleep = 1  # s How long to sleep at end of loop before refreshing page and checking again
        self.dead_thresh = 90  # % Dead time above which to consider detector dead

        self.repeat_num = 1000  # To repeat notify sound for alarm, audio buffer fails if too large, 1000 still good
        self.chimes = AudioSegment.from_file('chimes.wav')
        self.notify = AudioSegment.from_file('notify.wav') * self.repeat_num
        self.failure = AudioSegment.from_file('chord.wav') * 20
        self.run_finished = AudioSegment.from_file('Alarm04.wav')

        self.run_stop_text = 'Got the run stop request for run'
        self.run_start_text = 'Starting run #'
        self.trig2_all_name = 'ALL'
        self.running_state_text = "RUNNING"

        self.driver = None
        self.alarm_times = set_alarm_times()
        self.xpaths = set_xpaths()

        self.alarm_playback = None
        self.live_det_stamps = {x: dt.now() for x in self.xpaths['detectors']}
        self.dead_det_times = {x: 0 for x in self.xpaths['detectors']}

        self.keep_checking_daq = False

        self.status_out = None

        self.gui = None

    def start(self):
        """
        Start selenium with any browser that can be found in headless mode.
        Open STAR DAQ Monitor page and refresh until up to date (~8 times).
        :return:
        """
        self.driver = 1  # Count trying to start as being alive.
        self.print_status('Starting, please wait...')
        firefox_driver_path = ''
        if 'linux' in platform:
            chrome_driver_path = './chromedriver_linux'
        elif platform == 'darwin':
            chrome_driver_path = './chromedriver_mac'
        elif 'win' in platform:
            chrome_driver_path = './chromedriver_win.exe'
            firefox_driver_path = './geckodriver_win.exe'
        else:
            self.print_status('Unknown OS, don\'t know which selenium chrome driver to use. Exiting.')
            return

        try:
            ser = Service(chrome_driver_path)
            op = webdriver.ChromeOptions()
            op.add_argument('headless')
            self.driver = webdriver.Chrome(service=ser, options=op)
        except WebDriverException:
            self.print_status(f'Couldn\'t find Chrome binaries (probably), try firefox.')
            try:
                ser = Service(firefox_driver_path)
                op = webdriver.FirefoxOptions()
                op.headless = True
                self.driver = webdriver.Firefox(service=ser, options=op)
            except WebDriverException as e:
                self.print_status(f'Chrome and firefox both failed, giving up.\n{e}')
        self.driver.get('https://online.star.bnl.gov/daq/export/daq/')
        sleep(3)  # Give some time for page to load

        click_button(self.driver, self.xpaths['frames']['refresh'], self.xpaths['buttons']['refresh'], 8)
        self.keep_checking_daq = True
        # self.check_daq_async()  # Let GUI deal with threads
        self.check_daq()  # Run check_daq recursively until check_daq goes to false

    def is_alive(self):
        return self.driver is not None

    def stop(self):
        """
        Stop checking daq and then stop selenium driver.
        :return:
        """
        self.keep_checking_daq = False
        driver = self.driver  # Handoff
        self.driver = None  # Set immediately so is_alive is false
        # sleep(self.refresh_sleep + 3)
        if self.driver is not None:
            self.print_status('Stopping, wait for confirmation...')
            driver.close()  # Close open driver on own time.
            self.print_status('Stopped.')
        else:
            self.print_status('No running driver to stop? Doing nothing.')

    def silence(self):  # Not working at all?
        self.print_status('Trying to silence')
        if self.alarm_playback is not None and self.alarm_playback.is_playing():
            self.alarm_playback.stop()
        self.silent = True
        self.print_status('Silenced')

    def unsilence(self):
        self.print_status('Unsilencing')
        self.silent = False
        self.print_status('Unsilenced')

    # def check_daq_async(self):
    #     t2 = Thread(target=self.check_daq)
    #     t2.start()

    def check_daq(self):
        if self.keep_checking_daq:
            try:
                click_button(self.driver, self.xpaths['frames']['refresh'], self.xpaths['buttons']['refresh'],
                             click_pause=0.3)
                duration = read_field(self.driver, self.xpaths['frames']['header'], self.xpaths['info']['duration'])
                # recent_run_stop = check_run_end(self.driver, self.xpaths['frames']['footer'], self.xpaths['info'],
                #                                 self.run_stop_text, self.run_end_window, self.run_stop_messages)
                # between_runs = check_between_runs(self.driver, self.xpaths['frames']['footer'], self.xpaths['info'],
                #                                   self.run_stop_text, self.run_start_text, self.run_stop_messages)
                running = check_running(self.driver, self.xpaths['frames']['left'], self.xpaths['info']['run_state'],
                                        self.running_state_text)
                if check_duration(duration, self.min_run_time, self.run_duration_min, self.run_duration_max,
                                  self.run_finished, self.silent) and running:
                    self.print_status(f'\n{dt.now()} | Running. Check dead times')
                    try:
                        daq_hz = check_daq_hz(self.driver, self.xpaths['frames']['main'], self.xpaths['info'],
                                              self.trig2_all_name)
                        dets_read = read_dets(self.driver, self.xpaths['frames']['main'], self.xpaths['detectors'])
                    except selenium.common.exceptions.StaleElementReferenceException:
                        self.print_status('Something stale in detectors?')
                        # self.check_daq_async()  # Recursion to rerun check_daq asynchronously
                        self.check_daq()  # Will recursion without finishing function cause memory leak?
                        return
                    for det, dead in zip(self.xpaths['detectors'].keys(), dets_read):
                        dead = int(dead.strip('%'))
                        if dead > self.dead_thresh:
                            if self.dead_det_times[det] == 0 and self.dead_chime and not self.silent:
                                _play_with_simpleaudio(self.chimes)
                            self.dead_det_times[det] = (dt.now() - self.live_det_stamps[det]).total_seconds()
                        else:
                            self.dead_det_times[det] = 0
                            self.live_det_stamps[det] = dt.now()
                    alarm = False
                    any_dead = False
                    for det, dead_time in self.dead_det_times.items():
                        if dead_time > 0:
                            any_dead = True
                            self.print_status(f'{det} dead for more than {dead_time}s!')
                        if dead_time > self.alarm_times[det]:
                            if self.alarm_playback is None or not self.alarm_playback.is_playing() and not self.silent:
                                self.alarm_playback = _play_with_simpleaudio(self.notify)
                            alarm = True
                    if daq_hz < self.daq_hz_thresh and not any_dead:
                        self.print_status(f'DAQ Hz less than {self.daq_hz_thresh}Hz but all detectors alive!')
                        if self.alarm_playback is None or not self.alarm_playback.is_playing() and not self.silent:
                            self.alarm_playback = _play_with_simpleaudio(self.notify)
                        alarm = True
                    elif not any_dead:
                        self.print_status(f'All detectors alive')
                    if not alarm:
                        if self.alarm_playback is not None and self.alarm_playback.is_playing():
                            self.alarm_playback.stop()
                else:
                    if not running:
                        wait_reason = f'Not running'
                        self.live_det_stamps = {x: dt.now() for x in self.xpaths['detectors']}  # Reset dead time counters
                    else:
                        wait_reason = f'Not running for at least {self.min_run_time}s yet'
                    self.print_status(f'{dt.now()} | {wait_reason}, waiting...')
                    if self.alarm_playback is not None and self.alarm_playback.is_playing():
                        self.alarm_playback.stop()
                sleep(self.refresh_sleep)
            except Exception as e:
                self.print_status(f'Error reading Daq Monitor!\n{e}')
            # self.check_daq_async()  # Recursion to rerun check_daq asynchronously  # Let GUI handle threads
            self.check_daq()  # Recursively check_daq until keep_checking is false

    def print_status(self, status):
        if self.gui is not None:
            self.gui.print_status(status)
        else:
            print(status)


def set_alarm_times():
    """
    Set alarm times for each detector in seconds.
    If a detector is dead for longer than its corresponding alarm time, audio alarm will sound.
    Alarm will continue until no detectors are dead.
    :return: Dictionary of alarm times
    """

    alarm_times = {
        'tof_dead': 30,
        'btow_dead': 0,
        'trigger_dead': 0,
        'etow_dead': 0,
        'esmd_dead': 0,
        'tpx_dead': 40,
        'mtd_dead': 30,
        'gmt_dead': 0,
        'l4_dead': 0,
        'etof_dead': 0,
        'itpc_dead': 40,
        'fcs_dead': 30,
        'stgc_dead': 0,
        'fst_dead': 0,
    }

    return alarm_times


def set_xpaths():
    """
    Set relevant xpaths for DAQ webpage. If webpage changes, these xpaths will have to be adjusted.
    :return: Nested dictionary of xpaths for DAQ webpage
    """

    xpaths = {
        'frames':
            {
                'refresh': '//*[@id="left"]',
                'main': '//*[@id="main"]',
                'header': '//*[@id="header"]',
                'footer': '//*[@id="footer"]',
            },
        'buttons':
            {'refresh': '//*[@id="reload"]'},
        'info':
            {
                'duration': '//*[@id="duration"]',
                'run_state': '//*[@id="run_state"]',
                'message_time_col': 1,
                'message_text_col': 7,
                'message_first_index': 2,
                'messages': lambda row, col: f'//*[@id="tb"]/tbody/tr[{row}]/td[{col}]',
                'trig2_name': lambda row: f'//*[@id="trg2"]/tbody/tr[{row}]/td[1]',
                'trig2_hz': lambda row: f'//*[@id="trg2"]/tbody/tr[{row}]/td[3]',
            },
        'detectors':
            {
                'tof_dead': '//*[@id="det"]/tbody/tr[2]/td[3]',
                'btow_dead': '//*[@id="det"]/tbody/tr[3]/td[3]',
                'trigger_dead': '//*[@id="det"]/tbody/tr[4]/td[3]',
                'etow_dead': '//*[@id="det"]/tbody/tr[5]/td[3]',
                'esmd_dead': '//*[@id="det"]/tbody/tr[6]/td[3]',
                'tpx_dead': '//*[@id="det"]/tbody/tr[7]/td[3]',
                'mtd_dead': '//*[@id="det"]/tbody/tr[8]/td[3]',
                'gmt_dead': '//*[@id="det"]/tbody/tr[9]/td[3]',
                'l4_dead': '//*[@id="det"]/tbody/tr[10]/td[3]',
                'etof_dead': '//*[@id="det"]/tbody/tr[11]/td[3]',
                'itpc_dead': '//*[@id="det"]/tbody/tr[12]/td[3]',
                'fcs_dead': '//*[@id="det"]/tbody/tr[13]/td[3]',
                'stgc_dead': '//*[@id="det"]/tbody/tr[14]/td[3]',
                'fst_dead': '//*[@id="det"]/tbody/tr[15]/td[3]',
            },
    }

    return xpaths


def switch_frame(driver, xframe):
    """
    # Switch to xframe, returning to top level frame first. This seems to take longer than other actions?
    :param driver: Selenium driver
    :param xframe: Xpath of frame to switch to
    :return:
    """

    driver.switch_to.default_content()
    frame = driver.find_element(By.XPATH, xframe)
    driver.switch_to.frame(frame)


def click_button(driver, xframe, xbutton, num_click=1, click_pause=0.2):
    """
    Click button at xbutton xpath. Click num_click times with click_pause wait in between.
    :param driver: Chrome driver to webpage
    :param xframe: xpath for frame the button is in
    :param xbutton: xpath for the button
    :param num_click: Number of times to click button
    :param click_pause: Lenghth of time to pause between button clicks (seconds)
    :return:
    """

    switch_frame(driver, xframe)
    button = driver.find_element(By.XPATH, xbutton)
    for i in range(num_click):
        button.click()
        sleep(click_pause)


def read_field(driver, xframe, xfield):
    """
    Read text of given field
    :param driver: Chrome driver for webpage
    :param xframe: xpath for frame field is in
    :param xfield: xpath for field
    :return:
    """

    switch_frame(driver, xframe)
    field = driver.find_element(By.XPATH, xfield)
    return field.text


def read_dets(driver, xframe, xdets):
    """
    Read each detector dead time in xdets. Return these dead times
    :param driver: Chrome driver for webpage
    :param xframe: xpath to frame the detector dead times are in
    :param xdets: Dictionary of {detector names: detector dead time xpaths}
    :return: Dictionary of {detector names: detector dead times}
    """

    switch_frame(driver, xframe)
    dets_read = []
    for det, xdet in xdets.items():
        dets_read.append(driver.find_element(By.XPATH, xdet).text)
    return dets_read


def check_duration(duration, min_s, run_min, run_max, run_finished, silent):
    """
    Check if run duration field is in running state and longer than min_s seconds
    :param duration: Duration string from DAQ Monitor field
    :param min_s: s Minimum number of seconds running. Return false if running time less than this
    :param run_min: s If duration larger than this and less than run_max, notify that run is finished.
    :param run_max: s If duration less than this and greater than run_min, notify that run is finished.
    :param run_finished: Audio to play if run finished.
    :param silent: Only play sound if False
    :return: True if running for longer than min_s, else False
    """

    duration = duration.split(',')
    if len(duration) == 4:
        duration = [int(x.strip().strip(y)) for x, y in zip(duration, [' days', ' hr', ' min', ' s'])]
        duration = duration[0] * 24 * 60 * 60 + duration[1] * 60 * 60 + duration[2] * 60 + duration[
            3]  # Convert to s

        if run_min < duration < run_max:
            # print(f'Run more than {run_min / 60} minutes long.')
            print(f'Run duration {timedelta(seconds=duration)}, maybe time to start a new one?')
            if not silent:
                _play_with_simpleaudio(run_finished)

        if duration > min_s:
            return True

    return False


def check_run_end(driver, xframe, xinfos, run_stop_text, run_end_window, num_messages=5):
    """
    DEPRECATED!
    Check to see if the run has ended recently
    :param driver: Chrome driver to webpage
    :param xframe: xpath for frame of the daq messages
    :param xinfos: Dictionary of info which includes xpaths for DAQ messages
    :param run_stop_text: String indicating a run stop message on the DAQ
    :param run_end_window: Window in which to consider run recently stopped (seconds)
    :param num_messages: Number of messages in the DAQ to check for run stop message
    :return: True if run stopped recently, False if not
    """

    switch_frame(driver, xframe)
    for message_num in range(num_messages):
        row_index = xinfos['message_first_index'] + message_num
        message = driver.find_element(By.XPATH, xinfos['messages'](row_index, xinfos['message_text_col'])).text
        if message[:len(run_stop_text)] == run_stop_text:
            stop_time = driver.find_element(By.XPATH, xinfos['messages'](row_index, xinfos['message_time_col'])).text
            stop_time = dt.combine(dt.now().date(), dt.strptime(stop_time, '%H:%M:%S').time())
            stopped_seconds = (dt.now() - stop_time).total_seconds()
            while stopped_seconds < 0:
                stopped_seconds += 24 * 60 * 60  # Correct for wrongly assuming message time is today. Get nearest day.
            if stopped_seconds < run_end_window:
                return True
    return False


def check_between_runs(driver, xframe, xinfos, run_stop_text, run_start_text, num_messages=100):
    """
    Check to see if run start or run end message more recent. If run start, must be running so return False.
    If run end, must be between runs so return True. If neither found assume running (?)
    :param driver: Chrome driver to webpage
    :param xframe: xpath for frame of the daq messages
    :param xinfos: Dictionary of info which includes xpaths for DAQ messages
    :param run_stop_text: String indicating a run stop message on the DAQ
    :param run_start_text: String indicating a new run has started on the DAQ
    :param num_messages: Number of messages in the DAQ to check for run stop message
    :return: True if run stopped recently, False if not
    """

    switch_frame(driver, xframe)
    for message_num in range(num_messages):
        row_index = xinfos['message_first_index'] + message_num
        message = driver.find_element(By.XPATH, xinfos['messages'](row_index, xinfos['message_text_col'])).text
        if message[:len(run_start_text)] == run_start_text:  # Currently running
            return False
        if message[:len(run_stop_text)] == run_stop_text:
            return True
    return False


def check_daq_hz(driver, xframe, xinfos, trig2_all_name):
    switch_frame(driver, xframe)
    trig2_name = ''
    row = 1  # Row starts at 2 on page
    while trig2_name != trig2_all_name:
        row += 1
        # Need try catch here for if row is too large!
        trig2_name = driver.find_element(By.XPATH, xinfos['trig2_name'](row)).text
    daq_hz = int(driver.find_element(By.XPATH, xinfos['trig2_hz'](row)).text)

    return daq_hz


def check_running(driver, xframe, xrun_state, running_state_text):
    """
    Check if run state is running
    :param driver:
    :param xframe:
    :param xrun_state:
    :param running_state_text:
    :return:
    """
    switch_frame(driver, xframe)
    run_state = driver.find_element(By.XPATH, xrun_state).text
    return run_state == running_state_text



# class DaqWatcher:
#     def __init__(self):
#         self.min_run_time = 60  # s If run not this old, don't check dead time yet
#         self.run_stop_messages = 10  # Number of messages to check from most recent for a run stop
#         self.run_end_window = 60  # s Consider run stopped if message no more than this old
#         self.daq_hz_thresh = 1  # Hz If ALL DAQ Hz less than this, sound alarm (beam loss)
#         self.dead_chime = True  # If True play chime immediately after any detector goes dead,
#         # else just alarm for extended dead
#
#         self.silence_entry = None
#         self.silence = False  # Silence all alarms if true
#         self.silence_duration = 5  # minutes How long to silence alarm
#         self.silence_start = dt.now()  # Time at which silence was started.
#
#         self.run_duration_min = 30 * 60  # s How long run should go for.
#         self.run_duration_max = self.run_duration_min + 20  # s When to stop notifying that run is too long.
#
#         self.refresh_sleep = 1  # s How long to sleep at end of loop before refreshing page and checking again
#         self.dead_thresh = 90  # % Dead time above which to consider detector dead
#
#         self.repeat_num = 1000  # To repeat notify sound for alarm, audio buffer fails if too large, 1000 still good
#         self.chimes = AudioSegment.from_file('chimes.wav')
#         self.notify = AudioSegment.from_file('notify.wav') * self.repeat_num
#         self.failure = AudioSegment.from_file('chord.wav') * 20
#         self.run_finished = AudioSegment.from_file('Alarm04.wav')
#
#         self.run_stop_text = 'Got the run stop request for run'
#         self.run_start_text = 'Starting run #'
#         self.trig2_all_name = 'ALL'
#
#         self.last_clear = dt.now()
#         self.clear_interval = 5 * 60  # s
#         self.clear_keep_lines = 50
#
#         self.driver = None
#         self.alarm_times = set_alarm_times()
#         self.xpaths = set_xpaths()
#
#         self.alarm_playback = None
#         self.live_det_stamps = {x: dt.now() for x in self.xpaths['detectors']}
#         self.dead_det_times = {x: 0 for x in self.xpaths['detectors']}
#
#         self.keep_checking_daq = False
#
#         self.status_out = None
#
#         self.window = None
#
#     def start_click(self):
#         self.print_status('Starting, please wait...')
#         t1 = Thread(target=self.start)
#         t1.start()
#
#     def start(self):
#         firefox_driver_path = ''
#         if 'linux' in platform:
#             chrome_driver_path = './chromedriver_linux'
#         elif platform == 'darwin':
#             chrome_driver_path = './chromedriver_mac'
#         elif 'win' in platform:
#             chrome_driver_path = './chromedriver_win.exe'
#             firefox_driver_path = './geckodriver_win.exe'
#         else:
#             self.print_status('Unknown OS, don\'t know which selenium chrome driver to use. Exiting.')
#             return
#
#         try:
#             ser = Service(chrome_driver_path)
#             op = webdriver.ChromeOptions()
#             op.add_argument('headless')
#             self.driver = webdriver.Chrome(service=ser, options=op)
#         except WebDriverException:
#             self.print_status(f'Couldn\'t find Chrome binaries (probably), try firefox.')
#             try:
#                 ser = Service(firefox_driver_path)
#                 op = webdriver.FirefoxOptions()
#                 op.headless = True
#                 self.driver = webdriver.Firefox(service=ser, options=op)
#             except WebDriverException as e:
#                 self.print_status(f'Chrome and firefox both failed, giving up.\n{e}')
#         self.driver.get('https://online.star.bnl.gov/daq/export/daq/')
#         sleep(3)  # Give some time for page to load
#
#         click_button(self.driver, self.xpaths['frames']['refresh'], self.xpaths['buttons']['refresh'], 8)
#         self.keep_checking_daq = True
#         self.check_daq_async()
#
#     def stop(self):
#         self.keep_checking_daq = False
#         self.print_status('Stopping...')
#         sleep(self.refresh_sleep + 3)
#         if self.driver is not None:
#             self.driver.close()
#             self.driver = None
#         self.print_status('Stopped.')
#
#     def silence(self):  # Not working at all?
#         self.print_status('Here11')
#         if self.alarm_playback is not None and self.alarm_playback.is_playing():
#             self.alarm_playback.stop()
#         if self.silence_entry is not None:
#             entry = self.silence_entry.get()
#             try:
#                 self.silence_duration = float(entry)
#             except ValueError:
#                 self.print_status('Bad entry for silence time. Need a float.')
#         self.silence = True
#         self.silence_start = dt.now()
#         self.print_status('Silenced')
#
#     def check_daq_async(self):
#         t2 = Thread(target=self.check_daq)
#         t2.start()
#
#     def check_daq(self):
#         if self.keep_checking_daq:
#             if (dt.now() - self.last_clear).total_seconds() > self.clear_interval:
#                 self.clear_txt()
#                 self.last_clear = dt.now()
#             if self.silence:
#                 if (dt.now() - self.silence_start).total_seconds() > self.silence_duration * 60:
#                     self.silence = False
#             try:
#                 click_button(self.driver, self.xpaths['frames']['refresh'], self.xpaths['buttons']['refresh'],
#                              click_pause=0.3)
#                 duration = read_field(self.driver, self.xpaths['frames']['header'], self.xpaths['info']['duration'])
#                 # recent_run_stop = check_run_end(self.driver, self.xpaths['frames']['footer'], self.xpaths['info'],
#                 #                                 self.run_stop_text, self.run_end_window, self.run_stop_messages)
#                 between_runs = check_between_runs(self.driver, self.xpaths['frames']['footer'], self.xpaths['info'],
#                                                   self.run_stop_text, self.run_start_text, self.run_stop_messages)
#                 if check_duration(duration, self.min_run_time, self.run_duration_min, self.run_duration_max,
#                                   self.run_finished, self.silence) and not between_runs:
#                     self.print_status(f'\n{dt.now()} | Running. Check dead times')
#                     try:
#                         daq_hz = check_daq_hz(self.driver, self.xpaths['frames']['main'], self.xpaths['info'],
#                                               self.trig2_all_name)
#                         dets_read = read_dets(self.driver, self.xpaths['frames']['main'], self.xpaths['detectors'])
#                     except selenium.common.exceptions.StaleElementReferenceException:
#                         self.print_status('Something stale in detectors?')
#                         self.check_daq_async()  # Recursion to rerun check_daq asynchronously
#                         return
#                     for det, dead in zip(self.xpaths['detectors'].keys(), dets_read):
#                         dead = int(dead.strip('%'))
#                         if dead > self.dead_thresh:
#                             if self.dead_det_times[det] == 0 and self.dead_chime and not self.silence:
#                                 _play_with_simpleaudio(self.chimes)
#                             self.dead_det_times[det] = (dt.now() - self.live_det_stamps[det]).total_seconds()
#                         else:
#                             self.dead_det_times[det] = 0
#                             self.live_det_stamps[det] = dt.now()
#                     alarm = False
#                     any_dead = False
#                     for det, dead_time in self.dead_det_times.items():
#                         if dead_time > 0:
#                             any_dead = True
#                             self.print_status(f'{det} dead for more than {dead_time}s!')
#                         if dead_time > self.alarm_times[det]:
#                             if self.alarm_playback is None or not self.alarm_playback.is_playing() and not self.silence:
#                                 self.alarm_playback = _play_with_simpleaudio(self.notify)
#                             alarm = True
#                     if daq_hz < self.daq_hz_thresh and not any_dead:
#                         self.print_status(f'DAQ Hz less than {self.daq_hz_thresh}Hz but all detectors alive!')
#                         if self.alarm_playback is None or not self.alarm_playback.is_playing() and not self.silence:
#                             self.alarm_playback = _play_with_simpleaudio(self.notify)
#                         alarm = True
#                     elif not any_dead:
#                         self.print_status(f'All detectors alive')
#                     if not alarm:
#                         if self.alarm_playback is not None and self.alarm_playback.is_playing():
#                             self.alarm_playback.stop()
#                 else:
#                     if between_runs:
#                         wait_reason = f'Run stopped'
#                         self.live_det_stamps = {x: dt.now() for x in self.xpaths['detectors']}  # Reset dead time counters
#                     else:
#                         wait_reason = f'Not running for at least {self.min_run_time}s yet'
#                     self.print_status(f'{dt.now()} | {wait_reason}, waiting...')
#                     if self.alarm_playback is not None and self.alarm_playback.is_playing():
#                         self.alarm_playback.stop()
#                 sleep(self.refresh_sleep)
#             except Exception as e:
#                 self.print_status(f'Error reading Daq Monitor!\n{e}')
#             self.check_daq_async()  # Recursion to rerun check_daq asynchronously
#
#     def print_status(self, status):
#         if self.status_out is not None:
#             self.status_out.insert(tk.INSERT, f'\n{status}')
#             self.status_out.see('end')
#             self.window.update()
#
#     def clear_txt(self):
#         if self.status_out is not None:
#             text = self.status_out.get('1.0', tk.END)
#             text = '\n'.join(text.split('\n')[-self.clear_keep_lines:])
#             self.status_out.delete('1.0', tk.END)
#             self.print_status(text)
#
#
# def set_alarm_times():
#     """
#     Set alarm times for each detector in seconds.
#     If a detector is dead for longer than its corresponding alarm time, audio alarm will sound.
#     Alarm will continue until no detectors are dead.
#     :return: Dictionary of alarm times
#     """
#
#     alarm_times = {
#         'tof_dead': 30,
#         'btow_dead': 0,
#         'trigger_dead': 0,
#         'etow_dead': 0,
#         'esmd_dead': 0,
#         'tpx_dead': 40,
#         'mtd_dead': 30,
#         'gmt_dead': 0,
#         'l4_dead': 0,
#         'etof_dead': 0,
#         'itpc_dead': 40,
#         'fcs_dead': 30,
#         'stgc_dead': 0,
#         'fst_dead': 0,
#     }
#
#     return alarm_times
#
#
# def set_xpaths():
#     """
#     Set relevant xpaths for DAQ webpage. If webpage changes, these xpaths will have to be adjusted.
#     :return: Nested dictionary of xpaths for DAQ webpage
#     """
#
#     xpaths = {
#         'frames':
#             {
#                 'refresh': '//*[@id="left"]',
#                 'main': '//*[@id="main"]',
#                 'header': '//*[@id="header"]',
#                 'footer': '//*[@id="footer"]',
#             },
#         'buttons':
#             {'refresh': '//*[@id="reload"]'},
#         'info':
#             {
#                 'duration': '//*[@id="duration"]',
#                 'message_time_col': 1,
#                 'message_text_col': 7,
#                 'message_first_index': 2,
#                 'messages': lambda row, col: f'//*[@id="tb"]/tbody/tr[{row}]/td[{col}]',
#                 'trig2_name': lambda row: f'//*[@id="trg2"]/tbody/tr[{row}]/td[1]',
#                 'trig2_hz': lambda row: f'//*[@id="trg2"]/tbody/tr[{row}]/td[3]',
#             },
#         'detectors':
#             {
#                 'tof_dead': '//*[@id="det"]/tbody/tr[2]/td[3]',
#                 'btow_dead': '//*[@id="det"]/tbody/tr[3]/td[3]',
#                 'trigger_dead': '//*[@id="det"]/tbody/tr[4]/td[3]',
#                 'etow_dead': '//*[@id="det"]/tbody/tr[5]/td[3]',
#                 'esmd_dead': '//*[@id="det"]/tbody/tr[6]/td[3]',
#                 'tpx_dead': '//*[@id="det"]/tbody/tr[7]/td[3]',
#                 'mtd_dead': '//*[@id="det"]/tbody/tr[8]/td[3]',
#                 'gmt_dead': '//*[@id="det"]/tbody/tr[9]/td[3]',
#                 'l4_dead': '//*[@id="det"]/tbody/tr[10]/td[3]',
#                 'etof_dead': '//*[@id="det"]/tbody/tr[11]/td[3]',
#                 'itpc_dead': '//*[@id="det"]/tbody/tr[12]/td[3]',
#                 'fcs_dead': '//*[@id="det"]/tbody/tr[13]/td[3]',
#                 'stgc_dead': '//*[@id="det"]/tbody/tr[14]/td[3]',
#                 'fst_dead': '//*[@id="det"]/tbody/tr[15]/td[3]',
#             },
#     }
#
#     return xpaths
#
#
# def switch_frame(driver, xframe):
#     """
#     # Switch to xframe, returning to top level frame first. This seems to take longer than other actions?
#     :param driver: Selenium driver
#     :param xframe: Xpath of frame to switch to
#     :return:
#     """
#
#     driver.switch_to.default_content()
#     frame = driver.find_element(By.XPATH, xframe)
#     driver.switch_to.frame(frame)
#
#
# def click_button(driver, xframe, xbutton, num_click=1, click_pause=0.2):
#     """
#     Click button at xbutton xpath. Click num_click times with click_pause wait in between.
#     :param driver: Chrome driver to webpage
#     :param xframe: xpath for frame the button is in
#     :param xbutton: xpath for the button
#     :param num_click: Number of times to click button
#     :param click_pause: Lenghth of time to pause between button clicks (seconds)
#     :return:
#     """
#
#     switch_frame(driver, xframe)
#     button = driver.find_element(By.XPATH, xbutton)
#     for i in range(num_click):
#         button.click()
#         sleep(click_pause)
#
#
# def read_field(driver, xframe, xfield):
#     """
#     Read text of given field
#     :param driver: Chrome driver for webpage
#     :param xframe: xpath for frame field is in
#     :param xfield: xpath for field
#     :return:
#     """
#
#     switch_frame(driver, xframe)
#     field = driver.find_element(By.XPATH, xfield)
#     return field.text
#
#
# def read_dets(driver, xframe, xdets):
#     """
#     Read each detector dead time in xdets. Return these dead times
#     :param driver: Chrome driver for webpage
#     :param xframe: xpath to frame the detector dead times are in
#     :param xdets: Dictionary of {detector names: detector dead time xpaths}
#     :return: Dictionary of {detector names: detector dead times}
#     """
#
#     switch_frame(driver, xframe)
#     dets_read = []
#     for det, xdet in xdets.items():
#         dets_read.append(driver.find_element(By.XPATH, xdet).text)
#     return dets_read
#
#
# def check_duration(duration, min_s, run_min, run_max, run_finished, silence):
#     """
#     Check if run duration field is in running state and longer than min_s seconds
#     :param duration: Duration string from DAQ Monitor field
#     :param min_s: s Minimum number of seconds running. Return false if running time less than this
#     :param run_min: s If duration larger than this and less than run_max, notify that run is finished.
#     :param run_max: s If duration less than this and greater than run_min, notify that run is finished.
#     :param run_finished: Audio to play if run finished.
#     :param silence: Only play sound if False
#     :return: True if running for longer than min_s, else False
#     """
#
#     duration = duration.split(',')
#     if len(duration) == 4:
#         duration = [int(x.strip().strip(y)) for x, y in zip(duration, [' days', ' hr', ' min', ' s'])]
#         duration = duration[0] * 24 * 60 * 60 + duration[1] * 60 * 60 + duration[2] * 60 + duration[
#             3]  # Convert to s
#
#         if run_min < duration < run_max:
#             # print(f'Run more than {run_min / 60} minutes long.')
#             print(f'Run duration {timedelta(seconds=duration)}, maybe time to start a new one?')
#             if not silence:
#                 _play_with_simpleaudio(run_finished)
#
#         if duration > min_s:
#             return True
#
#     return False
#
# def check_run_end(driver, xframe, xinfos, run_stop_text, run_end_window, num_messages=5):
#     """
#     DEPRECATED!
#     Check to see if the run has ended recently
#     :param driver: Chrome driver to webpage
#     :param xframe: xpath for frame of the daq messages
#     :param xinfos: Dictionary of info which includes xpaths for DAQ messages
#     :param run_stop_text: String indicating a run stop message on the DAQ
#     :param run_end_window: Window in which to consider run recently stopped (seconds)
#     :param num_messages: Number of messages in the DAQ to check for run stop message
#     :return: True if run stopped recently, False if not
#     """
#
#     switch_frame(driver, xframe)
#     for message_num in range(num_messages):
#         row_index = xinfos['message_first_index'] + message_num
#         message = driver.find_element(By.XPATH, xinfos['messages'](row_index, xinfos['message_text_col'])).text
#         if message[:len(run_stop_text)] == run_stop_text:
#             stop_time = driver.find_element(By.XPATH, xinfos['messages'](row_index, xinfos['message_time_col'])).text
#             stop_time = dt.combine(dt.now().date(), dt.strptime(stop_time, '%H:%M:%S').time())
#             stopped_seconds = (dt.now() - stop_time).total_seconds()
#             while stopped_seconds < 0:
#                 stopped_seconds += 24 * 60 * 60  # Correct for wrongly assuming message time is today. Get nearest day.
#             if stopped_seconds < run_end_window:
#                 return True
#     return False
#
#
# def check_between_runs(driver, xframe, xinfos, run_stop_text, run_start_text, num_messages=100):
#     """
#     Check to see if run start or run end message more recent. If run start, must be running so return False.
#     If run end, must be between runs so return True. If neither found assume running (?)
#     :param driver: Chrome driver to webpage
#     :param xframe: xpath for frame of the daq messages
#     :param xinfos: Dictionary of info which includes xpaths for DAQ messages
#     :param run_stop_text: String indicating a run stop message on the DAQ
#     :param run_start_text: String indicating a new run has started on the DAQ
#     :param num_messages: Number of messages in the DAQ to check for run stop message
#     :return: True if run stopped recently, False if not
#     """
#
#     switch_frame(driver, xframe)
#     for message_num in range(num_messages):
#         row_index = xinfos['message_first_index'] + message_num
#         message = driver.find_element(By.XPATH, xinfos['messages'](row_index, xinfos['message_text_col'])).text
#         if message[:len(run_start_text)] == run_start_text:  # Currently running
#             return False
#         if message[:len(run_stop_text)] == run_stop_text:
#             return True
#     return False
#
#
# def check_daq_hz(driver, xframe, xinfos, trig2_all_name):
#     switch_frame(driver, xframe)
#     trig2_name = ''
#     row = 1  # Row starts at 2 on page
#     while trig2_name != trig2_all_name:
#         row += 1
#         # Need try catch here for if row is too large!
#         trig2_name = driver.find_element(By.XPATH, xinfos['trig2_name'](row)).text
#     daq_hz = int(driver.find_element(By.XPATH, xinfos['trig2_hz'](row)).text)
#
#     return daq_hz
