from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")  # downloads ~90MB on first run

docs = [
    "To reset your password, click 'Forgot password' on the login page.",
    "Our office is closed on public holidays.",
    "The Python function returns a list of integers.",
    "Refunds are processed within 5 business days.",
    "Cats sleep for most of the day.",
]
doc_emb = model.encode(docs)

for query in ["I can't log in to my account", "money back policy", "best pizza in Rome"]:
    scores = util.cos_sim(model.encode(query), doc_emb)[0]
    print(f"\nQuery: {query}")
    for score, doc in sorted(zip(scores.tolist(), docs), reverse=True):
        print(f"  {score:.3f}  {doc}")