#!/usr/bin/env python
#
# Capture screenshots from DSOs
# Copyright (c) 2011 Michael Walle
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import time
import vxi11


def get_source_list(host):
    """This query returns a list of the available waveforms that can be
    specified as the source for the SAVe:WAVEform command. Source
    waveforms must have their display mode set to On to appear in this
    list and to be saved.
    """
    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev.write('SAVE:WAVEFORM:SOURCELIST?')
    source_list = dev.read()
    dev.close()
    return source_list


def get_sources(model):

    if model in ['MSO58']:
        SOURCES = [
            'CH1', 'CH2', 'CH3', 'CH4',
            'CH5', 'CH6', 'CH7', 'CH8',
            'MATH1', 'MATH2', 'MATH3', 'MATH4'
        ]
    if model in ['MSO64']:
        SOURCES = [
            'CH1', 'CH2', 'CH3', 'CH4',
            'MATH1', 'MATH2', 'MATH3', 'MATH4'
        ]
    else:
        SOURCES = [
            'CHANNEL1', 'CHANNEL2', 'CHANNEL3', 'CHANNEL4',
            'FUNCTION1', 'FUNCTION2', 'FUNCTION3', 'FUNCTION4'
        ]

    return SOURCES


def take_screenshot(host, model, fullscreen=True, image_format='png'):

    if image_format.lower() != 'png':
        logging.warning('currently only png format supported')
        raise Exception()

    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev.io_timeout = 10

    if model in ['TDS5104', 'TDS7704']:
        dev.write(r'EXPORT:FILENAME "C:\TEMP\SCREEN.PNG"')
        dev.write('EXPORT:FORMAT PNG')
        dev.write('EXPORT:IMAGE NORMAL')
        dev.write('EXPORT:PALETTE COLOR')
        if fullscreen:
            dev.write('EXPORT:VIEW FULLSCREEN')
        else:
            dev.write('EXPORT:VIEW GRATICULE')
            dev.write('EXPORT:VIEW FULLNO')
        dev.write('EXPORT START')
        time.sleep(3)
        dev.write(r'FILESYSTEM:PRINT "C:\TEMP\SCREEN.PNG", GPIB')
        time.sleep(0.5)
        img_data = dev.read_raw()
        dev.write(r'FILESYSTEM:DELETE "C:\TEMP\SCREEN.PNG"')

    elif model in ['MSO54', 'MSO56', 'MSO58', 'MSO64']:
        dev.write(r'SAVE:IMAGE "screen.png"')
        save_time = 0
        dev.write('*OPC?')

        while '1' not in dev.read():
            time.sleep(0.01)
            save_time += 1
            dev.write('*OPC?')
            if save_time > 10000:
                raise Exception('save image takes longer than 10 seconds')
        dev.write('FILESYSTEM:READFILE "screen.png"')
        img_data = dev.read_raw()
        dev.write(r'FILESYSTEM:DELETE "screen.png"')

    else:
        raise Exception('scope type not known')

    dev.close()

    return img_data

def take_waveform(host, model, active_sources):
    import vxi11

    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev.io_timeout = 10

    if model in ['TDS5104', 'TDS7704']:
        raise('not supported')

    elif model in ['MSO54', 'MSO56', 'MSO58', 'MSO64']:

        waveforms = {}
        for source in active_sources:
            dev.write('SAVE:WAVEFORM {},"waveform.wfm"'.format(source))
            dev.write('*OPC?')

            while '1' not in dev.read():
                time.sleep(0.01)
                save_time += 1
                dev.write('*OPC?')
                if save_time > 10000:
                    raise Exception('save waveform takes longer than 10 seconds')

            dev.write(r'FILESYSTEM:READFILE "waveform.wfm"')
            waveforms[source] = dev.read_raw()
            dev.write(r'FILESYSTEM:DELETE "waveform.wfm"')

    dev.close()
    return waveforms
