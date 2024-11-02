import pprint
import shutil
import sys
from contextlib import contextmanager

from .windowsHelpers import pressAnyKeyToContinue

consoleWindow = None

hasPriorPrintSection = False
needsNewPrintSection = 0
sprintPads = 0

sprintRecording = None

def getConsoleWindow():
    return consoleWindow


def setConsoleWindow(hwnd):
    global consoleWindow
    consoleWindow = hwnd


def getSprintIsRecording():
    return sprintRecording is not None


def startSprintRecording():
    global sprintRecording
    sprintRecording = []


def recordSprint(func):
    # TODO: establish a reasonable array max length to avoid running out of memory
    if sprintRecording is not None:
        sprintRecording.append(func)


def recordAndRunSprint(func):
    try:
        result = func()
        recordSprint(func)
        return result
    except:
        raise


def replaySprintRecording():
    if sprintRecording is not None:
        for func in sprintRecording:
            func()


def clearSprintRecording():
    global sprintRecording
    sprintRecording = None


def eprint(*args, **kwargs):
    recordAndRunSprint(lambda: print(*args, file=sys.stderr, **kwargs))


def sprintApply():
    global needsNewPrintSection
    global sprintPads
    if needsNewPrintSection > 0:
        for i in range(needsNewPrintSection):
            if sprintPads > 0:
                sprintPads -= 1
            else:
                recordAndRunSprint(lambda: print())
    sprintPads = 0
    needsNewPrintSection = 0


def sprintPad(level=1):
    global needsNewPrintSection
    if hasPriorPrintSection:
        needsNewPrintSection = max(level, needsNewPrintSection)


def sprintSeparator(size=3):
    global sprintPads
    halfIndex = size // 2
    for i in range(size):
        if i == halfIndex:
            recordAndRunSprint(lambda: print('--------------------------------'))
        else:
            recordAndRunSprint(lambda: print())
    sprintPads += size


def sprint(*args, **kwargs):
    global hasPriorPrintSection
    sprintApply()
    result = recordAndRunSprint(lambda: print(*args, **kwargs))
    hasPriorPrintSection = True
    return result


def sprintP(*args, **kwargs):
    global hasPriorPrintSection
    sprintApply()
    result = recordAndRunSprint(lambda: pprint.pp(*args, **kwargs))
    hasPriorPrintSection = True
    return result


def sprintput(*args, **kwargs):
    global hasPriorPrintSection
    sprintApply()
    result = input(*args, **kwargs)
    def func():
        print(*args, **kwargs, end='')
        print(result)
    recordSprint(func)
    hasPriorPrintSection = True
    return result


def sprintClear():
    global hasPriorPrintSection
    global needsNewPrintSection
    global sprintPads
    cols, rows = shutil.get_terminal_size()
    print('\n' * (rows - 1))
    hasPriorPrintSection = False
    needsNewPrintSection = False
    sprintPads = 0


def esprint(*args, **kwargs):
    global hasPriorPrintSection
    sprintApply()
    result = recordAndRunSprint(lambda: eprint(*args, **kwargs))
    hasPriorPrintSection = True
    return result


@contextmanager
def oneLinePrinter():
    calledPrint = False

    def myPrint(message):
        nonlocal calledPrint
        sprint(message, end='')
        calledPrint = True
    try:
        yield myPrint
    finally:
        # end the line
        if calledPrint:
            sprint('')


def promptToContinue(purpose='to continue...', pad=True):
    if pad:
        sprintPad()
    # TODO: remove
    if False:
        result = sprintput(f'Press Enter {purpose}')
    else:
        pressAnyKeyToContinue()
    if pad:
        sprintPad()


def confirm(action, emptyMeansNo=None, pad=False, prefix=None):
    if pad:
        sprintPad()
    while True:
        result = sprintput(f'{prefix or ""}{action[0].upper()}{action[1:]} ({"Y" if emptyMeansNo is False else "y"}/{"N" if emptyMeansNo else "n"})? ').strip()
        if result.upper() == 'Y' or (not result and emptyMeansNo is False):
            confirmed = True
            break

        if result.upper() == 'N' or (not result and emptyMeansNo is True):
            confirmed = False
            break

    if pad:
        sprintPad()

    return confirmed


def confirmOverwrite(target, pad=True, prefix=None, emptyMeansNo=None):
    return confirm(f'overwrite "{target}"', emptyMeansNo=emptyMeansNo, pad=pad, prefix=prefix)
