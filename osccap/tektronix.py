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

def take_screenshot_png(host, fullscreen=True):
    dev = pyvxi11.Vxi11(host)
    dev.open()
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
    dev.write(r'FILESYSTEM:PRINT "C:\TEMP\SCREEN.PNG", GPIB')
    time.sleep(0.5)
    img_data = dev.read()
    dev.write(r'FILESYSTEM:DELETE "C:\TEMP\SCREEN.PNG"')
    dev.close()
    return img_data
