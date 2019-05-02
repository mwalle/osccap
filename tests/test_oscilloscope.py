#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mock import MagicMock
from nose.tools import eq_

from osccap.oscilloscope.agilent import (binary_block, convert_waveform_data,
                                         _take_waveform)


def test_binary_block():
    data_binary = b'#232\xfaq\xfd\xac\xfc@\xfdW\xfd+\xfc\xd0\xfa\xef\xfc\x8b\xfbB\xfcB\xfe\x0b\xfcl\xfbi\xfeR\xfdC\xfc\x8f\n'
    data = binary_block(data_binary)
    eq_((len(data_binary)-5), float(len(data)))
    eq_(data, b'\xfaq\xfd\xac\xfc@\xfdW\xfd+\xfc\xd0\xfa\xef\xfc\x8b\xfbB\xfcB\xfe\x0b\xfcl\xfbi\xfeR\xfdC\xfc\x8f')


def test_convert_waveform_data():
    data_binary = b'\x01\x00\x02\x00\xfc@\xfdW\xfd+\xfc\xd0\xfa\xef\xfc\x8b\xfbB\xfcB\xfe\x0b\xfcl\xfbi\xfeR\xfdC\xfc\x8f'
    data = convert_waveform_data(data_binary, 1, 0)
    eq_(len(data), len(data_binary)/2)
    eq_(data[0], 256)
    eq_(data[1], 512)

    data = convert_waveform_data(data_binary, 2, 0)
    eq_(len(data), len(data_binary)/2)
    eq_(data[0], 512)
    eq_(data[1], 1024)

    data = convert_waveform_data(data_binary, 1, 100)
    eq_(len(data), len(data_binary)/2)
    eq_(data[0], 356)
    eq_(data[1], 612)


def test_take_waveform():
    device = MagicMock()
    device.read = MagicMock()
    device.read.side_effect = [
        2,  # POINTS
        1,  # XINCREMENT
        0,  # XORIGIN
        2,  # POINTS
        1,  # YINCREMENT
        0,  # YORIGIN
        2,  # POINTS
        1,  # YINCREMENT
        0,  # YORIGIN
    ]
    device.read_raw = MagicMock()
    device.read_raw.side_effect = [
            b'#232\x00\x01\x00\x02\x00\x03\xfdW\xfd+\xfc\xd0\xfa\xef\xfc\x8b\xfbB\xfcB\xfe\x0b\xfcl\xfbi\xfeR\xfdC\xfc\x8f\n',
            b'#232\x00\x10\x00\x20\x00\x30\xfdW\xfd+\xfc\xd0\xfa\xef\xfc\x8b\xfbB\xfcB\xfe\x0b\xfcl\xfbi\xfeR\xfdC\xfc\x8f\n',
        ]
    (time_array, waveform) = _take_waveform(device, ['S1'])
    eq_(waveform['S1'][0], 1)
    eq_(waveform['S1'][1], 2)
