"""
diagnose_advisor.py — find out exactly where the advisor breaks.

Seven stages, each one independent, each failing loudly with the real
exception. Written because "I couldn't reach my reasoning engine" is
undebuggable from the outside — which is how an ImportError survived a whole
session disguised as a rate limit.

    cd ~/Desktop/LiquorIQ/backend
    source venv/bin/activate
    python diagnose_advisor.py
"""

import asyncio
import logging
import sys
import traceback

logging.disable(logging.INFO)
sys.path.insert(0, ".")

PASS, FAIL = "  \033[32mPASS\033[0m", "  \033[31mFAIL\033[0m"


def ok(label, detail=""):
    print(f"{PASS}  {label}" + (f"  ·  {detail}" if detail else ""))


def bad(label, exc):
    print(f"{FAIL}  {label}")
    print(f"        {type(exc).__name__}: {exc}")
    print("        " + "-" * 62)
    for line in traceback.format_exc().splitlines()[-6:]:
        print("        " + line)
    print("        " + "-" * 62)


async def main():
    print("\nLiquorIQ — AI Advisor diagnostics\n" + "=" * 70)

    # ── 1. Configuration ─────────────────────────────────────────────────────
    print("\n1. Configuration")
    try:
        from app.config import get_settings
        settings = get_settings()
        key = settings.openai_api_key or ""
        if not key:
            print(f"{FAIL}  OPENAI_API_KEY is EMPTY")
            print("        Add it to backend/.env as OPENAI_API_KEY=sk-...")
            print("        On Railway: Variables tab. Then restart the server.")
            return
        ok("OPENAI_API_KEY loaded", f"{key[:7]}…{key[-4:]} ({len(key)} chars)")
        ok("model configured", settings.openai_model)
    except Exception as exc:
        bad("could not read settings", exc)
        return

    # ── 2. The adapter imports at all ────────────────────────────────────────
    print("\n2. Advisor OpenAI adapter imports")
    try:
        from app.services.advisor.openai_agent import call_with_tools
        ok("app.services.advisor.openai_agent imported")
    except Exception as exc:
        bad("adapter import failed — this alone breaks every question", exc)
        return

    # ── 3. A bare call, no tools ─────────────────────────────────────────────
    print("\n3. Bare model call (no tools)")
    try:
        reply = await call_with_tools(
            [{"role": "user", "content": "Reply with exactly: OK"}], None)
        ok("model reachable", repr((reply.get("content") or "")[:40]))
    except Exception as exc:
        bad("the model itself is unreachable", exc)
        print("\n        Nothing below can work until this passes.")
        return

    # ── 4. The tool schema is well-formed ────────────────────────────────────
    print("\n4. Tool schema")
    try:
        from app.services.advisor import tools as TOOLS
        schema = TOOLS.openai_schema()
        for tool in schema:
            assert tool["type"] == "function"
            assert tool["function"]["name"]
            assert tool["function"]["parameters"]["type"] == "object"
        ok(f"{len(schema)} tools, all well-formed",
           ", ".join(t["function"]["name"] for t in schema[:4]) + " …")
    except Exception as exc:
        bad("tool schema is malformed", exc)
        return

    # ── 5. A call WITH tools ─────────────────────────────────────────────────
    print("\n5. Model call with tools attached")
    try:
        reply = await call_with_tools(
            [{"role": "system", "content": "You advise a liquor store."},
             {"role": "user", "content": "What is sold out right now?"}],
            schema)
        wanted = [c["name"] for c in reply.get("tool_calls", [])]
        ok("model accepted the schema",
           f"requested: {wanted}" if wanted else "answered without tools")
    except Exception as exc:
        bad("the schema is rejected by the API", exc)
        return

    # ── 6. Tools execute against the real database ───────────────────────────
    print("\n6. Tool execution against your data")
    try:
        from sqlalchemy import func, select

        from app.database import AsyncSessionLocal
        from app.models.normalized_sale import NormalizedSale
        from app.models.store import Store

        async with AsyncSessionLocal() as db:
            counts = dict((await db.execute(
                select(NormalizedSale.store_id, func.count())
                .group_by(NormalizedSale.store_id)
            )).all())
            stores = (await db.execute(select(Store))).scalars().all()
            if not stores:
                print(f"{FAIL}  no stores in the database")
                return
            store = max(stores, key=lambda s: counts.get(s.id, 0))
            ok("store selected", f"{store.name} ({counts.get(store.id, 0):,} sales rows)")

            for name in ("action_center", "category_intelligence", "customer_segments"):
                result = await TOOLS.execute(name, {}, store.id, db)
                if "error" in result:
                    print(f"{FAIL}  tool {name}: {result['error']}")
                else:
                    ok(f"tool {name}", f"{len(str(result)):,} chars returned")

            # ── 7. The whole loop ────────────────────────────────────────────
            print("\n7. Full agent loop")
            from app.services.advisor import agent as AGENT
            from app.services.advisor.context import build_base_context

            base = await build_base_context(store.id, db, store_name=store.name)
            ok("base context built", f"{len(str(base)):,} chars")

            out = await AGENT.ask("What should I reorder first?", base, store.id, db)
            if out["source"] == "ai":
                ok("agent answered", f"{out['rounds']} round(s), "
                                     f"tools: {[t['tool'] for t in out['tools_used']]}")
                print("\n" + "-" * 70)
                print(out["answer"][:900])
                print("-" * 70)
            else:
                print(f"{FAIL}  agent fell back")
                print(f"        {out.get('error', 'no error recorded')}")
    except Exception as exc:
        bad("database or agent stage failed", exc)
        return

    print("\n" + "=" * 70)
    print("All stages passed. The advisor is working end to end.\n")


if __name__ == "__main__":
    asyncio.run(main())
