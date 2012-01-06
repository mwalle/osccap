#!/usr/bin/env python

from setuptools import setup, find_packages

def main():
    setup(name = 'osccap',
            version = '0.3',
            description = 'Capture screenshot from digital oscilloscopes.',
            author_email = 'michael@walle.cc',
            options = {
                'bdist_wininst':
                    {'install_script': 'osccap_postinstall.py',
                    },
                'bdist_msi':
                    {'install_script': 'osccap_postinstall.py',
                    },
            },
            packages = find_packages(),
            package_data = {'osccap': ['data/*.png', 'data/osccap.ico']},
            #scripts = ['osccap.py', 'osccap_postinstall.py'],
            scripts = ['osccap_postinstall.py'],
    )

if __name__ == '__main__':
    main()
