import json
import sys
import os
import fasttext

MODEL_PATH = os.environ.get("FASTTEXT_MODEL_PATH", "/models/lid.176.bin")


def _load_model(path: str):
    try:
        return fasttext.load_model(path)
    except Exception as e:
        print(json.dumps({"error": f"Failed to load model: {e}"}))
        sys.exit(1)


def _detect_language(model, text: str, min_text_length: int = 20):
    print("fasttext input length:\n",len(text))
    print("type of text:", type(text))
    if not isinstance(text, str):
        return None
    text = text.replace("\n", " ")
    sample = text[:1000]
    print("fasttext sample:\n",sample)
    if len(sample) <= min_text_length:
        print("fasttext sample too short", len(sample), min_text_length)
        return None
    else:
        print("fasttext sample long enough", len(sample), min_text_length)
    result = model.predict(sample)
    print("fasttext result:\n",result)
    label = result[0][0]
    return label.replace("__label__", "")



def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No input provided"}))
        sys.exit(1)
    payload_filename = sys.argv[1]
    output_filename = sys.argv[2]
    if not os.path.isfile(payload_filename):
        print(json.dumps({"error": f"File not found: {payload_filename}"}))
        sys.exit(1)
    with open(payload_filename, "r", encoding='utf-8') as f:
        text = f.read()
    print(f"Input text length: {len(text)}")
    print(f"Input text: {text[:256]}")
    model = _load_model(MODEL_PATH)
    lang = _detect_language(model, text)
    print(f"Detected language: {lang}")
    print(json.dumps({"language": lang}))
    with open(output_filename, "w", encoding='utf-8') as f:
        f.write(json.dumps({"language": lang}))


if __name__ == "__main__":
    main()
