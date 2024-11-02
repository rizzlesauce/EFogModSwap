from .uassetHelpers import (ClassNameAnimBlueprintGeneratedClass,
                            ClassNameFieldName, ClassNameSkeletalMesh,
                            ClassPackageFieldName, ClassPackageScriptEngine,
                            ClassSuffix, ImportType, ItemTypeName,
                            findNextItemByFields, getImportPathFromObjectName,
                            getObjectNameValue)


def getSkeletalMeshImportObjectName(imports):
    return getObjectNameValue(
        findNextItemByFields(
            imports,
            [
                ItemTypeName,
                ClassPackageFieldName,
                ClassNameFieldName,
            ],
            [
                ImportType,
                ClassPackageScriptEngine,
                ClassNameSkeletalMesh,
            ]
        ),
    )


def getSkeletalMeshPath(imports):
    return getImportPathFromObjectName(
        imports,
        getSkeletalMeshImportObjectName(imports),
    )


def getAnimBlueprintImportObjectName(imports):
    return getObjectNameValue(
        findNextItemByFields(
            imports,
            [
                ItemTypeName,
                ClassPackageFieldName,
                ClassNameFieldName,
            ],
            [
                ImportType,
                ClassPackageScriptEngine,
                ClassNameAnimBlueprintGeneratedClass,
            ]
        ),
    )


def getAnimBlueprintPath(imports):
    objectName = getAnimBlueprintImportObjectName(imports)
    if objectName and objectName.endswith(ClassSuffix):
        objectName = objectName[:-len(ClassSuffix)]

    return getImportPathFromObjectName(
        imports,
        objectName,
    )
