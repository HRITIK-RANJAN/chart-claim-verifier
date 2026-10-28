"""One shared model loader (implementation.md §14): load the VLM once, reuse it for
claim parsing, the controller, and tools 1–2.

Anything that needs a language model takes an object with this method:

    generate(prompt: str, images: Sequence[str | PIL.Image] = (), temperature=0.0,
             max_new_tokens=256, n=1) -> list[str]

`VLM` is the real (GPU) implementation; `ScriptedLLM` is a stand-in for tests.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Protocol, Sequence


class LLM(Protocol):
    name: str

    def generate(self, prompt: str, images: Sequence = (), temperature: float = 0.0,
                 max_new_tokens: int = 256, n: int = 1, adapter: bool = False) -> list[str]: ...


def best_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class VLM:
    """Qwen3-VL (default Qwen/Qwen3-VL-4B-Instruct) via transformers.

    fp16 on a T4 (CUDA) or on Apple silicon (MPS); fp32 on plain CPU.
    """

    def __init__(self, model_id: str, dtype: str = "float16", lora_adapter: str | None = None,
                 load_in_4bit: bool = False, device: str | None = None, max_pixels: int = 640 * 28 * 28):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.device = device or best_device()
        self.base_name = model_id               # the adapter is used only for the chart-to-table task (adapter=True)
        self.name = model_id + (f"+{lora_adapter}" if lora_adapter else "")
        self.has_adapter = bool(lora_adapter)
        torch_dtype = getattr(torch, dtype) if self.device != "cpu" else torch.float32
        kwargs = {"dtype": torch_dtype}
        if load_in_4bit and self.device == "cuda":
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch_dtype)
            kwargs["device_map"] = "auto"
        # cap image size: charts do not need more than ~640 visual tokens
        self.processor = AutoProcessor.from_pretrained(model_id, max_pixels=max_pixels)
        self.model = AutoModelForImageTextToText.from_pretrained(model_id, **kwargs)
        if "device_map" not in kwargs:
            self.model.to(self.device)
        if lora_adapter:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, lora_adapter)
        self.model.eval()

    def generate(self, prompt, images=(), temperature=0.0, max_new_tokens=256, n=1, adapter=False):
        import contextlib
        import torch
        from PIL import Image

        content = [{"type": "image", "image": Image.open(i).convert("RGB") if isinstance(i, str) else i}
                   for i in images]
        content.append({"type": "text", "text": prompt})
        inputs = self.processor.apply_chat_template(
            [{"role": "user", "content": content}], tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt").to(self.model.device)
        sample = temperature > 0
        gen = {"max_new_tokens": max_new_tokens, "do_sample": sample, "num_return_sequences": n}
        if sample:
            gen.update(temperature=temperature, top_p=0.95)
        else:
            gen.update(temperature=None, top_p=None, top_k=None)
        off = self.model.disable_adapter() if self.has_adapter and not adapter else contextlib.nullcontext()
        with torch.inference_mode(), off:
            out = self.model.generate(**inputs, **gen)
        out = out[:, inputs["input_ids"].shape[1]:]
        return self.processor.batch_decode(out, skip_special_tokens=True)


class OfflineMiss(Exception):
    """A replay needed a model call that is not in the reading cache."""


class OfflineLLM:
    """Stand-in model for replays (`--offline`): answers nothing, so a missing reading is
    reported as `offline_miss` instead of silently loading the model."""

    def __init__(self, name: str, base_name: str | None = None):
        self.name, self.base_name = name, base_name or name

    def generate(self, *args, **kwargs):
        raise OfflineMiss("model call needed")


class ScriptedLLM:
    """Test double: answers come from a function of (prompt, images, call index)."""

    def __init__(self, respond: Callable[[str, Sequence, int], str], name: str = "scripted"):
        self.respond, self.name, self.calls = respond, name, 0

    def generate(self, prompt, images=(), temperature=0.0, max_new_tokens=256, n=1, adapter=False):
        out = []
        for _ in range(n):
            out.append(self.respond(prompt, images, self.calls))
            self.calls += 1
        return out


def extract_json(text: str):
    """First JSON object/array in a model answer (models like to add prose or ``` fences)."""
    text = re.sub(r"```(?:json)?", "", text)
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == opener:
                    depth += 1
                elif text[i] == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break
            start = text.find(opener, start + 1)
    raise ValueError("no JSON found")
