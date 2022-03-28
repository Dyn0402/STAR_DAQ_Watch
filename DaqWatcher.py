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
import configparser

import selenium.common.exceptions
from selenium.common.exceptions import WebDriverException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio


class DaqWatcher:
    def __init__(self):
        # config['General'] = {'run_start_buffer': '60',
        #                      'daq_hz_minimum': '1',
        #                      'run_duration_target': '30',
        #                      'run_over_alarm_time': '10',
        #                      'loop_sleep': '1',
        #                      'dead_threshold': '90'}

        self.config_path = 'watcher_config.ini'
        config = configparser.ConfigParser()

        self.min_run_time = 60  # s If run not this old, don't check dead time yet
        self.daq_hz_thresh = 1  # Hz If ALL DAQ Hz less than this, sound alarm (beam loss)

        self.run_duration_min = 30 * 60  # s How long run should go for.
        self.run_duration_max = self.run_duration_min + 20  # s When to stop notifying that run is too long.

        self.refresh_sleep = 1  # s How long to sleep at end of loop before refreshing page and checking again
        self.dead_thresh = 90  # % Dead time above which to consider detector dead

        self.repeat_num = 1000  # To repeat notify sound for alarm, audio buffer fails if too large, 1000 still good
        self.chimes = AudioSegment.from_file('chimes.wav')
        self.notify = AudioSegment.from_file('notify.wav') * self.repeat_num
        self.failure = AudioSegment.from_file('chord.wav') * 20
        self.run_finished = AudioSegment.from_file('Alarm04.wav')

        self.run_start_text = 'Starting run #'
        self.trig2_all_name = 'ALL'
        self.running_state_text = 'RUNNING'

        # If True play chime immediately after any detector goes dead, else just alarm for extended dead
        self.dead_chime = True
        self.silent = False  # Silence all alarms if true

        self.dt_format = '%a %H:%M:%S'

        self.driver = None
        self.alarm_times = set_alarm_times()
        self.xpaths = set_xpaths()

        self.was_running = False

        self.alarm_playback = None
        self.run_timer_playback = None
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
            op.add_argument('--log-level=3')
            self.driver = webdriver.Chrome(service=ser, options=op)
        except WebDriverException:
            self.print_status(f'Couldn\'t find Chrome binaries (probably), try firefox.')
            try:
                ser = Service(firefox_driver_path)
                op = webdriver.FirefoxOptions()
                op.add_argument('--log-level=3')
                op.headless = True
                self.driver = webdriver.Firefox(service=ser, options=op)
            except WebDriverException as e:
                self.print_status(f'Chrome and firefox both failed, giving up.\n{e}')
        self.driver.get('https://online.star.bnl.gov/daq/export/daq/')
        sleep(3)  # Give some time for page to load

        click_button(self.driver, self.xpaths['frames']['left'], self.xpaths['buttons']['refresh'], 8)
        self.keep_checking_daq = True
        self.live_det_stamps = {x: dt.now() for x in self.xpaths['detectors']}
        self.dead_det_times = {x: 0 for x in self.xpaths['detectors']}
        self.check_daq()  # Check daq until keep_checking goes to false

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
        if self.alarm_playback is not None and self.alarm_playback.is_playing():
            self.alarm_playback.stop()
        if driver is not None:
            self.print_status('\nStopping, wait for confirmation...')
            driver.close()
            driver.quit()
            self.print_status('Stopped.')
        else:
            self.print_status('\nNo running driver to stop? Doing nothing.')

    def restart(self):
        self.print_status('\nRestarting WebDriver')
        self.stop()
        self.start()

    def silence(self):
        if self.alarm_playback is not None and self.alarm_playback.is_playing():
            self.alarm_playback.stop()
        self.silent = True
        self.print_status('\nSilenced')

    def unsilence(self):
        self.silent = False
        self.print_status('\nUnsilenced')

    def check_daq(self):
        while self.keep_checking_daq:
            try:
                click_button(self.driver, self.xpaths['frames']['left'], self.xpaths['buttons']['refresh'],
                             click_pause=0.3)
                duration = read_field(self.driver, self.xpaths['frames']['header'], self.xpaths['info']['duration'])
                running = self.check_running()
                if self.was_running and not running:
                    self.was_running = False
                    break  # Restart driver after run
                if running:
                    self.was_running = True
                if self.check_duration(duration) and running:
                    self.print_status(f'\n{dt.now().strftime(self.dt_format)} | Running. Check dead times')
                    try:
                        daq_hz = self.check_daq_hz()
                        dets_read = read_dets(self.driver, self.xpaths['frames']['main'], self.xpaths['detectors'])
                    except selenium.common.exceptions.StaleElementReferenceException:
                        self.print_status('Something stale in detectors?')
                        continue
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
                            self.print_status(f'{det} dead for more than {dead_time:.2f}s!')
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
                    self.print_status(f'{dt.now().strftime(self.dt_format)} | {wait_reason}, waiting...')
                    if self.alarm_playback is not None and self.alarm_playback.is_playing():
                        self.alarm_playback.stop()
                sleep(self.refresh_sleep)
            except Exception as e:
                self.print_status(f'Error reading Daq Monitor!\n{e}')
            # self.check_daq_async()  # Recursion to rerun check_daq asynchronously  # Let GUI handle threads
            # self.check_daq()  # Recursively check_daq until keep_checking is false -> Memory leak
        if self.keep_checking_daq:
            self.restart()

    def print_status(self, status):
        if self.gui is not None:
            self.gui.print_status(status)
        else:
            print(status)

    def check_duration(self, duration):
        """
        Check if run duration field is in running state and longer than min_s seconds
        :param duration: Duration string from DAQ Monitor field
        :return: True if running for longer than min_s, else False
        """

        duration = duration.split(',')
        if len(duration) == 4:
            duration = [int(x.strip().strip(y)) for x, y in zip(duration, [' days', ' hr', ' min', ' s'])]
            duration = duration[0] * 24 * 60 * 60 + duration[1] * 60 * 60 + duration[2] * 60 + duration[
                3]  # Convert to s

            if self.run_duration_min < duration < self.run_duration_max:
                self.print_status(f'Run duration {timedelta(seconds=duration)}, maybe time to start a new one?')
                if self.run_timer_playback is None or not self.run_timer_playback.is_playing() and not self.silent:
                    self.run_timer_playback = _play_with_simpleaudio(self.run_finished)

            if duration > self.min_run_time:
                return True

        return False

    def check_running(self):
        """
        Check if run state is running
        :return: True if running, else false
        """
        switch_frame(self.driver, self.xpaths['frames']['left'])
        run_state = self.driver.find_element(By.XPATH, self.xpaths['info']['run_state']).text
        return run_state == self.running_state_text

    def check_daq_hz(self):
        switch_frame(self.driver, self.xpaths['frames']['main'])
        trig2_name = ''
        row = 1  # Row starts at 2 on page
        while trig2_name != self.trig2_all_name:
            row += 1
            # Need try catch here for if row is too large!
            trig2_name = self.driver.find_element(By.XPATH, self.xpaths['info']['trig2_name'](row)).text
        daq_hz = int(self.driver.find_element(By.XPATH, self.xpaths['info']['trig2_hz'](row)).text)

        return daq_hz

    def write_config(self):
        config = configparser.ConfigParser()
        config['General'] = {'run_start_buffer': str(self.min_run_time),
                             'daq_hz_minimum': str(self.daq_hz_thresh),
                             'run_duration_target': str(self.run_duration_min),
                             'run_over_alarm_time': str(self.run_duration_max - self.run_duration_min),
                             'loop_sleep': str(self.refresh_sleep),
                             'dead_threshold': str(self.dead_thresh)}

        config['Detector Dead Times'] = {
            'tof': 30,
            'btow': 0,
            'trigger': 0,
            'etow': 0,
            'esmd': 0,
            'tpx': 40,
            'mtd': 30,
            'gmt': 0,
            'l4': 0,
            'etof': 0,
            'itpc': 40,
            'fcs': 30,
            'stgc': 0,
            'fst': 0
        }

        with open(self.config_path, 'w') as configfile:
            config.write(configfile)

    def def_config(self):
        """
        Write a default config file.
        :return:
        """
        self.min_run_time = 60  # s If run not this old, don't check dead time yet
        self.daq_hz_thresh = 1  # Hz If ALL DAQ Hz less than this, sound alarm (beam loss)

        self.run_duration_min = 30 * 60  # s How long run should go for.
        self.run_duration_max = self.run_duration_min + 20  # s When to stop notifying that run is too long.

        self.refresh_sleep = 1  # s How long to sleep at end of loop before refreshing page and checking again
        self.dead_thresh = 90  # % Dead time above which to consider detector dead

        config = configparser.ConfigParser()
        config['General'] = {'run_start_buffer': '60',
                             'daq_hz_minimum': '1',
                             'run_duration_target': '30',
                             'run_over_alarm_time': '10',
                             'loop_sleep': '1',
                             'dead_threshold': '90'}

        config['Detector Dead Times'] = {
            'tof': 30,
            'btow': 0,
            'trigger': 0,
            'etow': 0,
            'esmd': 0,
            'tpx': 40,
            'mtd': 30,
            'gmt': 0,
            'l4': 0,
            'etof': 0,
            'itpc': 40,
            'fcs': 30,
            'stgc': 0,
            'fst': 0
        }

        with open(self.config_path, 'w') as configfile:
            config.write(configfile)


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
                'left': '//*[@id="left"]',
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
