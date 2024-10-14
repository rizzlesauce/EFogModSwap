#!/usr/bin/env python3
"""
Module Docstring
"""

import json
import yaml
import copy
import sys
import os
from itertools import combinations
import secrets
import hashlib
import argparse
from contextlib import contextmanager
import pathlib
import webbrowser
import platform
import subprocess
import shutil
import pprint
import tempfile
import re
import Attachment

__author__ = 'Ross Adamson'
__version__ = '0.1.4'
__license__ = 'MIT'

# TODO: provide file content to install this batch file into the game folder
DefaultLauncherRelPath = '4.4.2 Launcher.bat'
DefaultGameProgramName = 'DeadByDaylight-Win64-Shipping.exe'
DefaultGameServerProgramName = 'Server.exe'

DefaultPlatform = 'WindowsNoEditor'
DefaultSettingsPath = 'settings.yaml'
DefaultAttachmentsDir = 'attachments'
DefaultCustomizationItemDbPath = 'CustomizationItemDB.uasset'
DefaultUAssetGUIPath = 'UAssetGUI.exe'
DefaultUnrealPakPath = 'UnrealPak.exe'
DefaultPakingDir = 'paking'
UnrealEngineCookedSplitFileExtensions = {'.uasset', '.ubulk', '.uexp'}

ItemTypeName = '$type'
ECustomizationCategoryName = 'ECustomizationCategory'
ECustomizationCategoryNamePrefix = f'{ECustomizationCategoryName}::'
ValueFieldName = 'Value'
NameFieldName = 'Name'
ModelDisplayNamePropNameFieldName = 'CultureInvariantString'

hasPriorPrintSection = False
needsNewPrintSection = 0
sprintPads = 0

sprintRecording = None

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

def esprint(*args, **kwargs):
    global hasPriorPrintSection
    sprintApply()
    result = recordAndRunSprint(lambda: eprint(*args, **kwargs))
    hasPriorPrintSection = True
    return result

def promptToContinue(purpose='to continue...', pad=True):
    if pad:
        sprintPad()
    result = sprintput(f'Press Enter {purpose}')
    if pad:
        sprintPad()

@contextmanager
def oneLinePrinter():
    def myPrint(message):
        sprint(message, end='')
    try:
        yield myPrint
    finally:
        # end the line
        sprint('')

@contextmanager
def openTemporaryFile(dir=None, prefix=None, suffix=None, mode=None):
    file = tempfile.NamedTemporaryFile(
        dir=dir,
        prefix=prefix,
        suffix=suffix,
        mode=mode,
        delete=False,
    )
    try:
        yield file
    finally:
        file.close()
        pathlib.Path.unlink(file.name)

def normPath(path):
    if isinstance(path, str) and not path.strip():
        return ''

    if not isinstance(path, pathlib.Path):
        path = pathlib.Path(path)

    return path.as_posix()

def getPathInfo(path, relativeDir='./', debug=False):
    result = {
        'path': path,
        'normalized': '',
        'relativeDir': relativeDir,
        'relativeDirResolved': '',
        'isAbsolute': False,
        'absolute': '',
        'relative': None,
        'dir': '',
        'basename': '',
        'stem': '',
        'suffix': '',
        'suffixLower': '',
        'best': '',
    }

    if path.strip():
        result['normalized'] = normPath(path)
        relativeDirResolved = normPath(pathlib.Path(relativeDir).resolve())
        result['relativeDirResolved'] = relativeDirResolved

        if os.path.isabs(path):
            result['isAbsolute'] = True
            result['absolute'] = normPath(pathlib.Path(path).resolve())
            commonPath = normPath(os.path.commonpath([result['absolute'], relativeDirResolved]))
            if commonPath == relativeDirResolved:
                result['relative'] = normPath(os.path.relpath(result['absolute'], relativeDirResolved))
        else:
            result['absolute'] = normPath(pathlib.Path(os.path.join(relativeDir, path)).resolve())
            result['relative'] = normPath(os.path.relpath(result['absolute'], relativeDirResolved))

        pathlibPath = pathlib.Path(result['absolute'])

        result['dir'] = os.path.dirname(result['absolute'])
        result['basename'] = os.path.basename(result['absolute'])
        result['stem'] = pathlibPath.stem
        result['suffix'] = pathlibPath.suffix
        result['suffixLower'] = result['suffix'].lower()
        result['best'] = result['absolute'] if result['relative'] is None else result['relative']

    if debug:
        sprintPad()
        sprintP(result)
        sprintPad()

    return result

def getContentDirRelativePath(path):
    path = normPath(path)
    start = '/Content/'
    if path.startswith(start):
        return path[len(start):]

def listFilesRecursively(dir):
    """Lists all files in a directory recursively as relative paths."""
    for root, dirs, files in os.walk(dir):
        for file in files:
            absolutePath = os.path.join(root, file)
            relativePath = os.path.relpath(absolutePath, dir)
            yield normPath(relativePath)

def getWindowsDefaultEditor():
    """Gets the default editor for Windows."""

    try:
        # Try to get the editor from the environment variable
        editor = os.environ['EDITOR']
    except KeyError:
        # If the environment variable is not set, try to get the default editor from the registry
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Applets\\Notepad\\Execute") as key:
                editor = winreg.QueryValueEx(key, "")[0]
        except FileNotFoundError:
            # If the registry key is not found, return Notepad as the default editor
            editor = "notepad.exe"

    return editor

def osOpenDir(dirPath):
    os.system(f'start explorer "{dirPath}"')

def osOpenFile(filePath):
    success = False

    testingFailWebbrowser = False
    testingFailStartfile = False
    testingFailEditor = False

    sprintPad()

    try:
        sprintPad()
        sprint(f'Opening {filePath}...')
        if testingFailWebbrowser:
            raise ValueError('webbrowser failed to run')
        webbrowser.open(filePath)
        success = True
    except Exception as e:
        sprintPad()
        esprint(e)
        sprintPad()
        try:
            sprint(f'Trying a different way to open...')
            if testingFailStartfile:
                raise ValueError('startfile failed to run')
            os.startfile(filePath)
            success = True
        except Exception as e2:
            sprintPad()
            esprint(e2)
            sprintPad()
            if platform.system() == 'Windows':
                try:
                    editor = getWindowsDefaultEditor()
                    sprint(f'Opening with {editor}...')
                    if testingFailEditor:
                        raise ValueError('editor failed to run')
                    os.system(f'start {editor} {filePath}')
                    success = True
                except Exception as e3:
                    sprintPad()
                    esprint(e3)
                    sprintPad()

    sprintPad()

    return success

def jsonifyDataRecursive(value, isKey=False):
    if isinstance(value, dict):
        newValue = {jsonifyDataRecursive(k, isKey=True): jsonifyDataRecursive(v) for k, v in value.items()}
    elif isinstance(value, set) or isinstance(value, frozenset):
        listVersion = sorted([jsonifyDataRecursive(v, isKey=isKey) for v in value], key=lambda x: x.upper() if isinstance(x, str) else x)
        if isKey:
            newValue = ','.join(listVersion)
        else:
            newValue = listVersion
    else:
        newValue = value

    return newValue

class JsonSetEncoder(json.JSONEncoder):
    def default(self, value):
        if isinstance(value, set) or isinstance(value, frozenset):
            return sorted(list(value), key=lambda v: v.upper() if isinstance(v, str) else v)
        return json.JSONEncoder.default(self, value)

def jsonDump(value, stream=None, pretty=False):
    indent = 2 if pretty else None
    if stream:
        return json.dump(value, stream, indent=indent, cls=JsonSetEncoder)
    else:
        return json.dumps(value, indent=indent, cls=JsonSetEncoder)

def yamlDump(value, stream=None, customTypes=False):
    if customTypes:
        jsonStr = jsonDump(value)
        value = json.loads(jsonStr)

    return yaml.dump(value, stream=stream, default_flow_style=False, sort_keys=False)

def generateRandomHexString(length):
    return secrets.token_hex(length // 2)

def md5Hash(string):
  return hashlib.md5(string.encode()).hexdigest()

def sha256Hash(string):
    return hashlib.sha256(string.encode()).hexdigest()[:32]

def findNextItemByFields(items, fields, values):
    fieldsValuesMap = {f: v for f, v in zip(fields, values)}
    return next((item for item in items if all(item[field] == value for field, value in fieldsValuesMap.items())), None)

def findNextItemByType(items, typeName):
    return findNextItemByFields(items, [ItemTypeName], [typeName])

def getPropertyValue(property):
    return property[ValueFieldName]

def setPropertyValue(property, value):
    property[ValueFieldName] = value

def getModelName(model):
    return model[NameFieldName]

def setModelName(model, name):
    model[NameFieldName] = name

def getEnumValue(enum):
    return getPropertyValue(enum)

def findEnumByType(items, enumType):
    return findNextItemByFields(
        items,
        [
            ItemTypeName,
            'EnumType',
        ],
        [
            'UAssetAPI.PropertyTypes.Objects.EnumPropertyData, UAssetAPI',
            enumType,
        ],
    )

def findStructByType(items, structType):
    return findNextItemByFields(
        items,
        [
            ItemTypeName,
            'StructType',
        ],
        [
            'UAssetAPI.PropertyTypes.Structs.StructPropertyData, UAssetAPI',
            structType,
        ],
    )

def getModelIdProperty(modelValues):
    return findNextItemByFields(
        modelValues,
        [
            ItemTypeName,
            NameFieldName,
        ],
        [
            'UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI',
            'ID',
        ]
    )

def findSocketAttachmentsStruct(modelValues):
    return findNextItemByFields(
        modelValues,
        [
            ItemTypeName,
            'ArrayType',
            NameFieldName,
        ],
        [
            'UAssetAPI.PropertyTypes.Objects.ArrayPropertyData, UAssetAPI',
            'StructProperty',
            'SocketAttachements',
        ],
    )

def getSocketAttachments(modelValues):
    return getPropertyValue(findSocketAttachmentsStruct(modelValues))

def findUiDataStruct(modelValues):
    return findStructByType(modelValues, 'ItemUIData')

def getUiDataValues(modelValues):
    return getPropertyValue(findUiDataStruct(modelValues))

def getModelDisplayNameProperty(uiDataValues):
    return findNextItemByFields(
        uiDataValues,
        [
            ItemTypeName,
            NameFieldName,
        ],
        [
            'UAssetAPI.PropertyTypes.Objects.TextPropertyData, UAssetAPI',
            'DisplayName',
        ]
    )

def addAllToNameMap(value, nameMapSet, path=''):
    def addName(name):
        if name not in nameMapSet:
            # TODO: remove
            if False:
                sprint(f'NameMap++|{name}|')
            nameMapSet.add(name)

    if isinstance(value, dict):
        itemType = value.get(ItemTypeName, None)

        for k, v in value.items():
            if k.startswith('$'):
                continue

            if k in {'StructGUID'}:
                continue

            if isinstance(v, str):
                if not v:
                    continue

                # TODO: catch other numbers like this?
                if v in {'+0', '0'}:
                    # TODO: remove
                    if False:
                        sprint(f'Invalid Name: {path}{k} -> {v}')
                    continue

                if k in {
                    'PackageGuid',
                    'PersistentGuid',
                    'PackageFlags',
                    'ObjectFlags',
                    ModelDisplayNamePropNameFieldName,
                    'HistoryType',
                    'TransformType',
                }:
                    continue

                if k == 'Value':
                    if itemType in {
                        'UAssetAPI.PropertyTypes.Objects.StrPropertyData, UAssetAPI',
                        'UAssetAPI.PropertyTypes.Objects.TextPropertyData, UAssetAPI',
                    }:
                        continue

                if itemType in {
                    'AssetAPI.UnrealTypes.FVector2D, UAssetAPI',
                } and k in {
                    'X',
                    'Y',
                }:
                    continue

                if k == 'AssetName':
                    pathParts = v.split('.')
                    path = ''
                    for pathPart in pathParts:
                        if path:
                            path = f'{path}.{pathPart}'
                        else:
                            path = pathPart

                        addName(path)
                else:
                    addName(v)
            elif isinstance(v, dict) or isinstance(v, list):
                addAllToNameMap(v, nameMapSet, path=f'{path}{itemType or ""}.{k}/')
    elif isinstance(value, list):
        for vIndex, v in enumerate(value):
            addAllToNameMap(v, nameMapSet, f'{path}[{vIndex}]/')

def getResultsFilePath(settingsFilePath):
    return f"{settingsFilePath.removesuffix('.yaml')}-results.yaml"

def getAttachmentDisplayName(attachment):
    return attachment['displayName'] or attachment['attachmentId']

def getSettingsTemplate():
    return '''# settings file for DbdSocketsMixer

# other settings to import - keys in this file will replace keys in imports
import: []
#import:
#- settings_all_relations.yaml

# CustomizationItemDB for your custom slot outfit/models. This can either be a `.uasset` file,
# or a `.json` file saved by UAssetGUI.
customizationItemDbPath: {DefaultCustomizationItemDbPath}

# The path to the directory where socket attachment definition yaml files are stored
attachmentsDir: attachments

# These are attachments that are equivalent to the combination of other attachments.
# For example, KateLegsBlueChains is equivalent to combining KateLegsLeftBlueChain and KateLegsRightBlueChain.
# The mixer will make sure not to combine an equivalent attachment with its parts, and it will also skip combinations
# that include all parts of an equivalent (since this would duplicate the same combination containing the equivalent).
equivalentParts:
  # uncomment this if there are no equivalent parts in this category
  #SurvivorLegs: {}
  SurvivorLegs:
    # separated left/right sides of the original blue chains
    KateLegsBlueChains:
    - - KateLegsLeftBlueChain
      - KateLegsRightBlueChain
    # separated left/right sides of the shortened blue chains
    KateLegsShortBlueChains:
    - - KateLegsShortLeftBlueChain
      - KateLegsShortRightBlueChain

  # uncomment this if there are no equivalent parts in this category
  #SurvivorTorso: {}
  SurvivorTorso:
    # separated backpack/necklace parts of the original backpack/necklace attachment
    KateBackpackAndBlueGemNecklace:
    - - KateBackpack
      - KateBlueGemNecklace

# Unlike equivalent parts, these parts are incompletely equivalent to another attachment (they
# make up some of the attachment, but not the whole thing). Like equivalent parts, these parts will
# never be combined with the attachment they are part of.
supersetParts:
  # uncomment this if there are no equivalent parts in this category
  #SurvivorLegs: {}
  SurvivorLegs:
    # define each shortened variant of blue chains as a proper subset of the corresponding original length version
    KateLegsBlueChains:
    - - KateLegsShortBlueChains
    KateLegsRightBlueChain:
    - - KateLegsShortRightBlueChain
    KateLegsLeftBlueChain:
    - - KateLegsShortLeftBlueChain

  # uncomment this if there are no equivalent parts in this category
  SurvivorTorso: {}
  #SurvivorTorso:

# These are groups of mutually exclusive attachments (for example, backpacks).
mutuallyExclusive:
  # uncomment this if there are no groups in this category
  SurvivorLegs: {}
  #SurvivorLegs:

  # uncomment this if there are no groups in this category
  #SurvivorTorso: {}
  SurvivorTorso:
  # back conflict group 1
  - - KatePurpleHat
    - KateBackpack
    - MegHikingBackpack
    - MegSportBagWithShoes
    - NeaSkateboardBackpack

# Here we can define a list of attachments that conflict with a target attachment.
attachmentConflicts:
  # uncomment this if there are no conflicts in this category
  SurvivorLegs: {}
  #SurvivorLegs:

  # uncomment this if there are no conflicts in this category
  #SurvivorTorso: {}
  SurvivorTorso:
    KatePurpleHat:
    - KateBlueGemNecklace
    - KateGoldNecklaceNoRing
    - KateGuitar
    KateGuitar:
    - MegHikingBackpack
    - NeaSkateboardBackpack
    # optional - clipping is a bit noticeable
    - MegSportBagWithShoes
    # optional - clipping isn't too noticeable
    #- KateBackpack

# Skip attachment combinations that contain these combinations. By default, these apply to all base models
# in the target CustomizationItemDB. Syntax is available here ('==' and ':') to restrict exclusions. Using
# '==' after an attachment name means that it will skip the exact combination instead of
# all supersets of the combination. Additionally, ending the line with ':' and one or more comma separated base model
# names will limit the exclusion to those models only.
combosToSkip:
  # uncomment this if there are no combos to skip in this category
  #SurvivorLegs: []
  SurvivorLegs:
  # remove long chains for the lower waistline pants in some legs variants
  - - KateLegsBlueChains:KateBikerVariantsRoughRider,KateBikerVariantsHellsAngel
  - - KateLegsLeftBlueChain:KateBikerVariantsRoughRider,KateBikerVariantsHellsAngel
  - - KateLegsRightBlueChain:KateBikerVariantsRoughRider,KateBikerVariantsHellsAngel
  # remove right side chain for legs variants with the walkie talkie
  - - KateLegsShortRightBlueChain:KateBikerVariantsGreenWalkieTalkie
  - - KateLegsShortRightBlueChain:KateBikerVariantsBlueWalkieTalkie

  # uncomment this if there are no combos to skip in this category
  #SurvivorTorso: []
  SurvivorTorso:
  # items that conflict with purple hat
  - - KateBackpack
    - KatePurpleHat
  - - KateBlueGemNecklace
    - KatePurpleHat
  - - KateGoldNecklaceNoRing
    - KatePurpleHat
  - - KateGuitar
    - KatePurpleHat
  # skip the exact variants that already exist in another DLC or in the original game
  - - KateBikerJacketDanglingGloves==:KateBikerVariantsReadyToRide
  # (optional - can comment the below out) remove double necklaces
  - - KateBlueGemNecklace
    - KateGoldNecklaceNoRing
'''.format(DefaultCustomizationItemDbPath=DefaultCustomizationItemDbPath)

def runCall(args, cwd=None, shell=False):
    quoted = [f'"{arg}"' for arg in args]
    try:
        code = subprocess.call(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, shell=shell)
        if code:
            raise ValueError(f'subprocess returned error exit code: {code}')
    except:
        raise ValueError(f'subprocess call failed: cwd="{cwd}" {" ".join(quoted)}')

def getUnrealProjectCookedContentDir(unrealProjectDir, gameName):
    return normPath(os.path.join(unrealProjectDir, 'Saved', 'Cooked', 'WindowsNoEditor', gameName, 'Content'))

def getPakContentDir(pakDir, gameName):
    return normPath(os.path.join(pakDir, gameName, 'Content'))

def getPakchunkFilenameRegex():
    return re.compile(r'^pakchunk(?P<number>\d+)(?P<name>\w*)-(?P<platform>\w+)(?P<suffix>\.pak)?$', re.IGNORECASE)

def getGamePaksDir(gameDir, gameName):
    return normPath(os.path.join(gameDir, gameName, 'Content', 'Paks'))

def unrealPak(pakDir, destPakPath, unrealPakPath, compress=True, debug=False):
    pakDirPathInfo = getPathInfo(pakDir)
    responseFileContent = f'"{pakDirPathInfo["absolute"]}\*.*" "..\..\..\*.*" '
    if debug:
        sprintPad()
        sprint(f'Response file content: {responseFileContent}')
        sprintPad()

    programPathInfo = getPathInfo(unrealPakPath)
    programFilename = programPathInfo['basename']
    programPath = normPath(os.path.join(programPathInfo['dir'], programFilename))
    responseFilePath = None

    def runCommand(responseFile):
        if debug:
            sprintPad()
            sprint(f'Running UnrealPak')
            sprint(f'Response file content: `{responseFileContent}`')
            sprint(f'Writing response file content to "{normPath(responseFile.name)}"')
            sprintPad()

        responseFile.write(responseFileContent)
        responseFile.close()

        args = [
            programPath,
            getPathInfo(destPakPath)['absolute'],
            f'-create={normPath(responseFile.name)}',
        ]
        if compress:
            args.append('-compress')

        if debug:
            sprintPad()
            sprintP(args)
            sprintPad()

        runCall(args, cwd=programPathInfo['dir'])

    usingTempFile = True

    if usingTempFile:
        with openTemporaryFile(
            prefix='DbdSocketsMixer_UnrealPak_filelist_',
            suffix='.txt',
            mode='w',
            dir=programPathInfo['dir'],
        ) as file:
            runCommand(file)
    else:
        responseFilePath = normPath(os.path.join(programPathInfo['dir'], 'DbdSocketsMixer_UnrealPak_filelist.txt'))
        with open(responseFilePath, 'w') as file:
            runCommand(file)

    # TODO: do we need to use gamepath.txt or do anything with *.sig files?

    return responseFilePath

def unrealUnpak(pakPath, destDir, gameName, unrealPakPath):
    pakPathInfo = getPathInfo(pakPath)
    programPathInfo = getPathInfo(unrealPakPath)
    programFilename = programPathInfo['basename']
    programPath = normPath(os.path.join(programPathInfo['dir'], programFilename))
    destDirPathInfo = getPathInfo(destDir)
    actualDestDir = getPakContentDir(destDirPathInfo['absolute'], gameName)
    if not os.path.exists(actualDestDir):
        os.makedirs(actualDestDir, exist_ok=True)
    args = [
        programPath,
        pakPathInfo['absolute'],
        '-extract',
        actualDestDir,
        # TODO: remove - doesn't seem to be needed
        #'-extracttomountpoint',
    ]
    runCall(args, cwd=programPathInfo['dir'])

def jsonToUasset(jsonPath, uassetPath, uassetGuiPath):
    runCall([uassetGuiPath, 'fromjson', jsonPath, uassetPath])

def uassetToJson(uassetPath, jsonPath, uassetGuiPath):
    runCall([uassetGuiPath, 'tojson', uassetPath, jsonPath, 'VER_UE4_25'])

def confirm(action, emptyMeansNo=None, pad=False):
    if pad:
        sprintPad()
    while True:
        result = sprintput(f'{action[0].upper()}{action[1:]} (Y/n)? ').strip()
        if result.upper() == 'Y':
            confirmed = True
            break

        if result.upper() == 'N' or (not result and emptyMeansNo is True):
            confirmed = False
            break

    if pad:
        sprintPad()

    return confirmed

def confirmOverwrite(target, pad=True):
    return confirm(f'overwrite "{target}"', pad=pad)

def findSettingsFiles(dir='.'):
    for entry in os.scandir(dir):
        if (
            # TODO: remove
            #entry.name.lower().startswith('settings')
            not entry.name.lower().startswith('.')
            and entry.name.lower().endswith('.yaml')
            and '_CustomizationItemDB'.lower() not in entry.name.lower()
            and not entry.name.lower().endswith('-results.yaml')
            and not entry.name.lower().endswith('-altered.yaml')
            and not entry.name.lower().endswith('-unaltered.yaml')
        ):
            yield entry.name

def openGameLauncher(gameDir, startGame=False):
    launcherPath = normPath(os.path.join(gameDir, DefaultLauncherRelPath))
    return os.system(f'cd "{gameDir}" && "{launcherPath}"{" launch" if startGame else ""}')

def checkTaskRunning(programName):
    charLimitForFind = 25
    nameForFind = programName if len(programName) <= charLimitForFind else programName[:charLimitForFind]
    return os.system(f'tasklist /fi "imagename eq {programName}" 2>nul | find /i /n "{nameForFind}" >nul') == 0

def killTask(programName):
    return os.system(f'taskkill /f /t /im "{programName}"')

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

def main(params):
    """ Main entry point of the app """

    settingsFilePath = params.get('settingsFilePath', '')
    inspecting = params.get('inspecting', False)
    creatingAttachments = params.get('creatingAttachments', False)
    extractingAttachments = params.get('extractingAttachments', False)
    renamingAttachmentFiles = params.get('renamingAttachmentFiles', False)
    mixingAttachments = params.get('mixingAttachments', False)
    paking = params.get('paking', False)
    installingMods = params.get('installingMods', False)
    openingGameLauncher = params.get('openingGameLauncher', False)
    killingGame = params.get('killGame', False)
    nonInteractive = params.get('nonInteractive', False)
    debug = params.get('debug', False)
    uassetGuiPath = params.get('uassetGuiPath', '')
    overwriteOverride = params.get('overwriteOverride', None)

    if openingGameLauncher:
        startSprintRecording()

    # TODO: remove -- too verbose
    printingJson = False
    printingYaml = False

    writingUnalteredDb = True
    writingAlteredDb = True

    exitCode = 0

    warnings = []
    def printWarning(message, pad=True):
        warnings.append(str(message))
        if pad:
            sprintPad()
        sprint(f'WARN: {message}')
        if pad:
            sprintPad()

    errors = []
    def printError(message, pad=True):
        nonlocal exitCode

        exitCode = 1

        errors.append(str(message))
        if pad:
            sprintPad()
        esprint(f'ERROR: {message}')
        if pad:
            sprintPad()

    if killingGame:
        sprintPad()
        sprint(f'Killing game...')
        if getGameIsRunning():
            killGame()
            sprint(f'Game process terminated.')
            # TODO: need to wait?
        else:
            sprint('Game is not running.')
        sprintPad()

    if False:
        importAttachmentsSeparator = 'And'
    else:
        importAttachmentsSeparator = '_'

    exportAttachmentsSeparator = '_'

    settingsDirPathInfo = getPathInfo('.')
    discoveredSettingsFiles = []

    if inspecting:
        sprintPad()
        sprint(f'Scanning "{settingsDirPathInfo["best"]}" for settings files...')
        for filename in findSettingsFiles(settingsDirPathInfo['absolute']):
            discoveredSettingsFiles.append(filename)
            sprint(f'{len(discoveredSettingsFiles)} - {filename}')
        sprint('Done.', end=' ')
        sprint(f'Discovered {len(discoveredSettingsFiles)} settings files.')
        sprintPad()

    settingsFilePath = getPathInfo(settingsFilePath)['best']

    attachmentsDir = ''
    cookedContentDir = ''
    cookedContentPaths = []
    cookedContentResourcePathsMap = {}
    gameDir = ''
    gamePaksDir = ''
    gamePakchunks = []
    reservedPakchunks = []
    modsToBeActive = []
    pakingDirPakchunks = []
    gameName = ''
    unrealProjectDir = ''
    unrealPakPath = ''
    pakingDir = ''
    srcPakPath = ''
    srcPakStem = ''
    srcPakDir = ''
    srcContentDir = ''
    srcPakContentDir = ''
    srcPakContentPaths = []
    srcPakContentResourcePathsMap = {}
    destPakNumber = None
    destPakName = ''
    destPakResources = []

    destPakStem = ''
    destPakDir = ''
    destPakContentDir = ''
    destPakPath = ''

    destPlatform = DefaultPlatform

    customizationItemDbPath = ''
    customizationItemDbJsonPath = ''
    customizationItemDb = None
    combinationsAdded = {}
    combinationsSkipped = {}
    attachmentsToMix = {}
    nameMapNamesRemoved = []
    nameMapNamesAdded = []
    attachmentsCreated = []
    nameMapArray = []
    nameMapSet = set(nameMapArray)
    attachmentsRenamed = {}

    def ensureDir(dir, title='Directory', warnIfNotExist=True):
        dir = getPathInfo(dir)['best']
        if not os.path.exists(dir):
            if warnIfNotExist:
                printWarning(f'{title or "Directory"} ("{dir}") does not exist. Creating it now.')
            os.makedirs(dir, exist_ok=True)
        return dir

    def ensureAttachmentsDir():
        nonlocal attachmentsDir

        if not attachmentsDir:
            attachmentsDir = getPathInfo(settings.get('attachmentsDir', ''))['best']
            if not attachmentsDir:
                printWarning(f'`attachmentsDir` not specified. Defaulting to: "{getPathInfo(DefaultAttachmentsDir)["best"]}"')
                attachmentsDir = getPathInfo(DefaultAttachmentsDir)['best']

        return ensureDir(attachmentsDir, '`attachmentsDir`')

    def ensurePakingDir():
        return ensureDir(pakingDir, '`pakingDir`')

    def readyToWrite(path, delete=True, overwrite=None):
        path = getPathInfo(path)['best']

        if not os.path.exists(path):
            return True

        shouldWarn = True

        if overwrite is not None:
            result = overwrite
        elif overwriteOverride is not None:
            result = overwriteOverride
        elif nonInteractive:
            printWarning('Cannot confirm file overwrite in non-interactive mode')
            result = False
        else:
            result = confirmOverwrite(path)
            shouldWarn = False

        if shouldWarn:
            if result:
                printWarning(f'Overwriting "{path}"')
            else:
                printWarning(f'Skipping write of "{path}" (file exists)')

        if result and delete:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                pathlib.Path.unlink(path)

        return result

    def checkAttachmentName(category, attachmentName, otherInfo=None):
        if attachmentName not in attachmentsToMix.get(category, {}):
            printWarning(f"reference to missing attachment: {category}::{attachmentName}{' (' if otherInfo else ''}{otherInfo or ''}{')' if otherInfo else ''}")

    def mergeSettings(parentData, childData):
        for key, value in childData.items():
            # TODO: merge data instead of overwriting
            parentData[key] = childData[key]

    def readSettingsRecursive(filePath, relativeDir='.'):
        resultData = {}

        pathInfo = getPathInfo(filePath, relativeDir=relativeDir)
        filePath = pathInfo['best']

        sprint(f'Reading settings from "{filePath}"')
        if not os.path.isfile(filePath):
            printError(f'Could not read settings from "{filePath}" (file not found)')
            return None

        with open(filePath, 'r') as file:
            data = yaml.safe_load(file)

        # TODO: ensure relative paths in settings are converted to relative paths
        # to relativeDir

        for otherPath in data.get('import', []):
            # import paths are relative to the file importing them
            otherData = readSettingsRecursive(otherPath, relativeDir=pathInfo['dir'])
            if otherData is None:
                return None

            mergeSettings(resultData, otherData)

        mergeSettings(resultData, data)

        return resultData

    try:
        if not os.path.exists(settingsFilePath):
            printWarning(f'Settings file ("{settingsFilePath}") does not exist. Creating it now with default content.')
            if printingYaml:
                sprint(getSettingsTemplate())
                sprintPad()
            with open(settingsFilePath, 'w') as file:
                file.write(getSettingsTemplate())

        settingsPathInfo = getPathInfo(settingsFilePath)
        settingsDir = settingsPathInfo['dir']
        settings = readSettingsRecursive(settingsFilePath)

        if not gameDir:
            gameDir = getPathInfo(settings.get('gameDir', ''))['best']
            if not gameDir:
                message = 'Missing or empty `gameDir`'
                if openingGameLauncher:
                    printError(message)
                else:
                    printWarning(message)
        if not unrealProjectDir:
            unrealProjectDir = getPathInfo(settings.get('unrealProjectDir', ''))['best']
            if not unrealProjectDir:
                printWarning(f'Missing or empty `unrealProjectDir`')
        if not gameName:
            gameName = settings.get('gameName', '').strip()
            if not gameName:
                printWarning(f'Missing or empty `gameName`')
        if not uassetGuiPath:
            uassetGuiPath = settings.get('uassetGuiPath', None)
            usingDefault = uassetGuiPath is None
            if usingDefault:
                uassetGuiPath = DefaultUAssetGUIPath
            uassetGuiPath = getPathInfo(uassetGuiPath)['best']
            if usingDefault:
                printWarning(f'Missing or empty `uassetGuiPath`. Defaulting to "{uassetGuiPath}"')
        if not unrealPakPath:
            unrealPakPath = settings.get('unrealPakPath', None)
            usingDefault = unrealPakPath is None
            if usingDefault:
                unrealPakPath = DefaultUnrealPakPath
            unrealPakPath = getPathInfo(unrealPakPath)['best']
            if usingDefault:
                printWarning(f'Missing or empty `unrealPakPath`. Defaulting to "{unrealPakPath}"')
        if not srcPakPath:
            srcPakPath = getPathInfo(settings.get('srcPakPath', ''))['best']
            # TODO: remove
            if not srcPakPath and False:
                printWarning(f'Missing or empty `srcPakPath`')
        if not pakingDir:
            pakingDir = settings.get('pakingDir', None)
            usingDefault = pakingDir is None
            if usingDefault:
                pakingDir = DefaultPakingDir
            pakingDir = getPathInfo(pakingDir)['best']
            if usingDefault:
                printWarning(f'Missing or empty `pakingDir`. Defaulting to "{pakingDir}"')
        if destPakNumber is None:
            destPakNumber = int(settings.get('destPakNumber', -1))
            if destPakNumber < 0:
                printWarning(f'Missing, empty, or invalid `destPakNumber`')
        if not destPakName:
            destPakName = settings.get('destPakName', '').strip()
            if not destPakName:
                printWarning(f'Missing or empty `destPakName`')

        if creatingAttachments:
            if nonInteractive:
                printWarning('Cannot create attachment definition in non-interactive mode')
            else:
                done = False
                canceled = False

                def confirmCanceled():
                    nonlocal canceled
                    canceled = True
                    return canceled

                sprintPad()
                sprint('Adding attachment definition...')
                sprintPad()
                ensureAttachmentsDir()
                while not done:
                    attachment = copy.deepcopy(Attachment.BasicAttachment)
                    attachment['modelCategory'] = ''
                    categoryOptions = {'SurvivorTorso', 'SurvivorLegs', 'SurvivorHead'}
                    while not attachment['modelCategory']:
                        attachment['modelCategory'] = sprintput(f"Model category ({', '.join(categoryOptions)}): ").strip()
                        if not attachment['modelCategory']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        if attachment['modelCategory'] not in categoryOptions:
                            esprint('ERROR: unsupported category')
                            attachment['modelCategory'] = ''

                    if canceled:
                        break

                    attachment['attachmentId'] = ''
                    while not attachment['attachmentId']:
                        attachment['attachmentId'] = sprintput('Attachment ID: ').strip()
                        if not attachment['attachmentId']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        filename = Attachment.getAttachmentFilename(attachment['attachmentId'])
                        filePath = normPath(os.path.join(ensureAttachmentsDir(), filename))
                        if os.path.exists(filePath):
                            esprint('ERROR: attachment ID already exists')
                            attachment['attachmentId'] = ''

                    if canceled:
                        break

                    attachment['displayName'] = ''
                    while not attachment['displayName']:
                        attachment['displayName'] = sprintput('Display name: ').strip()
                        if not attachment['displayName']:
                            #  allow it to be empty
                            break

                    if canceled:
                        break

                    values = getPropertyValue(attachment['attachmentData'])
                    blueprintAttachment = findNextItemByFields(
                        values,
                        [
                            ItemTypeName,
                            NameFieldName,
                        ],
                        [
                            'UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData, UAssetAPI',
                            'AttachementBlueprint',
                        ]
                    )
                    assetPath = getPropertyValue(blueprintAttachment)['AssetPath']
                    assetPath['AssetName'] = ''
                    while not assetPath['AssetName']:
                        assetPath['AssetName'] = sprintput('Blueprint path: ').strip()
                        if not assetPath['AssetName']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        if not assetPath['AssetName'].startswith('/Game/'):
                            esprint('ERROR: should start with `/Game/`')
                            assetPath['AssetName'] = ''
                            continue

                        try:
                            path = pathlib.PurePosixPath(assetPath['AssetName'])
                        except:
                            esprint('ERROR: invalid game path')
                            assetPath['AssetName'] = ''
                            continue

                        if assetPath['AssetName'].endswith('/'):
                            esprint('ERROR: should not be a directory')
                            assetPath['AssetName'] = ''
                            continue

                        stem = path.stem
                        if not stem:
                            esprint('ERROR: invalid name')
                            assetPath['AssetName'] = ''
                            continue

                        suffix = f'.{stem}_C'
                        if path.suffix:
                            if path.suffix != suffix:
                                esprint('ERROR: invalid path suffix. Should be {suffix}')
                                assetPath['AssetName'] = ''
                                continue
                        else:
                            path = path.with_name(f'{stem}{suffix}')

                        normalizedPath = path.as_posix()
                        sprint(f'Normalized path: {normalizedPath}')
                        assetPath['AssetName'] = normalizedPath

                    if canceled:
                        break

                    sprint(f'Writing to "{filePath}"')
                    if readyToWrite(filePath):
                        with open(filePath, 'w') as file:
                            yamlDump(attachment, file)
                        sprint('done.')

                    if not confirm('add another', emptyMeansNo=True):
                        done = True

                if canceled:
                    sprintPad()
                    sprint(f'Add canceled.')
                    sprintPad()

        if (inspecting or extractingAttachments or mixingAttachments or paking) and srcPakPath:
            sprintPad()
            sprint(f'Resolving source pak content directory...')
            if gameName:
                if not os.path.exists(srcPakPath):
                    if not pathlib.Path(srcPakPath).suffix:
                        srcPakPath = f'{srcPakPath}.pak'
                        printWarning(f'`srcPakPath` does not exist. Trying it with ".pak" extension ("{srcPakPath})')

                if not os.path.exists(srcPakPath):
                    printError(f'`srcPakPath` ("{srcPakPath}") does not exist')
                elif os.path.isdir(srcPakPath):
                    srcPakDir = srcPakPath
                elif pathlib.Path(srcPakPath).suffix.lower() == '.pak':
                    srcPakPathInfo = getPathInfo(srcPakPath)
                    srcPakDir = getPathInfo(os.path.join(ensurePakingDir(), srcPakPathInfo['stem']))['best']
                    sprintPad()
                    sprint(f'Unpaking "{srcPakPath}" to "{srcPakDir}')
                    if os.path.exists(unrealPakPath):
                        ensurePakingDir()
                        if readyToWrite(srcPakDir):
                            unrealUnpak(srcPakPath, srcPakDir, gameName, unrealPakPath)
                        sprint('Done unpaking.')
                        sprintPad()
                    else:
                        printError(f'`unrealPakPath` ("{unrealPakPath})" does not exist')

                if srcPakDir:
                    srcPakPathInfo = getPathInfo(srcPakDir)
                    srcPakStem = srcPakPathInfo['stem']
                    srcPakContentDir = getPakContentDir(srcPakDir, gameName)
                    sprintPad()
                    sprint(f'Reading pak content at "{srcPakContentDir}"')
                    if os.path.isdir(srcPakContentDir):
                        for pathIndex, path in enumerate(listFilesRecursively(srcPakContentDir)):
                            srcPakContentPaths.append(path)
                            suffix = pathlib.Path(path).suffix.lower()
                            if suffix in UnrealEngineCookedSplitFileExtensions:
                                resourcePath = path[:-len(suffix)]
                                if resourcePath not in srcPakContentResourcePathsMap:
                                    srcPakContentResourcePathsMap[resourcePath] = []
                                    if debug:
                                        sprint(f'Resource {len(srcPakContentResourcePathsMap)}: {resourcePath}')
                                srcPakContentResourcePathsMap[resourcePath].append(suffix)
                            if debug:
                                sprint(f'{pathIndex + 1} - {path}')
                        sprintPad()
                        sprint(f'Discovered {len(srcPakContentResourcePathsMap)} pak resources ({len(srcPakContentPaths)} files).')
                        sprintPad()
                    else:
                        printError(f'Pak content directory ("{srcPakContentDir}") does not exist')
                        srcPakContentDir = ''
            else:
                printError(f'Cannot resolve source pak content directory (missing `gameName`)')

        if (inspecting or extractingAttachments or mixingAttachments or paking) and unrealProjectDir:
            if srcPakPath and not inspecting:
                printWarning(f'Not looking for unreal project cooked content because `srcPakDir` has precedence.')
            else:
                sprintPad()
                sprint(f'Resolving unreal project cooked content directory...')
                if gameName:
                    cookedContentDir = getUnrealProjectCookedContentDir(unrealProjectDir, gameName)
                    sprintPad()
                    sprint(f'Reading cooked content at "{cookedContentDir}"')
                    if os.path.isdir(cookedContentDir):
                        for pathIndex, path in enumerate(listFilesRecursively(cookedContentDir)):
                            cookedContentPaths.append(path)
                            suffix = pathlib.Path(path).suffix.lower()
                            if suffix in UnrealEngineCookedSplitFileExtensions:
                                resourcePath = path[:-len(suffix)]
                                if resourcePath not in cookedContentResourcePathsMap:
                                    cookedContentResourcePathsMap[resourcePath] = []
                                    if debug:
                                        sprint(f'Resource {len(cookedContentResourcePathsMap)}: {resourcePath}')
                                cookedContentResourcePathsMap[resourcePath].append(suffix)
                            if debug:
                                sprint(f'{pathIndex + 1} - {path}')

                        sprintPad()
                        sprint(f'Discovered {len(cookedContentResourcePathsMap)} cooked resources ({len(cookedContentPaths)} files).')
                        sprintPad()
                    else:
                        printError(f'Cooked content directory ("{cookedContentDir}") does not exist')
                        cookedContentDir = ''
                else:
                    printError(f'Cannot resolve unreal project cooked content directory (missing `gameName`)')

        if inspecting or extractingAttachments or mixingAttachments:
            sprintPad()
            sprint(f'Resolving CustomizationItemDB path...')

            customizationItemDbPath = getPathInfo(settings.get('customizationItemDbPath', ''))['normalized']
            if not customizationItemDbPath:
                customizationItemDbPath = DefaultCustomizationItemDbPath
                printWarning(f'`customizationItemDbPath` not specified. Defaulting to: "{customizationItemDbPath}"')

            customizationItemDbContentDirRelativePath = getContentDirRelativePath(customizationItemDbPath)
            if customizationItemDbContentDirRelativePath is None:
                sprint(f'Resolved path: "{customizationItemDbPath}"')
            else:
                sprint(f'Content directory relative path detected: "{customizationItemDbPath}"')

                if not getPathInfo(customizationItemDbContentDirRelativePath)['suffixLower']:
                    customizationItemDbContentDirRelativePath = f'{customizationItemDbContentDirRelativePath}.uasset'
                    sprint(f'Adding ".uasset" suffix: "{customizationItemDbContentDirRelativePath}"')

                customizationItemDbPathUnaltered = customizationItemDbPath
                customizationItemDbPath = ''

                allowTryingAsNormalPath = False

                if not customizationItemDbPath and srcPakPath:
                    if srcPakContentDir:
                        customizationItemDbPath = getPathInfo(os.path.join(srcPakContentDir, customizationItemDbContentDirRelativePath))['best']
                        if not os.path.exists(customizationItemDbPath):
                            printWarning(f'Content dir relative path ("{customizationItemDbPath}") does not exist')
                            customizationItemDbPath = ''
                    else:
                        message = 'Content directory relative path cannot be resolved because `srcPakPath` is missing content'
                        if allowTryingAsNormalPath:
                            printWarning(message)
                        else:
                            printError(message)
                elif not customizationItemDbPath and unrealProjectDir:
                    if cookedContentDir:
                        customizationItemDbPath = getPathInfo(os.path.join(cookedContentDir, customizationItemDbContentDirRelativePath))['best']
                        if not os.path.exists(customizationItemDbPath):
                            printWarning(f'Content dir relative path ("{customizationItemDbPath}") does not exist')
                            customizationItemDbPath = ''
                    else:
                        message = 'Content directory relative path cannot be resolved because `unrealProjectDir` is missing content'
                        if allowTryingAsNormalPath:
                            printWarning(message)
                        else:
                            printError(message)

                if customizationItemDbPath:
                    sprint(f'Resolved to "{customizationItemDbPath}".')
                elif allowTryingAsNormalPath:
                    customizationItemDbPath = customizationItemDbPathUnaltered
                    printWarning(f'Trying `customizationItemDbPath` as normal file path "{customizationItemDbPath}"')

        if customizationItemDbPath:
            customizationItemDbPathInfo = getPathInfo(customizationItemDbPath)
            customizationItemDbSupportedFileTypes = ['.json', '.uasset']
            if customizationItemDbPathInfo['suffixLower'] not in customizationItemDbSupportedFileTypes:
                printError(f'Unsupported file extension for {customizationItemDbPath}: must be one of ({", ".join(customizationItemDbSupportedFileTypes)})')
            elif not os.path.isfile(customizationItemDbPath):
                printWarning(f'`customizationItemDbPath` ("{customizationItemDbPath}") does not exist')
            elif customizationItemDbPathInfo['suffixLower'] == '.json':
                customizationItemDbJsonPath = customizationItemDbPath
            elif customizationItemDbPathInfo['suffixLower'] == '.uasset':
                customizationItemDbJsonPath = getPathInfo(os.path.join(
                    settingsPathInfo['dir'],
                    f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-unaltered.json",
                ))['best']
                sprintPad()
                sprint(f'Converting "{customizationItemDbPath}" to JSON, writing "{customizationItemDbJsonPath}"')
                if os.path.exists(uassetGuiPath):
                    if readyToWrite(customizationItemDbJsonPath, overwrite=True):
                        uassetToJson(customizationItemDbPath, customizationItemDbJsonPath, uassetGuiPath)
                        sprint('Done converting.')
                        sprintPad()
                else:
                    printError(f'`uassetGuiPath` ("{uassetGuiPath})" does not exist')
                    customizationItemDbJsonPath = ''
            else:
                raise ValueError('internal error')

            if customizationItemDbJsonPath:
                with oneLinePrinter() as oneLinePrint:
                    sprintPad()
                    oneLinePrint(f'Reading CustomizationItemDB JSON from "{customizationItemDbJsonPath}"...')
                    with open(customizationItemDbJsonPath, 'r') as file:
                        customizationItemDb = json.load(file)
                    oneLinePrint('done.')

                if printingJson:
                    sprintPad()
                    sprint(jsonDump(customizationItemDb, pretty=True))
                    sprintPad()

                if printingYaml:
                    sprintPad()
                    sprint(yamlDump(customizationItemDb))
                    sprintPad()

                if writingUnalteredDb:
                    outPath = getPathInfo(os.path.join(
                        settingsDir,
                        f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-unaltered.yaml",
                    ))['best']
                    sprintPad()
                    sprint(f'Writing unaltered CustomizationItemDB to "{outPath}"')
                    if readyToWrite(outPath, overwrite=True):
                        with open(outPath, 'w') as file:
                            yamlDump(customizationItemDb, file)
                    sprint(f'Done writing.')
                    sprintPad()

        if inspecting or mixingAttachments or renamingAttachmentFiles:
            sprintPad()
            sprint(f'Reading attachments...')
            attachmentFilenames = os.listdir(ensureAttachmentsDir())
            sprintPad()
            sprint(f'Discovered {len(attachmentFilenames)} attachment files')
            if len(attachmentFilenames):
                for filenameIndex, filename in enumerate(attachmentFilenames):
                    filePath = getPathInfo(os.path.join(ensureAttachmentsDir(), filename))['best']
                    try:
                        if filename.endswith('.yaml') or filename.endswith('.json'):
                            with oneLinePrinter() as printOneLine:
                                printOneLine(f'{filenameIndex + 1} - reading {filename}...')
                                with open(filePath, 'r') as file:
                                    if filename.endswith('.yaml'):
                                        attachmentData = yaml.safe_load(file)
                                    elif filename.endswith('.json'):
                                        attachmentData = json.load(file)
                                    else:
                                        raise ValueError(f'Invalid file type: {filename}')

                                attachmentName = attachmentData['attachmentId']
                                printOneLine(f'loaded {attachmentName}.')

                            if printingJson:
                                sprintPad()
                                sprint(jsonDump(attachmentData, pretty=True))
                                sprintPad()

                            if printingYaml:
                                sprintPad()
                                sprint(yamlDump(attachmentData))
                                sprintPad()

                            categoryName = attachmentData['modelCategory']

                            if attachmentName in attachmentsToMix.get(categoryName, {}):
                                printWarning(f'duplicate attachment {attachmentName}!')

                            if categoryName not in attachmentsToMix:
                                attachmentsToMix[categoryName] = {}
                            attachmentsToMix[categoryName][attachmentName] = attachmentData

                            if renamingAttachmentFiles:
                                newFilename = Attachment.getAttachmentFilename(attachmentName)
                                if newFilename == filename:
                                    sprint(f'rename not needed (already named correctly).')
                                else:
                                    sprint(f'Renaming {filename} to {newFilename}')
                                    newFilePath = getPathInfo(os.path.join(ensureAttachmentsDir(), newFilename))['best']
                                    if os.path.exists(newFilePath):
                                        raise ValueError(f'Could not rename {filename} to {newFilename} (file already exists)')

                                    os.rename(filePath, newFilePath)
                                    attachmentsRenamed[filename] = newFilename
                    except Exception as e:
                        printError(e)
                sprint('Done loading attachments.')
                sprintPad()

            if mixingAttachments or inspecting:
                sprintPad()
                sprint('Generating exclusion rules...')
                sprintPad()
                if customizationItemDb is not None:
                    nameMapArray = customizationItemDb['NameMap']
                    nameMapSet = set(nameMapArray)

                categoryCombinationsToSkip = {}
                categoryCombinationSubsetsToSkip = {}

                setEqualitySymbol = '=='
                modelRestrictSymbol = ':'
                modelRestrictSeparator = ','

                if debug:
                    sprintPad()
                    sprint('Reading combosToSkip...')

                def logSkip(combo, baseModels=None, category=None, isExact=False, info=''):
                    if baseModels is None:
                        baseModels = []
                    def mySorted(combo):
                        if False:
                            return sorted([n for n in combo])
                        return combo
                    sprint(f"skip {f'{category} ' if (category and False) else ''}combo {'=' if isExact else '⊇'} {','.join(mySorted(combo))}: {','.join(baseModels) or '*'}{f' ({info})' if info else ''}")

                for category, combosList in settings.get('combosToSkip', {}).items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    if category not in categoryCombinationsToSkip:
                        categoryCombinationsToSkip[category] = {}

                    for comboIndex, combo in enumerate(combosList):
                        isSubset = True
                        newCombo = set()
                        baseModels = set()
                        for attachmentIndex, attachment in enumerate(combo):
                            actualAttachment = attachment

                            if modelRestrictSymbol in actualAttachment:
                                markerIndex = actualAttachment.index(modelRestrictSymbol)
                                baseModelsString = actualAttachment[markerIndex + len(modelRestrictSymbol):]
                                if baseModelsString:
                                    for modelId in baseModelsString.split(modelRestrictSeparator):
                                        baseModels.add(modelId)
                                actualAttachment = actualAttachment[:markerIndex]

                            if setEqualitySymbol in actualAttachment:
                                isSubset = False
                                markerIndex = actualAttachment.index(setEqualitySymbol)
                                actualAttachment = actualAttachment[:markerIndex]

                            checkAttachmentName(category, actualAttachment, f'combosToSkip[{comboIndex}][{attachmentIndex}]')
                            newCombo.add(actualAttachment)

                        frozenCombo = frozenset(newCombo)
                        if isSubset:
                            categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset(baseModels)
                        else:
                            categoryCombinationsToSkip[category][frozenCombo] = frozenset(baseModels)
                        if debug:
                            logSkip(frozenCombo, baseModels, isExact=not isSubset, category=category)

                if debug:
                    sprintPad()
                    sprint('Reading mutuallyExclusive...')

                for category, groups in settings.get('mutuallyExclusive', {}).items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for groupIndex, attachments in enumerate(groups):
                        attachmentsSeen = set()
                        for attachmentIndex, attachment in enumerate(attachments):
                            if attachment in attachmentsSeen:
                                printWarning(f'duplicate attachment ID (mutuallyExclusive.{category}[{groupIndex}][{attachmentIndex}])')
                            else:
                                checkAttachmentName(category, attachment, f'mutuallyExclusive.{category}[{groupIndex}][{attachmentIndex}]')
                                attachmentsSeen.add(attachment)

                        for duo in combinations(set(attachments), 2):
                            frozenDuo = frozenset(duo)
                            categoryCombinationSubsetsToSkip[category][frozenDuo] = frozenset()
                            if debug:
                                logSkip(frozenDuo, category=category)

                if debug:
                    sprintPad()
                    sprint('Reading attachmentConflicts...')

                for category, attachmentConflictsMap in settings.get('attachmentConflicts', {}).items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for attachment, conflicts in attachmentConflictsMap.items():
                        checkAttachmentName(category, attachment, f'attachmentConflicts.{category}')
                        attachmentsSeen = {attachment}
                        for conflictIndex, conflict in enumerate(conflicts):
                            if conflict in attachmentsSeen:
                                printWarning(f'duplicate attachment ID (attachmentConflicts.{category}.{attachment}[{conflictIndex}])')
                            else:
                                checkAttachmentName(category, conflict, f'attachmentConflicts.{category}.{attachment}[{conflictIndex}]')
                                frozenDuo = frozenset({attachment, conflict})
                                categoryCombinationSubsetsToSkip[category][frozenDuo] = frozenset()
                                if debug:
                                    logSkip(frozenDuo, category=category)
                                attachmentsSeen.add(conflict)

                if debug:
                    sprintPad()
                    sprint('Reading equivalentParts...')

                categoryComboEquivalentMap = {}
                for category, equivalentCombosMap in settings.get('equivalentParts', {}).items():
                    if category not in categoryComboEquivalentMap:
                        categoryComboEquivalentMap[category] = {}

                    comboEquivalentMap = categoryComboEquivalentMap[category]

                    for equivalent, groups in equivalentCombosMap.items():
                        checkAttachmentName(category, equivalent, 'equivalentParts->equivalent')
                        for groupIndex, parts in enumerate(groups):
                            frozenParts = frozenset(parts)
                            if frozenParts in comboEquivalentMap:
                                printWarning(f'duplicate group (equivalentParts.{category}.{equivalent}[{groupIndex}])')
                                continue

                            # TODO: allow group to map to multiple equivalents?
                            comboEquivalentMap[frozenParts] = equivalent

                            if category not in categoryCombinationSubsetsToSkip:
                                categoryCombinationSubsetsToSkip[category] = {}

                            partsSeen = set()
                            for partIndex, part in enumerate(parts):
                                if part in partsSeen:
                                    printWarning(f'duplicate part (equivalentParts.{equivalent}[{groupIndex}][{partIndex}])')
                                else:
                                    checkAttachmentName(category, part, f'equivalentParts.{equivalent}[{groupIndex}][{partIndex}]')
                                    for comboToSkip, baseModels in [(k, v) for k, v in categoryCombinationSubsetsToSkip[category].items()]:
                                        if part in comboToSkip and not frozenParts <= comboToSkip:
                                            # if we would skip some of an aggregate's parts (but not all) when combined with attachments A,
                                            # skip attachments A when combined with the aggregate.
                                            newCombo = set(comboToSkip)
                                            newCombo.remove(part)
                                            newCombo.add(equivalent)
                                            if len(newCombo) > 1:
                                                frozenCombo = frozenset(newCombo)
                                                categoryCombinationSubsetsToSkip[category][frozenCombo] = baseModels
                                                if debug:
                                                    logSkip(frozenCombo, baseModels, category=category)

                                    # don't allow combos that contain both an attachment and one or more of its parts
                                    frozenCombo = frozenset({equivalent, part})
                                    categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                                    if debug:
                                        logSkip(frozenCombo, category=category)
                                    partsSeen.add(part)

                if debug:
                    sprintPad()
                    sprint('Reading supersetParts...')

                for category, attachmentProperSubsetsMap in settings.get('supersetParts', {}).items():
                    for attachment, properSubsets in attachmentProperSubsetsMap.items():
                        checkAttachmentName(category, attachment, f'supersetParts->superset')
                        for groupIndex, parts in enumerate(properSubsets):
                            properSubset = frozenset(parts)

                            if True:
                                if categoryComboEquivalentMap.get(category, {}).get(properSubset, None) == attachment:
                                    printWarning(f"proper subset ({properSubset}) is also a perfect subset of {attachment}")
                                    continue

                            if category not in categoryCombinationSubsetsToSkip:
                                categoryCombinationSubsetsToSkip[category] = {}

                            for partIndex, part in enumerate(parts):
                                checkAttachmentName(category, part, f'supersetParts.{attachment}[{groupIndex}][{partIndex}]')
                                for comboToSkip, baseModels in [(k, v) for k, v in categoryCombinationSubsetsToSkip[category].items()]:
                                    if part in comboToSkip:
                                        # if we would skip a subset part when combined with other attachments,
                                        # skip the same other attachments when combined with the superset attachment
                                        newCombo = set(comboToSkip)
                                        newCombo.remove(part)
                                        newCombo.add(attachment)
                                        if len(newCombo) > 1:
                                            frozenCombo = frozenset(newCombo)
                                            categoryCombinationSubsetsToSkip[category][frozenCombo] = baseModels
                                            if debug:
                                                logSkip(frozenCombo, baseModels, category=category, info=f"{attachment} ⊃ {part}...{','.join(comboToSkip)}")

                                # don't allow combos that contain both an attachment and one or more of its proper subset parts
                                frozenCombo = frozenset({attachment, part})
                                categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                                if debug:
                                    logSkip(frozenCombo, category=category)

                if debug:
                    sprintPad()
                    sprint('Excluding equivalent combos...')

                for category, comboEquivalentMap in categoryComboEquivalentMap.items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for frozenCombo in comboEquivalentMap.keys():
                        # don't allow combos containing all the parts of an entire equivalent attachment - use the equivalent instead
                        categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                        if debug:
                            logSkip(frozenCombo, category=category)

                sprintPad()
                sprint('Exclusion rules generated.')
                sprintPad()

                if debug:
                    sprintPad()
                    sprint('categoryCombinationSubsetsToSkip:')
                    sprintPad()
                    sprint(f'{yamlDump(jsonifyDataRecursive(categoryCombinationSubsetsToSkip))}')
                    sprintPad()
                    sprint('categoryCombinationsToSkip:')
                    sprintPad()
                    sprint(f'{yamlDump(jsonifyDataRecursive(categoryCombinationsToSkip))}')
                    sprintPad()

        if (inspecting or extractingAttachments or mixingAttachments) and customizationItemDb is not None:
            exports = customizationItemDb['Exports']
            dataTableExport = findNextItemByType(exports, 'UAssetAPI.ExportTypes.DataTableExport, UAssetAPI')
            models = dataTableExport['Table']['Data']
            modelsCopy = models.copy()
            if mixingAttachments:
                models.clear()
            sprintPad()
            sprint(f'Reading {len(modelsCopy)} models...')
            for modelIndex, model in enumerate(modelsCopy):
                try:
                    modelName = getModelName(model)
                    sprintPad()
                    sprint(f'{modelIndex + 1} - reading {modelName}...')

                    modelValues = getPropertyValue(model)

                    modelIdProp = getModelIdProperty(modelValues)
                    modelId = getPropertyValue(modelIdProp)
                    if modelId != modelName:
                        printWarning(f'ID ({modelId}) does not match model name ({modelName})')

                    modelNameParts = modelName.split('_')
                    modelBaseName = modelNameParts.pop(0)
                    sprint(f'Base Name: {modelBaseName}')

                    uiDataValues = getUiDataValues(modelValues)

                    modelDisplayNameProp = getModelDisplayNameProperty(uiDataValues)
                    modelDisplayName = modelDisplayNameProp[ModelDisplayNamePropNameFieldName]
                    sprint(f"Display Name: {modelDisplayName or '(none)'}")

                    categoryEnum = findEnumByType(modelValues, ECustomizationCategoryName)
                    categoryFullName = getEnumValue(categoryEnum)

                    categoryName = categoryFullName[len(ECustomizationCategoryNamePrefix):]
                    shortCategoryName = None
                    if categoryName == 'SurvivorTorso':
                        shortCategoryName = 'Torso'
                    elif categoryName == f'SurvivorLegs':
                        shortCategoryName = 'Legs'
                    elif categoryName == f'SurvivorHead':
                        shortCategoryName = 'Head'
                    else:
                        raise ValueError(f'Unsupported customization category: {categoryFullName}')

                    sprint(f'Category: {categoryName}')

                    socketAttachments = getSocketAttachments(modelValues)
                    sprint(f'Attachments: {len(socketAttachments)}')

                    if len(socketAttachments):
                        # TODO: ignore this - it's not a reliable way of determining attachment names
                        otherNames = [n for n in modelNameParts if n.lower() not in {'torso', 'legs', 'head', 'body', 'weapon', 'outfits', 'charm'}]
                        otherNamesString = '_'.join(otherNames)
                        attachmentNames = otherNamesString.split(importAttachmentsSeparator) if otherNamesString else []

                        if debug:
                            sprint(f"Potential attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        attachmentDisplayNamesString = ''
                        openParenIndex = modelDisplayName.find('(')
                        if openParenIndex > -1:
                            closeParenIndex = modelDisplayName.find(')', openParenIndex + 1)
                            if closeParenIndex > -1:
                                attachmentDisplayNamesString = modelDisplayName[openParenIndex + 1:closeParenIndex]

                        if debug:
                            sprint(f'Potential attachments display names string: {attachmentDisplayNamesString}')

                        attachmentDisplayNames = attachmentDisplayNamesString.split(', ') if attachmentDisplayNamesString else []
                        if debug:
                            sprint(f"Potential attachments display names: {', '.join(attachmentDisplayNames) if attachmentDisplayNames else '(unknown)'}")

                        if (
                            len(attachmentDisplayNames) == len(socketAttachments)
                            or (len(attachmentDisplayNames) > 1 and len(socketAttachments) == 1)
                        ):
                            attachmentNames = [''.join([word.capitalize() for word in displayName.split()]) for displayName in attachmentDisplayNames]
                            # TODO: try to handle cases with aggregate attachments?
                            if len(attachmentDisplayNames) > 1 and len(socketAttachments) == 1:
                                attachmentNames = ['And'.join(attachmentNames)]
                                attachmentDisplayNames = [', '.join(attachmentDisplayNames)]

                        if len(attachmentNames) != len(socketAttachments):
                            attachmentNames = []

                        if len(attachmentDisplayNames) != len(socketAttachments):
                            attachmentDisplayNames = []

                        if debug:
                            sprint(f"Synthesized attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        if extractingAttachments:
                            for attachmentIndex, attachmentData in enumerate(socketAttachments):
                                if attachmentIndex < len(attachmentNames):
                                    attachmentId = attachmentNames[attachmentIndex]
                                elif otherNamesString:
                                    attachmentId = f'{otherNamesString}_{attachmentIndex}'
                                else:
                                    attachmentId = f'{modelIndex}_{attachmentIndex}'

                                if attachmentIndex < len(attachmentDisplayNames):
                                    attachmentDisplayName = attachmentDisplayNames[attachmentIndex]
                                else:
                                    attachmentDisplayName = f'{otherNamesString}_{attachmentIndex}'

                                filename = f'SocketAttachment_{modelBaseName}_{shortCategoryName}_{attachmentId}.yaml'
                                filePath = getPathInfo(os.path.join(ensureAttachmentsDir(), filename))['best']

                                if os.path.exists(filePath):
                                    printWarning(f'Skipping attachment {attachmentIndex + 1} (file already exists): "{filePath}"', pad=False)
                                else:
                                    sprint(f'Exporting attachment {attachmentIndex + 1}: {attachmentId} ({attachmentDisplayName}) to "{filePath}"')

                                    attachmentInfo = {
                                        'attachmentId': attachmentId,
                                        'modelCategory': categoryName,
                                        'displayName': attachmentDisplayName,
                                        'attachmentData': attachmentData,
                                    }

                                    with open(filePath, 'w') as file:
                                        yamlDump(attachmentInfo, file)

                                    attachmentsCreated.append(filePath)
                    elif mixingAttachments:
                        models.append(model)
                        if categoryName in attachmentsToMix:
                            modelDisplayNameBase = modelDisplayName
                            openParenIndex = modelDisplayName.find('(')
                            if openParenIndex > -1:
                                closeParenIndex = modelDisplayName.find(')', openParenIndex + 1)
                                if closeParenIndex > -1:
                                    modelDisplayNameBase = modelDisplayName[:openParenIndex].rstrip()

                            comboCount = 0

                            attachmentsForCategory = attachmentsToMix[categoryName]
                            sprintPad()
                            sprint(f'Mixing {len(attachmentsForCategory)} attachments into combinations...')
                            sprintPad()
                            for r in range(1, len(attachmentsForCategory) + 1):
                                # TODO: use names instead of values in combinations()
                                for combo in combinations(attachmentsForCategory.values(), r):
                                    attachmentIds = [a['attachmentId'] for a in combo]

                                    attachmentIdsSet = frozenset(attachmentIds)

                                    shouldSkipCombo = False
                                    if not shouldSkipCombo:
                                        baseModels = categoryCombinationsToSkip.get(categoryName, {}).get(attachmentIdsSet, None)
                                        if baseModels is not None:
                                            if len(baseModels) == 0 or modelBaseName in baseModels:
                                                shouldSkipCombo = True

                                    if not shouldSkipCombo:
                                        for combosToSkip, baseModels in categoryCombinationSubsetsToSkip.get(categoryName, {}).items():
                                            if (len(baseModels) == 0 or modelBaseName in baseModels) and combosToSkip <= attachmentIdsSet:
                                                shouldSkipCombo = True
                                                break

                                    if shouldSkipCombo:
                                        if modelBaseName not in combinationsSkipped:
                                            combinationsSkipped[modelBaseName] = {}
                                        if categoryName not in combinationsSkipped[modelBaseName]:
                                            combinationsSkipped[modelBaseName][categoryName] = set()
                                        combinationsSkipped[modelBaseName][categoryName].add(attachmentIdsSet)
                                        continue

                                    if modelBaseName not in combinationsAdded:
                                        combinationsAdded[modelBaseName] = {}
                                    if categoryName not in combinationsAdded[modelBaseName]:
                                        combinationsAdded[modelBaseName][categoryName] = set()
                                    combinationsAdded[modelBaseName][categoryName].add(attachmentIdsSet)
                                    comboCount += 1

                                    attachmentNamesString = exportAttachmentsSeparator.join(attachmentIds)
                                    attachmentDisplayNamesString = ', '.join([getAttachmentDisplayName(a) for a in combo])
                                    newModelDisplayName = f'{modelDisplayNameBase} ({attachmentDisplayNamesString})'
                                    if True:
                                        attachmentNamesHashed = md5Hash(attachmentNamesString).upper()
                                        newModelId = f'{modelBaseName}_{shortCategoryName}_{attachmentNamesHashed}'
                                    else:
                                        # TODO: use UUID instead?
                                        newModelId = f'{modelBaseName}_{shortCategoryName}_{attachmentNamesString}'
                                    # TODO: warn if this ID has already been used
                                    sprint(f"Making combo: {', '.join(attachmentIds)}")
                                    newModel = copy.deepcopy(model)
                                    newModelValues = getPropertyValue(newModel)
                                    newModelIdProp = getModelIdProperty(newModelValues)
                                    setPropertyValue(newModelIdProp, newModelId)
                                    setModelName(newModel, newModelId)

                                    newUiDataValues = getUiDataValues(newModelValues)

                                    newModelDisplayNameProp = getModelDisplayNameProperty(newUiDataValues)
                                    newModelDisplayNameProp[ModelDisplayNamePropNameFieldName] = newModelDisplayName

                                    if False:
                                        newModelDisplayNameProp[ValueFieldName] = generateRandomHexString(32).upper()
                                    elif False:
                                        # TODO: use same algorithm unreal engine uses - this is not identical, but it seems to do the trick anyway
                                        newModelDisplayNameProp[ValueFieldName] = sha256Hash(newModelDisplayName.lower()).upper()
                                    else:
                                        newModelDisplayNameProp[ValueFieldName] = md5Hash(newModelDisplayName.lower()).upper()

                                    newSocketAttachmentsStruct = findSocketAttachmentsStruct(newModelValues)
                                    newSocketAttachmentsStruct.pop('DummyStruct', None)
                                    newSocketAttachments = getPropertyValue(newSocketAttachmentsStruct)

                                    for attachment in combo:
                                        newSocketAttachments.append(attachment['attachmentData'])
                                        # TODO: remove
                                        if False:
                                            addAllToNameMap(attachment['attachmentData'], nameMapSet)

                                    # TODO: alter model icons and descriptions if specified

                                    models.append(newModel)
                                    # TODO: remove
                                    if False:
                                        nameMapSet.add(newModelId)
                            sprint(f'Created {comboCount} combos')
                            sprintPad()
                except Exception as e:
                    printError(e)

            sprintPad()
            sprint('Models processed.')
            sprintPad()

            if mixingAttachments and customizationItemDb is not None:
                nameMapArrayCopy = nameMapArray.copy()
                nameMapArray.clear()
                nameMapSet.clear()
                addAllToNameMap(customizationItemDb.get('Imports', []), nameMapSet)
                addAllToNameMap(customizationItemDb.get('Exports', []), nameMapSet)

                if True:
                    # could other names be required?
                    for name in {
                        'EnumProperty',
                        'TextProperty',
                        'ObjectProperty',
                        'BoolProperty',
                        'UInt32Property',
                        'MapProperty',
                        'IntProperty',
                        'ArrayProperty',
                    }:
                        nameMapSet.add(name)

                # TODO: remove? doesn't seem to be required
                if False:
                    customizationItemDbName = next((name for name in nameMapArrayCopy if name.startswith('/Game/Data/Dlc/') and name.endswith('/CustomizationItemDB')), None)
                    if customizationItemDbName:
                        nameMapSet.add(customizationItemDbName)

                for name in nameMapSet:
                    nameMapArray.append(name)
                nameMapArray.sort(key=lambda v: v.upper())

                nameMapSetOld = set(nameMapArrayCopy)

                nameMapNamesRemoved = nameMapSetOld - nameMapSet
                nameMapNamesAdded = nameMapSet - nameMapSetOld

                if debug:
                    sprintPad()
                    sprint(f'NameMap names removed:')
                    sprint(yamlDump(jsonifyDataRecursive(nameMapNamesRemoved)))
                    sprintPad()

                if debug:
                    sprintPad()
                    sprint(f'NameMap names added:')
                    sprint(yamlDump(jsonifyDataRecursive(nameMapNamesAdded)))
                    sprintPad()

                if writingAlteredDb:
                    jsonOutPath = getPathInfo(os.path.join(
                        settingsDir,
                        f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.json",
                    ))['best']
                    sprintPad()
                    sprint(f'Writing altered CustomizationItemDB to "{jsonOutPath}"')
                    if readyToWrite(jsonOutPath, overwrite=True):
                        with open(jsonOutPath, 'w') as file:
                            jsonDump(customizationItemDb, file)
                        sprint('Done.')
                    sprintPad()

                    if customizationItemDbPathInfo['suffixLower'] == '.uasset':
                        sprintPad()
                        sprint(f'Writing altered CustomizationItemDB to "{customizationItemDbPath}"')
                        if os.path.exists(uassetGuiPath):
                            if readyToWrite(customizationItemDbPath):
                                jsonToUasset(jsonOutPath, customizationItemDbPath, uassetGuiPath)
                                sprint('Done.')
                        else:
                            printError(f'`uassetGuiPath` ("{uassetGuiPath})" does not exist')
                        sprintPad()

                    # TODO: this should be optional
                    if True:
                        yamlOutPath = getPathInfo(os.path.join(
                            settingsDir,
                            f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.yaml",
                        ))['best']
                        sprintPad()
                        sprint(f'Writing altered CustomizationItemDB to "{yamlOutPath}"')
                        if readyToWrite(yamlOutPath, overwrite=True):
                            with open(yamlOutPath, 'w') as file:
                                yamlDump(customizationItemDb, file)
                            sprint('Done.')
                        sprintPad()

        if paking or inspecting:
            sprintPad()
            sprint(f'Analyzing target pak configuration...')
            if destPakNumber >= 0 or destPakName or settings.get('destPakResources', []) or srcPakStem:
                if destPakNumber < 0 and srcPakStem:
                    match = getPakchunkFilenameRegex().match(srcPakStem)
                    if match:
                        newDestPakNumber = int(match.group('number'))
                        newDestPakName = match.group('name')
                        newDestPlatform = match.group('platform')
                        if newDestPakNumber != destPakNumber:
                            destPakNumber = newDestPakNumber
                            printWarning(f'Overriding missing or invalid `destPakNumber` with "{destPakNumber}" from `srcPakPath`')
                        if newDestPakName != destPakName:
                            destPakName = newDestPakName
                            printWarning(f'Overriding `destPakName` with "{destPakName}" from `srcPakPath`')
                        if newDestPlatform != destPlatform:
                            destPlatform = newDestPlatform
                            printWarning(f'Overriding `destPlatform` with "{destPlatform}" from `srcPakPath`')

                if destPakNumber < 0:
                    message = f'Missing or invalid `destPakNumber`'
                    if paking:
                        printError(message)
                    else:
                        printWarning(message)
                elif not destPakName:
                    printWarning(f'Missing `destPakName`')

                if destPakNumber >= 0:
                    destPakStem = f'pakchunk{destPakNumber}{destPakName}-{destPlatform}'
                    destPakDir = getPathInfo(os.path.join(ensurePakingDir(), destPakStem))['best']

                    sprintPad()
                    sprint(f'Destination pak: "{destPakDir}"')
                    sprintPad()

                    if gameName:
                        destPakContentDir = getPakContentDir(destPakDir, gameName)
                    else:
                        message = f'Cannot resolve destination pak content directory (missing `gameName`)'
                        if paking:
                            printError(message)
                        else:
                            printWarning(message)

                    destPakFilename = f'{destPakStem}.pak'
                    destPakPath = getPathInfo(os.path.join(ensurePakingDir(), destPakFilename))['best']

                destPakResources = [getPathInfo(p)['normalized'] for p in settings.get('destPakResources', [])]
                if not destPakResources:
                    printWarning(f'No resources configured for paking (empty or missing `destPakResources`)')

                if srcPakPath:
                    srcResourcePathMap = srcPakContentResourcePathsMap
                    srcContentDir = srcPakContentDir
                elif unrealProjectDir:
                    srcResourcePathMap = cookedContentResourcePathsMap
                    srcContentDir = cookedContentDir
                else:
                    srcResourcePathMap = {}
                    srcContentDir = ''

                shouldSearchForSrcResources = True

                if not srcContentDir:
                    message = f'Missing source content directory for paking'
                    if paking:
                        printError(message)
                        shouldSearchForSrcResources = False
                    else:
                        printWarning(message)

                if shouldSearchForSrcResources:
                    sprintPad()
                    sprint(f'Searching "{srcContentDir}" for {len(destPakResources)} resources to pak')

                    srcResourceCount = 0
                    srcFileCount = 0

                    missingResources = False
                    for resource in destPakResources:
                        if resource not in srcResourcePathMap:
                            missingResources = True
                            message = f'Missing "{resource}" from "{srcContentDir}"'
                            if paking:
                                printError(message)
                            else:
                                printWarning(message)
                        else:
                            srcResourceCount += 1
                            srcFileCount += len(srcResourcePathMap[resource])

                    sprintPad()
                    sprint(f'Found {srcResourceCount} resources ({srcFileCount} files).')
                    sprintPad()

                    if paking and not missingResources:
                        if not destPakContentDir:
                            printError(f'Cannot create pak because destination content directory is missing')
                        else:
                            assert destPakDir
                            sprintPad()
                            sprint(f'Copying {srcFileCount} files from "{srcContentDir}" to "{destPakContentDir}"')
                            ensurePakingDir()
                            sameDir = srcPakDir == destPakDir
                            if sameDir:
                                printWarning(f'Source and destination pak directory is the same. Files not in resource list will be removed.')
                            if readyToWrite(destPakDir, delete=not sameDir):
                                def writeFiles(srcContentDir):
                                    ensureDir(destPakContentDir, warnIfNotExist=False)
                                    for resource in destPakResources:
                                        for extension in srcResourcePathMap[resource]:
                                            relFilePath = f'{resource}{extension}'
                                            srcPath = normPath(os.path.join(srcContentDir, relFilePath))
                                            destPathFileInfo = getPathInfo(os.path.join(destPakContentDir, relFilePath))
                                            ensureDir(destPathFileInfo['dir'], warnIfNotExist=False)
                                            destPath = destPathFileInfo['best']
                                            sprint(f'Copying file to "{destPath}"')
                                            shutil.copy(srcPath, destPath)

                                if sameDir:
                                    with tempfile.TemporaryDirectory(
                                        dir=pakingDir,
                                        prefix=f'{destPakStem}_',
                                    ) as tempDir:
                                        printWarning(f'Creating temporary source pak directory ("{tempDir}") for file copying')
                                        os.rmdir(tempDir)
                                        shutil.move(srcPakDir, tempDir)
                                        assert gameName
                                        try:
                                            writeFiles(getPakContentDir(tempDir, gameName))
                                        except Exception as e:
                                            if not nonInteractive and debug:
                                                printError(e)
                                                promptToContinue(f'to open src content dir "{tempDir}"')
                                                osOpenDir(tempDir)
                                                promptToContinue()
                                            raise e
                                else:
                                    writeFiles(srcContentDir)

                                assert destPakPath
                                sprintPad()
                                sprint(f'Paking "{destPakDir}" into "{destPakPath}"')
                                if os.path.exists(unrealPakPath):
                                    unrealPak(destPakDir, destPakPath, unrealPakPath)
                                    sprint(f'Done paking.')
                                else:
                                    printError(f'`unrealPakPath` ("{unrealPakPath})" does not exist')
                                sprintPad()
        if installingMods or inspecting:
            sprintPad()
            sprint(f'Analyzing mod configuration...')
            sprintPad()
            sprint(f'Resolving game Paks directory path...')
            if not gameDir:
                message = f'Cannot resolve game Paks folder (missing `gameDir`)'
                if installingMods:
                    printError(message)
                else:
                    printWarning(message)

            if not gameName:
                message = f'Cannot resolve game Paks folder (missing `gameName`)'
                if installingMods:
                    printError(message)
                else:
                    printWarning(message)

            reservedPakchunks = [p.lower() for p in settings.get('reservedPakchunks', [])]
            if not reservedPakchunks:
                printWarning(f'Missing or empty `reservedPakchunks`')

            if gameDir and gameName:
                gamePaksDir = getGamePaksDir(gameDir, gameName)
                sprint(f'Resolved.')
                sprintPad()
                sprint(f'Scanning "{gamePaksDir}" for pakchunk files...')
                allPakchunks = []
                loggingReserved = debug
                for relPath in listFilesRecursively(gamePaksDir):
                    relPathPathInfo = getPathInfo(relPath, gamePaksDir)
                    if relPathPathInfo['basename'].lower().startswith('pakchunk'):
                        allPakchunks.append(relPath)
                        reserved = relPath.lower() in reservedPakchunks
                        if not reserved:
                            gamePakchunks.append(relPath)
                        if not reserved or loggingReserved:
                            sprint(f'{len(allPakchunks if loggingReserved else gamePakchunks)} - {relPath}{" -- RESERVED" if reserved else ""}')
                    else:
                        printWarning(f'Non-pakchunk file in Paks folder: "{relPath}"')
                sprint('Done.')
                sprintPad()
                sprint(f'Discovered {len(allPakchunks)} pakchunks ({len(allPakchunks) - len(gamePakchunks)} reserved, {len(gamePakchunks)} configurable)')

            sprintPad()
            sprint(f'Scanning "{pakingDir}" for available pakchunks...')
            ensurePakingDir()
            for entry in os.scandir(pakingDir):
                if entry.name.lower().startswith('pakchunk') and entry.name.lower().endswith('.pak'):
                    if entry.name not in pakingDirPakchunks:
                        pakingDirPakchunks.append(entry.name)
                        sprint(f'{len(pakingDirPakchunks)} - {entry.name}')
            sprint('Done.')
            sprintPad()
            sprint(f'Discovered {len(pakingDirPakchunks)} pakchunks.')
            sprintPad()
            sprint(f'Calculating mods to be active...')

            modGroupNamePakchunksMap = settings.get('modGroups', {})
            modConfigNameGroupsMap = settings.get('modConfigs', {})
            modActiveConfigName = settings.get('modConfig', '')

            hasError = False
            if not modActiveConfigName:
                printWarning('No active mod config (missing `modConfig`)')
            else:
                sprintPad()
                sprint(f'Active config: "{modActiveConfigName}"')
                if modActiveConfigName not in modConfigNameGroupsMap:
                    printError(f'Missing mod config "{modActiveConfigName}" in `modConfigs`')
                    hasError = True
                else:
                    for groupName in modConfigNameGroupsMap[modActiveConfigName]:
                        if groupName not in modGroupNamePakchunksMap:
                            printError(f'Missing mod group "{groupName}" in `modGroups`')
                            hasError = True
                        else:
                            for pakchunkIndex, pakchunk in enumerate(modGroupNamePakchunksMap[groupName]):
                                modConfigPath = f'groups.{groupName}[{pakchunkIndex + 1}]: {pakchunk}'
                                if pakchunk in modsToBeActive:
                                    printWarning(f'Already added mod to be active: {modConfigPath}')
                                else:
                                    modsToBeActive.append(pakchunk)
                                    sprint(f'{len(modsToBeActive)} - {modConfigPath}')

            if gamePaksDir:
                sprintPad()
                sprint(f'Locating pakchunk sources...')
                notFoundPakchunks = []
                pakchunkSourceMap = {}
                gamePakchunkFilenameRelPathMap = {}
                for relPath in gamePakchunks:
                    filename = os.path.basename(relPath)
                    gamePakchunkFilenameRelPathMap[filename] = relPath

                for relPath in modsToBeActive:
                    filename = os.path.basename(relPath)
                    if filename in pakingDirPakchunks:
                        pakchunkSourceMap[relPath] = source = normPath(os.path.join(pakingDir, filename))
                    elif filename in gamePakchunkFilenameRelPathMap:
                        pakchunkSourceMap[relPath] = source = normPath(os.path.join(gamePaksDir, gamePakchunkFilenameRelPathMap[filename]))
                    else:
                        printError(f'Pakchunk (to install) not found: {filename}')
                        hasError = True
                        notFoundPakchunks.append(filename)
                        source = None

                    if source is not None and debug:
                        sprint(f'"{relPath}" <- "{source}"')

                pakchunksToActivate = [p for p in modsToBeActive if p not in gamePakchunks]
                sprintPad()
                sprint(f'Pakchunks to activate: {len(pakchunksToActivate)}')
                for i, pakchunkRelPath in enumerate(pakchunksToActivate):
                    sprint(f'{i + 1} - {pakchunkRelPath}')

                pakchunksToDeactivate = [p for p in gamePakchunks if p not in modsToBeActive]
                sprintPad()
                sprint(f'Pakchunks to deactivate: {len(pakchunksToDeactivate)}')
                for i, pakchunkRelPath in enumerate(pakchunksToDeactivate):
                    sprint(f'{i + 1} - {pakchunkRelPath}')

                if not hasError and installingMods:
                    dryRun = False

                    noChanges = True

                    sprintPad()
                    sprint(f'Moving mods between "{pakingDir}" and "{gamePaksDir}"...')
                    for pakchunkRelPath in modsToBeActive:
                        source = pakchunkSourceMap[pakchunkRelPath]
                        dest = normPath(os.path.join(gamePaksDir, pakchunkRelPath))
                        if not os.path.exists(dest) or not os.path.samefile(source, dest):
                            sprint(f'Moving "{source}" to "[Paks]/{pakchunkRelPath}"')
                            if not dryRun:
                                if readyToWrite(dest):
                                    shutil.move(source, dest)
                                    noChanges = False
                                else:
                                    printWarning(f'Not allowed to overwrite "{pakchunkRelPath}"')

                    for pakchunkRelPath in pakchunksToDeactivate:
                        filename = os.path.basename(pakchunkRelPath)
                        source = normPath(os.path.join(gamePaksDir, pakchunkRelPath))
                        dest = normPath(os.path.join(pakingDir, filename))
                        if filename in pakingDirPakchunks:
                            sprint(f'Removing "[Paks]/{pakchunkRelPath}" which is also stored at "{dest}"')
                            if not dryRun:
                                if readyToWrite(source):
                                    pathlib.Path.unlink(source)
                                    noChanges = False
                        else:
                            sprint(f'Moving "{pakchunkRelPath}" to "{dest}"')
                            if not dryRun:
                                shutil.move(source, dest)
                                noChanges = False

                    if dryRun:
                        sprint('Done.')
                    else:
                        sprint(f'Installation succeeded{" - no changes" if noChanges else ""}.')
                    sprintPad()
    except Exception as e:
        printError(e)
        # TOOD: only for testing
        if False:
            raise e

    outputInfo = {
        'warnings': warnings,
        'errors': errors,
        'discoveredSettingsFiles': discoveredSettingsFiles,
        'srcContentDir': srcContentDir,
        'destPakNumber': destPakNumber,
        'destPakName': destPakName,
        'destPlatform': destPlatform,
        'destPakDir': destPakDir,
        'destPakPath': destPakPath,
        'srcPakContentDir': srcPakContentDir,
        'srcPakContentResources': list(srcPakContentResourcePathsMap.keys()),
        'srcPakContentFiles': srcPakContentPaths,
        'attachmentsRead': {category: list(attachmentDataMap.keys()) for category, attachmentDataMap in attachmentsToMix.items()},
        'attachmentsRenamed': attachmentsRenamed,
        'attachmentsCreated': attachmentsCreated,
        'combosAdded': combinationsAdded,
        'combosSkipped': combinationsSkipped,
        'nameMapAlterations': {
            'namesRemoved': nameMapNamesRemoved,
            'namesAdded': nameMapNamesAdded,
        },
        'pakingDirPakchunks': pakingDirPakchunks,
        'gamePaksDir': gamePaksDir,
        'gamePakchunks': gamePakchunks,
        'modsToBeActive': modsToBeActive,
        'cookedContentDir': cookedContentDir,
        'cookedContentResources': list(cookedContentResourcePathsMap.keys()),
        'cookedContentFiles': cookedContentPaths,
    }

    outputInfoFilename = getResultsFilePath(settingsFilePath)
    sprintPad()
    sprint(f'Writing command results to "{outputInfoFilename}"')
    # TODO: should we overwrite result file without confirming?
    if readyToWrite(outputInfoFilename, overwrite=True):
        with open(outputInfoFilename, 'w') as file:
            yamlDump(jsonifyDataRecursive(outputInfo), file)
    sprintPad()

    if openingGameLauncher and gameDir:
        sprintPad()
        sprint('Opening game launcher and starting game if not already running (exit the launcher to return)...')
        if nonInteractive:
            printError('Cannot open game launcher in non-interactive mode')
        else:
            warningOfLauncherClearScreen = sprintRecording is None
            if (
                warningOfLauncherClearScreen
                and overwriteOverride is not True
                and (
                    listingInfo
                    or extractingAttachments
                    or renamingAttachmentFiles
                    or creatingAttachments
                    or mixingAttachments
                    or paking
                    or installingMods
                )
            ):
                shouldProceed = confirm('open the launcher and clear the screen buffer history', pad=True)
            else:
                shouldProceed = True

            if shouldProceed:
                gameIsRunning = getGameIsRunning()
                try:
                    exitCode = openGameLauncher(getPathInfo(gameDir)['best'], startGame=not getGameIsRunning())
                    # clear any last bits of the launcher output left over
                    os.system('cls')
                    replaySprintRecording()
                except Exception as e:
                    printError(e)
                finally:
                    clearSprintRecording()
        sprintPad()

    return exitCode

def reportAmbigous(commands, token):
    Quote = '"'
    tokenLower = token.lower()

    def highlightedCommand(command):
        commandName = command['name']
        commandNameLower = commandName.lower()
        startIndex = commandNameLower.index(tokenLower)
        firstPart = commandName[:startIndex]
        lastPart = commandName[(startIndex + len(token)):]
        return f"{firstPart}{token.upper()}{lastPart}"

    esprint(f'"{token}" could be {" | ".join([highlightedCommand(c) for c in commands])}.')
    esprint('Type more of the word.')

def parseCommandFromToken(token):
    command = None

    tokenLower = token.lower()

    if not command:
        command = commandNumberMap.get(token, None)

    if not command:
        command = next((c for c in commandMap.values() if c['name'].lower() == tokenLower), None)

    if not command:
        commandMatches = [c for c in commandMap.values() if tokenLower in c['name'].lower()]
        if len(commandMatches) > 0:
            if len(commandMatches) == 1:
                command = commandMatches[0]
            else:
                command = commandMatches

    return command

if __name__ == '__main__':
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser(
        prog='DbdSocketsMixer',
        description='''Mixes socket attachments with character models.

Can also extract socket attachment definitions from a CustomizationItemDB.
A YAML settings file specifies the input CustomizationItemDB file and the
mix options.

UAssetGUI can be used to export a CustomizationItemDB.uasset file to JSON.
DbdSocketsMixer reads that JSON file and writes an altered version that
can be converted back to the original uasset file using UAssetGUI.
        ''',
    )
    parser.add_argument(
        'settingsFilePath',
        help=f'path to settings YAML file (defaults to `{getPathInfo(DefaultSettingsPath)["best"]}`)',
        type=str,
        nargs='?',
    )
    parser.add_argument(
        '--uassetGuiPath',
        help=f'path to UAssetGUI.exe (defaults to `{getPathInfo(DefaultUAssetGUIPath)["best"]}`)',
        type=str,
    )
    parser.add_argument(
        '--unrealPakPath',
        help=f'path to UnrealPak.exe (defaults to `{getPathInfo(DefaultUnrealPakPath)["best"]}`)',
        type=str,
    )
    parser.add_argument(
        '--list',
        help='list, inspect, and compute various data',
        action='store_true',
    )
    parser.add_argument(
        '--extract',
        help='extract socket attachment definitions',
        action='store_true',
    )
    parser.add_argument(
        '--create',
        help='create socket attachment definitions interactively',
        action='store_true',
    )
    parser.add_argument(
        '--rename',
        help='rename attachment files to match their corresponding attachment ID (IDs should be globally unique)',
        action='store_true',
    )
    parser.add_argument(
        '--mix',
        help='mix socket attachments with character models',
        action='store_true',
    )
    parser.add_argument(
        '--pak',
        help='pak content into pakchunk',
        action='store_true',
    )
    parser.add_argument(
        '--install',
        help='intall active mod configuration into the game',
        action='store_true',
    )
    parser.add_argument(
        '--launch',
        help='open game launcher',
        action='store_true',
    )
    parser.add_argument(
        '--kill',
        help='kill running game',
        action='store_true',
    )
    parser.add_argument(
        '-ni',
        help='run in non-interactive mode',
        action='store_true',
    )
    parser.add_argument(
        '--debug',
        help='output extra debug info to the console',
        action='store_true',
    )
    parser.add_argument(
        '--overwrite',
        help='force or prevent file overwrites without prompting',
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )
    args = parser.parse_args()

    if args.ni:
        sprint('Running in non-interactive mode.')

    exitCode = 0

    if (
        not args.list
        and not args.extract
        and not args.create
        and not args.rename
        and not args.mix
        and not args.pak
        and not args.install
        and not args.launch
        and not args.kill
        and not args.ni
    ):
        sprint('Welcome to DbdSocketsMixer!')
        sprintPad()
        sprint('You can run one or more command targets by entering menu numbers or any part of the command name')

        menuSettingsPath = '.menu_settings.yaml'
        menuSettings = {}
        if os.path.isfile(menuSettingsPath):
            try:
                with open(menuSettingsPath, 'r') as file:
                    menuSettings = yaml.safe_load(file)
            except Exception as e:
                sprintPad()
                esprint(e)
                sprintPad()

        def saveMenuSettings():
            try:
                with open(menuSettingsPath, 'w') as file:
                    yamlDump(menuSettings, file)
                return True
            except Exception as e:
                sprintPad()
                esprint(e)
                sprintPad()

        settingsFilePath = getPathInfo(args.settingsFilePath or menuSettings.get('settingsFilePath', DefaultSettingsPath))['best']
        uassetGuiPath = getPathInfo(args.uassetGuiPath or menuSettings.get('uassetGuiPath', ''))['best']
        debug = args.debug or menuSettings.get('debug', False)
        overwriteOverride = args.overwrite if args.overwrite is not None else menuSettings.get('overwriteOverride', None)

        actionsMap = {action.dest: action for action in parser._actions}

        availableCommandNames = [c for c in actionsMap.keys() if c not in {'ni', 'uassetGuiPath', 'unrealPakPath'}]
        availableCommandNames.insert(availableCommandNames.index('list') + 1, 'folder')
        availableCommandNames.insert(availableCommandNames.index('folder') + 1, 'editSettings')
        availableCommandNames.insert(availableCommandNames.index('editSettings') + 1, 'results')
        availableCommandNames.append('quit')
        commandMap = {c: { 'name': c, 'number': i + 1, 'action': actionsMap.get(c, None) } for i, c in enumerate(availableCommandNames)}
        commandNumberMap = {str(c['number']): c for c in commandMap.values()}

        showingMenu = True
        menuSettingsDirty = False

        while True:
            listingInfo = False
            creating = False
            extracting = False
            renaming = False
            mixing = False
            paking = False
            installing = False
            launching = False
            killingGame = False

            exitCode = 0

            if not showingMenu:
                showingMenu = True
            else:
                showServerRunning = False
                showGameRunning = False
                if showServerRunning:
                    gameServerRunning = getGameServerIsRunning()
                if showGameRunning:
                    gameRunning = getGameIsRunning()

                sprintPad()
                sprint(f"Settings file: {settingsFilePath or '<Not specified>'}")
                # TODO: remove
                if False:
                    sprint(f"UAssetGUI path: {uassetGuiPath or '<Read from settings or use default>'}")
                sprint(f"Debug mode: {'on' if debug else 'off'}")
                sprint(f"Overwrite mode: {'overwrite' if overwriteOverride else 'no overwrite' if overwriteOverride is False else 'prompt'}")
                if showServerRunning:
                    sprint(f'Game server running: {"yes" if gameServerRunning else "no"}')
                if showGameRunning:
                    sprint(f'Game running: {"yes" if gameRunning else "no"}')

                sprintPad()

                for commandName in availableCommandNames:
                    command = commandMap[commandName]
                    if commandName == 'help':
                        help = 'show help page'
                    elif commandName == 'version':
                        help = "show program version"
                    elif commandName == 'settingsFilePath':
                        help = f"{'change' if settingsFilePath else 'set'} {command['action'].help}"
                    elif commandName == 'uassetGuiPath':
                        help = f"{'change' if uassetGuiPath else 'set'} {command['action'].help}"
                    elif commandName == 'quit':
                        help = "quit program"
                    elif commandName == 'debug':
                        help = f"turn {'off' if debug else 'on'} debug flag ({'do not ' if debug else ''}{command['action'].help})"
                    elif commandName == 'overwrite':
                        help = f"switch overwrite mode ({command['action'].help})"
                    elif commandName == 'folder':
                        help = f'open settings folder in explorer'
                    elif commandName == 'editSettings':
                        help = f'open settings in editor'
                    elif commandName == 'results':
                        help = f'open command results in editor'
                    elif command['action'] is not None:
                        help = command['action'].help
                    else:
                        help = commandName

                    sprint(f"[ {command['number']} ] {commandName[0].upper()}{commandName[1:]} - {help}")
                sprintPad()

            if menuSettingsDirty:
                if saveMenuSettings():
                    menuSettingsDirty = False

            sprintPad()
            response = sprintput('Selection: ').strip()
            sprintPad()

            shouldPromptToContinue = False
            showingSeparator = True
            shouldQuit = False
            commands = []

            tokens = response.split()
            hasError = False
            results = [parseCommandFromToken(token) for token in tokens]

            # TODO: remove
            if False:
                sprintPad()
                sprintP(results)
                sprintPad()

            invalidTokens = []
            ambiguousMap = {}
            for token, result in zip(tokens, results):
                if isinstance(result, dict):
                    commands.append(result)
                elif isinstance(result, list):
                    ambiguousMap[token] = result
                    hasError = True
                else:
                    if token not in invalidTokens:
                        invalidTokens.append(token)
                        hasError = True

            if hasError:
                sprintSeparator()
                if invalidTokens:
                    sprintPad()
                    sprint(f'Invalid token(s): {" | ".join(invalidTokens)}')
                    sprintPad()

                if ambiguousMap:
                    for token, commandNames in ambiguousMap.items():
                        sprintPad()
                        reportAmbigous(commandNames, token)
                        sprintPad()

                commands = []
                showingMenu = False

            if commands:
                shouldRunMain = False

                commandNamesRemaining = {c['name'] for c in commands}

                def popCommand(commandName):
                    if commandName in commandNamesRemaining:
                        commandNamesRemaining.remove(commandName)
                        return commandName

                shouldPromptToContinueForSettings = False
                shouldPromptToContinueForExternalApp = False

                ranPriorCommand = False

                def prepCommandRun():
                    global ranPriorCommand
                    global shouldPromptToContinue
                    global showingSeparator

                    sprintSeparator()

                    if ranPriorCommand:
                        if shouldPromptToContinue:
                            promptToContinue()
                            sprintSeparator()

                    ranPriorCommand = True
                    shouldPromptToContinue = False
                    showingSeparator = True

                if popCommand('quit'):
                    shouldQuit = True

                if popCommand('help'):
                    prepCommandRun()
                    sprint(parser.format_help())
                    shouldPromptToContinue = True

                if popCommand('version'):
                    prepCommandRun()
                    sprint(f'Version: {parser.prog} {__version__}')
                    shouldPromptToContinue = True

                if popCommand('settingsFilePath'):
                    prepCommandRun()
                    sprintPad()
                    sprint('Local settings files: ')
                    filenames = []
                    for filenameIndex, filename in enumerate(findSettingsFiles()):
                        sprint(f'[ {filenameIndex + 1} ] - {filename}')
                        filenames.append(filename)
                    while True:
                        sprintPad()
                        settingsFilePath = sprintput('Settings YAML file path (enter number of type a path): ').strip()
                        sprintPad()
                        if not settingsFilePath:
                            settingsFilePath = DefaultSettingsPath
                            sprintSeparator()
                            sprint(f'(using default)')
                            sprintPad()
                            break
                        else:
                            try:
                                fileNumber = int(settingsFilePath)
                            except:
                                fileNumber = None

                            if fileNumber is not None:
                                if fileNumber < 1 or fileNumber > len(filenames):
                                    sprintPad()
                                    esprint('Invalid option.')
                                    sprintPad()
                                else:
                                    settingsFilePath = filenames[fileNumber - 1]
                                    break
                            else:
                                settingsFilePath = getPathInfo(settingsFilePath)['best']
                                break
                    exists = os.path.isfile(settingsFilePath)
                    sprintSeparator()
                    sprint(f'Settings path set to: "{settingsFilePath}"{"" if exists else " (new file)"}')
                    menuSettings['settingsFilePath'] = settingsFilePath
                    menuSettingsDirty = True
                    shouldPromptToContinue = True

                if popCommand('uassetGuiPath'):
                    prepCommandRun()
                    uassetGuiPath = sprintput('UAssetGUI path: ').strip()
                    if not uassetGuiPath:
                        sprintPad()
                        sprint(f'(not specified)')
                    else:
                        sprintPad()
                        sprint(f'UAssetGUI path set to: {uassetGuiPath}')
                    menuSettings['uassetGuiPath'] = uassetGuiPath
                    menuSettingsDirty = True
                    shouldPromptToContinue = True

                if popCommand('list'):
                    listingInfo = True
                    shouldRunMain = True
                if popCommand('extract'):
                    extracting = True
                    shouldRunMain = True
                if popCommand('create'):
                    creating = True
                    shouldRunMain = True
                if popCommand('rename'):
                    renaming = True
                    shouldRunMain = True
                if popCommand('mix'):
                    mixing = True
                    shouldRunMain = True
                if popCommand('pak'):
                    paking = True
                    shouldRunMain = True
                if popCommand('install'):
                    installing = True
                    shouldRunMain = True
                if popCommand('launch'):
                    launching = True
                    shouldRunMain = True
                if popCommand('kill'):
                    killingGame = True
                    shouldRunMain = True

                if popCommand('editSettings'):
                    prepCommandRun()
                    shouldPromptToContinue = shouldPromptToContinueForExternalApp
                    if not osOpenFile(settingsFilePath):
                        sprintPad
                        esprint('ERROR: could not open file')
                        sprintPad()
                        shouldPromptToContinue = True

                if popCommand('results'):
                    prepCommandRun()
                    shouldPromptToContinue = shouldPromptToContinueForExternalApp
                    filePath = getResultsFilePath(settingsFilePath)
                    if not osOpenFile(filePath):
                        sprintPad()
                        esprint('ERROR: could not open file')
                        sprintPad
                        shouldPromptToContinue = True

                if popCommand('folder'):
                    prepCommandRun()
                    shouldPromptToContinue = shouldPromptToContinueForExternalApp
                    if platform.system() != 'Windows':
                        sprintPad()
                        esprint('Only supported on Windows')
                        shouldPromptToContinue = True
                    else:
                        settingsPathInfo = getPathInfo(settingsFilePath)
                        settingsDir = settingsPathInfo['dir']
                        sprintPad()
                        sprint(f'Opening {settingsDir}')
                        try:
                            osOpenDir(settingsDir)
                        except Exception as e:
                            sprintPad()
                            esprint(e)
                            sprintPad()
                            shouldPromptToContinue = True
                    sprintPad()

                if popCommand('debug'):
                    prepCommandRun()
                    debug = not debug
                    sprint(f"Turned debug flag {'on' if debug else 'off'}")
                    sprintPad()
                    menuSettings['debug'] = debug
                    menuSettingsDirty = True
                    shouldPromptToContinue = shouldPromptToContinueForSettings

                if popCommand('overwrite'):
                    prepCommandRun()
                    if overwriteOverride:
                        overwriteOverride = False
                    elif overwriteOverride is False:
                        overwriteOverride = None
                    else:
                        overwriteOverride = True
                    sprint(f"Switched overwrite mode to `{'overwrite' if overwriteOverride else 'no overwrite' if overwriteOverride is False else 'prompt'}`")
                    sprintPad()
                    menuSettings['overwriteOverride'] = overwriteOverride
                    menuSettingsDirty = True
                    shouldPromptToContinue = shouldPromptToContinueForSettings

                if shouldRunMain:
                    prepCommandRun()
                    sprintPad()
                    exitCode = main({
                        'settingsFilePath': settingsFilePath,
                        'inspecting': listingInfo,
                        'creatingAttachments': creating,
                        'extractingAttachments': extracting,
                        'renamingAttachmentFiles': renaming,
                        'mixingAttachments': mixing,
                        'paking': paking,
                        'installingMods': installing,
                        'openingGameLauncher': launching,
                        'killGame': killingGame,
                        'nonInteractive': False,
                        'debug': debug,
                        'uassetGuiPath': uassetGuiPath,
                        'overwriteOverride': overwriteOverride,
                    })
                    if launching:
                        pass
                    else:
                        shouldPromptToContinue = True

                if commandNamesRemaining:
                    if ranPriorCommand:
                        sprintSeparator()
                        if shouldPromptToContinue:
                            promptToContinue()
                    sprintSeparator()
                    esprint(f'Command(s) not run: {" | ".join(commandNamesRemaining)}')
                    shouldPromptToContinue = True
                    showingSeparator = True

            if shouldQuit:
                break

            if shouldPromptToContinue:
                sprintSeparator()
                promptToContinue()
                showingSeparator = True

            if showingSeparator:
                sprintSeparator()
    else:
        exitCode = main({
            'settingsFilePath': args.settingsFilePath,
            'inspecting': args.list,
            'creatingAttachments': args.create,
            'extractingAttachments': args.extract,
            'renamingAttachmentFiles': args.rename,
            'mixingAttachments': args.mix,
            'paking': args.pak,
            'installingMods': args.install,
            'openingGameLauncher': args.launch,
            'killGame': args.kill,
            'nonInteractive': args.ni,
            'debug': args.debug,
            'uassetGuiPath': args.uassetGuiPath,
            'overwriteOverride': args.overwrite,
        })

    # TODO: remove
    if False:
        if not len(sys.argv) > 1:
            sprintPad()
            sprint(f'run `{parser.prog} -h` for more options and usage.')
            sprintPad()

    sys.exit(exitCode)
