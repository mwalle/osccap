![osccap](osccap/data/osccap-64.png)

# OscCap
OscCap is a small utility to capture screenshots from various
digial oscilloscopes. Screenshots can either be copied to the
clipboard or saved to a file.

## Supported Oscilloscopes

* Keysight Technologies DSOX91604A
* Tektronix TDS5104
* Tektronix TDS7704
* Tektronix MSO58
* Tektronix MSO56
* Tektronix MSO58
* Tektronix MSO64


## Configuration

### Window

The configuration is stored in the windows registry:

First the key in `HKEY_LOCAL_MACHINE` is checked:

```
HKEY_LOCAL_MACHINE
               `- SOFTWARE
                      `- OscCap
                            |`- Scopes
                            |      `- <name>
                            |            `- <host>
                            `- HotKeyModifiers
```


Second the key in `HKEY_CURRENT_USERA` is checked:

```
    HKEY_CURRENT_USER
                   `- SOFTWARE
                          `- OscCap
                                `- HotKeyModifiers
                                `- LastActiveName
```



### Linux

The configuration is stored in an ini style file at `~/.osccaprc`:

```
    [global]
    last_active_name = <name>
    
    [scope_<name>]
    host=192.168.0.1
```
