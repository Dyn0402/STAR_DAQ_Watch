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
from selenium.common.exceptions import WebDriverException, NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio


class DaqWatcher:
    def __init__(self, gui=None):
        # Webdriver and DaqWatchGUI objects
        self.driver = None
        self.gui = gui

        # All parameters below set by read_config
        self.min_run_time = None  # s If run not this old, don't check dead time yet
        self.daq_hz_thresh = None  # Hz If ALL DAQ Hz less than this, sound alarm (beam loss)
        self.run_duration_min = None  # min How long run should go for.
        self.run_dur_alarm_time = None  # s How long to play run end notification.
        self.refresh_sleep = None  # s How long to sleep at end of loop before refreshing page and checking again
        self.dead_thresh = None  # % Dead time above which to consider detector dead
        self.alarm_times = None  # How long to wait for each detector before sounding alarm

        # Read config from file, setting all above parameters. Use defaults if file read fails
        self.config_path = 'watcher_config.ini'
        self.read_config()

        # State objects, set with buttons and events
        self.dead_chime = True  # If True play chime (not alarm) immediately after any detector goes dead
        self.silent = False  # Silence all alarms if true
        self.was_running = False
        self.live_det_stamps = {x: dt.now() for x in self.alarm_times}
        self.dead_det_times = {x: 0 for x in self.alarm_times}
        self.keep_checking_daq = False

        # Audio objects, hard coded
        self.repeat_num = 1000  # To repeat notify sound for alarm, audio buffer fails if too large, 1000 still good
        self.chimes = AudioSegment.from_file('audio_files/chimes.wav')
        self.notify = AudioSegment.from_file('audio_files/notify.wav') * self.repeat_num
        self.failure = AudioSegment.from_file('audio_files/chord.wav') * 20
        self.run_finished = AudioSegment.from_file('audio_files/Alarm04.wav')
        self.alarm_playback = None
        self.run_timer_playback = None

        # Hard coded constants
        self.run_start_text = 'Starting run #'
        self.trig2_all_name = 'ALL'
        self.running_state_text = 'RUNNING'
        self.dt_format = '%a %H:%M:%S'
        self.xpaths = set_xpaths()

    def get_driver_paths(self):
        """
        Figure out operating system and get paths to drivers.
        :return:
        """
        if 'linux' in platform:
            sys_post = '_linux'
        elif platform == 'darwin':
            sys_post = '_mac'
        elif 'win' in platform:
            sys_post = '_win'
        else:
            self.print_status('Unknown OS, don\'t know which selenium chrome driver to use. Exiting.')
            return None

        driver_paths = {
            'Chrome':
                {'driver_path': f'drivers/chromedriver{sys_post}', 'options': 'ChromeOptions', 'driver': 'Chrome'},
            'Firefox':
                {'driver_path': f'drivers/geckodriver{sys_post}', 'options': 'FirefoxOptions', 'driver': 'Firefox'},
            'Edge':
                {'driver_path': f'drivers/msedgedriver{sys_post}', 'options': 'EdgeOptions', 'driver': 'Edge'},
        }

        if sys_post == '_win':
            driver_paths.update({
                'Firefox_32': {'driver_path': f'drivers/geckodriver{sys_post}32',
                               'options': 'FirefoxOptions', 'driver': 'Firefox'},
                'Edge_32': {'driver_path': f'drivers/msedgedriver{sys_post}32',
                            'options': 'EdgeOptions', 'driver': 'Edge'},
            })

        return driver_paths

    def start_driver(self, driver_paths):
        """
        Get selenium driver in headless and silent mode. Try Chrome, Firefox, then Edge drivers in that order.
        Take the first one that works
        :param driver_paths: Dictionary of driver paths and corresponding methods for selenium
        :return:
        """
        for browser_name, driver in driver_paths.items():
            try:
                op = getattr(webdriver, driver['options'])()
                op.headless = True
                op.add_argument('--log-level=3')
                self.driver = getattr(webdriver, driver['driver'])(executable_path=driver['driver_path'], options=op)
                self.print_status(f'Starting with {browser_name}')
                return  # Take the first good driver and run with it.
            except WebDriverException:
                self.print_status(f'Couldn\'t find {browser_name} binaries (probably), trying another browser.')
        self.print_status(f'Couldn\'t find any drivers that work, giving up.\n')

    def start(self, start_checking=True):
        """
        Start selenium with any browser that can be found in headless mode.
        Open STAR DAQ Monitor page and refresh until up to date (~8 times).
        :param start_checking: If True immediately start checking daq (default). Else just open driver and return
        :return:
        """
        self.keep_checking_daq = True
        self.print_status('Starting, please wait...')
        self.start_driver(self.get_driver_paths())  # Figure out distribution then try all browsers to start self.driver
        self.driver.get('https://online.star.bnl.gov/daq/export/daq/')
        sleep(0.1)  # Give some time for page to load. Doesn't seem like this is needed but keep to avoid any annoyances

        if self.driver is not None and type(self.driver) != str:
            click_button(self.driver, self.xpaths['frames']['left'], self.xpaths['buttons']['refresh'], 8)
            self.live_det_stamps = {x: dt.now() for x in self.alarm_times}
            self.dead_det_times = {x: 0 for x in self.alarm_times}
            if start_checking:
                self.check_daq()  # Check daq until keep_checking goes to false

    def stop(self):
        """
        Stop checking daq and then stop selenium driver.
        :return:
        """
        self.keep_checking_daq = False
        if self.alarm_playback is not None and self.alarm_playback.is_playing():
            self.alarm_playback.stop()
        if self.driver is not None:
            self.print_status('\nStopping, wait for confirmation...')
            sleep(self.refresh_sleep + 2)  # Wait for current loop to finish. Could make smarter later if needed.
            self.driver.close()
            self.driver.quit()
            self.driver = None
            self.print_status('Stopped')
        else:
            self.print_status('\nNo running driver to stop? Doing nothing.')

    def restart(self):
        self.print_status('\nRestarting WebDriver')
        self.stop()
        self.start()

    def is_alive(self):
        """
        Check if DaqWatcher is alive. keep_checking_daq state changes quickly while driver takes time to open/close.
        Comparing the two can tell if in the process of stopping or starting.
        :return:
        """
        if self.keep_checking_daq and self.driver is not None:
            return True
        elif self.keep_checking_daq and self.driver is None:
            return 'starting'
        elif self.driver is not None and not self.keep_checking_daq:
            return 'stopping'
        else:
            return False

    def silence(self):
        if self.alarm_playback is not None and self.alarm_playback.is_playing():
            self.alarm_playback.stop()
        self.silent = True
        self.print_status('\nSilenced')

    def unsilence(self):
        self.silent = False
        self.print_status('\nUnsilenced')

    def check_daq(self):
        """
        Check STAR DAQ Monitor page in a loop. If any detectors are dead or if trigger rate goes too low sound alarm.
        Should try to clean this method up later.
        :return:
        """
        while self.keep_checking_daq:
            try:
                click_button(self.driver, self.xpaths['frames']['left'], self.xpaths['buttons']['refresh'],
                             click_pause=0.3)
                duration = read_field(self.driver, self.xpaths['frames']['header'], self.xpaths['text']['duration'])
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
                        dead_dets = self.check_dead_dets()
                    except selenium.common.exceptions.StaleElementReferenceException:
                        self.print_status('Something stale in detectors?')
                        continue
                    unknown_dets = [det for det in dead_dets if det not in self.alarm_times]
                    for det in unknown_dets:
                        self.alarm_times.update({det: 0})  # If unknown detector, add to alarm times with 0s alarm
                        self.dead_det_times.update({det: 0})
                        self.live_det_stamps.update({det: dt.now()})

                    for det in self.alarm_times:
                        if det in dead_dets:
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
                        self.print_status(f'DAQ Hz less than {self.daq_hz_thresh} Hz but all detectors alive! '
                                          f'Beam loss?')
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
                        self.live_det_stamps = {x: dt.now() for x in self.alarm_times}  # Reset dead time counters
                    else:
                        wait_reason = f'Not running for at least {self.min_run_time}s yet'
                    self.print_status(f'{dt.now().strftime(self.dt_format)} | {wait_reason}, waiting...')
                    if self.alarm_playback is not None and self.alarm_playback.is_playing():
                        self.alarm_playback.stop()
                sleep(self.refresh_sleep)
            except Exception as e:
                self.print_status(f'Error reading Daq Monitor!\n{e}')
        if self.keep_checking_daq:
            self.restart()  # Restart driver if loop breaks, currently only after runs.

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
            duration = duration[0] * 24 * 60 * 60 + duration[1] * 60 * 60 + duration[2] * 60 + duration[3]  # stamp to s

            if self.run_duration_min * 60 < duration < self.run_duration_min * 60 + self.run_dur_alarm_time:
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
        run_state = self.driver.find_element(By.XPATH, self.xpaths['text']['run_state']).text
        return run_state == self.running_state_text

    def check_daq_hz(self):
        """
        Find and return total DAQ rate. This corresponds to the last "All" column on the monitor page.
        :return:
        """
        switch_frame(self.driver, self.xpaths['frames']['main'])
        trig2_name = ''
        row = 2  # Row starts at 2 on page
        while trig2_name != self.trig2_all_name:
            try:
                trig2_name = self.driver.find_element(By.XPATH, self.xpaths['text']['trig2_name'](row)).text
                if trig2_name == self.trig2_all_name:
                    daq_hz = int(self.driver.find_element(By.XPATH, self.xpaths['text']['trig2_hz'](row)).text)
                    return daq_hz
            except NoSuchElementException:
                row = -1  # Flag that end of table has been reached, stop looking for more detectors
            row += 1
        self.print_status('Daq Rate not found! Bypassing low Daq Rate alarm.')

        return self.daq_hz_thresh + 1

    def check_dead_dets(self):
        """
        Read each detector dead time. If any detector more than dead_thresh dead, return name of detector
        :return: List of dead detectors
        """

        switch_frame(self.driver, self.xpaths['frames']['main'])
        xpath, row = self.xpaths['text']['det_deads'], self.xpaths['consts']['det_dead_start_row']
        dets_dead = []
        while row >= 0:
            try:
                dead_percent = int(self.driver.find_element(By.XPATH, xpath(row, 3)).text.strip('%'))
                if dead_percent > self.dead_thresh:
                    dets_dead.append(self.driver.find_element(By.XPATH, xpath(row, 1)).text.lower())
                row += 1
            except NoSuchElementException:
                row = -1  # Flag that end of table has been reached, stop looking for more detectors
        return dets_dead

    def write_config(self):
        """
        Write current DaqWatcher parameters to config file.
        :return:
        """
        self.print_status('Writing parameters to config file...')
        config = configparser.ConfigParser()
        config['General'] = {'run_start_buffer': str(self.min_run_time),
                             'daq_hz_minimum': str(self.daq_hz_thresh),
                             'run_duration_target': str(self.run_duration_min),
                             'run_over_alarm_time': str(self.run_dur_alarm_time),
                             'loop_sleep': str(self.refresh_sleep),
                             'dead_threshold': str(self.dead_thresh)}

        config['Detector Alarm Times'] = {det: str(alarm_time) for det, alarm_time in self.alarm_times.items()}

        with open(self.config_path, 'w') as configfile:
            config.write(configfile)
        self.print_status(f'Parameters written to {self.config_path}')

    def read_config(self):
        """
        Read parameters from config file and set them in current DaqWatcher instance
        :return:
        """
        self.print_status(f'Reading parameters from {self.config_path}...')
        config = configparser.ConfigParser()
        config.read(self.config_path)
        use_default = False
        try:
            self.min_run_time = float(config['General']['run_start_buffer'])
            self.daq_hz_thresh = float(config['General']['daq_hz_minimum'])
            self.run_duration_min = float(config['General']['run_duration_target'])
            self.run_dur_alarm_time = float(config['General']['run_over_alarm_time'])
            self.refresh_sleep = float(config['General']['loop_sleep'])
            self.dead_thresh = float(config['General']['dead_threshold'])

            self.alarm_times = {det: float(alarm_time) for det, alarm_time in config['Detector Alarm Times'].items()}

        except KeyError:  # If any fields missing, just use defaults (could be smarter later if needed)
            use_default = True

        if use_default:  # If issues, use default and then immediately write defaults to file
            self.print_status('Couldn\'t read parameters from config file. Using default and writing defaults to file.')
            self.def_config()
            self.write_config()
        else:
            self.print_status('Parameters read from config file')

    def def_config(self):
        """
        Use default parameter values
        :return:
        """
        self.min_run_time = 60  # s If run not this old, don't check dead time yet
        self.daq_hz_thresh = 1  # Hz If ALL DAQ Hz less than this, sound alarm (beam loss)

        self.run_duration_min = 30  # min How long run should go for.
        self.run_dur_alarm_time = 20  # s How long to play run end notification.

        self.refresh_sleep = 1  # s How long to sleep at end of loop before refreshing page and checking again
        self.dead_thresh = 90  # % Dead time above which to consider detector dead

        self.alarm_times = {
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
            'fst': 0,
        }


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
        'text':
            {
                'duration': '//*[@id="duration"]',
                'run_state': '//*[@id="run_state"]',
                'messages': lambda row, col: f'//*[@id="tb"]/tbody/tr[{row}]/td[{col}]',  # Deprecated
                'trig2_name': lambda row: f'//*[@id="trg2"]/tbody/tr[{row}]/td[1]',
                'trig2_hz': lambda row: f'//*[@id="trg2"]/tbody/tr[{row}]/td[3]',
                'det_deads': lambda row, col: f'//*[@id="det"]/tbody/tr[{row}]/td[{col}]',
            },
        'consts':
            {
                'message_time_col': 1,  # Deprecated
                'message_text_col': 7,  # Deprecated
                'message_first_index': 2,  # Deprecated
                'det_dead_start_row': 2,
            }
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
