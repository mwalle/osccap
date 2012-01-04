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

import time
import pyvxi11

def binary_block(data):
    len_digits = int(data[1])
    block_len = int(data[2:2+len_digits])
    return data[2+len_digits:]

def take_screenshot_png(host, fullscreen=True):
    dev = pyvxi11.Vxi11(host)
    dev.open()
    dev.write(':DISPLAY:DATA? PNG')
    img_data = binary_block(dev.read())
    dev.close()
    return img_data
