"""E6: LoRA fine-tune Qwen3-VL-4B to turn a chart into a JSON table (the job of tool 2, `vlm_table`).

    python scripts/finetune_lora.py --pool ft_pool --out checkpoints/lora_chart2table --epochs 1

Training pairs: the chart image the report contains -> the true table as JSON, in the exact prompt the tool uses.
One chart per step (batch 1, gradient accumulation), loss on the answer tokens only, LoRA on the language model's
attention and MLP projections (rank 16, alpha 32). Writes a checkpoint every `--save_every` steps and a log line per step.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from chart_claim_verifier.tools.vlm_table import PROMPT

ROOT = Path("data/local/generated")


def target_json(table: dict) -> str:
    d = table.get("decimals", 1)
    out = {s: {str(x): round(v, d) for x, v in zip(table["x_values"], vals)} for s, vals in table["series"].items()}
    return json.dumps(out, ensure_ascii=False)


def load_pairs(pool: str) -> list[tuple[str, str]]:
    pairs = []
    for t in sorted((ROOT / pool).glob("*/truth.json")):
        for f in json.loads(t.read_text())["figures"]:
            pairs.append((str(t.parent / f["image"]), target_json(f["table"])))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="ft_pool")
    ap.add_argument("--out", default="checkpoints/lora_chart2table")
    ap.add_argument("--model", default="Qwen/Qwen3-VL-4B-Instruct")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--max_pixels", type=int, default=640 * 28 * 28)
    ap.add_argument("--max_answer_tokens", type=int, default=700)
    ap.add_argument("--val", type=int, default=50, help="charts held out to track the validation loss")
    ap.add_argument("--save_every", type=int, default=20, help="optimizer steps")
    ap.add_argument("--max_steps", type=int, default=0, help="stop early (speed test)")
    args = ap.parse_args()

    import torch
    from PIL import Image
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText, AutoProcessor

    random.seed(0)
    torch.manual_seed(0)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    proc = AutoProcessor.from_pretrained(args.model, max_pixels=args.max_pixels)
    model = AutoModelForImageTextToText.from_pretrained(args.model, dtype=torch.bfloat16).to(dev)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    cfg = LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                     target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)")
    model = get_peft_model(model, cfg)
    for p in model.parameters():                      # LoRA weights in fp32 for stable updates
        if p.requires_grad:
            p.data = p.data.float()
    model.print_trainable_parameters()

    def encode(img_path: str, answer: str):
        img = Image.open(img_path).convert("RGB")
        user = [{"role": "user", "content": [{"type": "image", "image": img}, {"type": "text", "text": PROMPT}]}]
        prompt = proc.apply_chat_template(user, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt")
        full = proc.apply_chat_template(user + [{"role": "assistant", "content": [{"type": "text", "text": answer}]}],
                                        tokenize=True, add_generation_prompt=False, return_dict=True, return_tensors="pt")
        labels = full["input_ids"].clone()
        labels[:, :prompt["input_ids"].shape[1]] = -100
        full["labels"] = labels
        return full

    pairs = load_pairs(args.pool)
    random.shuffle(pairs)
    val, train = pairs[:args.val], pairs[args.val:]
    tok = proc.tokenizer
    train = [(i, a) for i, a in train if len(tok(a)["input_ids"]) <= args.max_answer_tokens]
    print(f"train {len(train)} charts, val {len(val)} charts", flush=True)

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    total_micro = int(len(train) * args.epochs)
    total_opt = max(1, total_micro // args.accum)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 5) * max(0.05, 1 - s / total_opt))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "train_log.jsonl", "a")

    def val_loss() -> float:
        model.eval()
        tot = 0.0
        with torch.no_grad():
            for img, ans in val:
                b = encode(img, ans).to(dev)
                tot += model(**b).loss.item()
        model.train()
        return tot / max(1, len(val))

    model.train()
    t0 = time.time()
    micro, step, run_loss, skipped = 0, 0, 0.0, 0
    order = []
    while len(order) < total_micro:
        ep = train[:]
        random.shuffle(ep)
        order += ep
    order = order[:total_micro]
    print("val loss before:", round(val_loss(), 4), flush=True)
    for img, ans in order:
        try:
            b = encode(img, ans).to(dev)
            loss = model(**b).loss
            (loss / args.accum).backward()
            run_loss += loss.item()
        except RuntimeError as e:                     # MPS out of memory on a long chart: skip it, keep going
            if "out of memory" not in str(e):
                raise
            skipped += 1
            print("skipped one chart (out of memory)", flush=True)
            b = loss = None
        torch.mps.empty_cache()
        micro += 1
        if micro % args.accum == 0:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            step += 1
            rec = {"step": step, "of": total_opt, "loss": round(run_loss / args.accum, 4),
                   "elapsed_min": round((time.time() - t0) / 60, 1)}
            run_loss = 0.0
            print(json.dumps(rec), flush=True)
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if step % args.save_every == 0:
                model.save_pretrained(out)
            if args.max_steps and step >= args.max_steps:
                break
    model.save_pretrained(out)
    vl = val_loss()
    print("val loss after:", round(vl, 4), flush=True)
    (out / "summary.json").write_text(json.dumps({"charts": len(train), "epochs": args.epochs, "steps": step,
                                                  "val_loss_after": vl, "skipped_oom": skipped, "minutes": round((time.time() - t0) / 60, 1)}))
    print("finetune done", flush=True)


if __name__ == "__main__":
    main()
