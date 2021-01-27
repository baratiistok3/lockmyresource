#!/usr/bin/env python3

import json
import logging
import os
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import simpledialog
from typing import List, Dict

from configfile import LockMyResourceConfigFile
from lockmyresource import User, no_user, Core, Database
from tableformatter import JsonFormatter


class LockWidget(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.cells = {}
        self.rows_count = 0

    def update(self, data: List[Dict]):
        columns = "resource user locked_at comment".split()

        to_remove = [(x, y) for (x, y) in self.cells.keys() if y > len(data)]
        for xy in to_remove:
            self.cells[xy].grid_forget()
            del self.cells[xy]

        for y, row in enumerate(data):
            for x, column in enumerate(columns):
                cell = tk.Label(self, text=str(row[column]), relief=tk.RIDGE)
                cell.grid(row=y, column=x, sticky="NEWS")
                self.cells[(x, y)] = cell
        
        self.rows_count = len(data)


class Application(tk.Frame):
    def __init__(self, master, core: Core):
        super().__init__(master)
        self.core = core
        self.pack()

        self.locks_widget = LockWidget(self)
        self.locks_widget.pack(side=tk.TOP)

        self.status = tk.Text(self, state=tk.DISABLED, height=1)
        self.status.pack()

        self.buttons = tk.Frame()
        self.buttons.pack()

        self.quit = tk.Button(self.buttons, text="Quit", command=self.master.destroy)
        self.quit.pack(side=tk.LEFT)

        self.refresh = tk.Button(self.buttons, text = "Refresh", command=self.refresh_command)
        self.refresh.pack(side=tk.LEFT)

        self.refresh_command()

    def refresh_command(self):
        self.locks_widget.update(self.core.list_raw())
        self.show_message("List updated")

    def show_message(self, message):
        if isinstance(message, list):
            self.status.height = len(message)
            message = "\n".join(message)
        else:
            self.status.height = 1

        message = with_time(message)
        self.status.configure(state=tk.NORMAL)
        self.status.delete("1.0", tk.END)
        self.status.insert(tk.END, message)
        self.status.configure(state = tk.DISABLED)


def with_time(text: str) -> str:
    import datetime
    now = datetime.datetime.now().strftime("%H:%M:%S")
    return f"{now} {text}"
    

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
    # TODO: dbfile needs to be configurable
    dbfile = Path("lockmyresource.db")
    connection = sqlite3.connect(str(dbfile), isolation_level=None)
    core = Core(user, Database(connection, dbfile), JsonFormatter())
    app = Application(root, core)
    app.mainloop()
    connection.close()


if __name__ == "__main__":
    main()
