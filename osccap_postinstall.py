import sys
import os
import osccap

def install():
    try:
        # try common programs first, requires admin rights
        folder = get_special_folder_path('CSIDL_COMMON_PROGRAMS')
    except OSError:
        # otherwise, continue with user folder
        folder = get_special_folder_path('CSIDL_PROGRAMS')

    print ("Creating shortcut..")
    dst = os.path.join(folder, 'osccap.lnk')
    icon = os.path.join(os.path.dirname(osccap.__file__), 'data', 'osccap.ico')
    create_shortcut(
            os.path.join(sys.prefix, 'pythonw.exe'),
            'OscCap',
            dst,
            '-m osccap.main',
            '',
            icon,
    )
    file_created(dst)
    print ("done")


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '-install':
        install()
