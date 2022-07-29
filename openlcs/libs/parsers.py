import hashlib
import os
import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Specification for product/package manifest file schema.
MANIFEST_FILE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Product/package manifest file",
    "description": "Product/package manifest file",
    "type": "object",
    "properties": {
        "release": {
            "$ref": "#/definitions/Release",
        }
    },
    "definitions": {
        "Release": {
            "type": "object",
            "properties": {
                "productname": {"type": "string"},
                "version": {"type": "string"},
                "notes": {"type": ["null", "string"]},
                "containers": {"type": "array"},
                "src_packages": {"type": "array"},
            },
            "required": ["productname", "version"],
        }
    },
    "required": ["release"],
    "additionalProperties": False,
}


def parse_manifest_file(fp):
    """
    Accept a filepath or file-like object for the manifest json file,
    returns a dict as follows:
    {
        'productname': 'name_of_product',
        'version': 'product version',
        'notes': 'notes of the manifest file',
        'containers': ['container_nvr1', container_nvr2, ...],
        'src_packages': ['package_nvr1', 'package_nvr2', ...]
    }
    Raise runtime error in case of exceptions.
    """
    manifest_file = None
    if not hasattr(fp, 'read'):
        if not os.path.isfile(fp):
            raise RuntimeError(f'{fp} is not a file.')
        else:
            # 'utf-8' is the default encoding for python3
            manifest_file = open(fp, mode='r', encoding='utf-8')
    else:
        manifest_file = fp

    try:
        manifest_json = json.load(manifest_file)
        # Validate is done here so that the file is loaded only once.
        validate(instance=manifest_json, schema=MANIFEST_FILE_SCHEMA)
    except json.JSONDecodeError as e:
        raise RuntimeError(e.msg) from e
    except ValidationError as e:
        raise RuntimeError(e.message) from e
    else:
        return manifest_json['release']


def sha256sum(path, block_size=65536):
    """
    Counts checksum of file given by path

    :param str path: path to file
    :param int block_size: maximal length in bits read in one iteration
    :return: Returns checks sum of given file
    :rtype: str
    """
    checksum = hashlib.sha256()
    with open(path, 'rb') as f:
        chunk = f.read(block_size)
        while chunk:
            checksum.update(chunk)
            chunk = f.read(block_size)

    return checksum.hexdigest()
