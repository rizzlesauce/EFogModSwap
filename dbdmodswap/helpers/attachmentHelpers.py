basicAttachmentTemplate = {'attachmentId': '',
 'modelCategory': '',
 'displayName': '',
 'attachmentData': {'$type': 'UAssetAPI.PropertyTypes.Structs.StructPropertyData, '
                             'UAssetAPI',
                    'StructType': 'BPAttachementSocketData',
                    'SerializeNone': True,
                    'StructGUID': '{00000000-0000-0000-0000-000000000000}',
                    'Name': 'SocketAttachements',
                    'DuplicationIndex': 0,
                    'IsZero': False,
                    'Value': [{'$type': 'UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData, '
                                        'UAssetAPI',
                               'Name': 'AttachementBlueprint',
                               'DuplicationIndex': 0,
                               'IsZero': False,
                               'Value': {'$type': 'UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, '
                                                  'UAssetAPI',
                                         'AssetPath': {'$type': 'UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, '
                                                                'UAssetAPI',
                                                       'PackageName': None,
                                                       'AssetName': ''},
                                         'SubPathString': None}},
                              {'$type': 'UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData, '
                                        'UAssetAPI',
                               'Name': 'SkeletalMesh',
                               'DuplicationIndex': 0,
                               'IsZero': False,
                               'Value': {'$type': 'UAssetAPI.PropertyTypes.Objects.FSoftObjectPath, '
                                                  'UAssetAPI',
                                         'AssetPath': {'$type': 'UAssetAPI.PropertyTypes.Objects.FTopLevelAssetPath, '
                                                                'UAssetAPI',
                                                       'PackageName': None,
                                                       'AssetName': 'None'},
                                         'SubPathString': None}},
                              {'$type': 'UAssetAPI.PropertyTypes.Objects.NamePropertyData, '
                                        'UAssetAPI',
                               'Name': 'SocketName',
                               'DuplicationIndex': 0,
                               'IsZero': False,
                               'Value': 'None'},
                              {'$type': 'UAssetAPI.PropertyTypes.Objects.ArrayPropertyData, '
                                        'UAssetAPI',
                               'ArrayType': 'StructProperty',
                               'DummyStruct': {'$type': 'UAssetAPI.PropertyTypes.Structs.StructPropertyData, '
                                                        'UAssetAPI',
                                               'StructType': 'MaterialReplacerData',
                                               'SerializeNone': True,
                                               'StructGUID': '{00000000-0000-0000-0000-000000000000}',
                                               'Name': 'MaterialsMap',
                                               'DuplicationIndex': 0,
                                               'IsZero': False,
                                               'Value': []},
                               'Name': 'MaterialsMap',
                               'DuplicationIndex': 0,
                               'IsZero': False,
                               'Value': []},
                              {'$type': 'UAssetAPI.PropertyTypes.Structs.StructPropertyData, '
                                        'UAssetAPI',
                               'StructType': 'ConditionalMaterialReplacer',
                               'SerializeNone': True,
                               'StructGUID': '{00000000-0000-0000-0000-000000000000}',
                               'Name': 'ConditionalMaterialReplacer',
                               'DuplicationIndex': 0,
                               'IsZero': False,
                               'Value': [{'$type': 'UAssetAPI.PropertyTypes.Objects.NamePropertyData, '
                                                   'UAssetAPI',
                                          'Name': 'ItemTag',
                                          'DuplicationIndex': 0,
                                          'IsZero': False,
                                          'Value': 'None'},
                                         {'$type': 'UAssetAPI.PropertyTypes.Objects.MapPropertyData, '
                                                   'UAssetAPI',
                                          'Value': [],
                                          'KeyType': 'NameProperty',
                                          'ValueType': 'StructProperty',
                                          'KeysToRemove': [],
                                          'Name': 'ConditionalMaterials',
                                          'DuplicationIndex': 0,
                                          'IsZero': False}]}]}}

def getAttachmentFilename(attachmentId):
    return f'SocketAttachment_{attachmentId}.yaml'

def getAttachmentDisplayName(attachment):
    return attachment['displayName'] if 'displayName' in attachment else attachment['attachmentId']
