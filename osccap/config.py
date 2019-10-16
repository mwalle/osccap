#!/usr/bin/env python

import logging
import os
import sys

from collections import namedtuple

if sys.platform.startswith('win'):
    import winreg
else:
    from configparser import ConfigParser
    import configparser

OscProperties = namedtuple('OscProperties', 'name host')
HotKey = namedtuple('HotKey', 'modifiers keycode')


def get_configuration():
    if sys.platform.startswith('win'):
        return ConfigSettingsWindows()
    else:
        return ConfigSettingsLinux()


class ConfigSettings(object):
    def __init__(self):
        self.active_scope_name = None
        self.scopes = list()
        self.hotkey = None

    def load(self):
        pass

    def save(self):
        pass


class ConfigSettingsWindows(ConfigSettings):
    def __init__(self):
        super(ConfigSettingsWindows, self).__init__()

    def _try_query_value(self, k, value_name, default):
        try:
            return winreg.QueryValueEx(k, value_name)[0]
        except WindowsError:
            return default

    def load(self):
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
                    scope_host = winreg.QueryValueEx(entry, 'host')[0]
                    self.scopes.append(OscProperties(name, scope_host))
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
            self.active_scope_name = self._try_query_value(key,
                                                           'LastActiveName',
                                                           self.scopes[0].name)

    def save(self):
        # save common program properties
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'SOFTWARE\OscCap',
                             0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, 'LastActiveName', None, winreg.REG_SZ,
                          self.active_scope_name)
        winreg.CloseKey(key)


class ConfigSettingsLinux(ConfigSettings):
    def __init__(self):
        super(ConfigSettingsLinux, self).__init__()
        self.filename = os.path.expanduser('~/.osccaprc')

    def load(self):
        """ Load the configuration from a ini style configuration file.

        e.g.

        [global]
        last_active_name = osc01

        [scope_osc01]
        host=osc1

        [scope_osc02]
        host=osc2
        """
        parser = ConfigParser()

        try:
            parser.read(self.filename)
        except IOError:
            return

        try:
            self.active_scope_name = parser.get('global', 'last_active_name')
        except configparser.NoSectionError:
            pass
        except configparser.NoOptionError:
            pass

        for s in parser.sections():
            if s.startswith('scope_'):
                try:
                    name = s[len('scope_'):]
                    host = parser.get(s, 'host')
                    self.scopes.append(OscProperties(name, host))
                except configparser.NoOptionError:
                    pass
        self.scopes.sort(key=lambda e: e.name)

    def save(self):
        parser = ConfigParser()
        parser.read(self.filename)

        try:
            parser.add_section('global')
        except configparser.DuplicateSectionError:
            pass

        parser.set('global', 'last_active_name', str(self.active_scope_name))
        with open(self.filename, 'w') as configfile:
            parser.write(configfile)


if __name__ == '__main__':
    config = get_configuration()
    config.load()
    print(config.scopes)
    print(config.active_scope_name)
    print(config.hotkey)
    print(config.active_scope_name)
    config.save()
