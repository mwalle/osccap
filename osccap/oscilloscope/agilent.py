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
import math
import numpy as np
import time
import vxi11

from osccap.errors import NoDataAvailable


#class Timeit(object):
#    def __init__(self):
#        self.time = time.time()
#        print('{}: {}'.format('start', str(time.time() - self.time)))
#
#    def print(self, msg):
#        print('{}: {}'.format(msg, str(time.time() - self.time)))
#        self.time = time.time()


def binary_block(data):
    """Extract the binary block from the return value.

    .-----------------------------------------------------------.
    |  # | N | L (N bytes) | 0 1 2 ... L-1                | End |
    `-----------------------------------------------------------'
       |   |   |             |                               |
       |   |   |             |                               ` Termination
       |   |   |             |                                 character
       |   |   |             ` L bytes, words, or ASCII
       |   |   |               characters of waveform data
       |   |   ` Number L of bytes of waveform data to follow
       |   ` Number N of bytes in Length block
       ` Start of response
    """
    len_digits = int(chr(data[1]))
    bytes_to_read = data[2:2+len_digits]
    result = data[2+len_digits:-1]
    return result


def get_sources(model):
    if model != 'DSOX91604A':
        raise NotImplementedError()

    SOURCES = [
        'CHANNEL1', 'CHANNEL2', 'CHANNEL3', 'CHANNEL4',
        'FUNCTION1', 'FUNCTION2', 'FUNCTION3', 'FUNCTION4', 
        'FUNCTION5', 'FUNCTION6', 'FUNCTION7', 'FUNCTION8', 
        'FUNCTION9', 'FUNCTION10', 'FUNCTION11', 'FUNCTION12', 
        'FUNCTION13', 'FUNCTION14', 'FUNCTION15', 'FUNCTION16', 
        'WMEMORY1', 'WMEMORY2', 'WMEMORY3', 'WMEMORY4'
    ]
    return SOURCES


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


def get_waveform_preamble(dev):
    """Get the waveform preamble information.

    Following fileds will be returned:
    <format>, <type>, <points>, <count> , <X increment>, <X origin>,
    <X reference>, <Y increment>, <Y origin>, <Y reference>, <coupling>,
    <X display range>, <X display origin>, <Y display range>,
    <Y display origin>, <date>, <time>, <frame model #>, <acquisition mode>,
    <completion>, <X units>, <Y units>, <max bandwidth limit>,
    <min bandwidth limit>
    """

    dev.write(':WAVEFORM:PREAMBLE?')
    preamble = dev.read_raw()[:-1].decode('utf-8')
    preamble = preamble.replace('"', '').split(',')


def get_source_display(dev, source):
    """Get the display state of the source.

    source can be CHANNEL<N>, WMEMORY<N>, FUNCTION<N>

    Returns TRUE or FALSE
    """
    dev.write(':{}:DISPLAY?'.format(source))
    display = dev.read_raw()[:-1].decode('utf-8')
    return bool(int(display))


def convert_waveform_data(bin_data, increment, offset):
    """Convert the values in the (numpy) array.

    Multiply the values with 'increment' and add the 'offset'."""

    bin_data = np.frombuffer(bin_data, dtype='>i2')
    return np.multiply(bin_data, increment) + offset


def take_waveform(host, active_sources, format='ASCII'):
    import vxi11

    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    if format == 'ASCII':
        # waveforms is tuple of 
        # (time_array, time_fmt, waveforms[sources]) here:
        waveforms = _take_waveform(dev, active_sources)

    elif format == 'BINARY':
        dev.write(':WAVEFORM:FORMAT BINARY')

        waveforms = {}
        for source in active_sources:
            dev.write(':WAVEFORM:SOURCE ' + source)
            dev.write(':WAVEFORM:DATA?')
            waveforms[source] = binary_block(dev.read_raw())

    dev.close()
    return waveforms


def _take_time_info(dev):
    logging.debug('agilent: take_waveform TIME')

    dev.write(':WAVEFORM:POINTS?')
    points = int(dev.read())

    dev.write(':WAVEFORM:XINCREMENT?')
    delta_t = float(dev.read())

    dev.write(':WAVEFORM:XORIGIN?')
    t_start = float(dev.read())

    logging.debug('points={} delta_t={} t_start={}'.format(points, delta_t, t_start))

    if delta_t == 0.0:
        raise NoDataAvailable()

    # round t_start accuracy to floor of delta_t
    # -> timebase is closer to zero
    t_start = math.floor(t_start / delta_t) * delta_t

    t_end = t_start + points * delta_t

    # determine the precision of the mantisse for the format output
    mantisse_corner = math.floor( \
            math.log(max(abs(t_start),abs(t_end)),10))
    mantisse_delta_t = len(("%e" % delta_t).split('e')[0].rstrip('0')) - \
            2 - math.floor(math.log(delta_t,10))
    mantisse_time = str(mantisse_corner + mantisse_delta_t)

    time_fmt = '{:.' + mantisse_time + 'e}'

    logging.debug('agilent: TIME t_start={} t_end={} delta_t={} time_format={}'
                  .format(t_start, t_end, delta_t, time_fmt))

    time_array = np.arange(t_start, t_end, delta_t)

    return (time_array, time_fmt)


def _take_waveform_from_source(dev, source):

    dev.write(':ACQUIRE:POINTS?')
    points = int(dev.read())

    dev.write(':WAVEFORM:SOURCE ' + source)
    start_time = time.time()

    dev.write(':WAVEFORM:BYTEORDER MSBFIRST')

    dev.write(':WAVEFORM:YINCREMENT?')
    increment = float(dev.read())

    dev.write(':WAVEFORM:YORIGIN?')
    offset = float(dev.read())

    logging.debug('agilent: {} points={} increment={} offset={}'
                  .format(source, points, increment, offset))

    dev.write(':WAVEFORM:DATA?')
    binary = binary_block(dev.read_raw())
    waveform = convert_waveform_data(binary, increment, offset)

    logging.debug('agilent: {} read_time={}'
                  .format(source, str(time.time() - start_time)))

    return waveform


def _take_waveform(dev, active_sources):

    logging.debug('agilent: take_waveform sources {}'.format(active_sources))

    # Disable output header response
    dev.write(':SYSTEM:HEADER 0')

    # Set waveform read format. ASCII, BYTE, WORD, BINARY
    dev.write(':WAVEFORM:FORMAT WORD')

    waveforms = {}
    for source in [x for x in active_sources if x != 'TIME']:
        waveforms[source] = _take_waveform_from_source(dev, source)

    (time_array, time_fmt) = _take_time_info(dev)

    return (time_array, time_fmt, waveforms)


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s: %(message)s',
                        level=logging.DEBUG)
    (time_array, waveform) = take_waveform('osc05',
                                           ['TIME', 'CHANNEL1', 'CHANNEL2'])
    np.savetxt("foo.csv", waveform['CHANNEL1'], delimiter=",", fmt='%.7e')
