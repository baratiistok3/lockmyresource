#!/usr/bin/env python3

import datetime
import json
import logging
import os
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import simpledialog
from typing import List, Dict

from configfile import LockMyResourceConfigFile
from lockmyresource import User, no_user, Core, Database, Resource, LockRecord
from tableformatter import JsonFormatter


class LockRecordLockCommand:
    def __init__(self, lock_record: LockRecord, refresh_command):
        self.lock_record = lock_record
        self.text = "Lock"
        self.refresh_command = refresh_command

    def execute(self):
        self.lock_record.lock("no comment yet")
        self.refresh_command()


class LockRecordReleaseCommand:
    def __init__(self, lock_record: LockRecord, refresh_command):
        self.lock_record = lock_record
        self.text = "Release"
        self.refresh_command = refresh_command
    
    def execute(self):
        self.lock_record.release()
        self.refresh_command()


class LockWidget(tk.Frame):
    def __init__(self, master, core: Core, refresh_command):
        super().__init__(master)
        self.core = core
        self.refresh_command = refresh_command
        self.my_user = core.user.login
        self.cells = {}
        self.rows_count = 0
        column_heads = ["Resource", "User", "Locked at", "Comment", "Command"]
        for x, column_head in enumerate(column_heads):
            head = tk.Label(self, text=column_head)
            head.grid(row=0, column=x, sticky="NEWS")

    def update(self, locks: List[LockRecord]):
        to_remove = [(x, y) for (x, y) in self.cells.keys() if y > len(locks)]
        for xy in to_remove:
            self.cells[xy].grid_forget()
            del self.cells[xy]

        for y, row in enumerate(locks):
            y += 1
            self.set_cell(0, y, tk.Label(self, text=row.resource.name, relief=tk.RIDGE))
            self.set_cell(1, y, tk.Label(self, text=row.user.login, relief=tk.RIDGE))
            self.set_cell(2, y, tk.Label(self, text=row.locked_at, relief=tk.RIDGE))
            self.set_cell(3, y, tk.Label(self, text=row.comment, relief=tk.RIDGE))

            command = None
            if row.user == self.core.user:
                command = LockRecordReleaseCommand(row, self.refresh_command)
            elif row.user == no_user:
                command = LockRecordLockCommand(row, self.refresh_command)
            
            if command is not None:
                self.set_cell(4, y, tk.Button(self, text=command.text, command=command.execute))

        self.rows_count = len(locks)

    def set_cell(self, x: int, y: int, cell: tk.BaseWidget):
        cell.grid(row=y, column=x, sticky="NEWS")
        self.cells[(x, y)] = cell


class Application(tk.Frame):
    def __init__(self, master, core: Core):
        super().__init__(master)
        self.core = core
        self.pack()

        self.locks_widget = LockWidget(self, self.core, self.refresh_command)
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
        self.locks_widget.update(self.core.list())
        self.show_message("List updated")

    def show_message(self, message):
        if isinstance(message, list):
            self.status.height = len(message)
            message = "\n".join(message)
        else:
            self.status.height = 1

        message = with_time(message)
        logging.info(message)
        self.status.configure(state=tk.NORMAL)
        self.status.delete("1.0", tk.END)
        self.status.insert(tk.END, message)
        self.status.configure(state = tk.DISABLED)


class ApplicationRefresher:
    def __init__(self, app: Application, root: tk.Tk, refresh_interval_millis: int):
        self.app = app
        self.root = root
        self.refresh_interval_millis = refresh_interval_millis
    
    def refresh(self):
        self.app.refresh_command()
        self.root.after(self.refresh_interval_millis, self.refresh)


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
    refresher = ApplicationRefresher(app, root, 5000)
    root.after(500, refresher.refresh)
    app.mainloop()
    connection.close()


if __name__ == "__main__":
    main()
