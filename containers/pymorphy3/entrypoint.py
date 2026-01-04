#!/usr/bin/env python3
import sys
import json
import argparse

try:
    import pymorphy3
except Exception as e:
    print(json.dumps({"error": f"Failed to import pymorphy3: {e}"}))
    sys.exit(10)


def base_forms_for_name(name: str, language: str) -> list[str]:
    if not isinstance(name, str) or not name:
        return []
    if language != 'ru':
        # Non-Russian: return unchanged
        return [name]
    try:
        morph = pymorphy3.MorphAnalyzer()
        forms = {p.normal_form.capitalize() for p in morph.parse(name)}
        if not forms:
            return [name]
        return sorted(forms)
    except Exception:
        # If something goes wrong, fallback to original
        return [name]


def main():
    parser = argparse.ArgumentParser(description='Get base forms for Russian names using pymorphy3')
    parser.add_argument('input_json', help='Input JSON string with {"language": str, "names": [str, ...]}')
    args = parser.parse_args()

    raw = args.input_json

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    language = payload.get("language")
    names = payload.get("names")

    if not isinstance(names, list):
        print(json.dumps({"error": "'names' must be a list of strings"}))
        sys.exit(3)

    try:
        result = [base_forms_for_name(n, language) for n in names]
    except Exception as e:
        print(json.dumps({"error": f"Processing failed: {e}"}))
        sys.exit(4)

    print(json.dumps({"base_names": result}))


if __name__ == "__main__":
    main()
