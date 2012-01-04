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
import os.path
import StringIO
from collections import namedtuple

import wx
import pyvxi11

import sys
if sys.platform.startswith('win'):
    import _winreg as reg
    import win32con
    on_win = True
else:
    on_win = False

__version__ = '0.1'

__description__ = """OscCap is a small utility to capture screenshots from
various digial oscilloscopes. Screenshots can either be copied to the clipboard
or saved to a file."""

__licence__ = """This program is free software; you can redistribute it
and/or modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA"""

OscProperties = namedtuple('OscProperties', 'id name host type')
log = logging.getLogger(__name__)

OSC_TYPE_TEKTRONIX_TDS = 0
OSC_TYPE_AGILENT = 1

#import pkg_resources
#ICON = pkg_resources.resource_filename(__name__, 'data/osccap-64.png')
#TRAY_ICON = pkg_resources.resource_filename(__name__, 'data/osccap-16.png')
#TRAY_ICON_BUSY = \
#        pkg_resources.resource_filename(__name__, 'data/osccap-busy-16.png')

ICON = 'data/osccap-64.png'
TRAY_ICON = 'data/osccap-16.png'
TRAY_ICON_BUSY = 'data/osccap-busy-16.png'
TRAY_TOOLTIP = 'OscCap v%s' % __version__

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

def copy_screenshot_to_clipboard(host):
    screen = take_screenshot_png(host)
    stream = StringIO.StringIO(screen)
    bmp = wx.BitmapFromImage(wx.ImageFromStream(stream))
    cbbmp = wx.BitmapDataObject(bmp)
    if wx.TheClipboard.Open():
        wx.TheClipboard.SetData(cbbmp)
        wx.TheClipboard.Close()

def save_screenshot_to_file(host, filename):
    screen = take_screenshot_png(host)
    f = open(filename, 'wb')
    f.write(screen)
    f.close()

def create_menu_item(menu, label, func):
    item = wx.MenuItem(menu, -1, label)
    menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.AppendItem(item)
    return item

def try_query_value(k, value_name, default):
    try:
        return reg.QueryValueEx(k, value_name)[0]
    except WindowsError:
        return default

class ConfigSettings:
    def __init__(self):
        self.active_scope_id = 0
        self.scopes = list()

    def _check_windows_registry(self):
        if not on_win:
            raise RuntimeError('You are not on a windows platform')

    def load_from_win_registry(self):
        self._check_windows_registry()

        r = reg.ConnectRegistry(None, reg.HKEY_CURRENT_USER)
        # load scope definitions
        k = reg.OpenKey(r, r'Software\OscCap\Scopes')
        i = 0
        try:
            while True:
                name = reg.EnumKey(k, i)
                try:
                    s = reg.OpenKey(k, name)
                    id = reg.QueryValueEx(s, 'id')[0]
                    host = reg.QueryValueEx(s, 'host')[0]
                    type = reg.QueryValueEx(s, 'type')[0]
                    self.scopes.append(OscProperties(id, name, host, type))
                except WindowsError:
                    log.error('Could not load oscilloscope %s', name)
                i += 1
        except WindowsError:
            pass
        reg.CloseKey(k)
        self.scopes.sort(key=lambda e: e.id)

        # load common program properties
        k = reg.OpenKey(r, r'Software\OscCap')
        self.active_scope_id = try_query_value(k, 'LastActiveScope',
                self.scopes[0].id)
        reg.CloseKey(k)

    def save_to_win_registry(self):
        self._check_windows_registry()
        r = reg.ConnectRegistry(None, reg.HKEY_CURRENT_USER)
        # save common program properties
        k = reg.OpenKey(r, r'Software\OscCap', 0, reg.KEY_WRITE)
        reg.SetValueEx(k, 'LastActiveScope', None, reg.REG_DWORD,
                self.active_scope_id)
        reg.CloseKey(k)

# There is only one configuration, create it
config = ConfigSettings()

ID_HOTKEY = wx.NewId()
ID_TO_CLIPBOARD = wx.NewId()
ID_TO_FILE = wx.NewId()

class OscCapTaskBarIcon(wx.TaskBarIcon):
    def __init__(self):
        wx.TaskBarIcon.__init__(self)
        self.set_icon(busy=False)
        self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
        self._create_scope_ids()
        # just for global hotkey binding
        if on_win:
            self.frame = wx.Frame(None, -1)
            hotkey_id = ID_HOTKEY
            self.frame.RegisterHotKey(hotkey_id, win32con.MOD_ALT,
                    win32con.VK_F1)
            self.frame.Bind(wx.EVT_HOTKEY, self.on_to_clipboard, id=hotkey_id)

    def set_icon(self, busy=False):
        if not busy:
            icon = wx.IconFromBitmap(wx.Bitmap(TRAY_ICON))
        else:
            icon = wx.IconFromBitmap(wx.Bitmap(TRAY_ICON_BUSY))
        self.SetIcon(icon, TRAY_TOOLTIP)

    def _create_scope_ids(self):
        self.scopes = dict()
        self.active_scope = None
        for scope in config.scopes:
            id = wx.NewId()
            self.scopes[id] = scope
            if scope.id == config.active_scope_id:
                self.active_scope = scope
        if self.active_scope is None:
            self.active_scope = config.scopes[0]

    def CreatePopupMenu(self):
        menu = wx.Menu()
        item = wx.MenuItem(menu, ID_TO_CLIPBOARD, 'To clipboard')
        menu.Bind(wx.EVT_MENU, self.on_to_clipboard, id=item.GetId())
        menu.AppendItem(item)
        item = wx.MenuItem(menu, ID_TO_FILE, 'To file..')
        menu.Bind(wx.EVT_MENU, self.on_to_file, id=item.GetId())
        menu.AppendItem(item)
        menu.AppendSeparator()
        for id, scope in sorted(self.scopes.items()):
            item = menu.AppendCheckItem(id, scope.name)
            self.Bind(wx.EVT_MENU, self.on_host_select, item, id=id)
            if scope == self.active_scope:
                menu.Check(id, True)
        menu.AppendSeparator()
        item = wx.MenuItem(menu, wx.ID_ABOUT, 'About..')
        menu.Bind(wx.EVT_MENU, self.on_about, id=item.GetId())
        menu.AppendItem(item)
        item = wx.MenuItem(menu, wx.ID_EXIT, 'Exit')
        menu.Bind(wx.EVT_MENU, self.on_exit, id=item.GetId())
        menu.AppendItem(item)

        return menu

    def copy_screenshot_to_clipboard(self):
        if self.active_scope:
            self.set_icon(busy=True)
            copy_screenshot_to_clipboard(self.active_scope.host)
            self.set_icon(busy=False)

    def save_screenshot_to_file(self, filename):
        if self.active_scope:
            self.set_icon(busy=True)
            save_screenshot_to_file(self.active_scope.host, filename)
            self.set_icon(busy=False)

    def on_to_clipboard(self, event):
        self.copy_screenshot_to_clipboard()

    def on_to_file(self, event):
        d = wx.FileDialog(None, "Save to", wildcard="*.png",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if d.ShowModal() == wx.ID_OK:
            filename = os.path.join(d.GetDirectory(), d.GetFilename())
            self.save_screenshot_to_file(filename)
        d.Destroy()

    def on_host_select(self, event):
        event_id = event.GetId()
        self.active_scope = None
        for id, scope in self.scopes.items():
            if id == event_id:
                self.active_scope = scope
                break

    def on_left_down(self, event):
        self.copy_screenshot_to_clipboard()

    def on_exit(self, event):
        config.active_scope_id = self.active_scope.id
        config.save_to_win_registry()
        wx.CallAfter(self.Destroy)
        wx.CallAfter(self.frame.Destroy)

    def on_about(self, event):
        info = wx.AboutDialogInfo()

        info.SetIcon(wx.Icon(ICON, wx.BITMAP_TYPE_PNG))
        info.SetName('OscCap')
        info.SetVersion(__version__)
        info.SetDescription(__description__)
        info.SetCopyright('(c) 2011 - 2012 Michael Walle <michael@walle.cc>')
        info.SetWebSite('http://github.com/mwalle/osccap')
        info.SetLicence(__licence__)
        info.AddDeveloper('Michael Walle <michael@walle.cc>')

        wx.AboutBox(info)

def main():
    config.load_from_win_registry()
    app = wx.PySimpleApp()
    OscCapTaskBarIcon()
    app.MainLoop()

if __name__ == '__main__':
    main()
