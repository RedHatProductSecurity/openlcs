import os
import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Specification for product/package manifest file schema.
# Schema definition is based on sample file `release.json` from
# https://gitlab.cee.redhat.com/oscp/pelc-report, refer to
# https://red.ht/3t8ZRiS for the file snapshot. This may change
# in case there is update from upstream.
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
