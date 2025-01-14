import os

from modswap.helpers.pathHelpers import getPathInfo, normPath

from .processHelpers import runCall

ItemTypeName = '$type'
NameFieldName = 'Name'
ValueFieldName = 'Value'

UassetGuiProgramStem = 'UAssetGUI'
UassetGuiProgramFilename = f'{UassetGuiProgramStem}.exe'

PackageGuidFieldName = 'PackageGuid'
NamePropertyDataType = 'UAssetAPI.PropertyTypes.Objects.NamePropertyData, UAssetAPI'
StringPropertyDataType = 'UAssetAPI.PropertyTypes.Objects.StrPropertyData, UAssetAPI'
TextPropertyDataType = 'UAssetAPI.PropertyTypes.Objects.TextPropertyData, UAssetAPI'
SoftObjectPropertyDataType = 'UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData, UAssetAPI'
IntPropertyDataType = 'UAssetAPI.PropertyTypes.Objects.IntPropertyData, UAssetAPI'
ArrayPropertyDataType = 'UAssetAPI.PropertyTypes.Objects.ArrayPropertyData, UAssetAPI'
ImportType = 'UAssetAPI.Import, UAssetAPI'
ClassPackageCoreUObject = '/Script/CoreUObject'
ClassPackageScriptEngine = '/Script/Engine'
ClassPackageFieldName = 'ClassPackage'
ClassNameFieldName = 'ClassName'
ClassNamePackage = 'Package'
ClassNameSkeletalMesh = 'SkeletalMesh'
ClassNameSkeleton = 'Skeleton'
ClassSuffix = '_C'
ClassNameAnimBlueprintGeneratedClass = 'AnimBlueprintGeneratedClass'
ObjectNameFieldName = 'ObjectName'
ImportsFieldName = 'Imports'
ExportsFieldName = 'Exports'
ZeroGuid = '00000000-0000-0000-0000-000000000000'
JsonPackageGuidRegex = r'"PackageGuid":(?P<space>\s*)"{(?P<guid>[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12})}"'

AssetPathGamePrefix = '/Game/'

def getShortenedAssetPath(assetPath):
    if assetPath:
        assetPathInfo = getPathInfo(assetPath.removeprefix(AssetPathGamePrefix))
        return normPath(os.path.join(assetPathInfo['dirname'], assetPathInfo['stem']))


def findNextItemByFields(items, fields, values):
    if items:
        fieldsValuesMap = {f: v for f, v in zip(fields, [{item} if isinstance(item, str) else set(item) for item in values])}
        return next((item for item in items if all(item[field] in values for field, values in fieldsValuesMap.items())), None)


def findNextItemByType(items, typeName):
    return findNextItemByFields(items, [ItemTypeName], [typeName])


def getPropertyValue(property, default=None):
    return (property or {}).get(ValueFieldName, default)


def getObjectNameValue(property, default=None):
    return (property or {}).get(ObjectNameFieldName, default)


def setPropertyValue(property, value):
    property[ValueFieldName] = value


def getEnumValue(enum, default=None):
    return getPropertyValue(enum, default=default)


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


def jsonToUasset(jsonPath, uassetPath, uassetGuiPath):
    # TODO: capture error message if exists
    runCall([uassetGuiPath, 'fromjson', jsonPath, uassetPath])


def uassetToJson(uassetPath, jsonPath, uassetGuiPath, ueVersion):
    # TODO: capture error message if exists
    versionParts = ueVersion.split('.')
    version = 'VER_UE' + '_'.join(versionParts)
    runCall([uassetGuiPath, 'tojson', uassetPath, jsonPath, version])


def getImportPathFromObjectName(imports, objectName):
    if objectName:
        meshImport = next(
            (
                prop for prop in imports if (
                    prop.get(ItemTypeName, None) == ImportType
                    and prop.get(ClassPackageFieldName, None) == ClassPackageCoreUObject
                    and prop.get(ClassNameFieldName, None) == ClassNamePackage
                    and prop.get(ObjectNameFieldName, '').endswith(objectName)
                )
            ),
            None,
        )
        return (meshImport or {}).get(ObjectNameFieldName, None)
