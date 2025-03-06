import os
import shutil

import semver

from modswap.metadata.programMetaData import ProgramName

from .pathHelpers import normPath
from .tempFileHelpers import openTemporaryFile
from .windowsHelpers import (checkTaskRunning, getCheckTaskRunningCommand,
                             getPowershellCommand, getStartCommand,
                             getTaskKillCommand, taskKill)

DefaultGameName = 'DeadByDaylight'
DefaultGameVersion = '6.5.2'
DefaultPrevGameVersion = '6.5.2'
KnownSupportedGameVersions = [
    '4.4.2',
    '6.5.2',
    '6.7.0',
    '6.7.2',
]
DefaultLauncherRelPath = '4.4.2 Launcher.bat'
DefaultGameServerProgramName = 'Server.exe'
DefaultGameLobbyProgramName = 'steam_lobby.exe'


def getGameUnrealEngineVersion(gameVersion):
    gameVersionSemver = semver.VersionInfo.parse(gameVersion)
    if gameVersionSemver.match('4.4.2'):
        return '4.25'

    if gameVersionSemver.match('>=6.5.2') and gameVersionSemver.match('<=6.7.2'):
        return '4.27'


def getDefaultGameProgramName(gameName):
    return f'{gameName}-Win64-Shipping.exe'


def getGameBinariesRelDir(gameName):
    return os.path.join(gameName, 'Binaries', 'Win64')


def getDefaultGameBinariesDir(gameDir, gameName):
    return normPath(os.path.join(gameDir, getGameBinariesRelDir(gameName)))


def getGamePaksRelDir(gameName):
    return os.path.join(gameName, 'Content', 'Paks')


def getGamePaksDir(gameDir, gameName):
    return normPath(os.path.join(gameDir, getGamePaksRelDir(gameName)))


def getGameServerIsRunning():
    return checkTaskRunning(DefaultGameServerProgramName)


def getGameLobbyIsRunning():
    return checkTaskRunning(DefaultGameLobbyProgramName)


def getGameIsRunning(programName):
    return checkTaskRunning(programName)


def killGameServer(asAdmin=False):
    return taskKill(DefaultGameServerProgramName, asAdmin=asAdmin)


def killGameLobby(asAdmin=False):
    return taskKill(DefaultGameLobbyProgramName, asAdmin=asAdmin)


def killGame(gameProgramName, asAdmin=False):
    return taskKill(gameProgramName, asAdmin=asAdmin)


def getLauncherBatchFileContent(
    usingStandaloneExitOption=None,
    usingOriginalBehavior=False,
    isAdmin=False,
    usingServer=None,
    gameVersion=None,
    gameName=None,
    gameProgramName=None,
):
    cols, rows = shutil.get_terminal_size()

    if usingStandaloneExitOption is None:
        usingStandaloneExitOption = usingOriginalBehavior or False

    usingOriginalCls = usingOriginalBehavior
    usingOriginalPause = usingOriginalBehavior
    usingPageClearCls = False
    if usingServer is None:
        usingServer = semver.VersionInfo.parse(gameVersion).match('<6.5.2')

    if not gameName:
        gameName = DefaultGameName

    if not gameProgramName:
        gameProgramName = getDefaultGameProgramName(gameName)

    if not gameVersion:
        gameVersion = '4.4.2' if usingServer else DefaultGameVersion

    gameArgs = []
    if gameVersion == '4.4.2':
        gameArgs = ['-DX12']
    else:
        gameVersionSemver = semver.VersionInfo.parse(gameVersion)
        if gameVersionSemver.match('>=6.7.0') and gameVersionSemver.match('<=6.7.2'):
            gameArgs = ['-eac-nop-loaded']
            gameArgs.append('-DX12')
    gameArgs.extend([
        '-SaveToUserDir',
        '-UserDir="Data"',
    ])

    gameBinariesRelDir = getGameBinariesRelDir(gameName)

    def formatLines(lines, indent=0, keepEmpty=False, linesOnly=False):
        indentedLines = [f"{'    ' * indent}{line}" for line in lines if line or keepEmpty]
        if linesOnly:
            return indentedLines

        return ('\n' if True else os.linesep).join(indentedLines)

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
        return formatLines(lines, indent, linesOnly=linesOnly)

    def doWait():
        return 'timeout /t 3 /nobreak >nul'

    def pause(indent=0, wait=False, invalidInput=False, active=True, linesOnly=False, startingLobby=False):
        waitPart = doWait() if wait else ''
        pausePart = 'pause'
        pausing = True

        if waitPart and not usingOriginalPause and (not startingLobby or True):
            waitPart = f'REM {waitPart}'

        if pausePart and (not active or (not usingOriginalPause and not invalidInput)):
            pausePart = f'REM {pausePart}'
            pausing = False

        lines = [
            waitPart,
            *((['echo.'] if True else clearScreen(soft=True, linesOnly=True)) if pausing else []),
            pausePart,
        ]
        return formatLines(lines, indent, linesOnly=linesOnly)

    def actionIf(action, inputMatches, indent=0):
        lines = []
        for inputMatch in inputMatches:
            lines.append(f'if /I %op%=={inputMatch} {action}')
            if usingOriginalBehavior:
                # use only the first item (the menu number)
                break
        return formatLines(lines, indent)

    def confirmToUac(indent=0, linesOnly=False, forceConfirm=False):
        if isAdmin:
            return ''
        lines = [
            #'echo.', # TODO: remove
            'echo UAC window will open.',
        ]
        if forceConfirm:
            lines = [
                *lines,
                #'echo.', # TODO: remove
                'pause',
            ]
        return formatLines(lines, indent, linesOnly=linesOnly)

    def start(programOrPath, params=None, title='', indent=0, asAdmin=False, cwd=f'%cd%', wait=False, isProgram=False):
        return formatLines([getStartCommand(programOrPath, params, title, asAdmin, cwd, wait, isProgram=isProgram)], indent)

    def stopLobbyIfRunning(indent=0, failGoto='main', linesOnly=False):
        lines = [
            f'echo Checking lobby status...',
            getCheckTaskRunningCommand(DefaultGameLobbyProgramName),
            f'if "%errorlevel%"=="0" (',
            f'    echo Lobby already running.',
            f'    echo.',
            f'    echo Terminating prior lobby process...',
            *confirmToUac(indent=1, linesOnly=True, forceConfirm=True),
            f'    {getTaskKillCommand(DefaultGameLobbyProgramName, asAdmin=True)}',
            f'    set "err=!errorlevel!"',
            #f'    echo !err!', # TODO: remove
            f'    if !err! GTR 0 (',
            f'        echo.',
            f'        echo Failed to terminate prior lobby.',
            f'        pause',
            f'        goto :{failGoto}',
            f'    )',
            f'    echo Prior lobby process terminated.',
            f')',
            #f'echo Not running yet.', # TODO: remove
            f'echo.',
        ]
        return formatLines(lines, indent, keepEmpty=True, linesOnly=linesOnly)

    def startGameLobby(message, params=None, failGoto='main', indent=0, subTitle=''):
        lines = [
            *stopLobbyIfRunning(failGoto=failGoto, linesOnly=True),
            f'echo {message}',
            *confirmToUac(linesOnly=True),
            getPowershellCommand(f'%cd%\{DefaultGameLobbyProgramName}', params, asAdmin=True, wait=False, isProgram=True, title=f'Lobby{f" - {subTitle}" if subTitle else ""}'),
            #getStartCommand(DefaultGameLobbyProgramName, params, title='Lobby', asAdmin=True), # TODO: remove
            f'set "startGameLobbyErr=!errorlevel!"',
            f'if !startGameLobbyErr! GTR 0 (',
            f'    echo.',
            f'    echo Failed to start lobby.',
            f'    pause',
            f'    goto :{failGoto}',
            f')',
            *pause(wait=True, startingLobby=True, linesOnly=True),
            f'echo Lobby started.',
        ]
        return formatLines(lines, indent, keepEmpty=True)

    result = (
f'''@echo off
setlocal enabledelayedexpansion
title {gameVersion} Launcher - By Smirkzyy and Merky and Ross
cd /d "{gameBinariesRelDir}{os.path.sep * 2}"
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
    goto :{"launch" if usingServer else "launchefog"}
)

:main
if %prevContent%==1 (
{clearScreen(soft=True, active=False, indent=1)}
)
set prevContent=1
{clearScreen()}
echo Launcher Main Menu
echo.
echo [1] Launch {gameVersion}
echo [2] Join Public Lobby (Survivors Only)
echo [3] Custom Lobby
echo.
echo -------------[MISC]-------------
echo.
echo [4] Open Paks Folder
echo [5] Open Win64 Folder
echo [6] Open Config Folder
echo [7] {"Exit" if usingOriginalBehavior else "Quit" if usingStandaloneExitOption else f"Back to {ProgramName}"}
echo.
set /p op="Selection: "
{actionIf(f"goto :{'launch' if usingServer else 'launchefog'}", ['1', 'launch', 'launc', 'laun', 'lau', 'la', 'l', 'lnch', 'ln', 'lnc'])}
{actionIf("goto :join", ['2', 'j', 'pubs', 'pub', 'join', 'joi', 'jo', 'jn', 'lobby'])}
{actionIf("goto :customLobby", ['3', 'cust', 'custs', 'customs', 'custom lobby', 'customLobby', 'custom'])}
{actionIf("goto :openPaks", ['4', 'pak', 'pk', 'pks', 'paks', 'openPaks', 'open paks'])}
{actionIf("goto :openWin64", ['5', 'openWin64', 'win', 'win64', 'open win64'])}
{actionIf("goto :openConfig", ['6', 'openConfig', 'open config', 'config', 'conf'])}
{actionIf("exit", ['7',
    *[
        *(['x', 'ex', 'xi', 'exi', 'exit'] if usingStandaloneExitOption else []),
        *(['q', 'quit', 'qu', 'qui'] if usingStandaloneExitOption or True else []),
        *(['b', 'ba', 'bak', 'bac', 'back', 'bk'] if not usingStandaloneExitOption else []),
        *(['ret', 'return'] if not usingStandaloneExitOption else []),
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
    goto :launchefog
)

echo Starting server...
{start(DefaultGameServerProgramName, title='Server', isProgram=True)}
{doWait()}
goto :launchefog


:launchefog
{clearScreen(soft=True)}
echo Checking game status...
{getCheckTaskRunningCommand(gameProgramName)}

if "%errorlevel%"=="0" (
    echo Already running.
{pause(invalidInput=True, indent=1)}
    goto :main
)

echo Launching {gameName} {gameVersion}...
{start(gameProgramName, gameArgs, title='Game', isProgram=True)}
{pause(wait=True)}
goto :main


:join
{clearScreen(soft=True)}
{startGameLobby(f'Starting {gameVersion} lobby...', subTitle='Public', failGoto='main')}
goto :main


:openPaks
{clearScreen(soft=True)}
echo Opening Paks folder...
set "paksPath=%~dp0{gameName}\Content\Paks"
{start(f'%paksPath%')}
{pause(wait=True)}
goto :main


:openWin64
{clearScreen(soft=True)}
echo Opening Win64 folder...
set "win64path=%~dp0{gameBinariesRelDir}"
{start(f'%win64path%')}
{pause(wait=True)}
goto :main


:openConfig
{clearScreen(active=False)}
set "configPath=%localappdata%\{gameName}\Saved\Config\WindowsNoEditor"

IF EXIST "%configPath%" (
{clearScreen(soft=True, indent=1)}
    echo Opening Config folder...
{start(f'%configPath%', indent=1)}
{pause(wait=True, indent=1)}
) else (
    echo.
{clearScreen(active=False, indent=1)}
    echo ERROR: Config folder does not exist. Please launch {gameVersion} at least once to create it.
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
{startGameLobby('Creating custom lobby...', [f'%setSurv%'], subTitle='Custom', failGoto='killer2')}
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
{stopLobbyIfRunning(failGoto='GrabSteamURL')}
cd /d GrabSteamURL/bin/
java -cp "GrabSteamURL4Launcher.jar;jsoup-1.17.1.jar" GrabSteamURL2 "%~dp0{gameBinariesRelDir.replace(os.path.sep, f'{os.path.sep}{os.path.sep}')}{os.path.sep}{os.path.sep}{DefaultGameLobbyProgramName}"
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
{startGameLobby('Joining custom lobby...', [f'%steamLink%'], subTitle='DirectConnect', failGoto='DirectConnect')}
goto :customLobby


:steamPrivacySettings
{clearScreen(soft=True)}
echo Opening Steam privacy settings in default browser...
{start('https://www.steamcommunity.com/id/eroticgaben/edit/settings')}
{pause(wait=True)}
goto :killer'''
    )

    return result


def openGameLauncher(
    gameDir,
    startGame=False,
    usingExternalLauncher=False,
    fromMenu=False,
    usingServer=None,
    gameVersion=None,
):
    def runLauncherBatchScript(launcherPath):
        assert launcherPath
        return os.system(f'cd "{gameDir}" && "{launcherPath}"{" launch" if startGame else ""}')

    if usingExternalLauncher:
        # TODO: be able to use custom launcher path
        return runLauncherBatchScript(os.path.join(gameDir, DefaultLauncherRelPath))

    with openTemporaryFile(dir=gameDir, prefix=f'{ProgramName}_Launcher_', suffix='.bat', mode='w', encoding='utf-8') as file:
        # TODO: remove
        if False:
            print(getLauncherBatchFileContent())
        else:
            file.write(getLauncherBatchFileContent(
                usingStandaloneExitOption=not fromMenu or None,
                usingServer=usingServer,
                gameVersion=gameVersion,
            ))
            file.close()
            return runLauncherBatchScript(file.name)
