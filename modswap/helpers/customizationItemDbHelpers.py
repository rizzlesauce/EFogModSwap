import hashlib
import secrets

from .uassetHelpers import (ArrayPropertyDataType, IntPropertyDataType,
                            ItemTypeName, NameFieldName, NamePropertyDataType,
                            SoftObjectPropertyDataType, StringPropertyDataType,
                            TextPropertyDataType, ValueFieldName,
                            findNextItemByFields, findStructByType,
                            getPropertyValue)

CustomizationItemDbAssetName = 'CustomizationItemDB'
ECustomizationCategoryName = 'ECustomizationCategory'
ECustomizationCategoryNamePrefix = f'{ECustomizationCategoryName}::'
ModelDisplayNamePropNameFieldName = 'CultureInvariantString'
AssetPathFieldName = 'AssetPath'
AssetNameFieldName = 'AssetName'
NameMapFieldName = 'NameMap'
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
    return findNextItemByFields(
        modelValues,
        [
            ItemTypeName,
            NameFieldName,
        ],
        [
            StringPropertyDataType if gameVersion == '6.5.2' else NamePropertyDataType,
            'ID',
        ]
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
    elif gameVersion == '6.5.2':
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
                        'UAssetAPI.PropertyTypes.Objects.StrPropertyData, UAssetAPI',
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
