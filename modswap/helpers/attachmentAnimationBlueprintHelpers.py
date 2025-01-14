from .uassetHelpers import (ClassNameFieldName, ClassNameSkeleton,
                            ClassPackageFieldName, ClassPackageScriptEngine,
                            ImportType, ItemTypeName, findNextItemByFields,
                            getImportPathFromObjectName, getObjectNameValue)


def getSkeletonImportObjectName(imports):
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
                ClassNameSkeleton,
            ]
        ),
    )


def getSkeletonPath(imports):
    return getImportPathFromObjectName(
        imports,
        getSkeletonImportObjectName(imports),
    )
