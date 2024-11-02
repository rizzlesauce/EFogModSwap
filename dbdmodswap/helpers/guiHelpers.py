import tkinter as tk
from contextlib import contextmanager
from tkinter import filedialog

import win32con
import win32gui


def getForegroundWindow():
    return win32gui.GetForegroundWindow()


def setWindowFocus(hwnd):
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(hwnd)


@contextmanager
def restoreWindowFocus():
    hwnd = win32gui.GetForegroundWindow()
    try:
        yield hwnd
    finally:
        setWindowFocus(hwnd)


def newTkWindow(hide=True):
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    return root


@contextmanager
def tkWindow(hide=True):
    root = newTkWindow(hide)
    try:
        yield root
    finally:
        root.destroy()


def getDirectory(
    title=None,
    initialDir=None,
    mustExist=None,
):
    with restoreWindowFocus():
        with tkWindow():
            filePath = filedialog.askdirectory(
                title=title,
                initialdir=initialDir,
                mustexist=mustExist,
            )
            return filePath


def getFile(
    title=None,
    initialDir=None,
    initialFile=None,
    defaultExtension=None,
    fileTypes=None,
    mustExist=None,
):
    with restoreWindowFocus():
        with tkWindow():
            if mustExist:
                filePath = filedialog.askopenfilename(
                    title=title,
                    initialdir=initialDir,
                    initialfile=initialFile,
                    defaultextension=defaultExtension,
                    filetypes=fileTypes,
                )
            else:
                filePath = filedialog.asksaveasfilename(
                    confirmoverwrite=False,
                    title=title,
                    initialdir=initialDir,
                    initialfile=initialFile,
                    defaultextension=defaultExtension,
                    filetypes=fileTypes,
                )
            return filePath
