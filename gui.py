#!/usr/bin/env python3

import json
import logging
import os
import tkinter as tk
from tkinter import simpledialog
from pathlib import Path
from lockmyresource import User, no_user


class Application(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.pack()
        self.create_widgets()

    def create_widgets(self):
        self.quit = tk.Button(self, text="Quit", command=self.master.destroy)
        self.quit.pack(side=tk.BOTTOM)


def get_configfile() -> Path:
    userdir = os.getenv("APPDATA", None)
    filename = "lockmyresource.json"
    if userdir is None:
        userdir = os.getenv("HOME", None)
        filename = ".lockmyresource.json"
    if userdir is None:
        raise FileNotFoundError("Could not determine user directory")
    configfile = Path(userdir, filename)
    return configfile

def read_config(configfile: Path) -> str:
    if configfile.exists() is False:
        return {}
    return json.loads(configfile.read_text(encoding="utf-8"))

def init_user(root) -> User:
    user = User.from_os()
    if user != no_user:
        return user
    configfile = get_configfile()
    config = read_config(configfile)
    if "user" in config:
        return User(config["user"])
    username = simpledialog.askstring("User", "Enter username:", parent=root)
    config["user"] = username
    configfile.write_text(json.dumps(config), encoding="utf-8")
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
