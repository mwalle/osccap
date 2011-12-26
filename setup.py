#!/usr/bin/env python

from setuptools import setup, find_packages

def main():
    setup(name = 'osccap',
            version = '0.1',
            description = 'Capture screenshot from digital oscilloscopes.',
            author_email = 'michael@walle.cc',
            scripts = ['osccap.py'],
            include_package_data = True,
    )

if __name__ == '__main__':
    main()
