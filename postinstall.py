import sys
import osccap

def install():
    try:
        # try common programs first, requires admin rights
        folder = get_special_folder_path('CSIDL_COMMON_PROGRAMS')
    except OSError:
        # otherwise, continue with user folder
        folder = get_special_folder_path('CSIDL_PROGRAMS')

    dst = os.path.join(folder, 'osccap.lnk')
    create_shortcut(
            os.path.join(sys.prefix, 'pythonw.exe'),
            'OscCap',
            dst,
            osccap.__file__,
            '',
    )

    file_created(dst)

if __name__ == '__main__':
    if len(sys.args) == 2 and sys.args[1] == '-install':
        install()
