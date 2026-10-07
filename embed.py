"""
=====================================================
  RAG CHATBOT — STEP 2: EMBEDDING
  Converts your 123 text chunks into numbers
  that the chatbot can search through intelligently
=====================================================
WHAT THIS DOES (in plain English):
  Step 1 gave us 123 "index cards" of text.
  This script sends each card to OpenAI and gets
  back a list of numbers (called a vector/embedding)
  that represents the MEANING of that text.

  Think of it like giving each index card a unique
  GPS coordinate based on what it talks about.
  Cards about similar topics get similar coordinates.

SETUP:
  Already done! You installed openai earlier.

HOW TO USE:
  1. Open this file in Notepad
  2. Find the line that says: OPENAI_API_KEY = ""
  3. Paste your API key between the quotes
  4. Save and close Notepad
  5. Run: python embed.py
"""

import os
import json
import time
from pathlib import Path

# ── Check openai is installed ──────────────────────────
try:
    from openai import OpenAI
except ImportError:
    print("❌  openai not installed. Run:  pip install openai")
    input("Press Enter to close...")
    exit()


# ══════════════════════════════════════════════════════
#
#   ✏️  PASTE YOUR OPENAI API KEY HERE
#   (between the quotes, keep the quotes)
#   Example: OPENAI_API_KEY = "sk-abc123xyz..."
#
# ══════════════════════════════════════════════════════

OPENAI_API_KEY = "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"


# ══════════════════════════════════════════════════════
#   SETTINGS — leave these as they are
# ══════════════════════════════════════════════════════

INPUT_FILE  = "output/chunks.jsonl"       # output from Step 1
OUTPUT_FILE = "output/embeddings.jsonl"   # output of this step
MODEL       = "text-embedding-3-small"    # OpenAI embedding model
                                          # cheap, fast, very accurate
BATCH_SIZE  = 20   # process 20 chunks at a time (saves API calls)


# ══════════════════════════════════════════════════════
#   ENGINE — do not edit below
# ══════════════════════════════════════════════════════

def check_api_key(key):
    """Make sure the user actually pasted a key."""
    if not key or key.strip() == "":
        print("❌  No API key found!")
        print("    Open this file in Notepad and paste your")
        print("    OpenAI API key between the quotes on the")
        print("    OPENAI_API_KEY = \"\" line.")
        input("\nPress Enter to close...")
        exit()
    if not key.startswith("sk-"):
        print("⚠️   Your API key looks unusual (should start with sk-)")
        print("    Double check you copied the full key from OpenAI.")
        print("    Continuing anyway...\n")


def load_chunks(filepath):
    """Load all chunks from the Step 1 output file."""
    chunks = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def embed_batch(client, texts):
    """
    Send a batch of texts to OpenAI and get embeddings back.
    Batching is more efficient than sending one at a time.
    """
    response = client.embeddings.create(
        input=texts,
        model=MODEL
    )
    return [item.embedding for item in response.data]


def save_embeddings(records, filepath):
    """Save all chunks + their embeddings to a JSONL file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    print("\n" + "═"*55)
    print("  🧠  RAG Chatbot — Step 2: Embedding")
    print("  Converting text chunks → searchable numbers")
    print("═"*55)

    # ── Check API key ──────────────────────────────────
    check_api_key(OPENAI_API_KEY)

    # ── Check input file exists ────────────────────────
    if not Path(INPUT_FILE).exists():
        print(f"\n❌  Could not find: {INPUT_FILE}")
        print("    Make sure you ran Step 1 (ingest.py) first.")
        print("    The output/chunks.jsonl file should exist.")
        input("\nPress Enter to close...")
        return

    # ── Load chunks ────────────────────────────────────
    print(f"\n  📂  Loading chunks from {INPUT_FILE}...")
    chunks = load_chunks(INPUT_FILE)
    print(f"  ✅  Loaded {len(chunks)} chunks")

    # ── Connect to OpenAI ──────────────────────────────
    print(f"\n  🔌  Connecting to OpenAI...")
    client = OpenAI(api_key=OPENAI_API_KEY.strip())

    # ── Test connection with one chunk ─────────────────
    print(f"  🧪  Testing API key with a quick test...")
    try:
        test = client.embeddings.create(
            input=["test connection"],
            model=MODEL
        )
        print(f"  ✅  API key works! Connected to OpenAI successfully.")
    except Exception as e:
        print(f"\n❌  Could not connect to OpenAI: {e}")
        print("\n  Possible reasons:")
        print("  1. API key is wrong — double check it")
        print("  2. No internet connection")
        print("  3. You need to add a payment method on platform.openai.com")
        print("     (Even $1 credit is enough for this whole project)")
        input("\nPress Enter to close...")
        return

    # ── Process chunks in batches ──────────────────────
    print(f"\n  ⚙️   Embedding {len(chunks)} chunks in batches of {BATCH_SIZE}...")
    print(f"  ⏱️   Estimated time: {max(1, len(chunks)//20 * 3)} - {max(2, len(chunks)//20 * 6)} seconds\n")

    results     = []
    total       = len(chunks)
    processed   = 0
    failed      = 0

    # Process in batches
    for batch_start in range(0, total, BATCH_SIZE):
        batch_chunks = chunks[batch_start : batch_start + BATCH_SIZE]
        batch_texts  = [c["text"] for c in batch_chunks]
        batch_num    = (batch_start // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Batch {batch_num}/{total_batches} "
              f"(chunks {batch_start+1}–{min(batch_start+BATCH_SIZE, total)})...",
              end=" ")

        try:
            embeddings = embed_batch(client, batch_texts)

            for chunk, embedding in zip(batch_chunks, embeddings):
                record = {
                    "id":        chunk["id"],
                    "text":      chunk["text"],
                    "embedding": embedding,       # the list of numbers!
                    "metadata":  chunk["metadata"]
                }
                results.append(record)

            processed += len(batch_chunks)
            print(f"✅  ({len(embeddings[0])} dimensions per chunk)")

        except Exception as e:
            print(f"❌  Error: {e}")
            failed += len(batch_chunks)
            # Wait a bit and continue
            time.sleep(5)
            continue

        # Small pause between batches to be nice to the API
        time.sleep(0.5)

    # ── Save results ───────────────────────────────────
    if results:
        print(f"\n  💾  Saving {len(results)} embedded chunks...")
        save_embeddings(results, OUTPUT_FILE)
        print(f"  ✅  Saved → {OUTPUT_FILE}")

    # ── Summary ────────────────────────────────────────
    print(f"\n{'═'*55}")
    print(f"  📊  EMBEDDING SUMMARY")
    print(f"{'═'*55}")
    print(f"  Total chunks    : {total}")
    print(f"  ✅ Embedded      : {processed}")
    print(f"  ❌ Failed        : {failed}")
    print(f"  📐 Dimensions    : 1536 numbers per chunk")
    print(f"  💾 Output file   : {OUTPUT_FILE}")
    print(f"{'═'*55}")

    if processed == total:
        print(f"\n  🎉  All chunks embedded successfully!")
        print(f"  ✅  Step 2 complete!")
        print(f"  ▶️   Next: Step 3 — Building the Vector Database\n")
    else:
        print(f"\n  ⚠️   {failed} chunks failed. Try running again.")
        print(f"       Completed chunks are already saved.\n")

    input("Press Enter to close...")


if __name__ == "__main__":
    main()
