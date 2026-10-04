"""Command-line interface for the Personal Knowledge Assistant.

Examples:
    uv run personal-knowledge-assistant                       # interactive, fixed pipeline
    uv run personal-knowledge-assistant --agent               # interactive, tool-using agent
    uv run personal-knowledge-assistant "How do I run the Discord bot?"
    uv run personal-knowledge-assistant --reindex -v          # rebuild the index, show retrieval details
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SUPPORTED = {".md", ".txt"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="personal-knowledge-assistant",
        description="Ask questions about your own documents. Answers are grounded in the "
                    "retrieved text and cite their source files.",
    )
    p.add_argument("question", nargs="?",
                   help="Ask one question and exit. Omit it for an interactive session.")
    p.add_argument("--agent", action="store_true",
                   help="Use the tool-using agent instead of the fixed retrieve-then-answer pipeline.")
    p.add_argument("-k", type=int, default=8,
                   help="Chunks retrieved per search (default: 8).")
    p.add_argument("--docs", default="docs",
                   help="Folder of .md/.txt files to index (default: docs).")
    p.add_argument("--reindex", action="store_true",
                   help="Clear the vector index and rebuild it from the docs folder.")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Show retrieved chunks and similarities (pipeline) or search queries (agent).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Cheap checks first, so a missing key or empty folder fails fast
    # without loading the embedding model.
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
    docs = Path(args.docs)
    if not any(p.suffix in SUPPORTED for p in docs.glob("**/*")):
        sys.exit(f"No .md or .txt files found in '{docs}/'. Add some documents and try again.")

    # Heavy imports (embedding model, ChromaDB) happen only after the checks above.
    import anthropic

    from personal_knowledge_assistant import agent as agent_mod
    from personal_knowledge_assistant import rag

    if args.reindex:
        ids = rag.collection.get()["ids"]
        if ids:
            rag.collection.delete(ids=ids)
    rag.ingest(str(docs))

    if args.agent:
        agent_mod.K = args.k  # search_documents reads K at call time

        def ask(q: str) -> str:
            return agent_mod.run_agent(q, verbose=args.verbose)
    else:
        def ask(q: str) -> str:
            return rag.answer(q, k=args.k, verbose=args.verbose)

    def safe_ask(q: str) -> str | None:
        try:
            return ask(q)
        except anthropic.APIError as e:
            print(f"API error: {e}", file=sys.stderr)
            return None

    if args.question:
        reply = safe_ask(args.question)
        if reply is None:
            sys.exit(1)
        print(reply)
        return

    print(f"Mode: {'agent' if args.agent else 'pipeline'}, k={args.k}. Type 'quit' to exit.")
    while True:
        try:
            q = input("\nAsk: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in {"quit", "exit"}:
            break
        if q:
            reply = safe_ask(q)
            if reply is not None:
                print(reply)


if __name__ == "__main__":
    main()