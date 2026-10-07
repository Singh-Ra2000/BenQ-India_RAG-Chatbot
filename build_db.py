"""
=====================================================
  RAG CHATBOT — STEP 3: VECTOR DATABASE
  Stores your embeddings into ChromaDB so the
  chatbot can search them instantly
=====================================================
WHAT THIS DOES (in plain English):
  Step 2 gave us 123 chunks, each with 1536 numbers.
  This script puts all of them into ChromaDB —
  a fast searchable database that runs on YOUR computer.

  Think of it like building a library where every
  book is perfectly indexed and findable in seconds.

RUN:
  python build_db.py
"""

import json
from pathlib import Path

try:
    import chromadb
except ImportError:
    print("❌  chromadb not installed. Run:  pip install chromadb")
    input("Press Enter to close...")
    exit()

# ══════════════════════════════════════════════════
#   SETTINGS
# ══════════════════════════════════════════════════

INPUT_FILE = "output/embeddings.jsonl"   # from Step 2
DB_FOLDER  = "output/chroma_db"          # where DB is saved on your PC
COLLECTION = "projector_faq"             # name of our collection


# ══════════════════════════════════════════════════
#   ENGINE
# ══════════════════════════════════════════════════

def load_embeddings(filepath):
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main():
    print("\n" + "═"*55)
    print("  🗄️   RAG Chatbot — Step 3: Vector Database")
    print("  Storing embeddings into ChromaDB")
    print("═"*55)

    # ── Check input file ───────────────────────────
    if not Path(INPUT_FILE).exists():
        print(f"\n❌  Could not find: {INPUT_FILE}")
        print("    Make sure you ran Step 2 (embed.py) first.")
        input("\nPress Enter to close...")
        return

    # ── Load embeddings ────────────────────────────
    print(f"\n  📂  Loading embeddings from {INPUT_FILE}...")
    records = load_embeddings(INPUT_FILE)
    print(f"  ✅  Loaded {len(records)} embedded chunks")

    # ── Set up ChromaDB ────────────────────────────
    print(f"\n  🗄️   Setting up ChromaDB...")
    print(f"       Database will be saved at: {DB_FOLDER}")
    client = chromadb.PersistentClient(path=DB_FOLDER)

    # Delete existing collection if it exists (fresh start)
    try:
        client.delete_collection(name=COLLECTION)
        print(f"  🔄  Cleared existing collection (fresh start)")
    except Exception:
        pass

    # Create new collection
    # We set space to cosine — best for text similarity matching
    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"  ✅  Created collection: '{COLLECTION}'")

    # ── Add all chunks to the DB ───────────────────
    print(f"\n  ⚙️   Adding {len(records)} chunks to database...")

    # Prepare data in batches of 50
    BATCH = 50
    added = 0

    for i in range(0, len(records), BATCH):
        batch = records[i:i+BATCH]

        ids        = [r["id"]        for r in batch]
        embeddings = [r["embedding"] for r in batch]
        documents  = [r["text"]      for r in batch]
        metadatas  = [r["metadata"]  for r in batch]

        # ChromaDB metadata values must be strings, ints, floats or bools
        # Convert any lists (like model_names) to comma-separated strings
        clean_metadatas = []
        for m in metadatas:
            clean = {}
            for k, v in m.items():
                if isinstance(v, list):
                    clean[k] = ", ".join(str(x) for x in v)
                elif isinstance(v, (str, int, float, bool)):
                    clean[k] = v
                else:
                    clean[k] = str(v)
            clean_metadatas.append(clean)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=clean_metadatas
        )

        added += len(batch)
        batch_num = (i // BATCH) + 1
        total_batches = (len(records) + BATCH - 1) // BATCH
        print(f"  Batch {batch_num}/{total_batches} → added {added}/{len(records)} chunks ✅")

    # ── Verify it worked ───────────────────────────
    print(f"\n  🔍  Verifying database...")
    count = collection.count()
    print(f"  ✅  Database contains {count} searchable chunks")


    # ── Summary ────────────────────────────────────
    print(f"\n{'═'*55}")
    print(f"  📊  DATABASE SUMMARY")
    print(f"{'═'*55}")
    print(f"  Total chunks stored : {count}")
    print(f"  Database location   : {DB_FOLDER}/")
    print(f"  Collection name     : {COLLECTION}")
    print(f"  Search type         : Cosine similarity")
    print(f"{'═'*55}")
    print(f"\n  🎉  Step 3 complete!")
    print(f"  ✅  Your knowledge base is built and ready!")
    print(f"  ▶️   Next: Step 4 — Building the chatbot\n")

    input("Press Enter to close...")


if __name__ == "__main__":
    main()
