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
    type = None

    manufacturer = None
    model = None

    OSC_TYPE_TEKTRONIX_TDS = 0
    OSC_TYPE_AGILENT = 1

    def __init__(self, host, name):
        self.host = host
        self.name = name
#        self.type = type

    def __str__(self):
        return '[name: {} host: {}]'.format(self.name, self.host)

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

    def get_channels(self):
        DEFAULT_CHANNELS = [
            'CHANNEL1', 'CHANNEL2', 'CHANNEL3', 'CHANNEL4'
        ]

        if self.type == self.OSC_TYPE_TEKTRONIX_TDS:
            return tektronix.get_channels()
        elif self.type == self.OSC_TYPE_AGILENT:
            return agilent.get_channels()
        else:
            logging.warning('unknown scope type {}'.format(self.type))
            return DEFAULT_CHANNELS

    def _update_type(self):
        """For legacy purpose we update the type."""
        if self.type is None:
            (self.manufacturer, _) = self.get_idn()[0:2]

            if self.manufacturer == 'TEKTRONIX':
                self.type = self.OSC_TYPE_TEKTRONIX_TDS
            elif self.manufacturer == 'KEYSIGHT TECHNOLOGIES':
                self.type = self.OSC_TYPE_AGILENT

    def take_screenshot(self, fullscreen=True, image_format='png'):

        if not self.is_alive():
            raise NotAliveError()

        self._update_type()

        if self.type == self.OSC_TYPE_TEKTRONIX_TDS:
            return tektronix.take_screenshot(self.host)
        elif self.type == self.OSC_TYPE_AGILENT:
            return agilent.take_screenshot(self.host)
        else:
            raise NotImplementedError()

    def take_waveform(self, channel):

        if not self.is_alive():
            raise NotAliveError()

        self._update_type()

        if self.type == self.OSC_TYPE_TEKTRONIX_TDS:
            raise NotImplementedError()
        elif self.type == self.OSC_TYPE_AGILENT:
            return agilent.take_waveform(self.host, channel)
        else:
            raise NotImplementedError()
