import os
import json
import argparse
import numpy as np
import torch
import clip
from PIL import Image

_clip_model = None
_clip_preprocess = None
_clip_device = None


def _get_clip_model():
    global _clip_model, _clip_preprocess, _clip_device
    if _clip_model is None:
        _clip_device = 'cpu'
        model, preprocess = clip.load("ViT-B/32", device=_clip_device, download_root='/opt/openclip-cache')
        _clip_model = model.to(_clip_device)
        _clip_preprocess = preprocess
    return _clip_model, _clip_preprocess, _clip_device


def select_screenshots_by_CLIP_model(images_dir):
    model, preprocess, device = _get_clip_model()

    base_dir = '/data'
    abs_images_dir = os.path.join(base_dir, images_dir)
    images = os.listdir(abs_images_dir)
    images.sort()

    if len(images) < 18:
        return [], 0

    batch_size = 8
    max_images = 1000
    image_features_list = []
    valid_images = []
    current_batch = []
    current_batch_paths = []

    image_sizes = []

    for idx, image in enumerate(images[:max_images]):
        try:
            image_path = os.path.join(abs_images_dir, image)
            img = Image.open(image_path)
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
                image_sizes.append(len(image_bytes))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img_tensor = preprocess(img).unsqueeze(0)

            current_batch.append(img_tensor)
            current_batch_paths.append(image)

            if len(current_batch) == batch_size or idx == len(images) - 1:
                if current_batch:
                    batch_tensor = torch.cat(current_batch, dim=0).to(device)
                    with torch.no_grad():
                        batch_features = model.encode_image(batch_tensor)
                        batch_features /= batch_features.norm(dim=-1, keepdim=True)
                    for i in range(len(current_batch)):
                        image_features_list.append(batch_features[i:i+1].cpu())
                        valid_images.append(current_batch_paths[i])
                    current_batch = []
                    current_batch_paths = []
        except Exception as e:
            # skip bad image
            continue

    image_sizes.sort()
    if not image_sizes:
        return [], len(images)
    mid_index = len(image_sizes) // 2
    median_image_size = image_sizes[mid_index]

    if not valid_images:
        return [], len(images)

    all_image_features = torch.cat(image_features_list, dim=0).to(device)
    similarity_matrix = torch.mm(all_image_features, all_image_features.t())
    similarity_matrix = similarity_matrix.cpu().numpy()

    selected_indices = [0]
    n_select = min(20, len(valid_images))
    diversity_threshold = 0.80

    while len(selected_indices) < n_select:
        min_similarities = []
        for i in range(len(valid_images)):
            if i in selected_indices:
                continue
            sims = similarity_matrix[i][selected_indices]
            max_sim = float(np.max(sims))
            min_similarities.append((i, max_sim))
        if not min_similarities:
            break
        next_idx, min_sim = min(min_similarities, key=lambda x: x[1])
        if min_sim > diversity_threshold:
            break
        selected_indices.append(next_idx)

    result = [valid_images[i] for i in selected_indices]
    result.sort()
    filtered = []
    for img2 in result:
        image_path = os.path.join(abs_images_dir, img2)
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
            img2_size = len(image_bytes)
        if img2_size > (median_image_size / 5):
            filtered.append(img2)
    return filtered, len(images)


def main():
    parser = argparse.ArgumentParser(description='Select screenshots using CLIP model')
    parser.add_argument('--images_dir', required=True, help='Images directory relative to /data')
    parser.add_argument('--output_path', required=True, help='Output path')
    args = parser.parse_args()

    selected, total = select_screenshots_by_CLIP_model(args.images_dir)
    result_json = json.dumps({
        'selected': selected,
        'total': total
    })
    with open(args.output_path, 'w') as f:
        f.write(result_json)


if __name__ == '__main__':
    main()
