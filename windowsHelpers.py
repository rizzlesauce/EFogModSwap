import os
import webbrowser
import winreg


def getWindowsDefaultEditor():
    """Gets the default editor for Windows."""

    try:
        # Try to get the editor from the environment variable
        editor = os.environ['EDITOR']
    except KeyError:
        # If the environment variable is not set, try to get the default editor from the registry
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Applets\\Notepad\\Execute") as key:
                editor = winreg.QueryValueEx(key, "")[0]
        except FileNotFoundError:
            # If the registry key is not found, return Notepad as the default editor
            editor = "notepad.exe"

    return editor


def checkTaskRunning(programName):
    charLimitForFind = 25
    nameForFind = programName if len(programName) <= charLimitForFind else programName[:charLimitForFind]
    return os.system(f'tasklist /fi "imagename eq {programName}" 2>nul | find /i /n "{nameForFind}" >nul') == 0


def killTask(programName):
    return os.system(f'taskkill /f /t /im "{programName}"')


def pressAnyKeyToContinue():
    os.system('pause')


def openFolder(dirPath):
    os.system(f'start "" "{dirPath}"')


def openFile(filePath):
    success = False

    testingFailWebbrowser = False
    testingFailStartfile = False
    testingFailEditor = False

    try:
        if testingFailWebbrowser:
            raise ValueError('webbrowser failed to run')
        webbrowser.open(filePath)
        success = True
    except Exception as e:
        if False:
            print(e)
        try:
            if testingFailStartfile:
                raise ValueError('startfile failed to run')
            os.startfile(filePath)
            success = True
        except Exception as e2:
            if False:
                print(e2)
            try:
                editor = getWindowsDefaultEditor()
                if testingFailEditor:
                    raise ValueError('editor failed to run')
                os.system(f'start "{editor}" "{filePath}"')
                success = True
            except Exception as e3:
                if False:
                    print(e3)

    return success
