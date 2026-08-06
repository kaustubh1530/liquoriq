"""
routes/advisor.py — PHASE 23: the AI Business Advisor API.

GET  /advisor/brief             today's proactive briefing
GET  /advisor/suggestions       the opening question cards
GET  /advisor/context           what the advisor knows (transparency)
POST /advisor/ask               ask a question; remembers the thread
GET  /advisor/conversations     thread list
GET  /advisor/conversations/{id} one thread with its messages
DELETE /advisor/conversations/{id}

NO NEW CALCULATIONS. Every figure the advisor states comes from the
deterministic engine via services/advisor/tools.py, which are thin adapters
over services that already existed.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.advisor_conversation import AdvisorConversation, AdvisorMessage
from app.models.store import Store
from app.routes.stores import get_current_store
from app.services.advisor import agent as AGENT
from app.services.advisor import tools as TOOLS
from app.services.advisor.context import build_base_context
from app.services.knowledge import rules as RULES
from app.services.knowledge import service as KNOWLEDGE

router = APIRouter()

# Openers. Deliberately phrased as an owner would say them, not as feature
# names — "Find slow products" is a menu item; "What's not selling?" is a
# question, and the point of the page is that he can just ask.
SUGGESTIONS = [
    {"key": "analyse", "label": "Analyse my store",
     "question": "Give me a full read on my business right now — what's working, "
                 "what isn't, and what you'd fix first."},
    {"key": "inventory", "label": "Improve inventory",
     "question": "How do I improve my inventory turnover?"},
    {"key": "revenue", "label": "Increase revenue",
     "question": "What are the three fastest ways for me to increase revenue "
                 "next month?"},
    {"key": "slow", "label": "Find slow products",
     "question": "Which products should I stop carrying, and which should I "
                 "discount to clear?"},
    {"key": "holiday", "label": "Prepare for a holiday",
     "question": "What campaign should I run for the next holiday, and what "
                 "should I order for it?"},
    {"key": "dead", "label": "Reduce dead stock",
     "question": "How much cash is stuck in dead stock, and what's my plan to "
                 "get it back?"},
    {"key": "retention", "label": "Increase repeat customers",
     "question": "How do I get more repeat customers, and who should I contact "
                 "first?"},
    {"key": "deals", "label": "Best supplier deals",
     "question": "Look at my supplier deals — should I take any of them?"},
    {"key": "invest", "label": "Where to invest $1,000",
     "question": "If I had $1,000 to spend today, where would you put it?"},
    {"key": "risk", "label": "Biggest risks",
     "question": "What are the biggest risks in my business right now?"},
]


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    conversation_id: uuid.UUID | None = Field(
        default=None, description="Continue an existing thread. Omit to start one.")


async def _load_context(store: Store, db: AsyncSession) -> dict:
    return await build_base_context(store.id, db, store_name=store.name)


@router.get("/suggestions", summary="Opening question cards")
async def suggestions() -> dict:
    """Static, so the page paints instantly rather than waiting on the engine."""
    return {"suggestions": SUGGESTIONS}


@router.get("/context", summary="Everything the advisor knows before you ask")
async def context(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Transparency endpoint. The owner can see exactly what the advisor is
    working from, and which tools it can reach for. An advisor whose knowledge
    is a black box is one you have to take on faith.
    """
    return {
        "base_context": await _load_context(current_store, db),
        "available_tools": [
            {"name": name, "description": spec["description"]}
            for name, spec in TOOLS.REGISTRY.items()
        ],
        "knowledge_base": KNOWLEDGE.catalogue(),
        "business_rules": [
            {"rule": r.key, "statement": r.statement, "why": r.why}
            for r in RULES.CATALOGUE
        ],
    }


@router.get("/brief", summary="Today's business brief")
async def brief(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generated on page open — the advisor speaks first.

    Falls back to deterministic prose if OpenAI is unavailable, so the top of
    the page is never blank.
    """
    base = await _load_context(current_store, db)
    result = await AGENT.generate_brief(base, current_store.id, db)
    return {
        "brief": result["answer"],
        "source": result["source"],
        "error": result.get("error"),
        "signals": result.get("signals", []),
        "tools_used": result["tools_used"],
        "health_score": base.get("business_health", {}).get("score"),
        "period": base.get("reporting_period"),
    }


@router.post("/ask", summary="Ask the advisor a question")
async def ask(
    body: AskIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    The agent loop: assemble context → let GPT-4o call whatever tools the
    question needs → return the answer plus the tools that actually ran.

    The conversation is persisted first so a failure mid-answer still leaves
    the owner's question in the thread rather than swallowing it.
    """
    conversation = None
    if body.conversation_id:
        conversation = (await db.execute(
            select(AdvisorConversation).where(
                AdvisorConversation.id == body.conversation_id,
                AdvisorConversation.store_id == current_store.id,
            )
        )).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                detail="That conversation does not exist.")

    if conversation is None:
        conversation = AdvisorConversation(
            store_id=current_store.id,
            title=body.question[:120],
        )
        db.add(conversation)
        await db.flush()

    # Prior turns, oldest first — this is what makes "what should I promote?"
    # resolve to the Labor Day discussed two messages ago.
    history = [
        {"role": m.role, "content": m.content}
        for m in (await db.execute(
            select(AdvisorMessage)
            .where(AdvisorMessage.conversation_id == conversation.id)
            .order_by(AdvisorMessage.created_at)
        )).scalars().all()
    ]

    db.add(AdvisorMessage(conversation_id=conversation.id,
                          role="user", content=body.question))

    base = await _load_context(current_store, db)
    result = await AGENT.ask(body.question, base, current_store.id, db, history=history)

    db.add(AdvisorMessage(conversation_id=conversation.id, role="assistant",
                          content=result["answer"], tools_used=result["tools_used"]))
    conversation.message_count = len(history) + 2
    await db.commit()

    return {
        "conversation_id": str(conversation.id),
        "answer": result["answer"],
        "tools_used": result["tools_used"],
        "rounds": result["rounds"],
        "source": result["source"],
        # Workflow buttons, derived from the tools the advisor actually used.
        "next_actions": result.get("next_actions", []),
        # Which playbooks were retrieved and which business rules fired.
        # Observed during execution, exactly like tools_used.
        "knowledge_used": result.get("knowledge_used", []),
        # The exact exception when the model could not be reached. Surfaced
        # rather than logged-only: "I couldn't reach my reasoning engine" with
        # no cause is undebuggable from the outside, which is precisely how an
        # ImportError survived a whole session disguised as a rate limit.
        "error": result.get("error"),
    }


@router.get("/conversations", summary="Conversation history")
async def conversations(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (await db.execute(
        select(AdvisorConversation)
        .where(AdvisorConversation.store_id == current_store.id)
        .order_by(AdvisorConversation.updated_at.desc())
        .limit(50)
    )).scalars().all()

    return {"conversations": [
        {"id": str(c.id), "title": c.title, "message_count": c.message_count,
         "updated_at": str(c.updated_at)}
        for c in rows
    ]}


@router.get("/conversations/{conversation_id}", summary="One conversation")
async def conversation_detail(
    conversation_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    conversation = (await db.execute(
        select(AdvisorConversation)
        .options(selectinload(AdvisorConversation.messages))
        .where(AdvisorConversation.id == conversation_id,
               AdvisorConversation.store_id == current_store.id)
    )).scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail="That conversation does not exist.")

    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "messages": [
            {"role": m.role, "content": m.content,
             "tools_used": m.tools_used, "created_at": str(m.created_at)}
            for m in conversation.messages
        ],
    }


@router.delete("/conversations/{conversation_id}",
               status_code=status.HTTP_204_NO_CONTENT, summary="Delete a conversation")
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> None:
    conversation = (await db.execute(
        select(AdvisorConversation).where(
            AdvisorConversation.id == conversation_id,
            AdvisorConversation.store_id == current_store.id,
        )
    )).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail="That conversation does not exist.")
    await db.delete(conversation)
    await db.commit()
