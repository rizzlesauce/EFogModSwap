import os

from pathHelpers import normPath
from windowsHelpers import checkTaskRunning, killTask

# TODO: provide file content to install this batch file into the game folder
DefaultLauncherRelPath = '4.4.2 Launcher.bat'
DefaultGameProgramName = 'DeadByDaylight-Win64-Shipping.exe'
DefaultGameServerProgramName = 'Server.exe'

def checkTaskRunning(programName):
    charLimitForFind = 25
    nameForFind = programName if len(programName) <= charLimitForFind else programName[:charLimitForFind]
    return os.system(f'tasklist /fi "imagename eq {programName}" 2>nul | find /i /n "{nameForFind}" >nul') == 0

def killTask(programName):
    return os.system(f'taskkill /f /t /im "{programName}"')


def getGamePaksDir(gameDir, gameName):
    return normPath(os.path.join(gameDir, gameName, 'Content', 'Paks'))


def openGameLauncher(gameDir, startGame=False):
    launcherPath = normPath(os.path.join(gameDir, DefaultLauncherRelPath))
    return os.system(f'cd "{gameDir}" && "{launcherPath}"{" launch" if startGame else ""}')


def getGameServerIsRunning():
    return checkTaskRunning(DefaultGameServerProgramName)


def getGameIsRunning():
    return checkTaskRunning(DefaultGameProgramName)


def killGame(killServer=False):
    # TODO: also be able to kill lobby?
    targets = [DefaultGameProgramName]
    if killServer:
        targets.append(DefaultGameServerProgramName)

    return [killTask(programName) for programName in targets]
