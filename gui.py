#!/usr/bin/env python3

import json
import logging
import os
import tkinter as tk
from tkinter import simpledialog
from pathlib import Path
from configfile import LockMyResourceConfigFile
from lockmyresource import User, no_user


class Application(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.pack()
        self.create_widgets()

    def create_widgets(self):
        self.quit = tk.Button(self, text="Quit", command=self.master.destroy)
        self.quit.pack(side=tk.BOTTOM)


def init_user(root) -> User:
    user = User.from_os()
    if user != no_user:
        return user
    configfile = LockMyResourceConfigFile()
    config = configfile.read_config()
    if config.user is not None:
        return User(config.user)
    username = simpledialog.askstring("User", "Enter username:", parent=root)
    config.user = username
    configfile.write_config(config)
    return User(username)


def main():
    logging.basicConfig(level=logging.DEBUG)
    root = tk.Tk()
    user = init_user(root)
    logging.info("User: %s", user)
    root.title("Lock My Resource")
    app = Application(root)
    app.mainloop()


if __name__ == "__main__":
    main()
