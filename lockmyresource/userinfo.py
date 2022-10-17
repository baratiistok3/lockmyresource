import abc
import ctypes
import logging
import os
import sys


class UserInfo(abc.ABC):
    @abc.abstractmethod
    def get_user_name(self) -> str:
        pass


class LoginNameUserInfo(UserInfo):
    def get_user_name(self) -> str:
        return os.getlogin()


class WindowsDisplayNameUserInfo(UserInfo):
    def __init__(self, fallback_userinfo: UserInfo):
        self.fallback = fallback_userinfo

    def get_user_name(self) -> str:
        username = self.get_display_name()
        if username:
            return username

        logging.warning("Got an empty username from GetUserNameExW! %s", repr(username))
        return self.fallback.get_user_name()

    @staticmethod
    def get_display_name() -> str:
        get_user_name_ex = ctypes.windll.secur32.GetUserNameExW
        name_display = 3

        size = ctypes.pointer(ctypes.c_ulong(0))
        get_user_name_ex(name_display, None, size)

        name_buffer = ctypes.create_unicode_buffer(size.contents.value)
        get_user_name_ex(name_display, name_buffer, size)
        return name_buffer.value


def get_userinfo() -> UserInfo:
    loginname_userinfo = LoginNameUserInfo()
    if sys.platform.startswith("win"):
        return WindowsDisplayNameUserInfo(loginname_userinfo)
    return loginname_userinfo
