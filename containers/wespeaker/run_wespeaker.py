import json

import wespeaker
import argparse
import sys
import torch

def parse_args():
    # Docker command includes a literal "--" before script args; strip it so argparse works.
    argv = sys.argv[1:]
    if len(argv) > 0 and argv[0] == "--":
        argv = argv[1:]

    parser = argparse.ArgumentParser(description="wespeaker runner (external diarization via JSON)")
    # WhisperX-like minimal interface we rely on in whisperx_wrapper
    parser.add_argument("audio", help="Path to input audio file")
    parser.add_argument("output_json", help="Path to output json file")
    parser.add_argument("language", default="en", help="language code - en or anything else")
    return parser.parse_args(argv)

def main():
    args = parse_args()
    audio_path = args.audio
    json_path = args.output_json
    language = args.language

    if language == 'en':
        model = wespeaker.load_model('english')
    else:
        model = wespeaker.load_model('vblinkf')
    if torch.cuda.is_available():
        model.set_device('cuda:0')
    else:
        model.set_device('cpu')
        torch.set_num_threads(8)

    diar_result = model.diarize(audio_path)

    print(diar_result)
    result = []
    for (_, start, end, spkid) in diar_result:
        result.append({'start': start, 'end': end, 'speaker': spkid})
    json_result = {'diarization_segments': result}
    json_result_str = json.dumps(json_result)
    with open(json_path, 'w') as f:
        f.write(json_result_str)
    print(json_result_str)

if __name__ == "__main__":
    main()