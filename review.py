"""
local_summarizer.py
this one looks a bit diffrent
Usage:
    python local_summarizer.py --input-file chapter.txt --lang en
    python local_summarizer.py --input-file chapter_fa.txt --lang fa

You can also run without --input-file and paste text into stdin (end with EOF).
"""

import argparse
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import math
import os
import sys
from typing import List

# --------- Configurable defaults ----------
DEFAULT_EN_MODEL = "facebook/bart-large-cnn"   # good general English summarizer
DEFAULT_MULTI_MODEL = "google/mt5-small"       # multilingual (smaller) — supports many langs incl. fa
# You can replace DEFAULT_MULTI_MODEL with a Persian-finetuned model if you have one.

# size limits (characters) for chunking — tune based on model token limits and GPU/RAM
CHUNK_CHAR_SIZE = 2500    # approx characters per chunk (safe default)
SUMMARY_MAX_LENGTH = 130  # max tokens for per-chunk summary (model tokens; approximate)
SUMMARY_MIN_LENGTH = 30

# ------------------------------------------

def read_input(input_file: str):
    if input_file:
        with open(input_file, "r", encoding="utf-8") as f:
            return f.read()
    else:
        print("Paste the chapter text, then press Ctrl+D (or Ctrl+Z+Enter on Windows):")
        return sys.stdin.read()

def chunk_text(text: str, max_chunk_chars: int) -> List[str]:
    """Split text into chunks of ~max_chunk_chars without cutting sentences badly."""
    import re
    sentences = re.split(r'(?<=[.!؟!\n])\s+', text)  # split on sentence boundaries (includes Persian punctuation)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) <= max_chunk_chars or not current:
            current += ("" if current == "" else " ") + s
        else:
            chunks.append(current.strip())
            current = s
    if current.strip():
        chunks.append(current.strip())
    return chunks

def create_summarizer(model_name: str, device: int = -1):
    """
    Create a transformers summarization pipeline.
    device=-1 -> CPU, device=0 -> first GPU.
    """
    # load model and tokenizer explicitly for better control
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    summarizer = pipeline("summarization", model=model, tokenizer=tokenizer, device=device)
    return summarizer

def summarize_long_text(text: str, summarizer, lang: str = "en") -> str:
    """
    Hierarchical summarization:
      1) split into chunks
      2) summarize each chunk
      3) if >1 chunk, join summaries and summarize again
    """
    chunks = chunk_text(text, CHUNK_CHAR_SIZE)
    # safety: if text is short, run single summarization
    if len(chunks) == 1:
        out = summarizer(chunks[0], max_length=SUMMARY_MAX_LENGTH, min_length=SUMMARY_MIN_LENGTH, do_sample=False)
        return out[0]['summary_text'].strip()

    chunk_summaries = []
    for i, c in enumerate(chunks, 1):
        sys.stdout.write(f"Summarizing chunk {i}/{len(chunks)}...\n")
        sys.stdout.flush()
        # adjust max_length based on chunk length heuristically
        out = summarizer(c, max_length=SUMMARY_MAX_LENGTH, min_length=SUMMARY_MIN_LENGTH, do_sample=False)
        s = out[0]['summary_text'].strip()
        chunk_summaries.append(s)

    # join the short summaries and summarize them
    combined = "\n\n".join(chunk_summaries)
    sys.stdout.write("Summarizing combined chunk summaries into final summary...\n")
    sys.stdout.flush()
    # final summary shorter
    final_out = summarizer(combined, max_length=SUMMARY_MAX_LENGTH, min_length=SUMMARY_MIN_LENGTH, do_sample=False)
    return final_out[0]['summary_text'].strip()

def main():
    parser = argparse.ArgumentParser(description="Local chapter summarizer (English / Persian).")
    parser.add_argument("--input-file", "-i", help="Path to text file containing the chapter. If omitted, read stdin.")
    parser.add_argument("--lang", "-l", choices=["en", "fa"], default="en", help="Language of input (en or fa).")
    parser.add_argument("--model", help="(Optional) HuggingFace model name to use. If omitted, a default per-language will be used.")
    parser.add_argument("--device", type=int, default=-1, help="Device for model: -1 CPU, 0..n for GPU device IDs.")
    args = parser.parse_args()

    text = read_input(args.input_file)
    if not text or text.strip() == "":
        print("No input text provided. Exiting.")
        return

    # select model
    if args.model:
        model_name = args.model
    else:
        model_name = DEFAULT_EN_MODEL if args.lang == "en" else DEFAULT_MULTI_MODEL

    print(f"Using model: {model_name} (lang={args.lang})")
    summarizer = create_summarizer(model_name, device=args.device)
    final_summary = summarize_long_text(text, summarizer, lang=args.lang)

    print("\n" + "="*40 + "\nFINAL SUMMARY:\n" + "="*40 + "\n")
    print(final_summary)
    print("\n" + "="*40 + "\n")

if __name__ == "__main__":
    main()
