
pyhton-vxi11
============

Supported Scopes
----------------

* Keysight Technologies DSOX91604A
* Tektronix TDS5104
* Tektronix TDS7704
* Tektronix MSO64


Configuration
-------------

Window
''''''

The configuration is stored in the windows registry:

First the key in `HKEY_LOCAL_MACHINE` is checked:

.. code:: shell

    HKEY_LOCAL_MACHINE
                   `- SOFTWARE
                          `- OscCap
                                |`- Scopes
                                |      `- <name>
                                |            `- <host>
                                `- HotKeyModifiers

Second the key in `HKEY_CURRENT_USERA` is checked:

.. code:: shell

    HKEY_CURRENT_USER
                   `- SOFTWARE
                          `- OscCap
                                `- HotKeyModifiers
                                `- LastActiveName



Linux
'''''

The configuration is stored in a ini style file at `~/.osccaprc`

.. code:: shell

    [global]
    last_active_name = <name>
    
    [scope_<name>]
    host=192.168.0.1
