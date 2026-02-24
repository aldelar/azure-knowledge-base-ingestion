"""Display a summary of the AI Search index contents."""

import logging
from collections import Counter

logging.disable(logging.CRITICAL)

from azure.identity import DefaultAzureCredential  # noqa: E402
from azure.search.documents import SearchClient  # noqa: E402

from shared.config import config  # noqa: E402

client = SearchClient(
    endpoint=config.search_endpoint,
    index_name=config.search_index_name,
    credential=DefaultAzureCredential(),
)

docs = list(
    client.search(
        search_text="*",
        select=["id", "article_id", "title", "section_header", "image_urls", "content"],
        top=100,
    )
)

print()
print(f"Index: {config.search_index_name}  ({len(docs)} documents)")
print("─" * 140)

content_sizes = []
for d in sorted(docs, key=lambda x: x["id"]):
    imgs = d.get("image_urls") or []
    hdr = d.get("section_header", "") or ""
    content = d.get("content", "") or ""
    content_len = len(content)
    content_sizes.append(content_len)
    img_names = ", ".join(imgs) if imgs else ""
    print(f"  {d['id']:50s} | {hdr:40s} | {content_len:>6,} chars | images: {len(imgs)}  {img_names}")

print("─" * 140)

articles = Counter(d["article_id"] for d in docs)
print("Per-article chunk counts:")
for aid, cnt in sorted(articles.items()):
    print(f"  {aid}: {cnt} chunks")

if content_sizes:
    print()
    print(f"Content size: min={min(content_sizes):,} chars, max={max(content_sizes):,} chars, "
          f"avg={sum(content_sizes) // len(content_sizes):,} chars")
    tiny = [s for s in content_sizes if s < 100]
    if tiny:
        print(f"  ⚠  {len(tiny)} chunk(s) under 100 chars")
print()
