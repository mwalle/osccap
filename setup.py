#!/usr/bin/env python

from setuptools import setup, find_packages

def main():
    setup(name = 'osccap',
            version = '0.1',
            description = 'Capture screenshot from digital oscilloscopes.',
            author_email = 'michael@walle.cc',
            options = {
                'bdist_wininst':
                    {'install_script': 'postinstall.py',
                    },
                'bdist_msi':
                    {'install_script': 'postinstall.py',
                    },
            },
            scripts = ['osccap.py', 'postinstall.py'],
            include_package_data = True,
    )

if __name__ == '__main__':
    main()
