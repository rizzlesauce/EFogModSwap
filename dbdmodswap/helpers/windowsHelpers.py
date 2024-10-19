import ctypes
import os
import webbrowser
import winreg


def getIsRunningAsAdmin():
    return ctypes.windll.shell32.IsUserAnAdmin() == 1


def getStartCmd(programOrPath, params=None, title='', wait=False):
    cmd = f'start {"/WAIT" if wait else ""} "{title}" "{programOrPath}"'
    if params:
        cmd += ' ' + ' '.join(f'"{p}"' for p in params)
    return cmd


def getRenameWindowScript(title, processVarName='process'):
    # TODO: get this working
    return f'''# Wait for the main window handle to become available
for ($i = 0; $i -lt 60; $i++) {'{'}
    if (${processVarName}.MainWindowHandle -ne 0) {'{'}
        break
    {'}'}
    Start-Sleep -Milliseconds 500;
    ${processVarName}.Refresh()
{'}'}

if (${processVarName}.MainWindowHandle -ne 0) {'{'}
    $hwnd = ${processVarName}.MainWindowHandle;

    # Define the SetWindowText function from user32.dll

    Add-Type -Name Win32Functions -Namespace User32 -MemberDefinition '[DllImport(''user32.dll'', SetLastError = true, CharSet = CharSet.Auto)] public static extern bool SetWindowText(IntPtr hWnd, string lpString);';

    # Set the window title
    [User32.Win32Functions]::SetWindowText($hwnd, '{title}') | Out-Null

#    $signature = @'
#using System;
#using System.Runtime.InteropServices;
#
#public static class Win32Functions {'{'}
#    [DllImport(''user32.dll'', SetLastError = true, CharSet = CharSet.Auto)]
#    public static extern bool SetWindowText(IntPtr hWnd, string lpString)
#{'}'}
#'@;
#    Add-Type -TypeDefinition $signature -PassThru;
#
#    # Set the window title
#    [Win32Functions]::SetWindowText($hwnd, '{title}') | Out-Null
{'}'} else {'{'}
    Write-Host 'Could not find the window handle.'
{'}'}
'''


def getPowershellCommand(programOrPath, params=None, asAdmin=False, cwd=f'%cd%', hidden=False, wait=True, gettingExitCode=True, isProgram=False, title=''):
    # NOTE: hidden=True can cause caller program to be hidden

    usingRenameWindowScript = False

    def escapeCmd(cmd):
        return cmd.replace('"', '\\"').replace('%', f'%%')

    if isProgram or False:
        if title and not usingRenameWindowScript:
            if True:
                def escape(arg):
                    return arg.replace('"', "'").replace("'", "''").replace('\\', '\\\\')

                program = 'powershell.exe'
                if params:
                    paramsPart = ' ' + ' '.join([f"''{escape(arg)}''" for arg in params])
                else:
                    paramsPart = ''
                noExitPart = "'-NoExit', " if False else ''
                argsPart = f' -ArgumentList {noExitPart}\'-Command\', \'$host.UI.RawUI.WindowTitle = \'\'{title}\'\'; & \'\'{escape(programOrPath)}\'\'{paramsPart}\''
        else:
            program = programOrPath
            if params:
                argsPart = ' -ArgumentList ' + ', '.join([f"'{escapeCmd(arg)}'" for arg in params])
            else:
                argsPart = ''
    else:
        program = 'cmd.exe'
        cmdEscaped = escapeCmd(getStartCmd(programOrPath, params, title, wait))
        cmdExitCodePart = escapeCmd(f' && set "exitCode=%ERRORLEVEL%" && exit /b %exitCode%') if True and wait and gettingExitCode else ''
        argsPart = f' -ArgumentList \'/c\', \'cd /d \\"{cwd}\\"{f" && {cmdEscaped}" if cmdEscaped else ""}{cmdExitCodePart}\''

    startPart = f'start {"/WAIT" if wait else ""} "" /min ' if hidden and not gettingExitCode else ''
    windowStylePart = ' -WindowStyle Hidden' if hidden else ''
    errorActionPart = "$ErrorActionPreference = 'Stop'; " if True else ''
    usingTry = gettingExitCode and asAdmin
    tryStartPart = 'try { ' if usingTry else ''
    runAsPart = ' -Verb RunAs' if asAdmin else ''
    waitPart = ' -Wait' if wait else ''
    setWindowTitlePart = ''
    if title and usingRenameWindowScript:
        lines = [line.strip() for line in getRenameWindowScript(title, 'process').split('\n')]
        lines = [line for line in lines if line and line[0] != '#']
        if lines:
            setWindowTitlePart = '; ' + ' '.join(lines)

    psExitCodePart = f'{" -PassThru" if (wait and gettingExitCode) or setWindowTitlePart else ""}{" -ErrorAction Stop | Out-Null" if True else ""}{setWindowTitlePart}{"; exit $process.ExitCode" if wait and gettingExitCode else "; exit 0"}' if True else ''
    tryEndPart = ' } catch { exit 1223 }' if usingTry else ''
    result = f'{startPart}powershell{windowStylePart} -Command "{errorActionPart}{tryStartPart}{"$process = " if setWindowTitlePart or (wait and gettingExitCode) else ""}Start-Process \'{program}\'{argsPart} -WorkingDirectory \'{cwd}\'{runAsPart}{waitPart}{psExitCodePart}{tryEndPart}"{" 2>nul" if True else ""}'
    # TODO: remove
    if False:
        print(result)
    return result


def getStartCommand(programOrPath, params=None, title='', asAdmin=False, cwd=f'%cd%', wait=False, gettingExitCode=None, isProgram=False):
    usingPowershell = True

    if asAdmin or usingPowershell:
        if gettingExitCode is None:
            gettingExitCode = True
        # use powershell because it tends to ensure the window is opened in the foreground
        result = getPowershellCommand(programOrPath, params, asAdmin=asAdmin, wait=wait, gettingExitCode=gettingExitCode, isProgram=isProgram)
    else:
        # this can lead to a window being opened in the background
        result = getStartCmd(programOrPath, params, title, wait)

    return result


def runAsAdmin(cmd, params, cwd=None):
    """
    Run a command as an administrator.

    Parameters:
        cmd (str): The command to execute.
        params (str): Parameters for the command.
        cwd (str, optional): The working directory. Defaults to the current directory.
    """
    if cwd is None:
        cwd = os.getcwd()

    # Prepare the arguments for ShellExecuteW
    operation = 'runas'  # Indicates we want to run as admin
    lpFile = cmd
    lpParameters = params
    lpDirectory = cwd
    nShowCmd = 1  # 1 = SW_SHOWNORMAL

    # Execute the command
    ret = ctypes.windll.shell32.ShellExecuteW(None, operation, lpFile, lpParameters, lpDirectory, nShowCmd)

    return ret


def setConsoleTitle(title):
    os.system(f'title {title}')


def getWindowsDefaultEditor():
    """Gets the default editor for Windows."""

    try:
        # Try to get the editor from the environment variable
        editor = os.environ['EDITOR']
    except KeyError:
        # If the environment variable is not set, try to get the default editor from the registry
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\Windows\\CurrentVersion\\Applets\\Notepad\\Execute') as key:
                editor = winreg.QueryValueEx(key, '')[0]
        except FileNotFoundError:
            # If the registry key is not found, return Notepad as the default editor
            editor = 'notepad.exe'

    return editor


def checkTaskRunning(programName):
    charLimitForFind = 25
    nameForFind = programName if len(programName) <= charLimitForFind else programName[:charLimitForFind]
    return os.system(f'tasklist /fi "imagename eq {programName}" 2>nul | find /i /n "{nameForFind}" >nul') == 0


def getTaskKillCommandParts(programName):
    cmd = 'taskkill.exe'
    params = f'/f /t /im "{programName}"'
    return [cmd, params]


def getTaskKillCommand(programName, asAdmin=False):
    cmd, params = getTaskKillCommandParts(programName)
    if asAdmin:
        result = getPowershellCommand(cmd, [params], isProgram=True, asAdmin=True)
    else:
        result = f'{cmd} {params}'

    return result


def taskKill(programName, asAdmin=False):
    if asAdmin:
        cmd, params = getTaskKillCommandParts(programName)
        code = runAsAdmin(cmd, params)
        if code > 32:
            # translate this to the success exit code
            code = 0
        return code

    return os.system(getTaskKillCommand(programName))


def pressAnyKeyToContinue():
    os.system('pause')


def openFolder(dirPath):
    os.system(getStartCommand(dirPath))


def openFile(filePath):
    success = False

    orderToTry = [
        # can open in background
        'webbrowser',
        # can open in background
        'startfile',
        # may open in foreground, but using notepad even if you have a better editor
        'editor',
    ]

    testFail = {
        'webbrowser': False,
        'startfile': False,
        'editor': False,
    }

    for item in orderToTry:
        try:
            if testFail.get(item, False):
                raise ValueError(f'[Test] {item} failed to run')

            if item == 'webbrowser':
                webbrowser.open(filePath)
            elif item == 'startfile':
                os.startfile(filePath)
            elif item == 'editor':
                editor = getWindowsDefaultEditor()
                os.system(getStartCommand(editor, [filePath]))
            else:
                raise ValueError('internal error')

            success = True
            break
        except Exception as e:
            if False:
                print(e)

    return success


def getCheckTaskRunningCommand(programName):
    charLimitForFind = 25
    nameForFind = programName if len(programName) <= charLimitForFind else programName[:charLimitForFind]
    return f'tasklist /fi "imagename eq {programName}" 2>nul | find /i /n "{nameForFind}" >nul'

def checkTaskRunning(programName):
    return os.system(getCheckTaskRunningCommand(programName)) == 0
