import copy
import json
import logging
import os
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from dacite import Config, from_dict

from src.helpers.filepath_helper import generate_random_filename, get_abs_path

logger = logging.getLogger(__name__)

def copy_arguments(args):
    return copy.deepcopy(args)


def one_of(loaders, arg, validator=None):
    last_exception = None
    print(f"Trying to load {arg}")
    print(f"Will iterate {len(loaders)} loaders: {[loader.__name__ for loader in loaders]}")
    for i, loader in enumerate(loaders):
        try:
            print(f"  Trying {loader.__name__}, {i + 1}/{len(loaders)}")
            result = loader(arg)
            if validator is not None:
                if not validator(result, arg):
                    continue
            print(f"    Success {loader.__name__}")
            return result
        except Exception as e:
            logger.debug(f"Failed {loader.__name__}: {e}")
            last_exception = e
            print(f"    Failed {loader.__name__}, trying next one")
    if last_exception:
        raise last_exception
    return None


@dataclass(frozen=True)
class PipelineResource:
    factory: Callable[[], Any]
    setup: Callable[[Any], None]


@dataclass
class PipelineStage:
    func: Callable
    inputs: list[str]
    outputs: list[str]
    enabled: bool = True
    resources: list[PipelineResource] = field(default_factory=list)
    _given_name: str = None

    @property
    def name(self):
        return self._given_name or self.func.__name__


def run_with_resources(func, resources: list[PipelineResource], current_args):
    if not resources:
        return func(*current_args)

    resource_def = resources[0]
    with resource_def.factory() as resource:
        resource_def.setup(resource)
        return run_with_resources(func, resources[1:], current_args)


def fold_pipeline(pipeline: list[PipelineStage], video):
    current_video = video
    index = 1
    active_pipeline = [stage for stage in pipeline if stage.enabled]
    for stage in active_pipeline:
        args = []
        output_calculated = False
        for output in stage.outputs:
            if getattr(current_video, output) is not None:
                output_calculated = True
        if output_calculated:
            index += 1
            print(f"{stage.name} skipped")
            continue
        for input_ in stage.inputs:
            if input_ is None:
                args.append(None)
            else:
                args.append(getattr(current_video, input_))
        try:
            start_time = time.time()
            args = copy.deepcopy(args)

            results = run_with_resources(stage.func, stage.resources, args)

            if not isinstance(results, tuple):
                results = (results,)
            for output, result in zip(stage.outputs, list(results), strict=False):
                setattr(current_video, output, result)
            end_time = time.time()
            execution_time = end_time - start_time
            if not hasattr(current_video, "execution_times"):
                current_video.execution_times = {}
            current_video.execution_times[stage.name] = execution_time
            print(f"{stage.name} done {index}/{len(active_pipeline)} in {execution_time:.2f}s")
            index += 1
        except Exception as e:
            print(f"fold_pipeline {stage.name} failed with {e}")
            args_text = ""
            for i, arg in enumerate(args):
                args_text += f"arg {i}: {str(arg)[:128]}\n"
            print(f"args: {args_text}")
            logger.debug(traceback.format_exc())
            index += 1
            continue
    video_json = asdict(current_video)
    log_filename = generate_random_filename(
        "pipeline_state_" + video.__class__.__name__.lower(), "json"
    )
    with open(get_abs_path(log_filename), "w", encoding="utf-8") as f:
        json.dump(video_json, f, indent=4, ensure_ascii=False)
    return current_video, log_filename


def restart_stage(stage_name: str, pipeline, log_filename, class_instance):
    abs_log_filename = get_abs_path(log_filename)
    video_dict = json.load(open(abs_log_filename, encoding="utf-8"))

    start_idx = 0
    for idx, stage in enumerate(pipeline):
        if stage.name == stage_name:
            start_idx = idx
            break
    tail_pipeline = pipeline[start_idx:]

    for stage in tail_pipeline:
        for output in stage.outputs:
            video_dict[output] = None
    video = from_dict(data_class=class_instance, data=video_dict, config=Config(check_types=False))
    return fold_pipeline(pipeline, video)


def get_last_pipeline_state(class_instance, query) -> str | None:
    prefix = "pipeline_state_" + class_instance.__name__.lower()
    files = [f for f in os.listdir("data") if f.startswith(prefix)]
    if not files:
        return None
    files2 = []
    for f in files:
        state_dict = json.load(open(os.path.join("data", f), encoding="utf-8"))
        correct = True
        for k, v in query.items():
            if state_dict.get(k) != v:
                correct = False
        if correct:
            files2.append(f)
    if not files2:
        return None
    files2.sort(key=lambda f: os.path.getctime(os.path.join("data", f)))
    return files2[-1]
