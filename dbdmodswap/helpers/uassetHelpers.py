from .processHelpers import runCall

ItemTypeName = '$type'
NameFieldName = 'Name'
ValueFieldName = 'Value'

UassetGuiProgramStem = 'UAssetGUI'
UassetGuiProgramFilename = f'{UassetGuiProgramStem}.exe'


def findNextItemByFields(items, fields, values):
    fieldsValuesMap = {f: v for f, v in zip(fields, values)}
    return next((item for item in items if all(item[field] == value for field, value in fieldsValuesMap.items())), None)


def findNextItemByType(items, typeName):
    return findNextItemByFields(items, [ItemTypeName], [typeName])


def getPropertyValue(property):
    return property[ValueFieldName]


def setPropertyValue(property, value):
    property[ValueFieldName] = value


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


def jsonToUasset(jsonPath, uassetPath, uassetGuiPath):
    runCall([uassetGuiPath, 'fromjson', jsonPath, uassetPath])


def uassetToJson(uassetPath, jsonPath, uassetGuiPath):
    runCall([uassetGuiPath, 'tojson', uassetPath, jsonPath, 'VER_UE4_25'])
