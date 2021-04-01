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

    _manufacturer = None
    _model = None

    def __init__(self, host, name):
        self.host = host
        self.name = name
        self.selected_sources = list()

    def __str__(self):
        return '[name: {} host: {}]'.format(self.name, self.host)

    def _update_manufacturer_model(self):
        """For legacy purpose we update the type."""
        try:
            (self._manufacturer, self._model) = self.get_idn()[0:2]
        except Exception as e:
            pass

    def get_manufacturer(self):
        if self.is_alive() and self._manufacturer == None:
            self._update_manufacturer_model()
        return self._manufacturer

    def get_model(self):
        if self.is_alive() and self._model == None:
            self._update_manufacturer_model()
        return self._model

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
            return DEFAULT_CHANNELS

        if self.get_manufacturer() == 'TEKTRONIX':
            return tektronix.get_sources(self._model)
        elif self.get_manufacturer() == 'KEYSIGHT TECHNOLOGIES':
            return agilent.get_sources(self._model)
        else:
            logging.warning('unsupported scope {}'.format(self._manufacturer))
            return DEFAULT_CHANNELS

    def take_screenshot(self, fullscreen=True, image_format='png'):

        if not self.is_alive():
            raise NotAliveError()

        if self.get_manufacturer() == 'TEKTRONIX':
            return tektronix.take_screenshot(self.host, self._model)
        elif self.get_manufacturer() == 'KEYSIGHT TECHNOLOGIES':
            return agilent.take_screenshot(self.host, self._model)
        else:
            logging.warning('unsupported scope {}'.format(self._manufacturer))
            raise NotImplementedError()

    def take_waveform(self, waveform_format='ASCII'):

        if not self.is_alive():
            raise NotAliveError()

        self._update_manufacturer_model()

        if self._manufacturer == 'KEYSIGHT TECHNOLOGIES':
            return agilent.take_waveform(self.host,
                                         self._model,
                                         self.selected_sources,
                                         waveform_format=waveform_format)
        elif self._manufacturer == 'TEKTRONIX':
            return tektronix.take_waveform(self.host,
                                           self._model,
                                           self.selected_sources)
        else:
            logging.warning('unsupported scope {}'.format(self._manufacturer))
            raise NotImplementedError()
