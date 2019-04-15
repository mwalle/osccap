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

import vxi11

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def binary_block(data):
    len_digits = int(data[1])
    block_len = int(data[2:2+len_digits])
    return data[2+len_digits:]

def take_screenshot_png(host, fullscreen=True):
    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev.write(':DISPLAY:DATA? PNG')
    img_data = binary_block(dev.read_raw())
    dev.close()
    return img_data

def take_waveform_word(host, channel):
    dev = vxi11.Instrument("TCPIP::" + host + "::INSTR")
    dev.open()
    dev.write(':WAVEFORM:SOURCE ' + channel)
    dev.write(':WAVEFORM:FORMAT WORD') # ASCII, BYTE, WORD, BINARY
    dev.write(':WAVEFORM:DATA?')
    data = dev.read_raw()
    data = data[int(data[1])+2:-1]
    if len(data)%2 != 0:
        raise ValueError('received data length not mutiple of 2')
    dev.write(':WAVEFORM:YINCREMENT?')
    inc = float(dev.read()[:-1])
    dev.write(':WAVEFORM:YORIGIN?')
    offs = float(dev.read()[:-1])
    """"convert data to 2 8 bit chunks, take HO bits, shift left, add LO bits, 
    subtract rightmost HO bit multiplied by #FFFF for signage, multiply with increment and add offset"""
    values = [(((i[0]<<8 + i[1]) - ((i[0]>>7)*0xffff)) * inc + offs) for i in chunks(data,2)] #Python 3 FIXME test formula for correctness
    #values = map(lambda i: ( (ord(i[0])<<8) + ord(i[1]) - ((ord(i[0])&0x80)>>7)*0xffff ) * inc + offs, \
    #       chunks(data,2)) #Python 2
    dev.close()
    return values

def take_waveform(dev, filename, channel='CHANNEL1', form='ASCII'):
    dev.write(':WAVEFORM:SOURCE ' + channel)
    dev.write(':WAVEFORM:FORMAT ' + form) # ASCII, BYTE, WORD, BINARY
    dev.write(':WAVEFORM:DATA?')
    data = dev.read()
    if form == 'WORD':
        data = data[int(data[1])+2:-1]
        filename = filename + '.bin'
    if form == 'ASCII':
        filename = filename + '.csv'
    with open(filename, 'w') as f:
        f.write(data)
