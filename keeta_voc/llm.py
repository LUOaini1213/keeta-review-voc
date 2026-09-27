"""Method 2: local LLM labeler (Ollama), constrained JSON output, validated against the taxonomy.

Every call is logged (prompt, raw response, parse status). Invalid outputs are kept and counted:
the review gets status != "ok" and NO labels; evaluation scores it as predicting nothing.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request

from .taxonomy import InvalidLabels, label_names, load_taxonomy, validate_labels

OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_REVIEW_CHARS = 1500
PROMPT_VERSION = "v1"


def system_prompt() -> str:
    tax = load_taxonomy()
    lines = [
        "You label customer reviews of Keeta, a food-delivery app, for an operations team.",
        "Reviews may be in English, Arabic or Chinese. Choose ALL labels whose topic the review mentions,",
        "whether the mention is positive or negative. Use 'other' only when no other label applies,",
        "and never combine 'other' with another label.",
        "",
        "Labels:",
    ]
    for name, spec in tax["labels"].items():
        lines.append(f"- {name}: {spec['definition']}")
    lines += ["", 'Answer with JSON only, e.g. {"labels": ["delivery_time", "customer_service"]}.']
    return "\n".join(lines)


def user_prompt(title: str, text: str) -> str:
    body = text if len(text) <= MAX_REVIEW_CHARS else text[:MAX_REVIEW_CHARS] + " [...]"
    return f"Review title: {title}\nReview text: {body}"


def response_schema() -> dict:
    return {"type": "object",
            "properties": {"labels": {"type": "array", "items": {"type": "string", "enum": list(label_names())}}},
            "required": ["labels"]}


def parse_response(raw: str) -> tuple[str, list[str] | None, str | None]:
    """Return (status, labels, error). status is 'ok', 'bad_json' or 'bad_labels'."""
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        return "bad_json", None, str(exc)[:200]
    if not isinstance(obj, dict) or "labels" not in obj:
        return "bad_json", None, "missing 'labels' key"
    try:
        return "ok", validate_labels(obj["labels"]), None
    except InvalidLabels as exc:
        return "bad_labels", None, str(exc)


def build_request(model: str, title: str, text: str, seed: int = 0) -> dict:
    return {
        "model": model,
        "stream": False,
        "format": response_schema(),
        "options": {"temperature": 0, "seed": seed, "num_gpu": 0, "num_ctx": 2048, "num_predict": 64},
        "messages": [{"role": "system", "content": system_prompt()},
                     {"role": "user", "content": user_prompt(title, text)}],
    }


def call_ollama(req: dict, timeout: float = 300.0) -> dict:
    data = json.dumps(req).encode("utf-8")
    r = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:  # noqa: S310 - localhost
        return json.loads(resp.read().decode("utf-8"))


def label_one(model: str, review_key: str, title: str, text: str, call=call_ollama) -> dict:
    req = build_request(model, title, text)
    t0 = time.time()
    try:
        resp = call(req)
        raw = resp.get("message", {}).get("content", "")
        err_http = None
    except Exception as exc:  # recorded, counted as invalid
        resp, raw, err_http = {}, "", repr(exc)
    status, labels, err = ("http_error", None, err_http) if err_http else parse_response(raw)
    prompt_text = req["messages"][0]["content"] + "\n" + req["messages"][1]["content"]
    return {
        "review_key": review_key,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "user_prompt": req["messages"][1]["content"],
        "raw_response": raw,
        "status": status,
        "labels": labels,
        "error": err,
        "seconds": round(time.time() - t0, 2),
        "eval_count": resp.get("eval_count"),
        "prompt_eval_count": resp.get("prompt_eval_count"),
    }
