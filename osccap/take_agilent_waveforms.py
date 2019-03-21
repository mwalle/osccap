#!/usr/bin/env python

import time
import pyvxi11
import datetime
import csv

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def take_waveform_word(dev, filename, channel):
    dev.write(':WAVEFORM:SOURCE ' + channel)
    dev.write(':WAVEFORM:FORMAT WORD') # ASCII, BYTE, WORD, BINARY
    dev.write(':WAVEFORM:DATA?')
    data = dev.read()
    data = data[int(data[1])+2:-1]
    if len(data)%2 != 0:
        raise ValueError('recieved data length not mutiple of 2')
    dev.write(':WAVEFORM:YINCREMENT?')
    inc = float(dev.read()[:-1])
    dev.write(':WAVEFORM:YORIGIN?')
    offs = float(dev.read()[:-1])
    values = map(lambda i: ( (ord(i[0])<<8) + ord(i[1]) - ((ord(i[0])&0x80)>>7)*0xffff ) * inc + offs, \
            chunks(data,2))
    filename = filename + '.csv'
    with open(filename, 'wb') as f:
        wr = csv.writer(f)
        values = zip(values)
        for value in values:
            wr.writerow(value)
#        wr.writerow(values)

def take_waveform(dev, filename, channel='CHANNEL1', form='ASCII'):
    dev.write(':WAVEFORM:SOURCE ' + channel)
    dev.write(':WAVEFORM:FORMAT ' + form) # ASCII, BYTE, WORD, BINARY
    dev.write(':WAVEFORM:DATA?')
    data = dev.read()
    if form == 'WORD':
        data = data[int(data[1])+2:-1]
        filename = filename + '.bin'
    if form == 'ASCII':
        filename = filename + '.csv'
    with open(filename, 'w') as f:
        f.write(data)


HOST = 'osc05'
CHANNEL = 'CHANNEL2'
CHANNEL = 'WMEMORY1'
CHANNEL = 'FUNCTION1'

def main():
    dev = pyvxi11.Vxi11(HOST)
    dev.open()
    dev.io_timeout = 300
    datestring = datetime.datetime.now().strftime('%y-%m-%d_%H-%M-%S')

    filename = 'waveform_' + CHANNEL + '_' + datestring
#    take_waveform(dev, filename, CHANNEL, 'WORD')
#    take_waveform(dev, filename, CHANNEL, 'ASCII')

    take_waveform_word(dev, filename, CHANNEL)
    dev.write(':WAVEFORM:XINCREMENT?')
   # print 'x_increment:' + dev.read()
    dev.write(':WAVEFORM:XORIGIN?')
   # print 'x_origin:' + dev.read()
    dev.write(':WAVEFORM:YINCREMENT?')
   # print 'y_increment:' + dev.read()
    dev.write(':WAVEFORM:YORIGIN?')
   # print 'y_origin:' + dev.read()

    dev.close()

if __name__ == '__main__':
    main()
