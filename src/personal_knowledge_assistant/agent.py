import json
import anthropic
import re
from dotenv import load_dotenv

from personal_knowledge_assistant.rag import collection, ingest, retrieve

load_dotenv()
client = anthropic.Anthropic()

MODEL = "claude-haiku-4-5-20251001"
K = 8
MIN_SIM = 0.2

SHELL_BLOCK = re.compile(r"```(?:bash|sh|shell|powershell|console)\n(.*?)```", re.S)

def ungrounded_commands(answer: str, evidence: str) -> list[str]:
    """Lines in the answer's shell code blocks that never appear in the retrieved text."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    ev = norm(evidence)
    return [
        line.strip()
        for block in SHELL_BLOCK.findall(answer)
        for line in block.splitlines()
        if line.strip() and norm(line) not in ev
    ]

def document_names() -> list[str]:
    metas = collection.get(include=["metadatas"])["metadatas"]
    return sorted({m["source"] for m in metas})

def search_documents(query: str, source: str | None = None) -> str:
    hits = retrieve(query, K, source)
    if not hits or hits[0]["sim"] < MIN_SIM:
        return "No relevant results found."
    return "\n\n".join(f"[{h['source']} #{h['chunk']}]\n{h['text']}" for h in hits)

def build_tools(docs: list[str]) -> list[dict]:
    return [{
        "name": "search_documents",
        "description": (
            "Search the user's project documentation. Returns the most relevant excerpts, "
            "each labeled [file #chunk]. Leave `source` empty to search every document, "
            "or set it to search one project's document only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A full question or sentence, e.g. 'How do I run the Discord bot?'",
                },
                "source": {
                    "type": "string",
                    "enum": docs,
                    "description": "Optional: restrict the search to this document.",
                },
            },
            "required": ["query"],
        },
    }]

TOOL_FUNCTIONS = {
    "search_documents": search_documents,
}

SYSTEM = """You answer questions about the user's own projects using the search_documents tool.
The documentation covers these files: {docs}. Treat every question that isn't general knowledge (like arithmetic) as a question about these projects, even if it doesn't say "my project". Never ask the user clarifying questions; search instead.

- Search before answering. Write each query as a full question or sentence (for example "How do I run the Discord bot?"), not a bare keyword.
- If a question is about one specific project, set `source` to that file. If it covers several projects or any project ("which projects..."), make one search per file with `source` set, and name every project that matches.
- If the results don't contain the answer, search again with a rephrased query. Use at most 5 searches.
- Answer only from the search results. Never suggest commands, versions, or facts that aren't in them.
- Cite sources as [file #chunk] after each claim.
- If nothing relevant is found after searching, say you couldn't find it in the documents. Do not guess, and don't suggest places to look.
"""

def run_agent(
    question: str, 
    max_steps: int = 5,
    verbose: bool = False,
    trace: list | None = None,
) -> str:
    messages = [{"role": "user", "content": question}]
    docs = document_names()
    system = SYSTEM.format(docs=", ".join(docs))
    tools = build_tools(docs)
    evidence: list[str] = []

    for _ in range(max_steps):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=messages,
        )

        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            bad = ungrounded_commands(text, "\n".join(evidence))
            if bad:
                if trace is not None:
                    trace.append({"guard": "dropped answer", "commands": bad})
                if verbose:
                    print(f"  guard: dropped answer, ungrounded commands: {bad}")
                return "I couldn't find that in the documents."
            return text

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if trace is not None:
                trace.append(dict(block.input))
            if verbose:
                print(f"  search: {block.input}")

            func = TOOL_FUNCTIONS.get(block.name)
            if func is None:
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Unknown tool: {block.name}",
                    "is_error": True,
                })
                continue
            try:
                output = func(**block.input)
                if isinstance(output, str):
                    evidence.append(output)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output if isinstance(output, str) else json.dumps(output),
                })
            except Exception as e:
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Error: {e}",
                    "is_error": True,
                })
                
        messages.append({"role": "user", "content": results})
    return "Stopped: too many steps."

if __name__ == "__main__":
    ingest()
    while True:
        q = input("\nAsk (or 'quit'): ")
        if q.strip().lower() == "quit":
            break
        print(run_agent(q, verbose=True))