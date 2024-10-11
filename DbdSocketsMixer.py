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
import Attachment

__author__ = 'Ross Adamson'
__version__ = '0.1.4'
__license__ = 'MIT'

ItemTypeName = '$type'
ECustomizationCategoryName = 'ECustomizationCategory'
ECustomizationCategoryNamePrefix = f'{ECustomizationCategoryName}::'
ValueFieldName = 'Value'
NameFieldName = 'Name'
ModelDisplayNamePropNameFieldName = 'CultureInvariantString'

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

@contextmanager
def oneLinePrinter():
    def myPrint(message):
        print(message, end='')
    try:
        yield myPrint
    finally:
        # end the line
        print('')

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

def openFile(filePath):
    success = False

    testingFailWebbrowser = False
    testingFailStartfile = False
    testingFailEditor = False

    try:
        print(f'Opening {filePath}...')
        if testingFailWebbrowser:
            raise ValueError('webbrowser failed to run')
        webbrowser.open(filePath)
        success = True
    except Exception as e:
        eprint()
        eprint(e)
        eprint()
        try:
            print(f'Trying a different way to open...')
            if testingFailStartfile:
                raise ValueError('startfile failed to run')
            os.startfile(filePath)
            success = True
        except Exception as e2:
            eprint()
            eprint(e2)
            eprint()
            if platform.system() == 'Windows':
                try:
                    editor = getWindowsDefaultEditor()
                    print(f'Opening with {editor}...')
                    if testingFailEditor:
                        raise ValueError('editor failed to run')
                    os.system(f'start {editor} {filePath}')
                    success = True
                except Exception as e3:
                    eprint()
                    eprint(e3)
                    eprint()

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
                print(f'NameMap++|{name}|')
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
                        print(f'Invalid Name: {path}{k} -> {v}')
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
customizationItemDbPath: CustomizationItemDB.uasset

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
'''

def getPathInfo(path, relativeDir='./'):
    result = {
        'absolute': '',
        'dir': '',
        'stem': '',
        'suffix': '',
        'suffixLower': '',
    }

    if os.path.isabs(path):
        result['absolute'] = path
    else:
        result['absolute'] = pathlib.Path(os.path.join(relativeDir, path)).resolve()

    result['dir'] = os.path.dirname(result['absolute'])
    result['stem'] = pathlib.Path(path).stem
    result['suffix'] = pathlib.Path(path).suffix
    result['suffixLower'] = result['suffix'].lower()

    return result

def runCall(args):
    quoted = [f'"{arg}"' for arg in args]
    try:
        code = subprocess.call(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if code:
            raise ValueError(f'subprocess returned error exit code: {code}')
    except:
        raise ValueError(f"subprocess call failed: {' '.join(quoted)}")

def jsonToUasset(jsonPath, uassetPath, uassetGuiPath):
    runCall([uassetGuiPath, 'fromjson', jsonPath, uassetPath])

def uassetToJson(uassetPath, jsonPath, uassetGuiPath):
    runCall([uassetGuiPath, 'tojson', uassetPath, jsonPath, 'VER_UE4_25'])

def confirm(action, emptyMeansNo=None):
    while True:
        result = input(f'{action[0].upper()}{action[1:]} (Y/n)? ').strip()
        if result.upper() == 'Y':
            confirmed = True
            break

        if result.upper() == 'N' or (not result and emptyMeansNo is True):
            confirmed = False
            break

    return confirmed

def confirmOverwrite(target):
    return confirm(f'overwrite "{target}"')

def main(
    settingsFilePath,
    listingInfo,
    creating,
    exportingSocketAttachments,
    renamingAttachmentFiles,
    mixingAttachments,
    nonInteractive,
    debug,
    uassetGuiPath,
    overwriteOverride,
):
    """ Main entry point of the app """

    # TODO: remove -- too verbose
    printingJson = False
    printingYaml = False

    writingUnalteredDb = True
    writingAlteredDb = True

    exitCode = 0

    warnings = []
    def printWarning(message, newline=False):
        warnings.append(str(message))
        if newline:
            print('\n')
        print(f'WARN: {message}')

    errors = []
    def printError(message, newline=False):
        errors.append(str(message))
        if newline:
            print('\n')
        eprint(f'ERROR: {message}')

    if False:
        importAttachmentsSeparator = 'And'
    else:
        importAttachmentsSeparator = '_'

    exportAttachmentsSeparator = '_'

    combinationsAdded = {}
    combinationsSkipped = {}
    attachmentsToMix = {}
    nameMapNamesRemoved = []
    nameMapNamesAdded = []
    attachmentsCreated = []
    nameMapArray = []
    nameMapSet = set(nameMapArray)
    attachmentsRenamed = {}

    def allowWrite(path):
        if not os.path.exists(path):
            return True

        shouldWarn = True

        if overwriteOverride is not None:
            result = overwriteOverride
        elif nonInteractive:
            printWarning('Cannot confirm file overwrite in non-interactive mode', newline=True)
            result = False
        else:
            print()
            result = confirmOverwrite(path)
            print()
            shouldWarn = False

        if shouldWarn:
            if result:
                printWarning(f'Overwriting "{path}"', newline=True)
            else:
                printWarning(f'Skipping write of "{path}" (file exists)', newline=True)

        return result

    def checkAttachmentName(category, attachmentName, otherInfo=None):
        if attachmentName not in attachmentsToMix.get(category, {}):
            printWarning(f"reference to missing attachment: {category}::{attachmentName}{' (' if otherInfo else ''}{otherInfo or ''}{')' if otherInfo else ''}", newline=True)

    def mergeSettings(parentData, childData):
        for key, value in childData.items():
            # TODO: merge data instead of overwriting
            parentData[key] = childData[key]

    def readSettingsRecursive(filePath):
        nonlocal exitCode

        resultData = {}

        print(f'Reading settings from {filePath}')
        if not os.path.isfile(filePath):
            printError(f'Could not read settings from {filePath} (file not found)', newline=True)
            exitCode = 1
            return None

        with open(filePath, 'r') as file:
            data = yaml.safe_load(file)

        for otherPath in data.get('import', []):
            otherData = readSettingsRecursive(otherPath)
            if otherData is None:
                return None

            mergeSettings(resultData, otherData)

        mergeSettings(resultData, data)

        return resultData

    try:
        if not os.path.exists(settingsFilePath):
            printWarning(f'Settings file ({settingsFilePath}) does not exist. Creating it now with default content.')
            if printingYaml:
                print(getSettingsTemplate())
            with open(settingsFilePath, 'w') as file:
                file.write(getSettingsTemplate())

        settingsPathInfo = getPathInfo(settingsFilePath)
        settingsDir = settingsPathInfo['dir']
        settings = readSettingsRecursive(settingsFilePath)

        attachmentsDir = settings.get('attachmentsDir', None)
        if attachmentsDir is None:
            defaultAttachmentsDir = 'attachments'
            printWarning(f'`attachmentsDir` not specified. Defaulting to: {defaultAttachmentsDir}', newline=True)
            attachmentsDir = defaultAttachmentsDir

        if not os.path.exists(attachmentsDir):
            printWarning(f'`attachmentsDir` ({attachmentsDir}) does not exist. Creating it now.', newline=True)
            os.makedirs(attachmentsDir, exist_ok=True)

        if creating:
            if nonInteractive:
                printWarning('Cannot create attachment definition in non-interactive mode', newline=True)
            else:
                done = False
                canceled = False

                def confirmCanceled():
                    nonlocal canceled
                    canceled = True
                    return canceled

                print('Adding attachment definition...')
                while not done:
                    attachment = copy.deepcopy(Attachment.BasicAttachment)
                    attachment['modelCategory'] = ''
                    categoryOptions = {'SurvivorTorso', 'SurvivorLegs', 'SurvivorHead'}
                    while not attachment['modelCategory']:
                        attachment['modelCategory'] = input(f"Model category ({', '.join(categoryOptions)}): ").strip()
                        if not attachment['modelCategory']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        if attachment['modelCategory'] not in categoryOptions:
                            eprint('ERROR: unsupported category')
                            attachment['modelCategory'] = ''

                    if canceled:
                        break

                    attachment['attachmentId'] = ''
                    while not attachment['attachmentId']:
                        attachment['attachmentId'] = input('Attachment ID: ').strip()
                        if not attachment['attachmentId']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        filename = Attachment.getAttachmentFilename(attachment['attachmentId'])
                        filePath = os.path.join(attachmentsDir, filename)
                        if os.path.exists(filePath):
                            eprint('ERROR: attachment ID already exists')
                            attachment['attachmentId'] = ''

                    if canceled:
                        break

                    attachment['displayName'] = ''
                    while not attachment['displayName']:
                        attachment['displayName'] = input('Display name: ').strip()
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
                        assetPath['AssetName'] = input('Blueprint path: ').strip()
                        if not assetPath['AssetName']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        if not assetPath['AssetName'].startswith('/Game/'):
                            eprint('ERROR: should start with `/Game/`')
                            assetPath['AssetName'] = ''
                            continue

                        try:
                            path = pathlib.PurePosixPath(assetPath['AssetName'])
                        except Exception as e:
                            eprint('ERROR: invalid path')
                            assetPath['AssetName'] = ''
                            continue

                        if not path.stem:
                            eprint('ERROR: invalid name')
                            assetPath['AssetName'] = ''
                            continue

                        stem = path.stem
                        suffix = f'.{stem}_C'
                        if path.suffix:
                            if path.suffix != suffix:
                                eprint('ERROR: invalid path suffix. Should be {suffix}')
                                assetPath['AssetName'] = ''
                                continue
                        else:
                            path = path.with_name(f'{stem}{suffix}')

                        normalizedPath = path.as_posix()
                        print(f'Normalized path: {normalizedPath}')
                        assetPath['AssetName'] = normalizedPath

                    if canceled:
                        break

                    print(f'Writing to "{filePath}"')
                    if allowWrite(filePath):
                        with open(filePath, 'w') as file:
                            yamlDump(attachment, file)
                        print('done.')

                    if not confirm('add another', emptyMeansNo=True):
                        done = True

                if canceled:
                    print(f'\nAdd canceled.\n')

        customizationItemDbPath = settings.get('customizationItemDbPath', None)
        if customizationItemDbPath is None:
            customizationItemDbPath = 'CustomizationItemDB.json'
            printWarning(f'`customizationItemDbPath` not specified. defaulting to: {customizationItemDbPath}', newline=True)
        customizationItemDbPathInfo = getPathInfo(customizationItemDbPath)
        customizationItemDbSupportedFileTypes = ['.json', '.uasset']
        if customizationItemDbPathInfo['suffixLower'] not in customizationItemDbSupportedFileTypes:
            raise ValueError(f'Unsupported file extension for {customizationItemDbPath}: must be one of ({", ".join(customizationItemDbSupportedFileTypes)})')

        if not os.path.isfile(customizationItemDbPath):
            raise ValueError(f'{customizationItemDbPath} does not exist')

        if customizationItemDbPathInfo['suffixLower'] == '.json':
            customizationItemDbJsonPath = customizationItemDbPath
        elif customizationItemDbPathInfo['suffixLower'] == '.uasset':
            customizationItemDbJsonPath = os.path.join(
                settingsPathInfo['dir'],
                f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-unaltered.json",
            )
            print(f'\nConverting "{customizationItemDbPath}" to JSON, writing "{customizationItemDbJsonPath}"')
            if allowWrite(customizationItemDbJsonPath):
                uassetToJson(customizationItemDbPath, customizationItemDbJsonPath, uassetGuiPath)
                print('Done converting.')
        else:
            raise ValueError('internal error')

        with oneLinePrinter() as oneLinePrint:
            oneLinePrint(f'\nReading CustomizationItemDB JSON from {customizationItemDbJsonPath}...')
            with open(customizationItemDbJsonPath, 'r') as file:
                data = json.load(file)
            oneLinePrint('done.')

        if printingJson:
            print('\n')
            print(jsonDump(data, pretty=True))

        if printingYaml:
            print('\n')
            print(yamlDump(data))

        if writingUnalteredDb:
            outPath = os.path.join(
                settingsDir,
                f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-unaltered.yaml",
            )
            print(f'\nWriting unaltered CustomizationItemDB to "{outPath}"')
            if allowWrite(outPath):
                with open(outPath, 'w') as file:
                    yamlDump(data, file)

        if listingInfo or mixingAttachments or renamingAttachmentFiles:
            attachmentFilenames = os.listdir(attachmentsDir)
            print(f'\nDiscovered {len(attachmentFilenames)} attachment files')
            if len(attachmentFilenames):
                print(f'Reading attachments...')
                for filenameIndex, filename in enumerate(attachmentFilenames):
                    filePath = os.path.join(attachmentsDir, filename)
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
                                print('\n')
                                print(jsonDump(attachmentData, pretty=True))

                            if printingYaml:
                                print('\n')
                                print(yamlDump(attachmentData))

                            categoryName = attachmentData['modelCategory']

                            if attachmentName in attachmentsToMix.get(categoryName, {}):
                                printWarning(f'duplicate attachment {attachmentName}!', newline=True)

                            if categoryName not in attachmentsToMix:
                                attachmentsToMix[categoryName] = {}
                            attachmentsToMix[categoryName][attachmentName] = attachmentData

                            if renamingAttachmentFiles:
                                newFilename = Attachment.getAttachmentFilename(attachmentName)
                                if newFilename == filename:
                                    print(f'rename not needed (already named correctly).')
                                else:
                                    print(f'Renaming {filename} to {newFilename}')
                                    newFilePath = os.path.join(attachmentsDir, newFilename)
                                    if os.path.exists(newFilePath):
                                        raise ValueError(f'Could not rename {filename} to {newFilename} (file already exists)')

                                    os.rename(filePath, newFilePath)
                                    attachmentsRenamed[filename] = newFilename
                    except Exception as e:
                        printError(e, newline=True)
                        exitCode = 1
                print('\nDone loading attachments.')

            if mixingAttachments:
                print('\nGenerating exclusion rules...')
                nameMapArray = data['NameMap']
                nameMapSet = set(nameMapArray)

                categoryCombinationsToSkip = {}
                categoryCombinationSubsetsToSkip = {}

                setEqualitySymbol = '=='
                modelRestrictSymbol = ':'
                modelRestrictSeparator = ','

                if debug:
                    print('\nReading combosToSkip...')

                def logSkip(combo, baseModels=None, category=None, isExact=False, info=''):
                    if baseModels is None:
                        baseModels = []
                    def mySorted(combo):
                        if False:
                            return sorted([n for n in combo])
                        return combo
                    print(f"skip {f'{category} ' if (category and False) else ''}combo {'=' if isExact else '⊇'} {','.join(mySorted(combo))}: {','.join(baseModels) or '*'}{f' ({info})' if info else ''}")

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
                    print('\nReading mutuallyExclusive...')

                for category, groups in settings.get('mutuallyExclusive', {}).items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for groupIndex, attachments in enumerate(groups):
                        attachmentsSeen = set()
                        for attachmentIndex, attachment in enumerate(attachments):
                            if attachment in attachmentsSeen:
                                printWarning(f'duplicate attachment ID (mutuallyExclusive.{category}[{groupIndex}][{attachmentIndex}])', newline=True)
                            else:
                                checkAttachmentName(category, attachment, f'mutuallyExclusive.{category}[{groupIndex}][{attachmentIndex}]')
                                attachmentsSeen.add(attachment)

                        for duo in combinations(set(attachments), 2):
                            frozenDuo = frozenset(duo)
                            categoryCombinationSubsetsToSkip[category][frozenDuo] = frozenset()
                            if debug:
                                logSkip(frozenDuo, category=category)

                if debug:
                    print('\nReading attachmentConflicts...')

                for category, attachmentConflictsMap in settings.get('attachmentConflicts', {}).items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for attachment, conflicts in attachmentConflictsMap.items():
                        checkAttachmentName(category, attachment, f'attachmentConflicts.{category}')
                        attachmentsSeen = {attachment}
                        for conflictIndex, conflict in enumerate(conflicts):
                            if conflict in attachmentsSeen:
                                printWarning(f'duplicate attachment ID (attachmentConflicts.{category}.{attachment}[{conflictIndex}])', newline=True)
                            else:
                                checkAttachmentName(category, conflict, f'attachmentConflicts.{category}.{attachment}[{conflictIndex}]')
                                frozenDuo = frozenset({attachment, conflict})
                                categoryCombinationSubsetsToSkip[category][frozenDuo] = frozenset()
                                if debug:
                                    logSkip(frozenDuo, category=category)
                                attachmentsSeen.add(conflict)

                if debug:
                    print('\nReading equivalentParts...')

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
                                printWarning(f'duplicate group (equivalentParts.{category}.{equivalent}[{groupIndex}])', newline=True)
                                continue

                            # TODO: allow group to map to multiple equivalents?
                            comboEquivalentMap[frozenParts] = equivalent

                            if category not in categoryCombinationSubsetsToSkip:
                                categoryCombinationSubsetsToSkip[category] = {}

                            partsSeen = set()
                            for partIndex, part in enumerate(parts):
                                if part in partsSeen:
                                    printWarning(f'duplicate part (equivalentParts.{equivalent}[{groupIndex}][{partIndex}])', newline=True)
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
                    print('\nReading supersetParts...')

                for category, attachmentProperSubsetsMap in settings.get('supersetParts', {}).items():
                    for attachment, properSubsets in attachmentProperSubsetsMap.items():
                        checkAttachmentName(category, attachment, f'supersetParts->superset')
                        for groupIndex, parts in enumerate(properSubsets):
                            properSubset = frozenset(parts)

                            if True:
                                if categoryComboEquivalentMap.get(category, {}).get(properSubset, None) == attachment:
                                    printWarning(f"proper subset ({properSubset}) is also a perfect subset of {attachment}", newline=True)
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
                    print('\nExcluding equivalent combos...')

                for category, comboEquivalentMap in categoryComboEquivalentMap.items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for frozenCombo in comboEquivalentMap.keys():
                        # don't allow combos containing all the parts of an entire equivalent attachment - use the equivalent instead
                        categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                        if debug:
                            logSkip(frozenCombo, category=category)

                print('\nExclusion rules generated.')

                if debug:
                    print('\ncategoryCombinationSubsetsToSkip:')
                    print(f'\n{yamlDump(jsonifyDataRecursive(categoryCombinationSubsetsToSkip))}')

                    print('\ncategoryCombinationsToSkip:')
                    print(f'\n{yamlDump(jsonifyDataRecursive(categoryCombinationsToSkip))}')

        if listingInfo or exportingSocketAttachments or mixingAttachments:
            exports = data['Exports']
            dataTableExport = findNextItemByType(exports, 'UAssetAPI.ExportTypes.DataTableExport, UAssetAPI')
            models = dataTableExport['Table']['Data']
            modelsCopy = models.copy()
            if mixingAttachments:
                models.clear()
            print(f'\nReading {len(modelsCopy)} models...')
            for modelIndex, model in enumerate(modelsCopy):
                try:
                    modelName = getModelName(model)
                    print(f'\n{modelIndex + 1} - reading {modelName}...')

                    modelValues = getPropertyValue(model)

                    modelIdProp = getModelIdProperty(modelValues)
                    modelId = getPropertyValue(modelIdProp)
                    if modelId != modelName:
                        printWarning(f'ID ({modelId}) does not match model name ({modelName})', newline=True)

                    modelNameParts = modelName.split('_')
                    modelBaseName = modelNameParts.pop(0)
                    print(f'Base Name: {modelBaseName}')

                    uiDataValues = getUiDataValues(modelValues)

                    modelDisplayNameProp = getModelDisplayNameProperty(uiDataValues)
                    modelDisplayName = modelDisplayNameProp[ModelDisplayNamePropNameFieldName]
                    print(f"Display Name: {modelDisplayName or '(none)'}")

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

                    print(f'Category: {categoryName}')

                    socketAttachments = getSocketAttachments(modelValues)
                    print(f'Attachments: {len(socketAttachments)}')

                    if len(socketAttachments):
                        # TODO: ignore this - it's not a reliable way of determining attachment names
                        otherNames = [n for n in modelNameParts if n.lower() not in {'torso', 'legs', 'head', 'body', 'weapon', 'outfits', 'charm'}]
                        otherNamesString = '_'.join(otherNames)
                        attachmentNames = otherNamesString.split(importAttachmentsSeparator) if otherNamesString else []

                        if debug:
                            print(f"Potential attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        attachmentDisplayNamesString = ''
                        openParenIndex = modelDisplayName.find('(')
                        if openParenIndex > -1:
                            closeParenIndex = modelDisplayName.find(')', openParenIndex + 1)
                            if closeParenIndex > -1:
                                attachmentDisplayNamesString = modelDisplayName[openParenIndex + 1:closeParenIndex]

                        if debug:
                            print(f'Potential attachments display names string: {attachmentDisplayNamesString}')

                        attachmentDisplayNames = attachmentDisplayNamesString.split(', ') if attachmentDisplayNamesString else []
                        if debug:
                            print(f"Potential attachments display names: {', '.join(attachmentDisplayNames) if attachmentDisplayNames else '(unknown)'}")

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
                            print(f"Synthesized attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        if exportingSocketAttachments:
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
                                filePath = os.path.join(attachmentsDir, filename)

                                if os.path.exists(filePath):
                                    printWarning(f'Skipping attachment {attachmentIndex + 1} (file already exists): {filePath}', newline=True)
                                else:
                                    print(f'Exporting attachment {attachmentIndex + 1}: {attachmentId} ({attachmentDisplayName}) to {filePath}')

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
                            print(f'Mixing {len(attachmentsForCategory)} attachments into combinations...')
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
                                    print(f"Making combo: {', '.join(attachmentIds)}")
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
                                        # TODO: use same algorithm UE4 uses - this is not identical, but it seems to do the trick anyway
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
                            print(f'Created {comboCount} combos')
                except Exception as e:
                    printError(e, newline=True)
                    exitCode = 1

            print('\nModels processed.')

            if mixingAttachments:
                nameMapArrayCopy = nameMapArray.copy()
                nameMapArray.clear()
                nameMapSet.clear()
                addAllToNameMap(data.get('Imports', []), nameMapSet)
                addAllToNameMap(data.get('Exports', []), nameMapSet)

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
                    print(f'\nNameMap names removed:')
                    print(yamlDump(jsonifyDataRecursive(nameMapNamesRemoved)))

                if debug:
                    print(f'\nNameMap names added:')
                    print(yamlDump(jsonifyDataRecursive(nameMapNamesAdded)))

                if writingAlteredDb:
                    jsonOutPath = os.path.join(
                        settingsDir,
                        f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.json",
                    )
                    print(f'\nWriting altered CustomizationItemDB to "{jsonOutPath}"')
                    if allowWrite(jsonOutPath):
                        with open(jsonOutPath, 'w') as file:
                            jsonDump(data, file)
                        print('Done.')

                    if customizationItemDbPathInfo['suffixLower'] == '.uasset':
                        print(f'\nWriting altered CustomizationItemDB to "{customizationItemDbPath}"')
                        if allowWrite(customizationItemDbPath):
                            jsonToUasset(jsonOutPath, customizationItemDbPath, uassetGuiPath)
                            print('Done.')

                    # TODO: this should be optional
                    if True:
                        yamlOutPath = os.path.join(
                            settingsDir,
                            f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.yaml",
                        )
                        print(f'\nWriting altered CustomizationItemDB to "{yamlOutPath}"')
                        if allowWrite(yamlOutPath):
                            with open(yamlOutPath, 'w') as file:
                                yamlDump(data, file)
                            print('Done.')
    except Exception as e:
        printError(e, newline=True)
        exitCode = 1

    outputInfo = {
        'errors': errors,
        'warnings': warnings,
        'attachmentsRead': {category: list(attachmentDataMap.keys()) for category, attachmentDataMap in attachmentsToMix.items()},
        'attachmentsRenamed': attachmentsRenamed,
        'attachmentsCreated': attachmentsCreated,
        'combosAdded': combinationsAdded,
        'combosSkipped': combinationsSkipped,
        'nameMapAlterations': {
            'namesRemoved': nameMapNamesRemoved,
            'namesAdded': nameMapNamesAdded,
        },
    }

    outputInfoFilename = getResultsFilePath(settingsFilePath)
    print(f'\nWriting command results to "{outputInfoFilename}"')
    if allowWrite(outputInfoFilename):
        with open(outputInfoFilename, 'w') as file:
            yamlDump(jsonifyDataRecursive(outputInfo), file)

    return exitCode

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
    defaultSettingsPath = 'settings.yaml'
    parser.add_argument(
        'settingsFilePath',
        help=f'path to settings YAML file (defaults to `{defaultSettingsPath}`)',
        type=str,
        default=defaultSettingsPath,
        nargs='?',
    )
    defaultUAssetGUIPath = 'UAssetGUI.exe'
    parser.add_argument(
        '--uassetGuiPath',
        help=f'path to UAssetGUI.exe (defaults to `{defaultUAssetGUIPath}`)',
        type=str,
        default=defaultUAssetGUIPath,
    )
    parser.add_argument(
        '--list',
        help='list attachments and models',
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
        print('Running in non-interactive mode.')

    exitCode = 0

    if (
        not args.list
        and not args.extract
        and not args.create
        and not args.rename
        and not args.mix
        and not args.ni
    ):
        print('Welcome to DbdSocketsMixer!')

        settingsFilePath = args.settingsFilePath
        uassetGuiPath = args.uassetGuiPath
        debug = args.debug
        overwriteOverride = args.overwrite

        actionsMap = {action.dest: action for action in parser._actions}

        commandNames = [c for c in actionsMap.keys() if c not in {'ni'}]
        commandNames.insert(commandNames.index('list') + 1, 'folder')
        commandNames.insert(commandNames.index('folder') + 1, 'editSettings')
        commandNames.insert(commandNames.index('editSettings') + 1, 'results')
        commandNames.append('quit')
        commandMap = {c: { 'name': c, 'number': i + 1, 'action': actionsMap.get(c, None) } for i, c in enumerate(commandNames)}
        commandNumberMap = {str(c['number']): c for c in commandMap.values()}

        while True:
            listingInfo = False
            creating = False
            extracting = False
            renaming = False
            mixing = False

            exitCode = 0

            print()

            print(f"Settings file: {settingsFilePath or '<Not specified>'}")
            print(f"UAssetGUI path: {uassetGuiPath or '<Not specified>'}")
            print(f"Debug mode: {'on' if debug else 'off'}")
            print(f"Overwrite mode: {'overwrite' if overwriteOverride else 'no overwrite' if overwriteOverride is False else 'prompt'}")

            print()

            for commandName in commandNames:
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

                print(f"[ {command['number']} ] {commandName[0].upper()}{commandName[1:]} - {help}")

            shouldPromptToContinue = False

            response = input('\nSelection: ').strip()
            command = None
            try:
                command = commandNumberMap[response]
            except:
                try:
                    if response:
                        responseUpper = response.upper()
                        commandMatches = [c for c in commandMap.values() if c['name'].upper().startswith(responseUpper)]
                        if len(commandMatches) == 0:
                            raise ValueError()

                        if len(commandMatches) == 1:
                            command = commandMatches[0]
                        else:
                            eprint(f"\nAmbiguous command prefix ({'|'.join([c['name'] for c in commandMatches])}). Needs more characters.")
                            shouldPromptToContinue = True
                except:
                    eprint('\nInvalid option.')
                    shouldPromptToContinue = True

            if command is not None:
                print()

                shouldRunMain = False

                commandName = command['name']

                if commandName == 'help':
                    print(parser.format_help())
                    shouldPromptToContinue = True
                elif commandName == 'version':
                    print(f'Version: {parser.prog} {__version__}')
                    shouldPromptToContinue = True
                elif commandName == 'quit':
                    break
                elif commandName == 'settingsFilePath':
                    settingsFilePath = input('Settings YAML file path: ').strip()
                    if not settingsFilePath:
                        settingsFilePath = defaultSettingsPath
                        print(f'\n(using default)')

                    print(f'\nSettings path set to: {settingsFilePath}')
                    shouldPromptToContinue = True
                elif commandName == 'uassetGuiPath':
                    uassetGuiPath = input('UAssetGUI path: ').strip()
                    if not uassetGuiPath:
                        uassetGuiPath = defaultUAssetGUIPath
                        print(f'\n(using default)')

                    print(f'\nUAssetGUI path set to: {uassetGuiPath}')
                    shouldPromptToContinue = True
                elif commandName == 'debug':
                    debug = not debug
                    print(f"Turned debug flag {'on' if debug else 'off'}")
                    shouldPromptToContinue = True
                elif commandName == 'overwrite':
                    if overwriteOverride:
                        overwriteOverride = False
                    elif overwriteOverride is False:
                        overwriteOverride = None
                    else:
                        overwriteOverride = True
                    print(f"Switched overwrite mode to `{'overwrite' if overwriteOverride else 'no overwrite' if overwriteOverride is False else 'prompt'}`")
                    shouldPromptToContinue = True
                elif commandName == 'folder':
                    shouldPromptToContinue = False
                    if platform.system() != 'Windows':
                        eprint('Only supported on Windows')
                        shouldPromptToContinue = True
                    else:
                        settingsPathInfo = getPathInfo(settingsFilePath)
                        settingsDir = settingsPathInfo['dir']
                        print(f'Opening {settingsDir}')
                        try:
                            os.system(f'start explorer "{settingsDir}"')
                        except Exception as e:
                            eprint()
                            eprint(e)
                            eprint()
                            shouldPromptToContinue = True
                elif commandName == 'editSettings':
                    shouldPromptToContinue = False
                    if not openFile(settingsFilePath):
                        eprint('ERROR: could not open file')
                        shouldPromptToContinue = True
                elif commandName == 'results':
                    shouldPromptToContinue = False
                    filePath = getResultsFilePath(settingsFilePath)
                    if not openFile(filePath):
                        eprint('ERROR: could not open file')
                        shouldPromptToContinue = True
                elif commandName == 'list':
                    listingInfo = True
                    shouldRunMain = True
                elif commandName == 'extract':
                    extracting = True
                    shouldRunMain = True
                elif commandName == 'create':
                    creating = True
                    shouldRunMain = True
                elif commandName == 'rename':
                    renaming = True
                    shouldRunMain = True
                elif commandName == 'mix':
                    mixing = True
                    shouldRunMain = True
                else:
                    print('Not yet implemented.')

                if shouldRunMain:
                    exitCode = main(
                        settingsFilePath,
                        listingInfo,
                        creating,
                        extracting,
                        renaming,
                        mixing,
                        False,
                        debug,
                        uassetGuiPath,
                        overwriteOverride,
                    )
                    shouldPromptToContinue = True

            if shouldPromptToContinue:
                input('\nPress Enter to continue...')

            print('\n--------------------------')
    else:
        exitCode = main(
            args.settingsFilePath,
            args.list,
            args.create,
            args.extract,
            args.rename,
            args.mix,
            args.ni,
            args.debug,
            args.uassetGuiPath,
            args.overwrite,
        )

    # TODO: remove
    if False:
        if not len(sys.argv) > 1:
            print(f'\nrun `{parser.prog} -h` for more options and usage.\n')

    sys.exit(exitCode)
