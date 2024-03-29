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

import io
import logging
import numpy
import os
import socket
import sys
import threading
import time
import traceback
import wx
import wx.adv

from functools import partial

from osccap.config import get_configuration
from osccap.errors import NotAliveError, NoDataAvailable
from osccap.oscilloscope import create_oscilloscopes_from_config


if sys.platform.startswith('win'):
    import winreg
    import win32gui
    on_win = True
else:
    on_win = False


try:
    from osccap.version import __version__
except ImportError:
    __version__ = 'dev'


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
TRAY_ICON_READY = os.path.join(DATA_PATH, 'osccap-ready-16.png')
TRAY_ICON_BUSY = os.path.join(DATA_PATH, 'osccap-busy-16.png')
TRAY_TOOLTIP = 'OscCap v%s' % __version__


def save_waveform_to_file(scope, filename, fmt):

    if fmt == 'binary':
        waveforms = scope.take_waveform('BINARY')
        for source in scope.selected_sources:
            save_filename = filename.replace('.bin', '_{}.bin'.format(source))
            with open(save_filename, 'wb') as f:
                f.write(waveforms[source])

    else:
        (time_array, time_fmt, waveforms) = scope.take_waveform()
        if fmt == 'combined':
            save_fmt = list()

            array = numpy.array(list(waveforms.values()))

            for source in scope.selected_sources:
                save_fmt.append('%.7e')

            start_time = time.time()
            numpy.savetxt(filename, numpy.transpose(array),
                          delimiter=",", fmt=save_fmt)
            logging.debug('save_waveform_to_file: {} save_time={}'
                          .format(scope.selected_sources,
                                  str(time.time() - start_time)))

        elif fmt == 'separated':

            for source in scope.selected_sources:
                save_filename = filename.replace('.csv', '_{}.csv'.format(source))
                start_time = time.time()
                numpy.savetxt(save_filename, waveforms[source],
                              delimiter=",", fmt='%.7e')
                logging.debug('save_waveform_to_file: {} save_time={}'
                              .format(source, str(time.time() - start_time)))

        elif fmt == 'timed-combined':
            save_fmt = list()

            array = time_array
            save_fmt.append(time_fmt)

            for source in scope.selected_sources:
                array = numpy.vstack((array, waveforms[source]))
                save_fmt.append('%.7e')

            start_time = time.time()
            numpy.savetxt(filename, numpy.transpose(array),
                          delimiter=",", fmt=save_fmt)
            logging.debug('save_waveform_to_file: {} save_time={}'
                          .format(source, str(time.time() - start_time)))

        elif fmt == 'timed-separated':
            save_fmt = list()
            save_fmt.append(time_fmt)
            save_fmt.append('%.7e')

            for source in scope.selected_sources:

                save_filename = filename.replace('.csv', '_{}.csv'.format(source))
                array = time_array
                array = numpy.vstack((array, waveforms[source]))

                start_time = time.time()
                numpy.savetxt(save_filename, numpy.transpose(array),
                              delimiter=",", fmt=save_fmt)
                logging.debug('save_waveform_to_file: {} save_time={}'
                              .format(source, str(time.time() - start_time)))


# There is only one configuration, create it
config = get_configuration()

ID_HOTKEY = wx.NewIdRef(count=1)
ID_TO_CLIPBOARD = wx.NewIdRef(count=1)
ID_TO_FILE = wx.NewIdRef(count=1)
ID_WAVEFORM_TO_FILE = wx.NewIdRef(count=1)


EVT_RESULT_ID = wx.ID_ANY

def EVT_RESULT(win, func):
    """Define Result Event."""
    win.Connect(-1, -1, EVT_RESULT_ID, func)


class ScopeAliveEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, scope, alive):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_RESULT_ID)
        self.data = scope
        self.scope = scope
        self.alive = alive


class CheckScopeThread(threading.Thread):
    running = False

    def __init__(self, wxObject, scope, interval=5):
        self.wxObject = wxObject
        self.scope = scope
        self.interval = interval
        threading.Thread.__init__(self)
        self.running = True
        self.start()

    def run(self):
        while True and self.running:
            alive = True if self.scope.is_alive() else False
            wx.PostEvent(self.wxObject, ScopeAliveEvent(self.scope, alive))
            time.sleep(self.interval)

    def stop(self):
        self.running = False


class OscCapTaskBarIcon(wx.adv.TaskBarIcon):
    active_scope = None
    selected_waveform_fmt = 'timed-separated'

    def __init__(self, oscilloscopes):
        self.busy = False
        self.ready = False
        self.all_check_threads = []

        wx.adv.TaskBarIcon.__init__(self)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
        self.set_tray_icon(busy=False, ready=False)

        for scope in oscilloscopes:
            check = CheckScopeThread(self, scope)
            self.all_check_threads.append(check)
            if scope.name == config.active_scope_name:
                self._set_active_scope(scope)

        self.oscilloscopes = oscilloscopes

        self.frame = wx.Frame(None, -1)

        EVT_RESULT(self, self.check_scope_ready)

        # just for global hotkey binding
        if on_win and config.hotkey is not None:
            self.frame.RegisterHotKey(ID_HOTKEY, config.hotkey.modifiers,
                                      config.hotkey.keycode)
            self.frame.Bind(wx.EVT_HOTKEY, self.on_to_clipboard, id=ID_HOTKEY)

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

    def set_tray_icon(self, busy=None, ready=None):
        if busy is not None:
            self.busy = busy
        if ready is not None:
            self.ready = ready

        if self.busy:
            self.icon = wx.Icon(TRAY_ICON_BUSY)
        else:
            path = TRAY_ICON_READY if self.ready else TRAY_ICON
            self.icon = wx.Icon(path)

        self.SetIcon(self.icon, TRAY_TOOLTIP)

    def _update_sources_menu_for_scope(self, scope):
        for source in scope.get_sources():
            id = wx.NewIdRef(count=1)
            item = self.sources_menu.AppendCheckItem(id, source)
            self.Bind(wx.EVT_MENU,
                      partial(self.on_source_select, source=source),
                      item, id=id)

            if source in scope.get_selected_sources():
                self.sources_menu.Check(id, True)

        logging.info('select sources {}'
                     .format(self.active_scope.get_selected_sources()))

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
        menu.Bind(wx.EVT_MENU, partial(self.on_waveform_to_file,
                                       fmt=self.selected_waveform_fmt),
                  id=item.GetId())
        menu.Append(item)
        menu_waveform_format = wx.Menu()
        menu.AppendSubMenu(menu_waveform_format, 'Waveform Format')
        for fmt in ['binary', 'combined', 'separated', 'timed-combined', 'timed-separated']:
            id = wx.NewIdRef(count=1)
            item = menu_waveform_format.AppendCheckItem(id, fmt)
            self.Bind(wx.EVT_MENU,
                      partial(self.on_waveform_fmt_select, fmt=fmt),
                      item, id=id)
            if fmt == self.selected_waveform_fmt:
                menu_waveform_format.Check(id, True)

        menu.AppendSeparator()
        if len(self.oscilloscopes) == 0:
            item = wx.MenuItem(menu, -1, 'No scopes')
            menu.Append(item)
            menu.Enable(item.GetId(), False)
            menu.Enable(ID_TO_CLIPBOARD, False)
            menu.Enable(ID_TO_FILE, False)
            menu.Enable(ID_WAVEFORM_TO_FILE, False)
        else:
            for scope in self.oscilloscopes:
                id = wx.NewIdRef(count=1)
                item = menu.AppendCheckItem(id, '{} - {} {}'
                                            .format(scope.name,
                                                    scope.get_manufacturer(),
                                                    scope.get_model()))
                self.Bind(wx.EVT_MENU,
                          partial(self.on_scope_select, scope=scope),
                          item)
                if scope == self.active_scope:
                    menu.Check(id, True)

        menu.AppendSeparator()
        self.sources_menu = wx.Menu()
        if self.active_scope:
            self._update_sources_menu_for_scope(self.active_scope)
            menu.AppendSubMenu(self.sources_menu, 'Select Source')

        menu.AppendSeparator()
        item = wx.MenuItem(menu, wx.ID_ABOUT, 'About..')
        menu.Bind(wx.EVT_MENU, self.on_about, id=item.GetId())
        menu.Append(item)
        item = wx.MenuItem(menu, wx.ID_EXIT, 'Exit')
        menu.Bind(wx.EVT_MENU, self.on_exit, id=item.GetId())
        menu.Append(item)

        return menu

    def _get_screenshot(self):
        screenshot = None

        if self.active_scope:
            try:
                self.set_tray_icon(busy=True)
                screenshot = self.active_scope.take_screenshot()
            except NotAliveError:
                self.ShowBallon('Error', 'Scope not alive. Cannot capture '
                                'the screenshot!',
                                flags=wx.ICON_ERROR)
            except Exception as exp:
                exp = sys.exc_info()[0]
                logging.error('cannot take screenshot from {} {}'
                              .format(self.active_scope.name,
                                      traceback.format_exc()))
                self.ShowBallon('Unknown Error while taking screenshot',
                                traceback.format_exc(),
                                flags=wx.ICON_ERROR)
            finally:
                self.set_tray_icon(busy=False)

        return screenshot

    def _copy_screenshot_to_clipboard(self):
        screenshot = self._get_screenshot()

        if screenshot is not None:
            stream = io.BytesIO(screenshot)
            bmp = wx.Bitmap(wx.Image(stream))
            cbbmp = wx.BitmapDataObject(bmp)
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(cbbmp)
                wx.TheClipboard.Close()

    def _save_screenshot_to_file(self, filename):
        screenshot = self._get_screenshot()

        if screenshot is not None:
            with open(filename, 'wb') as f:
                f.write(screenshot)

    def _save_waveform_to_file(self, filename, fmt):
        if self.active_scope:
            try:
                self.set_tray_icon(busy=True)
                save_waveform_to_file(self.active_scope, filename, fmt)
            except NotAliveError:
                self.ShowBallon('Error', 'Scope not alive. Cannot capture '
                                'the waveform!',
                                flags=wx.ICON_ERROR)
            except NoDataAvailable:
                logging.error('no waveform data available from {} {}'
                              .format(self.active_scope.name,
                                      traceback.format_exc()))
                self.ShowBallon('Error', 'No waveform data available.',
                                flags=wx.ICON_ERROR)
            except Exception as exc:
                logging.error('cannot take waveform from {} {}'
                              .format(self.active_scope.name,
                                      traceback.format_exc()))
                self.ShowBallon('Unknown Error while taking waveform',
                                traceback.format_exc(),
                                flags=wx.ICON_ERROR)
            finally:
                self.set_tray_icon(busy=False)

    def _set_active_scope(self, scope):
        self.active_scope = scope

    def on_to_clipboard(self, event):
        self._copy_screenshot_to_clipboard()

    def on_to_file(self, event):
        d = wx.FileDialog(None, "Save to", wildcard="*.png",
                          style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if d.ShowModal() == wx.ID_OK:
            filename = os.path.join(d.GetDirectory(), d.GetFilename())
            self._save_screenshot_to_file(filename)
        d.Destroy()

    def on_waveform_to_file(self, event, fmt):
        wildcard = '*.bin' if fmt == 'binary' else '*.cvs'
        d = wx.FileDialog(None, "Save to", wildcard=wildcard,
                          style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

        if d.ShowModal() == wx.ID_OK:
            filename = os.path.join(d.GetDirectory(), d.GetFilename())
            self._save_waveform_to_file(filename, fmt)

        d.Destroy()

    def on_scope_select(self, event, scope):
        logging.info('select scope {}'.format(scope))
        self._set_active_scope(scope)

    def on_source_select(self, event, source):
        logging.info('select source {}'.format(source))

        if source in self.active_scope.get_selected_sources():
            self.active_scope.remove_selected_source(source)
        else:
            self.active_scope.add_selected_source(source)

    def check_scope_ready(self, msg):
        if msg.scope == self.active_scope:
            self.set_tray_icon(ready=msg.alive)

    def on_waveform_fmt_select(self, event, fmt):
        self.selected_waveform_fmt = fmt

    def on_left_down(self, event):
        self._copy_screenshot_to_clipboard()

    def on_exit(self, event):
        for thread in self.all_check_threads:
            thread.stop()

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
    app = wx.App()
    OscCapTaskBarIcon(oscilloscopes)
    app.MainLoop()


if __name__ == '__main__':
    main()
