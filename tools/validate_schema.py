#!/usr/bin/env python3
import json
import sys
import tempfile
import argparse
from pathlib import Path
from jsonschema import Draft7Validator, Draft202012Validator
from jsonschema.exceptions import ValidationError

try:
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012, DRAFT7
    import referencing.retrieval

    HAS_REFERENCING = True
except ImportError:
    # Without the referencing library, fall back to the old RefResolver
    from jsonschema import RefResolver

    HAS_REFERENCING = False


def strip_jsonc_comments(text):
    """
    Strip JSONC comments, keeping the JSON structure (and line numbers) intact
    """
    # State machine: 0=normal, 1=in a string, 2=after an escape
    result = []
    state = 0
    i = 0

    while i < len(text):
        char = text[i]

        if state == 0:  # normal
            if char == '"':
                result.append(char)
                state = 1
                i += 1
            elif i + 1 < len(text) and text[i : i + 2] == "//":
                # line comment: skip to the end of the line
                while i < len(text) and text[i] != "\n":
                    i += 1
                if i < len(text):
                    result.append("\n")  # keep the newline
                    i += 1
            elif i + 1 < len(text) and text[i : i + 2] == "/*":
                # block comment: skip to */
                i += 2
                while i + 1 < len(text) and text[i : i + 2] != "*/":
                    if text[i] == "\n":
                        result.append("\n")  # keep the newline so line numbers stay right
                    i += 1
                i += 2  # skip */
            else:
                result.append(char)
                i += 1
        elif state == 1:  # in a string
            result.append(char)
            if char == "\\":
                state = 2
            elif char == '"':
                state = 0
            i += 1
        elif state == 2:  # after an escape
            result.append(char)
            state = 1
            i += 1

    return "".join(result)


def load_jsonc(file_path):
    """Load a JSONC file"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip comments
    clean_content = strip_jsonc_comments(content)

    try:
        return json.loads(clean_content)
    except json.JSONDecodeError as e:
        print(f"JSON decode error in {file_path}: {e}")
        # Debug: save the cleaned content
        debug_file = Path(tempfile.gettempdir()) / f"debug_{Path(file_path).name}"
        with open(debug_file, "w") as f:
            f.write(clean_content)
        print(f"Cleaned content saved to {debug_file}")
        raise


def get_validator_class(schema):
    """Pick the validator class from the schema's $schema field"""
    schema_uri = schema.get("$schema", "")

    if "draft-07" in schema_uri or "draft/07" in schema_uri:
        return Draft7Validator
    elif "2020-12" in schema_uri:
        return Draft202012Validator
    else:
        # default to 2020-12
        return Draft202012Validator


def find_line_number(file_path, json_path):
    """Find the line number of a JSON path in the file

    Only top-level keys are looked up, to avoid matching a nested field
    e.g. /SomeNode/recognition -> the line of SomeNode
    """
    if not json_path or json_path == "/":
        return None

    parts = [p for p in json_path.split("/") if p]
    if not parts:
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # top level only
        # must be a key (followed by a colon), not a comment or string value
        key = parts[0]
        import re

        # match "key": or "key" :
        pattern = re.compile(rf'"{re.escape(key)}"\s*:')

        for i, line in enumerate(lines):
            if pattern.search(line):
                return i + 1  # line numbers start at 1

    except:
        pass

    return None


def validate_file(file_path, validator):
    """Validate one file"""
    try:
        data = load_jsonc(file_path)
        errors = list(validator.iter_errors(data))

        if errors:
            print(f"\n❌ Validation failed for {file_path}:")
            print(f"   Found {len(errors)} error(s):")
            for idx, error in enumerate(errors[:10], 1):
                path = "/" + "/".join(str(p) for p in error.path) if error.path else "/"
                # print(f"   {idx}. {path}: {error.message}")

                # find the line and print a GitHub Actions error annotation
                line_num = find_line_number(file_path, path)
                if line_num:
                    print(
                        f"::error file={file_path},line={line_num},title=Schema Validation Error::{path}: {error.message}"
                    )
                else:
                    print(
                        f"::error file={file_path},title=Schema Validation Error::{path}: {error.message}"
                    )
            return False

        print(f"✓ {file_path}")
        return True
    except Exception as e:
        print(f"\n❌ Error validating {file_path}: {e}")
        # print a GitHub Actions error annotation
        print(f"::error file={file_path},title=Validation Error::{e}")
        return False


def create_validator(schema, schema_store):
    """Create a validator with the referencing API, or fall back to RefResolver"""
    ValidatorClass = get_validator_class(schema)

    if HAS_REFERENCING:
        # referencing API
        registry = Registry()

        # pick the spec from the schema
        spec = DRAFT202012 if ValidatorClass == Draft202012Validator else DRAFT7

        # register every schema
        for uri, schema_content in schema_store.items():
            resource = Resource.from_contents(
                schema_content, default_specification=spec
            )
            registry = registry.with_resource(uri, resource)

        return ValidatorClass(schema, registry=registry)
    else:
        # fall back to the old RefResolver
        # find the main schema's URI in schema_store
        schema_uri = None
        for uri, content in schema_store.items():
            if content == schema:
                schema_uri = uri
                break

        if schema_uri is None:
            schema_uri = "file:///schema.json"

        resolver = RefResolver(base_uri=schema_uri, referrer=schema, store=schema_store)
        return ValidatorClass(schema, resolver=resolver)


def main():
    parser = argparse.ArgumentParser(
        description="Validate JSON/JSONC files against JSON Schema"
    )
    parser.add_argument(
        "--schema-dir",
        type=str,
        default="tools/schema",
        help="Directory containing schema files (default: tools/schema)",
    )
    parser.add_argument(
        "--resource-dirs",
        type=str,
        nargs="+",
        default=["assets/resource"],
        help="Directories containing resource files to validate (default: assets/resource)",
    )
    parser.add_argument(
        "--exclude-dirs",
        type=str,
        nargs="*",
        default=[],
        help="Directories to exclude from pipeline validation (default: none)",
    )
    parser.add_argument(
        "--interface-files",
        type=str,
        nargs="+",
        default=["assets/interface.json"],
        help="Path to interface.json files (default: assets/interface.json)",
    )
    parser.add_argument(
        "--task-dirs",
        type=str,
        nargs="*",
        default=[],
        help="Directories containing task files to validate against interface_import.schema.json (default: none)",
    )

    args = parser.parse_args()

    all_valid = True

    # Load all schema files
    schema_dir = Path(args.schema_dir).resolve()
    schema_store = {}

    print("Loading schemas...")
    for schema_file in schema_dir.glob("*.json"):
        try:
            schema = load_jsonc(schema_file)
            # key them by several URI forms
            file_uri = schema_file.as_uri()
            relative_path = f"./{schema_file.name}"
            absolute_path = f"/{schema_file.name}"

            schema_store[file_uri] = schema
            schema_store[relative_path] = schema
            schema_store[absolute_path] = schema
        except Exception as e:
            print(f"Warning: Failed to load schema {schema_file}: {e}")

    # Load and create the pipeline validator
    pipeline_schema_path = schema_dir / "pipeline.schema.json"
    pipeline_schema = load_jsonc(pipeline_schema_path)
    pipeline_schema_uri = pipeline_schema_path.as_uri()
    schema_store[pipeline_schema_uri] = pipeline_schema

    pipeline_validator = create_validator(pipeline_schema, schema_store)

    # Folders to skip
    exclude_paths = [Path(d).resolve() for d in args.exclude_dirs]

    def is_excluded(file_path):
        """Is the file inside a skipped folder?"""
        file_path = Path(file_path).resolve()
        for exclude_path in exclude_paths:
            try:
                file_path.relative_to(exclude_path)
                return True
            except ValueError:
                continue
        return False

    print("Validating pipeline resources...")
    # Validate pipeline files
    for resource_dir in args.resource_dirs:
        resource_path = Path(resource_dir)
        if not resource_path.exists():
            print(
                f"Warning: Resource directory {resource_dir} does not exist, skipping..."
            )
            continue

        for file_path in resource_path.rglob("*.json"):
            if is_excluded(file_path):
                continue
            if not validate_file(file_path, pipeline_validator):
                all_valid = False

        for file_path in resource_path.rglob("*.jsonc"):
            if is_excluded(file_path):
                continue
            if not validate_file(file_path, pipeline_validator):
                all_valid = False

    print("\nValidating interface files...")
    # Validate interface files
    interface_schema_path = schema_dir / "interface.schema.json"
    if interface_schema_path.exists():
        interface_schema = load_jsonc(interface_schema_path)
        interface_schema_uri = interface_schema_path.as_uri()
        schema_store[interface_schema_uri] = interface_schema

        interface_validator = create_validator(interface_schema, schema_store)

        for interface_file in args.interface_files:
            interface_path = Path(interface_file)
            if interface_path.exists():
                if not validate_file(interface_path, interface_validator):
                    all_valid = False
            else:
                print(
                    f"Warning: Interface file {interface_file} does not exist, skipping..."
                )

    # Validate task files
    if args.task_dirs:
        print("\nValidating task files...")
        task_schema_path = schema_dir / "interface_import.schema.json"
        if task_schema_path.exists():
            task_schema = load_jsonc(task_schema_path)
            task_schema_uri = task_schema_path.as_uri()
            schema_store[task_schema_uri] = task_schema

            task_validator = create_validator(task_schema, schema_store)

            for task_dir in args.task_dirs:
                task_path = Path(task_dir)
                if not task_path.exists():
                    print(
                        f"Warning: Task directory {task_dir} does not exist, skipping..."
                    )
                    continue

                for file_path in task_path.rglob("*.json"):
                    if not validate_file(file_path, task_validator):
                        all_valid = False

                for file_path in task_path.rglob("*.jsonc"):
                    if not validate_file(file_path, task_validator):
                        all_valid = False
        else:
            print(
                f"Warning: Task schema {task_schema_path} does not exist, skipping task validation..."
            )

    if all_valid:
        print("\n✅ All validations passed!")
        sys.exit(0)
    else:
        print("\n❌ Some validations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
