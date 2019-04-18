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
import vxi11


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def binary_block(data):
    len_digits = int(chr(data[1]))
    return data[2+len_digits:-1]


def get_channels(model):
    if model != 'DSOX91604A':
        raise NotImplementedError()

    CHANNELS = [
        'TIME',
        'CHANNEL1', 'CHANNEL2', 'CHANNEL3', 'CHANNEL4'
    ]
    return CHANNELS


def take_screenshot(host, model=None, fullscreen=True, image_format='png'):
    logging.debug('agilent: take_screenshot')

    if image_format.lower() != 'png':
        logging.warning('currently only png format supported')
        raise Exception()

    if model != 'DSOX91604A':
        raise NotImplementedError()

    try:
        dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
        dev.open()
        dev.write(':DISPLAY:DATA? PNG')
        img_data = binary_block(dev.read_raw())
        dev.close()
    except Exception as exp:
        logging.error('agilent error taking screenshot')
        print(exp)
        return None

    return img_data


def take_waveform(host, channel, model=None):
    logging.debug('agilent: take_waveform channel {}'.format(channel))

    if model != 'DSOX91604A':
        raise NotImplementedError()

    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev.write(':WAVEFORM:SOURCE ' + channel)
    dev.write(':WAVEFORM:FORMAT WORD') # ASCII, BYTE, WORD, BINARY
    dev.write(':WAVEFORM:DATA?')
    data = dev.read_raw()
    data = data[int(data[1])+2:-1]
    if len(data) % 2 != 0:
        raise ValueError('received data length not mutiple of 2')
    dev.write(':WAVEFORM:YINCREMENT?')
    inc = float(dev.read()[:-1])
    dev.write(':WAVEFORM:YORIGIN?')
    offs = float(dev.read()[:-1])
    dev.close()

    # convert data to 2 8 bit chunks, take HO bits, shift left, add LO bits,
    # subtract rightmost HO bit multiplied by #FFFF for signage, multiply
    # with increment and add offset
    values = [(((i[0]<<8 + i[1]) - ((i[0]>>7)*0xffff)) * inc + offs) for i in chunks(data,2)] #Python 3 FIXME test formula for correctness

    return values
