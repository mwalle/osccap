import logging
import socket
import vxi11

from osccap.errors import NotAliveError
from osccap.oscilloscope import (agilent, tektronix)


def create_oscilloscopes_from_config(config):
    oscs = list()
    for scope in config.scopes:
        osc = Oscilloscope(scope.host, scope.name)
        oscs.append(osc)

    return oscs


class Oscilloscope(object):
    host = None
    name = None

    manufacturer = None
    model = None

    OSC_TYPE_TEKTRONIX_TDS = 0
    OSC_TYPE_AGILENT = 1

    def __init__(self, host, name):
        self.host = host
        self.name = name
        self.selected_sources = list()

    def __str__(self):
        return '[name: {} host: {}]'.format(self.name, self.host)

    def _update_manufacturer_model(self):
        """For legacy purpose we update the type."""
        (self.manufacturer, self.model) = self.get_idn()[0:2]

    def is_alive(self, timeout=0.1):
        """Check if the oscilloscope's network connection is alive."""
        try:
            with socket.socket(socket.AF_INET) as sock:
                sock.settimeout(timeout)
                sock.connect((self.host, 111))
        except socket.timeout:
            return False

        return True

    def get_idn(self):
        """This query might return :TEKTRONIX,TDS5104,CF:91.1CT
        FV:01.00.912, indicating the instrument model number,
        configured number, and firmware version number.
        """
        dev = vxi11.Instrument("TCPIP::" + self.host + "::INSTR")
        dev.open()
        dev.write('*IDN?')
        idn = dev.read()
        dev.close()
        logging.info('IDN: {}'.format(idn))
        return idn.split(',')

    def get_selected_sources(self):
        return self.selected_sources

    def add_selected_source(self, source):
        self.selected_sources.append(source)

    def remove_selected_source(self, source):
        self.selected_sources.remove(source)

    def get_sources(self):
        DEFAULT_CHANNELS = []

        if not self.is_alive():
            logging.warning('scope {} is not alive'.format(self))
            return DEFAULT_CHANNELS

        self._update_manufacturer_model()

        if self.manufacturer == 'TEKTRONIX':
            return tektronix.get_sources(self.model)
        elif self.manufacturer == 'KEYSIGHT TECHNOLOGIES':
            return agilent.get_sources(self.model)
        else:
            logging.warning('unknown scope type {}'.format(self.type))
            return DEFAULT_CHANNELS

    def take_screenshot(self, fullscreen=True, image_format='png'):

        if not self.is_alive():
            raise NotAliveError()

        self._update_manufacturer_model()

        if self.manufacturer == 'TEKTRONIX':
            return tektronix.take_screenshot(self.host, self.model)
        elif self.manufacturer == 'KEYSIGHT TECHNOLOGIES':
            return agilent.take_screenshot(self.host, self.model)
        else:
            raise NotImplementedError()

    def take_waveform(self, format='ASCII'):

        if not self.is_alive():
            raise NotAliveError()

        self._update_manufacturer_model()

        if self.manufacturer == 'KEYSIGHT TECHNOLOGIES':
            return agilent.take_waveform(self.host, self.selected_sources, format)
        else:
            raise NotImplementedError()

