"""LoRA fine-tuning of the VLM for chart -> table (implementation.md §10). Runs on a T4 (fp16).

    python finetune/train_lora.py --data data/finetune --out checkpoints/lora_chart2table

Then set `models.lora_adapter: checkpoints/lora_chart2table` in the config and
RE-RUN CALIBRATION: the old calibration table is invalid for a changed tool.

Starting values from the plan: rank 16, alpha 32, attention + MLP projections of
the language model only, 2 epochs. Loss is computed on the answer tokens only.
"""
from __future__ import annotations

import argparse
import json

import torch
from PIL import Image
from torch.utils.data import Dataset


class ChartTableData(Dataset):
    def __init__(self, path: str):
        self.rows = [json.loads(l) for l in open(path)]

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        return self.rows[i]


def make_collate(processor, max_len: int = 2048):
    def collate(rows):
        images = [Image.open(r["image"]).convert("RGB") for r in rows]
        full = [processor.apply_chat_template(r["messages"], tokenize=False) for r in rows]
        prompt = [processor.apply_chat_template(r["messages"][:1], tokenize=False, add_generation_prompt=True)
                  for r in rows]
        batch = processor(text=full, images=images, return_tensors="pt", padding=True,
                          truncation=True, max_length=max_len)
        prompt_len = [len(processor(text=[p], images=[im], return_tensors="pt")["input_ids"][0])
                      for p, im in zip(prompt, images)]
        labels = batch["input_ids"].clone()
        for i, n in enumerate(prompt_len):
            labels[i, :n] = -100                                   # learn only the table
        labels[batch["attention_mask"] == 0] = -100
        batch["labels"] = labels
        return batch
    return collate


def main() -> None:
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText, AutoProcessor, Trainer, TrainingArguments

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-VL-4B-Instruct")
    ap.add_argument("--data", default="data/finetune")
    ap.add_argument("--out", default="checkpoints/lora_chart2table")
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--grad-accum", type=int, default=8)
    args = ap.parse_args()

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(args.model, torch_dtype=torch.float16, device_map="auto")
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    lora = LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model,
        args=TrainingArguments(output_dir=args.out, num_train_epochs=args.epochs, learning_rate=args.lr,
                               per_device_train_batch_size=1, per_device_eval_batch_size=1,
                               gradient_accumulation_steps=args.grad_accum, fp16=True, logging_steps=20,
                               eval_strategy="steps", eval_steps=500, save_steps=500, save_total_limit=2,
                               warmup_ratio=0.03, lr_scheduler_type="cosine", remove_unused_columns=False,
                               report_to="none", seed=0),
        train_dataset=ChartTableData(f"{args.data}/train.jsonl"),
        eval_dataset=ChartTableData(f"{args.data}/val.jsonl"),
        data_collator=make_collate(processor),
    )
    trainer.train()
    model.save_pretrained(args.out)
    processor.save_pretrained(args.out)


if __name__ == "__main__":
    main()
