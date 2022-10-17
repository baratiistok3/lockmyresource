import logging
import os
import sys

if sys.platform.startswith("win"):
    import ctypes


class UserInfo:
    @staticmethod
    def get_user_name():
        if sys.platform.startswith("win"):
            username = UserInfo.get_display_name()
            if username:
                return username
            logging.warning("Got an empty username from GetUserNameExW! %s", repr(username))
        return os.getlogin()

    if sys.platform.startswith("win"):
        @staticmethod
        def get_display_name():
            get_user_name_ex = ctypes.windll.secur32.GetUserNameExW
            name_display = 3

            size = ctypes.pointer(ctypes.c_ulong(0))
            get_user_name_ex(name_display, None, size)

            name_buffer = ctypes.create_unicode_buffer(size.contents.value)
            get_user_name_ex(name_display, name_buffer, size)
            return name_buffer.value
