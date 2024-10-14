import hashlib
import secrets

from uassetHelpers import (ItemTypeName, NameFieldName, findNextItemByFields,
                           findStructByType, getPropertyValue)

CustomizationItemDbAssetName = 'CustomizationItemDB'
ECustomizationCategoryName = 'ECustomizationCategory'
ECustomizationCategoryNamePrefix = f'{ECustomizationCategoryName}::'
ModelDisplayNamePropNameFieldName = 'CultureInvariantString'

def generateRandomHexString(length):
    return secrets.token_hex(length // 2)


def md5Hash(string):
  return hashlib.md5(string.encode()).hexdigest()


def sha256Hash(string):
    return hashlib.sha256(string.encode()).hexdigest()[:32]


def getModelName(model):
    return model[NameFieldName]


def setModelName(model, name):
    model[NameFieldName] = name


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
