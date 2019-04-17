#!/usr/bin/env python

import logging
import os
import sys

from collections import namedtuple



on_win = None

if sys.platform.startswith('win'):
    import winreg
    on_win = True
else:
    from configparser import SafeConfigParser
    import configparser
    on_win = False


OscProperties = namedtuple('OscProperties', 'name host type')
HotKey = namedtuple('HotKey', 'modifiers keycode')


class ConfigSettings(object):
    def __init__(self):
        self.active_scope_id = 0
        self.scopes = list()
        self.hotkey = None

    def load(self):
        if on_win:
            self.load_from_win_registry()
        else:
            self.load_from_dot_config()

    def save(self):
        if on_win:
            self.save_to_win_registry()
        else:
            self.save_to_dot_config()

    def _try_query_value(self, k, value_name, default):
        try:
            return winreg.QueryValueEx(k, value_name)[0]
        except WindowsError:
            return default

    def load_from_win_registry(self):
        # load scope definitions
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 'SOFTWARE\OscCap\Scopes')
        except WindowsError:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 'SOFTWARE\OscCap\Scopes')

        index = 0
        try:
            while True:
                name = winreg.EnumKey(key, index)
                try:
                    entry = winreg.OpenKey(key, name)
#                    scope_id = winreg.QueryValueEx(entry, 'id')[0]
                    scope_host = winreg.QueryValueEx(entry, 'host')[0]
                    scope_type = winreg.QueryValueEx(entry, 'type')[0]
                    self.scopes.append(OscProperties(name,
                                                     scope_host, scope_type))
                except WindowsError:
                    logging.error('Error loading config oscilloscope %s', name)
                index += 1
        except WindowsError:
            pass

        winreg.CloseKey(key)
        self.scopes.sort(key=lambda e: e.host)

        # load common program properties
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap')
        except WindowsError:
            winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap')
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\OscCap')

        hk_modifiers = self._try_query_value(key, 'HotKeyModifiers', None)
        hk_keycode = self._try_query_value(key, 'HotKeyKeycode', None)
        if (hk_modifiers, hk_keycode) != (None, None):
            self.hotkey = HotKey(hk_modifiers, hk_keycode)
        winreg.CloseKey(key)

        # load local user properties
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap') as key:
            self.active_scope_host = self._try_query_value(key,
                                                           'LastActiveHost',
                                                           self.scopes[0].host)

    def save_to_win_registry(self):
        # save common program properties
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap',
                             0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, 'LastActiveHost', None, winreg.REG_SZ,
                          self.active_scope_host)
        winreg.CloseKey(key)

    def load_from_dot_config(self):
        """ Load the configuration from a ini style configuration file.

        e.g.

        [global]
        last_active_scope = 2

        [scope_1]
        id = 1
        name=Tek
        host=osc1
        type=1

        [scope_2]
        id = 2
        name=Agilent
        host=osc2
        type=2
        """
        filename = os.path.expanduser('~/.osccaprc')
        parser = SafeConfigParser()

        try:
            parser.readfp(open(filename, 'r'))
        except IOError:
            return

        try:
            self.active_scope_host = parser.get('global', 'last_active_host')
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
        self.scopes.sort(key=lambda e: e.host)

    def save_to_dot_config(self):
        filename = os.path.expanduser('~/.osccaprc')
        parser = SafeConfigParser()
        fd = open(filename, 'r')
        parser.readfp(fd)

        try:
            parser.add_section('global')
        except configparser.DuplicateSectionError:
            pass

        parser.set('global', 'last_active_host', str(self.active_scope_host))
        fd = open(filename + '~', 'w')
        parser.write(fd)
        os.rename(filename + '~', filename)


if __name__ == '__main__':
    print('load config')
    config = ConfigSettings()
    config.load()
    print(config.scopes)
    print(config.active_scope_host)
    print(config.hotkey)
