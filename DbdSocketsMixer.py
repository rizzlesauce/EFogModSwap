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

__author__ = 'Ross Adamson'
__version__ = '0.1.0'
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

def generateRandomHexString(length):
    return secrets.token_hex(length // 2)

def md5Hash(string):
  return hashlib.md5(string.encode()).hexdigest()

def sha256Hash(string):
    return hashlib.sha256(string.encode()).hexdigest()[:32]

def findNextItemByFields(items, fields, values):
    fieldsValuesMap = {f: v for f, v in zip(fields, values)}
    return next((item for item in items if all(item[field] == value for field, value in fieldsValuesMap.items())), None)

def findNextItemByType(items, typeName, fieldName=ItemTypeName):
    return findNextItemByFields(items, [fieldName], [typeName])

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

def getSettingsTemplate():
    return '''# KateBikerVariants

# CustomizationItemDB.json for your custom slot outfit/models (exported from UAssetGUI -- name it whatever you want)
customizationItemDbPath: CustomizationItemDB.json
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
    # define each shortened variant of blue chains as a strict subset of the corresponding original length version
    KateLegsBlueChains:
    - - KateLegsShortBlueChains
    KateLegsRightBlueChain:
    - - KateLegsShortRightBlueChain
    KateLegsLeftBlueChain:
    - - KateLegsShortLeftBlueChain
  # uncomment this if there are no equivalent parts in this category
  SurvivorTorso: {}
  #SurvivorTorso:
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

def main(args):
    """ Main entry point of the app """

    # TODO: remove -- too verbose
    printingJson = False
    printingYaml = False

    exportingSocketAttachments = args.extract
    renamingAttachmentFiles = args.rename
    mixingAttachments = args.mix
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

    def checkAttachmentName(category, attachmentName, otherInfo=None):
        if attachmentName not in attachmentsToMix.get(category, {}):
            printWarning(f"reference to missing attachment: {category}::{attachmentName}{' (' if otherInfo else ''}{otherInfo or ''}{')' if otherInfo else ''}", newline=True)

    settingsFilePath = args.settingsFilePath
    settings = {}
    if not os.path.isfile(settingsFilePath):
        printWarning(f'Settings file ({settingsFilePath}) does not exist. Creating it now with template content.')
        if printingYaml:
            print(getSettingsTemplate())
        with open(settingsFilePath, 'w') as file:
            file.write(getSettingsTemplate())

    with oneLinePrinter() as oneLinePrint:
        oneLinePrint(f'Reading settings from {settingsFilePath}...')
        with open(settingsFilePath, 'r') as file:
            settings = yaml.safe_load(file)
        oneLinePrint('done.')

    attachmentsDir = settings.get('attachmentsDir', None)
    if attachmentsDir is None:
        defaultAttachmentsDir = 'attachments'
        printWarning(f'`attachmentsDir` not specified. Defaulting to: {defaultAttachmentsDir}')
        attachmentsDir = defaultAttachmentsDir

    if not os.path.exists(attachmentsDir):
        printWarning(f'`attachmentsDir` ({attachmentsDir}) does not exist. Creating it now.')
        os.makedirs(attachmentsDir, exist_ok=True)

    customizationItemDbPath = settings.get('customizationItemDbPath', None)
    if customizationItemDbPath is None:
        customizationItemDbPath = 'CustomizationItemDB.json'
        printWarning(f'`customizationItemDbPath` not specified. defaulting to: {customizationItemDbPath}', newline=True)
    customizationItemDbPathNoExtension = customizationItemDbPath.removesuffix('.json')
    if os.path.isfile(customizationItemDbPath):
        with oneLinePrinter() as oneLinePrint:
            oneLinePrint(f'Reading CustomizationItemDB from {customizationItemDbPath}...')
            with open(customizationItemDbPath, 'r') as file:
                # TODO: also handle yaml and uasset file types
                data = json.load(file)
            oneLinePrint('done.')

        if printingJson:
            print('\n')
            print(json.dumps(data, indent=2))

        if printingYaml:
            print('\n')
            print(yaml.dump(data, default_flow_style=False, sort_keys=False))

        if writingUnalteredDb:
            # TODO: prevent overwrite if already exists?
            outFilename = f'{customizationItemDbPathNoExtension}-unaltered.yaml'
            print(f'\nWriting unaltered CustomizationItemDB to {outFilename}')
            with open(outFilename, 'w') as file:
                yaml.dump(data, file, default_flow_style=False, sort_keys=False)

        if mixingAttachments or renamingAttachmentFiles:
            attachmentFilenames = os.listdir(attachmentsDir)
            print(f'\nDiscovered {len(attachmentFilenames)} attachment files')
            if len(attachmentFilenames):
                print(f'Loading attachments...')
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
                                print(json.dumps(attachmentData, indent=2))

                            if printingYaml:
                                print('\n')
                                print(yaml.dump(attachmentData, default_flow_style=False, sort_keys=False))

                            categoryName = attachmentData['modelCategory']

                            if attachmentName in attachmentsToMix.get(categoryName, {}):
                                printWarning(f'duplicate attachment {attachmentName}!', newline=True)

                            if categoryName not in attachmentsToMix:
                                attachmentsToMix[categoryName] = {}
                            attachmentsToMix[categoryName][attachmentName] = attachmentData

                            if renamingAttachmentFiles:
                                newFilename = f'SocketAttachment_{attachmentName}.yaml'
                                if newFilename == filename:
                                    print(f'rename not needed (already named correctly).')
                                else:
                                    print(f'Renaming {filename} to {newFilename}')
                                    newFilePath = os.path.join(attachmentsDir, newFilename)
                                    if os.path.exists(newFilePath):
                                        printError(f'Could not rename {filename} to {newFilename} (file already exists)!')
                                        exitCode = 1
                                    else:
                                        os.rename(filePath, newFilePath)
                                        attachmentsRenamed[filename] = newFilename
                    except Exception as e:
                        printError(e)
                        exitCode = 1
                print('\nDone loading attachments.')

            if mixingAttachments:
                print('\nGenerating exclusions...')
                nameMapArray = data['NameMap']
                nameMapSet = set(nameMapArray)

                categoryCombinationsToSkip = {}
                categoryCombinationSubsetsToSkip = {}
                setEqualitySymbol = '=='
                modelRestrictSymbol = ':'
                modelRestrictSeparator = ','
                for category, combosList in settings.get('combosToSkip', {}).items():
                    combosToSkip = {}
                    subsetsToSkip = {}
                    for combo in combosList:
                        isSubset = True
                        newCombo = set()
                        baseModels = set()
                        for attachment in combo:
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

                            checkAttachmentName(category, actualAttachment, 'combosToSkip')
                            newCombo.add(actualAttachment)

                        if isSubset:
                            subsetsToSkip[frozenset(newCombo)] = frozenset(baseModels)
                        else:
                            combosToSkip[frozenset(newCombo)] = frozenset(baseModels)

                    categoryCombinationsToSkip[category] = combosToSkip
                    categoryCombinationSubsetsToSkip[category] = subsetsToSkip

                categoryComboEquivalentMap = {}
                for category, equivalentCombosMap in settings.get('equivalentParts', {}).items():
                    # TODO: do we even need this?
                    comboEquivalentMap = {}
                    for equivalent, combos in equivalentCombosMap.items():
                        checkAttachmentName(category, equivalent, 'equivalentParts->equivalent')
                        for parts in combos:
                            combo = frozenset(parts)
                            # TODO: do we even need this?
                            comboEquivalentMap[combo] = equivalent

                            if category not in categoryCombinationSubsetsToSkip:
                                categoryCombinationSubsetsToSkip[category] = {}

                            for part in parts:
                                checkAttachmentName(category, part, f'equivalentParts.{equivalent}->part')
                                for comboToSkip, baseModels in [(k, v) for k, v in categoryCombinationSubsetsToSkip[category].items()]:
                                    if part in comboToSkip and not combo <= comboToSkip:
                                        # if we would skip an aggregate part (not all comprising parts) when combined with other attachments,
                                        # skip other attachments when combined with aggregate
                                        newCombo = set(comboToSkip)
                                        newCombo.remove(part)
                                        newCombo.add(equivalent)
                                        if len(newCombo) > 1:
                                            categoryCombinationSubsetsToSkip[category][frozenset(newCombo)] = baseModels

                                # don't allow combos that contain both an attachment and one or more of its parts
                                categoryCombinationSubsetsToSkip[category][frozenset([equivalent, part])] = []

                    # TODO: do we even need this?
                    categoryComboEquivalentMap[category] = comboEquivalentMap

                if args.debug:
                    print('\nProcessing supersetParts...')

                categoryPartsSupersetAttachmentMap = {}
                for category, attachmentProperSubsetsMap in settings.get('supersetParts', {}).items():
                    # TODO: do we even need this?
                    partsSupersetAttachmentMap = {}
                    for attachment, properSubsets in attachmentProperSubsetsMap.items():
                        checkAttachmentName(category, attachment, f'supersetParts->superset')
                        for parts in properSubsets:
                            properSubset = frozenset(parts)

                            if True:
                                if categoryComboEquivalentMap.get(category, {}).get(properSubset, None) == attachment:
                                    printWarning(f"proper subset ({properSubset}) is also a perfect subset of {attachment}", newline=True)
                                    continue

                            # TODO: do we even need this?
                            partsSupersetAttachmentMap[properSubset] = attachment

                            if category not in categoryCombinationSubsetsToSkip:
                                categoryCombinationSubsetsToSkip[category] = {}

                            if args.debug:
                                print('Adding new combos to skip...')

                            for part in parts:
                                checkAttachmentName(category, part, f'supersetParts.{attachment}->part')
                                for comboToSkip, baseModels in [(k, v) for k, v in categoryCombinationSubsetsToSkip[category].items()]:
                                    if part in comboToSkip:
                                        # if we would skip a subset part when combined with other attachments,
                                        # skip the same other attachments when combined with the superset attachment
                                        newCombo = set(comboToSkip)
                                        newCombo.remove(part)
                                        newCombo.add(attachment)
                                        if len(newCombo) > 1:
                                            if args.debug:
                                                print(f'Original comboToSkip: {comboToSkip}. New comboToSkip: {newCombo}')
                                            categoryCombinationSubsetsToSkip[category][frozenset(newCombo)] = baseModels

                                # don't allow combos that contain both an attachment and one or more of its proper subset parts
                                categoryCombinationSubsetsToSkip[category][frozenset([attachment, part])] = []

                    # TODO: do we even need this?
                    categoryPartsSupersetAttachmentMap[category] = partsSupersetAttachmentMap

                for category, comboEquivalentMap in categoryComboEquivalentMap.items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for combo in comboEquivalentMap.keys():
                        # don't allow combos containing all the parts of an entire equivalent attachment - use the equivalent instead
                        categoryCombinationSubsetsToSkip[category][combo] = []
                print('\nExclusions generated.')

        if exportingSocketAttachments or mixingAttachments:
            exports = data['Exports']
            dataTableExport = findNextItemByType(exports, 'UAssetAPI.ExportTypes.DataTableExport, UAssetAPI')
            models = dataTableExport['Table']['Data']
            modelsCopy = models.copy()
            models.clear()
            print(f'\nProcessing {len(modelsCopy)} models...')
            for modelIndex, model in enumerate(modelsCopy):
                try:
                    modelName = getModelName(model)
                    print(f'\n{modelIndex + 1} - processing {modelName}...')

                    modelValues = getPropertyValue(model)

                    modelIdProp = getModelIdProperty(modelValues)
                    modelId = getPropertyValue(modelIdProp)
                    if modelId != modelName:
                        printWarning(f'ID ({modelId}) does not match model name ({modelName})')

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

                        if args.debug:
                            print(f"Potential attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        attachmentDisplayNamesString = ''
                        openParenIndex = modelDisplayName.find('(')
                        if openParenIndex > -1:
                            closeParenIndex = modelDisplayName.find(')', openParenIndex + 1)
                            if closeParenIndex > -1:
                                attachmentDisplayNamesString = modelDisplayName[openParenIndex + 1:closeParenIndex]

                        if args.debug:
                            print(f'Potential attachments display names string: {attachmentDisplayNamesString}')

                        attachmentDisplayNames = attachmentDisplayNamesString.split(', ') if attachmentDisplayNamesString else []
                        if args.debug:
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

                        if args.debug:
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
                                    printWarning(f'Skipping attachment {attachmentIndex + 1} (file already exists): {filePath}')
                                else:
                                    print(f'Exporting attachment {attachmentIndex + 1}: {attachmentId} ({attachmentDisplayName}) to {filePath}')

                                    attachmentInfo = {
                                        'attachmentId': attachmentId,
                                        'modelCategory': categoryName,
                                        'displayName': attachmentDisplayName,
                                        'attachmentData': attachmentData,
                                    }

                                    with open(filePath, 'w') as file:
                                        yaml.dump(attachmentInfo, file, default_flow_style=False, sort_keys=False)

                                    attachmentsCreated.append(filePath)
                    else:
                        models.append(model)
                        if mixingAttachments:
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
                                                if not len(baseModels) or modelBaseName in baseModels:
                                                    shouldSkipCombo = True

                                        if not shouldSkipCombo:
                                            for combosToSkip, baseModels in categoryCombinationSubsetsToSkip.get(categoryName, {}).items():
                                                if (not len(baseModels) or modelBaseName in baseModels) and combosToSkip <= attachmentIdsSet:
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
                                        attachmentDisplayNamesString = ', '.join([a['displayName'] for a in combo])
                                        newModelDisplayName = f'{modelDisplayNameBase} ({attachmentDisplayNamesString})'
                                        # TODO: need this?
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
                    printError(e)
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

                nameMapNamesRemoved = sorted(list(nameMapSetOld - nameMapSet), key=lambda n: n.upper())
                nameMapNamesAdded = sorted(list(nameMapSet - nameMapSetOld), key=lambda n: n.upper())

                if args.debug:
                    print(f'\nNameMap names removed: {nameMapNamesRemoved}')

                if args.debug:
                    print(f'\nNameMap names added: {nameMapNamesAdded}')

                if writingAlteredDb:
                    outFilename = f'{customizationItemDbPathNoExtension}-output.json'
                    print(f'\nWriting altered CustomizationItemDB to {outFilename}')
                    with open(outFilename, 'w') as file:
                        json.dump(data, file)

                    if True:
                        outFilename = f'{customizationItemDbPathNoExtension}-output.yaml'
                        print(f'\nWriting altered CustomizationItemDB to {outFilename}')
                        with open(outFilename, 'w') as file:
                            yaml.dump(data, file, default_flow_style=False, sort_keys=False)
    else:
        printError(f'{customizationItemDbPath} does not exist')
        exitCode = 1

    outputInfoFilename = f"{settingsFilePath.removesuffix('.yaml')}-output.yaml"
    print(f'\nWriting command output to {outputInfoFilename}')
    combosAdded = {}
    for modelNameBase, categoryCombinations in combinationsAdded.items():
        newCategoryCombinations = {}
        for category, combos in categoryCombinations.items():
            newCombos = []
            for combo in combos:
                newCombos.append(sorted(list(combo), key=lambda v: v.upper()))
            newCategoryCombinations[category] = newCombos
        combosAdded[modelNameBase] = newCategoryCombinations

    combosSkipped = {}
    for modelNameBase, categoryCombinations in combinationsSkipped.items():
        newCategoryCombinations = {}
        for category, combos in categoryCombinations.items():
            newCombos = []
            for combo in combos:
                newCombos.append(sorted(list(combo), key=lambda v: v.upper()))
            newCategoryCombinations[category] = newCombos
        combosSkipped[modelNameBase] = newCategoryCombinations

    attachmentsRead = {}
    for category, attachments in attachmentsToMix.items():
        attachmentsRead[category] = [aId for aId in attachments.keys()]

    outputInfo = {
        'errors': errors,
        'warnings': warnings,
        'attachmentsRead': attachmentsRead,
        'attachmentsRenamed': attachmentsRenamed,
        'attachmentsCreated': attachmentsCreated,
        'combosAdded': combosAdded,
        'combosSkipped': combosSkipped,
        'nameMapAlterations': {
            'namesRemoved': nameMapNamesRemoved,
            'namesAdded': nameMapNamesAdded,
        },
    }

    with open(outputInfoFilename, 'w') as file:
        yaml.dump(outputInfo, file, default_flow_style=False, sort_keys=False)

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
    parser.add_argument(
        'settingsFilePath',
        help='path to settings YAML file (if not specified, default settings.yaml will be created)',
        type=str,
        default='settings.yaml',
        nargs='?',
    )
    parser.add_argument(
        '--extract',
        help='extract socket attachment definitions',
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
        '--debug',
        help='output extra debug info to the console',
        action='store_true',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )
    args = parser.parse_args()
    sys.exit(main(args))