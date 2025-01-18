import hashlib
import secrets

import semver

from modswap.helpers.uassetHelpers import NameMapFieldName

from .consoleHelpers import sprint, sprintPad
from .uassetHelpers import (ArrayPropertyDataType, EnumPropertyDataType,
                            ExportsFieldName, IntPropertyDataType,
                            ItemTypeName, NameFieldName, NamePropertyDataType,
                            SoftObjectPropertyDataType, StringPropertyDataType,
                            StructPropertyDataType, StructTypeFieldName,
                            TextPropertyDataType, ValueFieldName,
                            findNextItemByFields, findStructByType,
                            getPropertyValue)

CustomizationItemDbAssetName = 'CustomizationItemDB'
ECustomizationCategoryName = 'ECustomizationCategory'
ECustomizationCategoryNamePrefix = f'{ECustomizationCategoryName}::'
ModelDisplayNamePropNameFieldName = 'CultureInvariantString'
AssetPathFieldName = 'AssetPath'
AssetNameFieldName = 'AssetName'
AttachmentBlueprintName = 'AttachementBlueprint'
AccessoryBlueprintName = 'AccessoryBlueprint'

def generateRandomHexString(length):
    return secrets.token_hex(length // 2)


def md5Hash(string):
  return hashlib.md5(string.encode()).hexdigest()


def sha256Hash(string):
    return hashlib.sha256(string.encode()).hexdigest()[:32]


def convertNone(value):
    if value == 'None':
        value = None
    return value


def getAssetPathProperty(assetProperty):
    return (assetProperty or {}).get(AssetPathFieldName, None)


def getPathPropertyPath(pathProperty):
    return (pathProperty or {}).get(AssetNameFieldName, None)


def getAssetPath(assetProperty):
    return convertNone(
        getPathPropertyPath(
            getAssetPathProperty(assetProperty),
        ),
    )


def getModelName(model):
    return model[NameFieldName]


def setModelName(model, name):
    model[NameFieldName] = name


def getModelIdProperty(modelValues, gameVersion):
    gameVersionSemver = semver.VersionInfo.parse(gameVersion)
    return findNextItemByFields(
        modelValues,
        [
            ItemTypeName,
            NameFieldName,
        ],
        [
            NamePropertyDataType if gameVersionSemver < semver.VersionInfo.parse('6.5.2') \
                # TODO: It appears it's supposed to be StringPropertyDataType for 6.5.2, but possibly can also be NamePropertyDataType
                else [StringPropertyDataType, NamePropertyDataType] if gameVersionSemver == semver.VersionInfo.parse('6.5.2') \
                # >= 6.5.2
                else StringPropertyDataType,
            'CustomizationId' if gameVersionSemver >= semver.VersionInfo.parse('6.7.0') else 'ID',
        ],
    )


def getItemMeshProperty(modelValues):
    return findNextItemByFields(
        modelValues,
        [
            ItemTypeName,
            NameFieldName,
        ],
        [
            SoftObjectPropertyDataType,
            'ItemMesh',
        ]
    )


def getAssociatedCharacterProperty(modelValues):
    return findNextItemByFields(
        modelValues,
        [
            ItemTypeName,
            NameFieldName,
        ],
        [
            IntPropertyDataType,
            'AssociatedCharacter',
        ]
    )


def getAssociatedCharacterId(modelValues):
    return convertNone(
        getPropertyValue(
            getAssociatedCharacterProperty(modelValues),
        ),
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
            ArrayPropertyDataType,
            'StructProperty',
            'SocketAttachements',
        ],
    )


def getSocketAttachments(modelValues):
    return getPropertyValue(findSocketAttachmentsStruct(modelValues))


def getAttachmentSocketName(attachmentValues):
    return convertNone(
        getPropertyValue(
            findNextItemByFields(
                attachmentValues,
                [
                    ItemTypeName,
                    NameFieldName,
                ],
                [
                    NamePropertyDataType,
                    'SocketName',
                ]
            ),
        ),
    )


def getAttachmentBlueprintProperty(attachmentValues, gameVersion=None):
    name = None
    if gameVersion is None:
        name = [AccessoryBlueprintName, AttachmentBlueprintName]
    elif semver.VersionInfo.parse(gameVersion) >= semver.VersionInfo.parse('6.5.2'):
        name = AccessoryBlueprintName
    else:
        name = AttachmentBlueprintName

    return findNextItemByFields(
        attachmentValues,
        [
            ItemTypeName,
            NameFieldName,
        ],
        [
            SoftObjectPropertyDataType,
            name,
        ]
    )


def getAttachmentBlueprintPath(attachmentValues, gameVersion):
    return convertNone(
        getAssetPath(
            getPropertyValue(
                getAttachmentBlueprintProperty(attachmentValues, gameVersion),
            ),
        ),
    )


def getAttachmentSkeletalMeshPath(attachmentValues):
    return convertNone(
        getAssetPath(
            getPropertyValue(
                findNextItemByFields(
                    attachmentValues,
                    [
                        ItemTypeName,
                        NameFieldName,
                    ],
                    [
                        SoftObjectPropertyDataType,
                        'SkeletalMesh',
                    ]
                ),
            ),
        ),
    )


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
            TextPropertyDataType,
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

                if k == ValueFieldName:
                    if itemType in {
                        StringPropertyDataType,
                        TextPropertyDataType,
                    }:
                        continue

                if itemType in {
                    'AssetAPI.UnrealTypes.FVector2D, UAssetAPI',
                } and k in {
                    'X',
                    'Y',
                }:
                    continue

                if k == AssetNameFieldName:
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


def upgradeCustomizationItemDb(customizationItemDb, gameVersion, newGameVersion, dryRun=False, debug=False):
    if gameVersion != '6.5.2':
        raise ValueError('Only supports upgrading from version 6.5.2')
    if newGameVersion != '6.7.0':
        raise ValueError('Only supports upgrading to version 6.7.0')

    # TODO: use this in a different function to "unlock" items, levels, etc., in base game files.
    # Another way of doing this is to not rename the field, but to change the value of the field.
    lockReplacements = [
        {
            'from': {
                'structType': 'CustomizationItemData',
                'Name': 'PrestigeUlockLevex',
                '$type': 'UAssetAPI.PropertyTypes.Objects.IntPropertyData, UAssetAPI',
            },
            'to': {
                'Name': 'PrestigeUlockLevel',
            },
        },
        {
            'from': {
                'structType': 'CustomizationItemData',
                'Name': 'EventIx',
                '$type': 'UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI',
            },
            'to': {
                'Name': 'EventId',
            },
        },
        {
            'from': {
                'structType': 'CustomizationItemData',
                'Name': 'IsInStorx',
                '$type': 'UAssetAPI.PropertyTypes.Objects.BoolPropertyData, UAssetAPI',
            },
            'to': {
                'Name': 'IsInStore',
            },
        },
        {
            'from': {
                'structType': 'CustomizationItemData',
                'Name': 'PlatformExclusiveFlax',
                '$type': 'UAssetAPI.PropertyTypes.Objects.UInt32PropertyData, UAssetAPI',
            },
            'to': {
                'Name': 'PlatformExclusiveFlag',
            },
        },
        {
            'from': {
                'structType': 'ItemAvailability',
                'Name': 'itemAvailabilitx',
                '$type': EnumPropertyDataType,
            },
            'to': {
                'Name': 'itemAvailability',
            },
        },
        {
            'from': {
                'structType': 'ItemAvailability',
                'Name': 'DLCIx',
                '$type': StringPropertyDataType,
            },
            'to': {
                'Name': 'DLCId',
            },
        },
        {
            'from': {
                'structType': 'ItemAvailability',
                'Name': 'CloudInventoryIx',
                '$type': 'UAssetAPI.PropertyTypes.Objects.IntPropertyData, UAssetAPI',
            },
            'to': {
                'Name': 'CloudInventoryId',
            },
        },
        {
            'from': {
                'structType': 'ItemAvailability',
                'Name': 'CommunityIx',
                '$type': StringPropertyDataType,
            },
            'to': {
                'Name': 'CommunityId',
            },
        },
    ]

    replacements = [
        {
            'from': {
                'structType': 'CustomizationItemData',
                'Name': 'ID',
                '$type': [
                    'UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI',
                    StringPropertyDataType,
                ],
            },
            'to': {
                'Name': 'CustomizationId',
                '$type': StringPropertyDataType,
                'index': -1,
            },
        },
    ]

    structTypeReplacementsMap = {}
    nameReplacementMap = {}
    for replacement in replacements:
        nameReplacementMap[replacement['from'][NameFieldName]] = replacement
        structType = replacement['from']['structType']
        if structType not in structTypeReplacementsMap:
            structTypeReplacementsMap[structType] = []
        structTypeReplacementsMap[structType].append(replacement)

    if debug:
        sprintPad()
        sprint('Names to replace:')
        for name, replacement in nameReplacementMap.items():
            sprint(f"{name} -> {replacement['to'][NameFieldName]}")
        sprintPad()

    nameMapArray = customizationItemDb[NameMapFieldName]
    nameMapSet = set(nameMapArray)

    if debug:
        sprintPad()

    for name in nameMapSet.copy():
        if False and debug:
            sprint(f'NameMap name: {name}')
        replacement = nameReplacementMap.get(name, None)
        if replacement is not None:
            newName = replacement['to'][NameFieldName]
            if debug:
                sprint(f'Replacing NameMap name from `{name}` to `{newName}`')
            nameMapSet.remove(name)
            nameMapSet.add(newName)

    if debug:
        sprintPad()

    def traverse(value, structType=None):
        if value is None:
            return

        if isinstance(value, dict):
            itemType = value.get(ItemTypeName, None)
            itemName = value.get(NameFieldName, None)

            if False and debug:
                sprint(f'{structType or "[]"}.{itemType}.{itemName}')

            if itemType == StructPropertyDataType:
                traverse(value[ValueFieldName], structType=value[StructTypeFieldName])
            elif structType in structTypeReplacementsMap:
                for replacement in structTypeReplacementsMap[structType]:
                    fromTypeData = replacement['from'].get(ItemTypeName, None)
                    replacementFromTypes = [fromTypeData] if isinstance(fromTypeData, str) else fromTypeData
                    if (
                        replacement['from'][NameFieldName] == itemName
                        and (
                            not fromTypeData or (
                                itemType in replacementFromTypes
                            )
                        )
                    ):
                        newName = replacement['to'][NameFieldName]
                        newType = replacement['to'].get(ItemTypeName, None)

                        # TODO: handle 'index' for repositioning elements?

                        if debug:
                            sprint(f'Renaming {structType}.{itemType}.{itemName} to {newType or itemType}.{newName}')

                        if not dryRun:
                            if newType is not None:
                                value[ItemTypeName] = newType
                            value[NameFieldName] = replacement['to'][NameFieldName]
        elif isinstance(value, list):
            for vIndex, v in enumerate(value):
                traverse(v, structType=structType)

    exports = customizationItemDb.get(ExportsFieldName, [])
    for export in exports:
        traverse(export['Table']['Data'])

    if debug:
        sprintPad()

    if not dryRun:
        nameMapArray.clear()
        for name in nameMapSet:
            nameMapArray.append(name)
        nameMapArray.sort(key=lambda v: v.upper())
