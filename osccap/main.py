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

import csv
import io
import logging
import os
import sys
import wx
import wx.adv

from functools import partial

from osccap.config import ConfigSettings
from osccap.errors import NotAliveError
from osccap.oscilloscope import create_oscilloscopes_from_config


if sys.platform.startswith('win'):
    import winreg
    import win32gui
    on_win = True
else:
    on_win = False


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


try:
    from pkg_resources import resource_filename
    DATA_PATH = resource_filename(__name__, 'data')
except ImportError:
    DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')

ICON = os.path.join(DATA_PATH, 'osccap-64.png')
TRAY_ICON = os.path.join(DATA_PATH, 'osccap-16.png')
TRAY_ICON_BUSY = os.path.join(DATA_PATH, 'osccap-busy-16.png')
TRAY_TOOLTIP = 'OscCap v%s' % __version__


def copy_screenshot_to_clipboard(scope):
    wx.InitAllImageHandlers()
    screen = scope.take_screenshot()
    stream = io.BytesIO(screen)
    bmp = wx.Bitmap(wx.Image(stream))
    cbbmp = wx.BitmapDataObject(bmp)
    if wx.TheClipboard.Open():
        wx.TheClipboard.SetData(cbbmp)
        wx.TheClipboard.Close()


def save_screenshot_to_file(scope, filename):
    screen = scope.take_screenshot()

    with open(filename, 'wb') as f:
        f.write(screen)


def save_waveform_to_file(scope, channel, filename):
    waveform = scope.take_waveform(channel)

    with open(filename, 'w') as f:
        writer = csv.writer(f)
        values = zip(waveform)
        for value in values:
            writer.writerow(value)


# There is only one configuration, create it
config = ConfigSettings()

ID_HOTKEY = wx.NewIdRef(count=1)
ID_TO_CLIPBOARD = wx.NewIdRef(count=1)
ID_TO_FILE = wx.NewIdRef(count=1)
ID_WAVEFORM_TO_FILE = wx.NewIdRef(count=1)


class OscCapTaskBarIcon(wx.adv.TaskBarIcon):
    scopes = dict()
    active_scope = None
    channels = dict()
    active_channel = None

    def __init__(self, oscilloscopes):
        wx.adv.TaskBarIcon.__init__(self)
        self.set_tray_icon(busy=False)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

        self._create_scope_ids(oscilloscopes)
#        self._create_channel_ids()

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

        This is ugly but for now there is no way to find this window
        directly from wx.
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

    def set_tray_icon(self, busy):
        self.busy = busy

        self.icon = wx.Icon()
        if not self.busy:
            wx.Icon.CopyFromBitmap(self.icon, wx.Bitmap(TRAY_ICON))
        else:
            wx.Icon.CopyFromBitmap(self.icon, wx.Bitmap(TRAY_ICON_BUSY))
        self.SetIcon(self.icon, TRAY_TOOLTIP)

    def _create_scope_ids(self, oscilloscopes):
        for scope in oscilloscopes:
            id = wx.NewIdRef(count=1)
            self.scopes[id] = scope
            if scope.name == config.active_scope_name:
                self.active_scope = scope

    def _create_channel_ids(self):
        # TODO maybe add in loading a channel
        CHANNELS = [
            'TIME',
            'CHANNEL1', 'CHANNEL2', 'CHANNEL3', 'CHANNEL4',
            'FUNCTION1', 'FUNCTION2', 'FUNCTION3', 'FUNCTION4'
        ]

        for channel in sorted(CHANNELS):
            id = wx.NewIdRef(count=1)
            self.channels[id] = channel
            if self.active_channel is None:
                self.active_channel = self.channels[id]

    def _update_channel_menu_for_scope(self, scope):
        channels = scope.get_channels()
        for channel in channels:
            id = wx.NewIdRef(count=1)
            item = self.channel_menu.AppendCheckItem(id, channel)
            self.Bind(wx.EVT_MENU,
                      partial(self.on_channel_select, channel=channel),
                      item, id=id)
            if channel == self.active_channel:
                self.channel_menu.Check(id, True)

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
                item = menu.AppendCheckItem(id, '{} - {} {}'
                                            .format(scope.name,
                                                    scope.manufacturer,
                                                    scope.model))
                self.Bind(wx.EVT_MENU,
                          partial(self.on_host_select, scope=scope),
                          item)
                if scope == self.active_scope:
                    menu.Check(id, True)
        menu.AppendSeparator()
        self.channel_menu = wx.Menu()
        self._update_channel_menu_for_scope(self.active_scope)
        menu.Append(wx.ID_ANY, 'Select Channel', self.channel_menu)
        menu.AppendSeparator()
        item = wx.MenuItem(menu, wx.ID_ABOUT, 'About..')
        menu.Bind(wx.EVT_MENU, self.on_about, id=item.GetId())
        menu.Append(item)
        item = wx.MenuItem(menu, wx.ID_EXIT, 'Exit')
        menu.Bind(wx.EVT_MENU, self.on_exit, id=item.GetId())
        menu.Append(item)

        return menu

    def _copy_screenshot_to_clipboard(self):
        if self.active_scope:
            try:
                self.set_tray_icon(busy=True)
                copy_screenshot_to_clipboard(self.active_scope)
            except NotAliveError:
                logging.error('cannot take screenshot from {}'
                              .format(self.active_scope.name))
                self.ShowBallon('Error', 'Scope not alive. Cannot capture '
                                'the screenshot!',
                                flags=wx.ICON_ERROR)
            except Exception:
                exp = sys.exc_info()[0]
                logging.error('cannot take screenshot from {} {}'
                              .format(self.active_scope.name), exp)
                self.ShowBallon('Error', 'There was an error while capturing '
                                'the screenshot!',
                                flags=wx.ICON_ERROR)
            finally:
                self.set_tray_icon(busy=False)

    def _save_screenshot_to_file(self, filename):
        if self.active_scope:
            try:
                self.set_tray_icon(busy=True)
                save_screenshot_to_file(self.active_scope, filename)
            except NotAliveError:
                logging.error('cannot take screenshot from {}'
                              .format(self.active_scope.name))
                self.ShowBallon('Error', 'Scope not alive. Cannot capture '
                                'the screenshot!',
                                flags=wx.ICON_ERROR)
            except Exception:
                exp = sys.exc_info()[0]
                logging.error('cannot take screenshot from {} {}'
                              .format(self.active_scope.name), exp)
                self.ShowBallon('Error', 'There was an error while capturing '
                                'the screenshot!',
                                flags=wx.ICON_ERROR)
            finally:
                self.set_tray_icon(busy=False)

    def _save_waveform_to_file(self, filename):
        if self.active_scope:
            try:
                self.set_tray_icon(busy=True)
                save_waveform_to_file(self.active_scope, self.active_channel,
                                      filename)
            except:
                exp = sys.exc_info()[0]
                logging.error('cannot take waveform from {} {}'
                              .format(self.active_scope.name), exp)
                self.ShowBallon('Error', 'There was an error while capturing '
                                'the screenshot!',
                                flags=wx.ICON_ERROR)
                pass
            finally:
                self.set_tray_icon(busy=False)

    def on_to_clipboard(self, event):
        self._copy_screenshot_to_clipboard()

    def on_to_file(self, event):
        d = wx.FileDialog(None, "Save to", wildcard="*.png",
                          style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if d.ShowModal() == wx.ID_OK:
            filename = os.path.join(d.GetDirectory(), d.GetFilename())
            self._save_screenshot_to_file(filename)
        d.Destroy()

    def on_waveform_to_file(self, event):
        d = wx.FileDialog(None, "Save to", wildcard="*.csv",
                          style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if d.ShowModal() == wx.ID_OK:
            filename = os.path.join(d.GetDirectory(), d.GetFilename())
            self._save_waveform_to_file(filename)
        d.Destroy()

    def on_host_select(self, event, scope):
        self.active_scope = scope
        logging.info('select scope {}'.format(self.active_scope))

    def on_channel_select(self, event, channel):
        self.active_channel = channel
        logging.info('select channel {}'.format(self.active_channel))

    def on_left_down(self, event):
        self._copy_screenshot_to_clipboard()

    def on_exit(self, event):
        if self.active_scope:
            config.active_scope_name = self.active_scope.name
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
    logging.basicConfig(format='%(levelname)s: %(message)s',
                        level=logging.DEBUG)

    config.load()
    oscilloscopes = create_oscilloscopes_from_config(config)
    app = wx.App(False)
    OscCapTaskBarIcon(oscilloscopes)
    app.MainLoop()


if __name__ == '__main__':
    main()
