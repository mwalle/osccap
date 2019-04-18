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


def _get_idn(dev):
    """This query might return :TEKTRONIX,TDS5104,CF:91.1CT
    FV:01.00.912, indicating the instrument model number,
    configured number, and firmware version number.
    """
    dev.write('*IDN?')
    idn = dev.read()
    logging.info('Tektronix IDN: {}'.format(idn))
    return idn.split(',')


def get_channel_list(host):
    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev.write('SAVE:WAVEFORM:SOURCELIST?')
    channel_list = dev.read()
    dev.close()
    return channel_list


def get_channels():
    CHANNELS = [
        'TIME',
        'CHANNEL1', 'CHANNEL2', 'CHANNEL3', 'CHANNEL4',
        'FUNCTION1', 'FUNCTION2', 'FUNCTION3', 'FUNCTION4'
    ]
    return CHANNELS


def take_screenshot(host, fullscreen=True, image_format='png'):

    if image_format.lower() != 'png':
        logging.warning('currently only png format supported')
        raise Exception()

    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev.io_timeout = 10

    model = _get_idn(dev)[1]

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

    elif model in ['MSO64', 'MSO58']:
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

    else:
        raise Exception('scope type not known')

    img_data = dev.read_raw()
    dev.write(r'FILESYSTEM:DELETE "C:\TEMP\SCREEN.PNG"')
    dev.close()

    return img_data
