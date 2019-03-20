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
import os
import os.path
import io
from collections import namedtuple
from configparser import SafeConfigParser
import configparser
import csv

import wx
from wx import adv

import sys
if sys.platform.startswith('win'):
    import winreg as reg
    import win32con
    import win32gui
    on_win = True
else:
    on_win = False

from . import tektronix
from . import agilent

__version__ = '0.3'

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
HotKey = namedtuple('HotKey', 'modifiers keycode')
log = logging.getLogger(__name__)

OSC_TYPE_TEKTRONIX_TDS = 0
OSC_TYPE_AGILENT = 1

try:
    from pkg_resources import resource_filename
    DATA_PATH = resource_filename(__name__, 'data')
except ImportError:
    DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')

ICON = os.path.join(DATA_PATH, 'osccap-64.png')
TRAY_ICON = os.path.join(DATA_PATH, 'osccap-16.png')
TRAY_ICON_BUSY = os.path.join(DATA_PATH, 'osccap-busy-16.png')
TRAY_TOOLTIP = 'OscCap v%s' % __version__

def copy_screenshot_to_clipboard(host, screenshot_func):
    wx.InitAllImageHandlers()
    screen = screenshot_func(host)
    stream = io.BytesIO(screen)
    bmp = wx.Bitmap(wx.Image(stream))
    cbbmp = wx.BitmapDataObject(bmp)
    if wx.TheClipboard.Open():
        wx.TheClipboard.SetData(cbbmp)
        wx.TheClipboard.Close()


def save_screenshot_to_file(host, filename, screenshot_func):
    screen = screenshot_func(host)
    f = open(filename, 'wb')
    f.write(screen)
    f.close()

def save_waveform_to_file(host, channel, filename, waveform_func):
    waveform = waveform_func(host, channel) #FIXME current fuckup
    f = open(filename, 'wb')
    print("starting write")
    wr = csv.writer(f)
    values = zip(waveform)
    for value in values:
        wr.writerow(value)
    f.close()

def try_query_value(k, value_name, default):
    try:
        return reg.QueryValueEx(k, value_name)[0]
    except WindowsError:
        return default

class ConfigSettings:
    def __init__(self):
        self.active_scope_id = 0
        self.scopes = list()
        self.hotkey = None

    def load(self):
        if on_win:
            config.load_from_win_registry()
        else:
            config.load_from_dot_config()

    def save(self):
        if on_win:
            config.save_to_win_registry()
        else:
            config.save_to_dot_config()

    def load_from_win_registry(self):
        # load scope definitions
        try:
            k = reg.OpenKey(reg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap\Scopes')
        except WindowsError:
            k = reg.OpenKey(reg.HKEY_LOCAL_MACHINE, 'SOFTWARE\OscCap\Scopes')
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
        try:
            k = reg.OpenKey(reg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap')
        except WindowsError:
            reg.CreateKeyEx(reg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap')
            k = reg.OpenKey(reg.HKEY_LOCAL_MACHINE, 'SOFTWARE\OscCap')
        hk_modifiers = try_query_value(k, 'HotKeyModifiers', None)
        hk_keycode = try_query_value(k, 'HotKeyKeycode', None)
        if (hk_modifiers, hk_keycode) != (None, None):
            self.hotkey = HotKey(hk_modifiers, hk_keycode)
        reg.CloseKey(k)
        # load local user properties
        with reg.OpenKey(reg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap') as k:
            self.active_scope_id = try_query_value(k, 'LastActiveScope',
                    self.scopes[0].id)

    def save_to_win_registry(self):
        # save common program properties
        k = reg.OpenKey(reg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap',
                0, reg.KEY_WRITE)
        reg.SetValueEx(k, 'LastActiveScope', None, reg.REG_DWORD,
                self.active_scope_id)
        reg.CloseKey(k)

    def load_from_dot_config(self):
        filename = os.path.expanduser('~/.osccaprc')
        parser = SafeConfigParser()
        try:
            parser.readfp(open(filename, 'r'))
        except IOError:
            return
        try:
            self.active_scope_id = parser.getint('global', 'last_active_scope')
        except configparser.NoSectionError:
            pass
        except configparser.NoOptionError:
            pass
        for s in parser.sections():
            if s.startswith('scope'):
                try:
                    id = parser.getint(s, 'id')
                    name = parser.get(s, 'name')
                    host = parser.get(s, 'host')
                    type = parser.getint(s, 'type')
                    self.scopes.append(OscProperties(id, name, host, type))
                except configparser.NoOptionError:
                    pass
        self.scopes.sort(key=lambda e: e.id)

    def save_to_dot_config(self):
        filename = os.path.expanduser('~/.osccaprc')
        parser = SafeConfigParser()
        fd = open(filename, 'r')
        parser.readfp(fd)
        try:
            parser.add_section('global')
        except configparser.DuplicateSectionError:
            pass
        parser.set('global', 'last_active_scope', str(self.active_scope_id))
        fd = open(filename + '~', 'w')
        parser.write(fd)
        os.rename(filename + '~', filename)

# There is only one configuration, create it
config = ConfigSettings()

ID_HOTKEY = wx.NewIdRef(count=1)
ID_TO_CLIPBOARD = wx.NewIdRef(count=1)
ID_TO_FILE = wx.NewIdRef(count=1)
ID_WAVEFORM_TO_FILE = wx.NewIdRef(count=1)

class OscCapTaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self):
        wx.adv.TaskBarIcon.__init__(self)
        self.busy = False
        self.set_icon()
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
        self._create_scope_ids()
        self._create_channel_ids()
        # just for global hotkey binding
        if on_win and config.hotkey is not None:
            self.frame = wx.Frame(None, -1)
            self.frame.RegisterHotKey(ID_HOTKEY, config.hotkey.modifiers,
                    config.hotkey.keycode)
            self.frame.Bind(wx.EVT_HOTKEY, self.on_to_clipboard, id=ID_HOTKEY)
        else:
            self.frame = None

    # from http://stackoverflow.com/questions/7523511
    def ShowBallon(self, title, text, msec=0, flags=0):
        if on_win and self.IsIconInstalled():
            self._SetBallonTip(self.icon.GetHandle(), title, text, msec,
                    flags)

    def _SetBallonTip(self, hicon, title, msg, msec, flags):
        infoFlags = 0
        if flags & wx.ICON_INFORMATION:
            infoFlags |= win32gui.NIIF_INFO
        elif flags & wx.ICON_WARNING:
            infoFlags |= win32gui.NIIF_WARNING
        elif flags & wx.ICON_ERROR:
            infoFlags |= win32gui.NIIF_ERROR

        lpdata = (self._GetIconHandle(),
                  99,  # XXX
                  win32gui.NIF_MESSAGE | win32gui.NIF_INFO | win32gui.NIF_ICON,
                  0,
                  hicon,
                  '',
                  msg,
                  msec,
                  title,
                  infoFlags,
                  )
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, lpdata)

    def _GetIconHandle(self):
        """
        Find the icon window.
        This is ugly but for now there is no way to find this window directly from wx
        """
        if not hasattr(self, "_chwnd"):
            try:
                for handle in wx.GetTopLevelWindows():
                    if handle.GetWindowStyle():
                        continue
                    handle = handle.GetHandle()
                    if len(win32gui.GetWindowText(handle)) == 0:
                        self._chwnd = handle
                        break
                if not hasattr(self, "_chwnd"):
                    raise Exception
            except:
                raise Exception('Icon window not found')
        return self._chwnd

    def set_icon(self):
        self.icon = wx.Icon()
        if not self.busy:
             wx.Icon.CopyFromBitmap(self.icon, wx.Bitmap(TRAY_ICON))
        else:
             wx.Icon.CopyFromBitmap(self.icon, wx.Bitmap(TRAY_ICON_BUSY))
        self.SetIcon(self.icon, TRAY_TOOLTIP)

    def _create_scope_ids(self):
        self.scopes = dict()
        self.active_scope = None
        for scope in config.scopes:
            id = wx.NewIdRef(count=1)
            self.scopes[id] = scope
            if scope.id == config.active_scope_id:
                self.active_scope = scope

    def _create_channel_ids(self):
        self.channels = dict()
        self.active_channel = None
        for channel in [ 'ch1', 'ch2', 'ch3', 'ch4' ]: #TODO maybe add in loading a channel list from config
            id = wx.NewIdRef(count=1)
            self.channels[id] = channel
            if self.active_channel == None:
                self.active_channel = self.channels[id]

    def CreatePopupMenu(self):
        menu = wx.Menu()
        item = wx.MenuItem(menu, ID_TO_CLIPBOARD, 'To clipboard')
        menu.Bind(wx.EVT_MENU, self.on_to_clipboard, id=item.GetId())
        menu.Append(item)
        item = wx.MenuItem(menu, ID_TO_FILE, 'To file..')
        menu.Bind(wx.EVT_MENU, self.on_to_file, id=item.GetId())
        menu.Append(item)
        menu.AppendSeparator()
        item = wx.MenuItem(menu, ID_WAVEFORM_TO_FILE, 'Waveform to file..')
        menu.Bind(wx.EVT_MENU, self.on_waveform_to_file, id=item.GetId())
        menu.Append(item)
        menu.AppendSeparator()
        if len(self.scopes) == 0:
            item = wx.MenuItem(menu, -1, 'No scopes')
            menu.AppendCheckItem(item)
            menu.Enable(item.GetId(), False)
            menu.Enable(ID_TO_CLIPBOARD, False)
            menu.Enable(ID_TO_FILE, False)
            menu.Enable(ID_WAVEFORM_TO_FILE, False)
        else:
            for id, scope in sorted(self.scopes.items()):
                item = menu.AppendCheckItem(id, scope.name)
                self.Bind(wx.EVT_MENU, self.on_host_select, item, id=id)
                if scope == self.active_scope:
                    menu.Check(id, True)
        menu.AppendSeparator()
        channel_menu = wx.Menu()
        for id, channel in self.channels.items():
            item = channel_menu.AppendCheckItem(id, channel)
            self.Bind(wx.EVT_MENU, self.on_channel_select, item, id=id)
            if channel == self.active_channel:
                channel_menu.Check(id, True)
        menu.Append(wx.ID_ANY, 'Select Channel', channel_menu)
        menu.AppendSeparator()
        item = wx.MenuItem(menu, wx.ID_ABOUT, 'About..')
        menu.Bind(wx.EVT_MENU, self.on_about, id=item.GetId())
        menu.Append(item)
        item = wx.MenuItem(menu, wx.ID_EXIT, 'Exit')
        menu.Bind(wx.EVT_MENU, self.on_exit, id=item.GetId())
        menu.Append(item)

        return menu

    def copy_screenshot_to_clipboard(self):
        if self.active_scope:
            if self.active_scope.type == OSC_TYPE_TEKTRONIX_TDS:
                func = tektronix.take_screenshot_png
            elif self.active_scope.type == OSC_TYPE_AGILENT:
                func = agilent.take_screenshot_png
            else:
                return
            try:
                self.busy = True
                self.set_icon()
                copy_screenshot_to_clipboard(self.active_scope.host, func)
            except:
                self.ShowBallon("Error", "There was an error while capturing "
                        "the screenshot!", flags=wx.ICON_ERROR);
                pass
            finally:
                self.busy = False
                self.set_icon()

    def save_screenshot_to_file(self, filename):
        if self.active_scope:
            if self.active_scope.type == OSC_TYPE_TEKTRONIX_TDS:
                func = tektronix.take_screenshot_png
            elif self.active_scope.type == OSC_TYPE_AGILENT:
                func = agilent.take_screenshot_png
            else:
                return
            try:
                self.busy = True
                self.set_icon()
                save_screenshot_to_file(self.active_scope.host, filename, func)
            except:
                pass
            finally:
                self.busy = False
                self.set_icon()
    
    def save_waveform_to_file(self, filename):
        if self.active_scope:
            if self.active_scope.type == OSC_TYPE_TEKTRONIX_TDS:
                print("currently not possible")
                return
            elif self.active_scope.type == OSC_TYPE_AGILENT:
                func = agilent.take_waveform_word
            else:
                return
            try:
                self.busy = True
                self.set_icon()
                save_waveform_to_file(self.active_scope.host, self.active_channel, filename, func)
            except:
                self.ShowBallon("Error", "There was an error while capturing "
                        "the waveform!", flags=wx.ICON_ERROR);
                pass
            finally:
                self.busy = False
                self.set_icon()

    def on_to_clipboard(self, event):
        self.copy_screenshot_to_clipboard()

    def on_to_file(self, event):
        d = wx.FileDialog(None, "Save to", wildcard="*.png",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if d.ShowModal() == wx.ID_OK:
            filename = os.path.join(d.GetDirectory(), d.GetFilename())
            self.save_screenshot_to_file(filename)
        d.Destroy()
    
    def on_waveform_to_file(self, event):
        d = wx.FileDialog(None, "Save to", wildcard="*.csv",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if d.ShowModal() == wx.ID_OK:
            filename = os.path.join(d.GetDirectory(), d.GetFilename())
            self.save_waveform_to_file(filename)
        d.Destroy()

    def on_host_select(self, event):
        event_id = event.GetId()
        self.active_scope = None
        for id, scope in self.scopes.items():
            if id == event_id:
                self.active_scope = scope
                break

    def on_channel_select(self, event):
        event_id = event.GetId()
        self.active_channel = None
        for id, channel in self.channels.items():
            if id == event_id:
                self.active_channel = channel
                print(self.active_channel)
                break

    def on_left_down(self, event):
        self.copy_screenshot_to_clipboard()

    def on_exit(self, event):
        if self.active_scope:
            config.active_scope_id = self.active_scope.id
        config.save()
        wx.CallAfter(self.Destroy)
        if self.frame:
            wx.CallAfter(self.frame.Destroy)

    def on_about(self, event):
        info = wx.adv.AboutDialogInfo()

        info.SetIcon(wx.Icon(ICON, wx.BITMAP_TYPE_PNG))
        info.SetName('OscCap')
        info.SetVersion(__version__)
        info.SetDescription(__description__)
        info.SetCopyright('(c) 2011 - 2012 Michael Walle <michael@walle.cc>')
        info.SetWebSite('http://github.com/mwalle/osccap')
        info.SetLicence(__licence__)
        info.AddDeveloper('Michael Walle <michael@walle.cc>')

        wx.adv.AboutBox(info)

def main():
    config.load()
    app = wx.App(False)
    OscCapTaskBarIcon()
    app.MainLoop()

if __name__ == '__main__':
    main()
