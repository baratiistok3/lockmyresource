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
from tkinter import filedialog
from typing import List, Dict, Optional

from configfile import LockMyResourceConfigFile
from lockmyresource import User, no_user, Core, Database, Resource, LockRecord, traced
from tableformatter import JsonFormatter


class LockRecordLockCommand:
    def __init__(self, lock_record: LockRecord, refresh_command, get_lock_comment):
        self.lock_record = lock_record
        self.text = "Lock"
        self.refresh_command = refresh_command
        self.get_lock_comment = get_lock_comment


    def execute(self):
        success = self.lock_record.lock(self.get_lock_comment())
        resource = self.lock_record.resource.name
        message = f"Lock acquired on {resource}" if success else f"Couldn't lock {resource}"
        logging.debug(message)
        self.refresh_command(message)


class LockRecordReleaseCommand:
    def __init__(self, lock_record: LockRecord, refresh_command):
        self.lock_record = lock_record
        self.text = "Release"
        self.refresh_command = refresh_command
    
    def execute(self):
        success = self.lock_record.release()
        resource = self.lock_record.resource.name
        message = f"Lock released on {resource}" if success else f"Couldn't release {resource}"
        logging.debug(message)
        self.refresh_command(message)


class LockWidget(tk.Frame):
    def __init__(self, master, core: Core, refresh_command, get_lock_comment):
        super().__init__(master)
        self.core = core
        self.refresh_command = refresh_command
        self.get_lock_comment = get_lock_comment
        self.my_user = core.user.login
        self.cells = {}
        self.rows_count = 0
        column_heads = ["Resource", "User", "Locked at", "Comment", "Command"]
        for x, column_head in enumerate(column_heads):
            head = tk.Label(self, text=column_head)
            head.grid(row=0, column=x, sticky="NEWS")

    def update(self, locks: List[LockRecord]):
        for y in range(self.rows_count):
            for grid_cell in self.grid_slaves(row=1 + y):
                grid_cell.grid_forget()

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
                command = LockRecordLockCommand(row, self.refresh_command, self.get_lock_comment)
            
            if command is not None:
                self.set_cell(4, y, tk.Button(self, text=command.text, command=command.execute))

        self.rows_count = len(locks)

    def set_cell(self, x: int, y: int, cell: tk.BaseWidget):
        cell.grid(row=y, column=x, sticky="NEWS")


class Application(tk.Frame):
    def __init__(self, master, core: Core):
        super().__init__(master)
        self.core = core
        self.pack()

        self.locks_widget = LockWidget(self, self.core, self.refresh_command, self.get_lock_comment)
        self.locks_widget.pack(side=tk.TOP)

        self.text_panel = tk.Frame(self)
        self.text_panel.pack()

        self.lock_comment_label = tk.Label(self.text_panel, text="Lock comment ")
        self.lock_comment_label.grid(row=0, column=0, sticky="W")

        self.lock_comment = tk.Text(self.text_panel, state=tk.NORMAL, height=1)
        def ignore_enter(event):
            if event.keysym == "Return":
                return "break"

        self.lock_comment.bind("<Key>", ignore_enter)
        self.lock_comment.grid(row=0, column=1, sticky="NEWS")

        self.status_label = tk.Label(self.text_panel, text="Status ")
        self.status_label.grid(row=1, column=0, sticky="W")

        self.status = tk.Text(self.text_panel, state=tk.DISABLED, height=1)
        self.status.grid(row=1, column=1, sticky="NEWS")

        self.buttons = tk.Frame()
        self.buttons.pack()

        self.open_db = tk.Button(self.buttons, text="Open DB", command=self.open_db_command)
        self.open_db.pack(side=tk.LEFT)

        self.quit = tk.Button(self.buttons, text="Quit", command=self.master.destroy)
        self.quit.pack(side=tk.LEFT)

        self.refresh = tk.Button(self.buttons, text = "Refresh", command=self.refresh_command)
        self.refresh.pack(side=tk.LEFT)

        self.refresh_command("Table initialized")

    def refresh_command(self, message: Optional[str] = "List updated"):
        self.locks_widget.update(self.core.list())
        if message is not None:
            self.show_message(message)

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

    def get_lock_comment(self):
        return self.lock_comment.get("1.0", tk.END).strip()

    def open_db_command(self):
        dbfilename = filedialog.askopenfilename(
            parent=self,
            title="Choose DB file",
            initialdir=self.get_dbdir(),
            initialfile=self.get_dbfile(),
            filetypes=[(".DB file", "*.db")]
            )
        if not dbfilename:
            return
        self.core.set_dbfile(Path(dbfilename))
        self.refresh_command(f"Opened {dbfilename}")
        self.save_dbfile_config()

    def save_dbfile_config(self):
        configfile = LockMyResourceConfigFile()
        config = configfile.read_config()
        config.dbfile = str(self.core.database.dbfile)
        configfile.write_config(config)


    def get_dbdir(self) -> str:
        return str(self.core.database.dbfile.parent)
    
    def get_dbfile(self) -> str:
        return str(self.core.database.dbfile.name)


class ApplicationRefresher:
    def __init__(self, app: Application, root: tk.Tk, refresh_interval_millis: int):
        self.app = app
        self.root = root
        self.refresh_interval_millis = refresh_interval_millis
    
    def refresh(self):
        self.app.refresh_command(message=None)
        self.root.after(self.refresh_interval_millis, self.refresh)


def with_time(text: str) -> str:
    import datetime
    now = datetime.datetime.now().strftime("%H:%M:%S")
    return f"{now} {text}"
    

@traced
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


@traced
def init_db(default_path: str) -> Path:
    configfile = LockMyResourceConfigFile()
    config = configfile.read_config()
    if config.dbfile is None:
        config.dbfile = default_path
        configfile.write_config(config)
    return Path(config.dbfile)


def main():
    logging.basicConfig(level=logging.DEBUG)
    root = tk.Tk()
    user = init_user(root)
    logging.info("User: %s", user)
    root.title("Lock My Resource")
    dbfile = init_db("lockmyresource.db")
    core = Core(user, Database.open(dbfile), JsonFormatter())
    app = Application(root, core)
    refresher = ApplicationRefresher(app, root, 5000)
    root.after(500, refresher.refresh)
    app.mainloop()
    core.database.connection.close()


if __name__ == "__main__":
    main()
