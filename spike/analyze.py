# /// script
# requires-python = ">=3.11"
# ///
"""M0 spike: what a sitting's Claude Code transcript holds.

    uv run spike/analyze.py <transcript.jsonl> [...]

Reports: events by kind (through the viewer's parser), thinking blocks with and without text,
tokens (per API message, counted once), images, timing, and every entry that is not the
painter's own words or tool traffic: attachments, system entries, meta messages and compaction.
Those are what Claude Code itself put in front of the model, and the white room (NFR-9) needs
each one known.
"""
import collections, json, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "viewer"))
import studio  # noqa: E402


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    for path in sys.argv[1:]:
        print(f"== {path}")
        events, images = studio.parse(path)
        print("events:", dict(collections.Counter(e["kind"] for e in events)))
        lines = [json.loads(l) for l in open(path) if l.strip()]
        types = collections.Counter(d.get("type") for d in lines)
        print("entry types:", dict(types))
        think = [b for d in lines if d.get("type") == "assistant" for b in (d.get("message") or {}).get("content") or []
                 if isinstance(b, dict) and b.get("type") == "thinking"]
        with_text = [b for b in think if (b.get("thinking") or "").strip()]
        print(f"thinking blocks: {len(think)}, with text: {len(with_text)}, chars: {sum(len(b['thinking']) for b in with_text)}")
        if with_text:
            print("  first thinking:", with_text[0]["thinking"][:400].replace("\n", " "))
        usage, models = {}, set()
        for d in lines:
            m = d.get("message") or {}
            if d.get("type") == "assistant" and m.get("id") and m.get("usage"):
                usage[m["id"]] = m["usage"]
                models.add(m.get("model"))
        tot = collections.Counter()
        for u in usage.values():
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
                tot[k] += u.get(k) or 0
            tot["thinking_tokens"] += (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0
        ctx = [(u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
               for u in usage.values()]
        print(f"models: {models}; API messages: {len(usage)}; tokens: {dict(tot)}; largest context: {max(ctx, default=0)}")
        sizes = [len(b64) * 3 // 4 for _, b64 in images]
        print(f"images: {len(images)}, total {sum(sizes)//1024} KB, largest {max(sizes, default=0)//1024} KB")
        stamps = [ts(d["timestamp"]) for d in lines if d.get("timestamp")]
        if stamps:
            mins = (max(stamps) - min(stamps)).total_seconds() / 60
            paints = sum(1 for e in events if e["kind"] == "paint")
            print(f"duration: {mins:.1f} min; paint calls: {paints} ({paints / max(mins, 1e-9) * 60:.0f}/h); "
                  f"looks: {sum(1 for e in events if e['kind'] == 'look')}; errors: {sum(1 for e in events if e.get('err'))}")
        print("-- what Claude Code itself added:")
        for d in lines:
            t = d.get("type")
            if t == "attachment":
                a = d.get("attachment") or {}
                r = " | ".join((x.get("content") or "")[:300] for x in d.get("rendered") or [])
                print(f"  attachment {a.get('type')}: {r!r}"[:600])
            elif t == "system":
                print(f"  system {d.get('subtype')}: {json.dumps({k: v for k, v in d.items() if k in ('content', 'level', 'compactMetadata')})[:500]}")
            elif t == "user" and (d.get("isMeta") or d.get("isCompactSummary")):
                print(f"  user meta: {json.dumps((d.get('message') or {}).get('content'))[:500]}")
            elif t == "user":
                c = (d.get("message") or {}).get("content")
                texts = [c] if isinstance(c, str) else [x.get("text", "") for x in c or [] if isinstance(x, dict) and x.get("type") == "text"]
                for x in texts:
                    if x.strip():
                        print(f"  user text: {x[:400]!r}")
            elif t not in ("assistant",):
                print(f"  {t}: {json.dumps(d)[:200]}")


if __name__ == "__main__":
    main()
