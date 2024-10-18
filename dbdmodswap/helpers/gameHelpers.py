import os
import shutil

from dbdmodswap.metadata.programMetaData import ProgramName

from .pathHelpers import normPath
from .tempFileHelpers import openTemporaryFile
from .windowsHelpers import checkTaskRunning, killTask

DefaultLauncherRelPath = '4.4.2 Launcher.bat'
DefaultGameName = 'DeadByDaylight'
DefaultGameBinariesRelDir = os.path.join(DefaultGameName, 'Binaries', 'Win64')
DefaultGameProgramName = f'{DefaultGameName}-Win64-Shipping.exe'
DefaultGameServerProgramName = 'Server.exe'

def getCheckTaskRunningCommand(programName):
    charLimitForFind = 25
    nameForFind = programName if len(programName) <= charLimitForFind else programName[:charLimitForFind]
    return f'tasklist /fi "imagename eq {programName}" 2>nul | find /i /n "{nameForFind}" >nul'


def checkTaskRunning(programName):
    return os.system(getCheckTaskRunningCommand(programName)) == 0


def killTask(programName):
    return os.system(f'taskkill /f /t /im "{programName}"')


def getGamePaksDir(gameDir, gameName):
    return normPath(os.path.join(gameDir, gameName, 'Content', 'Paks'))


def openGameLauncher(gameDir, startGame=False, usingExternalLauncher=False, fromMenu=False):
    def runLauncherBatchScript(launcherPath):
        assert launcherPath
        return os.system(f'cd "{gameDir}" && "{launcherPath}"{" launch" if startGame else ""}')

    if usingExternalLauncher:
        return runLauncherBatchScript(os.path.join(gameDir, DefaultLauncherRelPath))

    with openTemporaryFile(dir=gameDir, prefix=f'{ProgramName}_Launcher_', suffix='.bat', mode='w') as file:
        # TODO: remove
        if False:
            print(getLauncherBatchFileContent())
        else:
            file.write(getLauncherBatchFileContent(usingStandaloneExitOption=not fromMenu or None))
            file.close()
            return runLauncherBatchScript(file.name)


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


def getLauncherBatchFileContent(usingStandaloneExitOption=None, usingOriginalBehavior=False):
    cols, rows = shutil.get_terminal_size()

    if usingStandaloneExitOption is None:
        usingStandaloneExitOption = usingOriginalBehavior or False

    usingOriginalCls = usingOriginalBehavior
    usingOriginalPause = usingOriginalBehavior
    usingPageClearCls = False

    def formatLines(lines, indent=0):
        return '\n'.join([f"{'    ' * indent}{line}" for line in lines if line])

    def clearScreen(indent=0, soft=False, active=True, long=False, linesOnly=False):
        clsPart = 'cls'

        if clsPart and not usingOriginalCls:
            clsPart = f'REM {clsPart}'

        if usingOriginalCls:
            return formatLines([
                clsPart,
            ], indent)

        if soft or not usingPageClearCls:
            lines = [
                'echo.',
                (
                    'echo ------------------------------------------------------'
                ) if long or not soft else (
                    'echo --------------------------------'
                ),
                'echo.',
            ]
        else:
            lines = [
                f'for /L %%n in (1,1,{rows}) do echo.',
            ]

        if not active:
            lines = [f'REM {line}' for line in lines]

        lines.append(clsPart)

        if linesOnly:
            return lines

        return formatLines(lines, indent)


    def pause(indent=0, wait=False, invalidInput=False, active=True, linesOnly=False):
        waitPart = 'timeout /t 3 /nobreak >nul' if wait else ''
        pausePart = 'pause'
        pausing = True

        if waitPart and not usingOriginalPause:
            waitPart = f'REM {waitPart}'

        if pausePart and (not active or (not usingOriginalPause and not invalidInput)):
            pausePart = f'REM {pausePart}'
            pausing = False

        lines = [
            waitPart,
            *((['echo.'] if True else clearScreen(soft=True, linesOnly=True)) if pausing else []),
            pausePart,
        ]

        if linesOnly:
            return lines

        return formatLines(lines, indent)

    def actionIf(action, inputMatches, indent=0):
        lines = []
        for inputMatch in inputMatches:
            lines.append(f'if /I %op%=={inputMatch} {action}')
            if usingOriginalBehavior:
                # use only the first item (the menu number)
                break

        return formatLines(lines, indent)

    return (
f'''@echo off
setlocal enabledelayedexpansion
title 4.4.2 Launcher - By Smirkzyy and Merky and Ross
cd /d "{DefaultGameBinariesRelDir}\\"
set "originalDir=%cd%"
set prevContent=0
set launchNow=0
if "%1"=="launch" set launchNow=1

{clearScreen(active=False)}

if %launchNow%==1 (
{clearScreen(indent=1)}
    echo Launcher
    set prevContent=1
    set launchNow=0
    goto :launch
)

:main
if %prevContent%==1 (
{clearScreen(soft=True, active=False, indent=1)}
)
set prevContent=1
{clearScreen()}
echo Launcher Main Menu
echo.
echo [1] Launch 4.4.2
echo [2] Join Public Lobby (Survivors Only)
echo [3] Custom Lobby
echo.
echo -------------[MISC]-------------
echo.
echo [4] Open Paks Folder
echo [5] Open Win64 Folder
echo [6] Open Config Folder
echo [7] {"Exit" if usingStandaloneExitOption else f"Exit (back to {ProgramName})"}
echo.
set /p op="Selection: "
{actionIf("goto :launch", ['1', 'launch', 'launc', 'laun', 'lau', 'la', 'l', 'lnch', 'ln', 'lnc'])}
{actionIf("goto :join", ['2', 'j', 'pubs', 'pub', 'join', 'joi', 'jo', 'jn', 'lobby'])}
{actionIf("goto :customLobby", ['3', 'cust', 'custs', 'customs', 'custom lobby', 'customLobby', 'custom'])}
{actionIf("goto :openPaks", ['4', 'pak', 'pk', 'pks', 'paks', 'openPaks', 'open paks'])}
{actionIf("goto :openWin64", ['5', 'openWin64', 'win', 'win64', 'open win64'])}
{actionIf("goto :openConfig", ['6', 'openConfig', 'open config', 'config', 'conf'])}
{actionIf("exit", ['7',
    *[
        *(['x', 'ex', 'xi', 'exi', 'exit'] if usingStandaloneExitOption or True else []),
        *(['q', 'quit', 'qu', 'qui'] if not usingStandaloneExitOption or True else []),
        *(['b', 'ba', 'bak', 'bac', 'back', 'bk'] if not usingStandaloneExitOption else []),
        *(['ret', 'return'] if not usingStandaloneExitOption or True else []),
    ],
])}
echo.
{clearScreen(active=False)}
echo Invalid option, Please try again.
{pause(invalidInput=True)}
goto :main


:launch
{clearScreen(soft=True)}
echo Checking server status...
{getCheckTaskRunningCommand(DefaultGameServerProgramName)}

if "%errorlevel%"=="0" (
    echo Already running.
    goto :launchdbd
)

echo Starting server...
start "Server" "Server.exe"
timeout /t 3 /nobreak >nul
goto :launchdbd


:launchdbd
{clearScreen(soft=True)}
echo Checking game status...
{getCheckTaskRunningCommand(DefaultGameProgramName)}

if "%errorlevel%"=="0" (
    echo Already running.
{pause(invalidInput=True, indent=1)}
    goto :main
)

echo Launching Dead by Daylight...
start "Game" "DeadByDaylight-Win64-Shipping.exe" -DX12
{pause(wait=True)}
goto :main


:join
{clearScreen(soft=True)}
echo Checking lobby status...
{getCheckTaskRunningCommand("steam_lobby.exe")}

if "%errorlevel%"=="0" (
    echo Already running.
{pause(invalidInput=True, indent=1)}
    goto :main
)

echo Starting 4.4.2 lobby...
echo (UAC prompt may open)
start "Lobby" "steam_lobby.exe"
{pause(wait=True)}
goto :main


:openPaks
{clearScreen(soft=True)}
echo Opening Paks folder...
set "paksPath=%~dp0DeadByDaylight\Content\Paks"
start "" "%paksPath%"
{pause(wait=True)}
goto :main


:openWin64
{clearScreen(soft=True)}
echo Opening Win64 folder...
set "win64path=%~dp0DeadByDaylight\Binaries\Win64"
start "" "%win64path%"
{pause(wait=True)}
goto :main


:openConfig
{clearScreen(active=False)}
set "configPath=%localappdata%\DeadByDaylight\Saved\Config\WindowsNoEditor"

IF EXIST "%configPath%" (
{clearScreen(soft=True, indent=1)}
    echo Opening Config folder...
    start "" "%configPath%"
{pause(wait=True, indent=1)}
) else (
    echo.
{clearScreen(active=False, indent=1)}
    echo ERROR: Config folder does not exist. Please launch 4.4.2 at least once to create it.
{pause(invalidInput=True, wait=True, indent=1)}
)
goto :main


:customLobby
{clearScreen()}
echo Are you playing as Killer or Survivor?
echo.
echo [1] Killer
echo [2] Survivor
echo [3] Return
echo.
set /p op1="Selection: "
if %op1%==1 goto :killer
if %op1%==2 goto :survivor
if %op1%==3 goto :main
echo.
{clearScreen(active=False)}
echo Invalid option. Please try again.
{pause(invalidInput=True)}
goto :customLobby


:killer
{clearScreen()}
echo Make sure your Profile and Game Details privacy setting on Steam are set to "Public", and that you're Online.
echo.
echo [1] Create Lobby
echo [2] Open Steam Privacy Settings
echo [3] Return
echo.
set /p op2="Selection: "
if %op2%==1 goto :killer2
if %op2%==2 goto :steamPrivacySettings
if %op2%==3 goto :customLobby


:killer2
{clearScreen()}
echo How many survivors do you want to join your lobby? (minimum 1, maximum 4, 0 to go back)
echo.
set /p setSurv="Your choice: "
if %setSurv%==0 goto :killer

for /f %%a in ("!setSurv!") do (
    set "validNumber=%%a"
    set "validNumber=!validNumber:~0,1!"
)

if "!validNumber!" lss "1" (
    echo.
    echo Invalid option. Please try again.
{pause(invalidInput=True, indent=1)}
    goto killer2
)

if "!validNumber!" gtr "4" (
    echo.
    echo Invalid option. Please try again.
{pause(invalidInput=True, indent=1)}
    goto killer2
)

{clearScreen(active=False)}
echo Checking lobby status...
{getCheckTaskRunningCommand("steam_lobby.exe")}

if "%errorlevel%"=="0" (
    echo Already running.
{pause(invalidInput=True, indent=1)}
    goto :killer2
)

echo Creating custom lobby...
echo (UAC prompt may open)
start "Lobby" "steam_lobby.exe" %setSurv%
{pause(wait=True)}
goto :customLobby


:survivor
{clearScreen()}
echo Choose your connection method. If GrabSteamURL doesn't work then use the DirectURL connection method.
echo.
echo [1] GrabSteamURL Connect
echo [2] DirectURL Connect
echo [3] Return
echo.
set /p op3="Selection: "
if %op3%==1 goto :GrabSteamURL
if %op3%==2 goto :DirectConnect
if %op3%==3 goto :customLobby
echo.
echo Invalid option. Please try again.
{pause(invalidInput=True)}
goto :survivor


:GrabSteamURL
{clearScreen(active=False)}
cd /d GrabSteamURL/bin/
java -cp "GrabSteamURL4Launcher.jar;jsoup-1.17.1.jar" GrabSteamURL2 "%~dp0DeadByDaylight\\Binaries\\Win64\\steam_lobby.exe"
cd /d "%originalDir%"
{pause(wait=True)}
goto :customLobby


:DirectConnect
{clearScreen()}
echo Paste the killers Join Lobby URL below (not their profile link). Type "return" to go back.
echo.
set /p steamLink="Paste link here: "
if %steamLink%==return goto :survivor
{clearScreen(soft=True)}
echo Checking lobby status...
{getCheckTaskRunningCommand("steam_lobby.exe")}

if "%errorlevel%"=="0" (
    echo Already running.
{pause(invalidInput=True, indent=1)}
    goto :DirectConnect
)

echo Joining custom lobby...
echo (UAC prompt may open)
start "Lobby" "steam_lobby.exe" %steamLink%
{pause(wait=True)}
goto :customLobby


:steamPrivacySettings
{clearScreen(soft=True)}
echo Opening Steam privacy settings in default browser...
start "" https://www.steamcommunity.com/id/eroticgaben/edit/settings
{pause(wait=True)}
goto :killer'''
    )
