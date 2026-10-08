"""A durable workflow: three steps with a durable sleep in between.

Kept separate from main.py on purpose: the SDK re-imports this module inside
a deterministic sandbox to run workflow bodies, so it should stay light.
"""

from datetime import UTC, datetime

from vercel import workflow

# The registry. pyproject.toml points `[[tool.vercel.workflows]]` at it, and
# Vercel deploys it as its own function triggered by Vercel Queues.
wf = workflow.Workflows()


# Steps are normal async Python: do I/O, read the clock, call APIs here.
# Each step runs as its own invocation, and its result goes into the run's
# event log, so a step that already succeeded never runs again.
@wf.step
async def reserve_inventory(order_id: str) -> str:
    return f"reserved items for {order_id}"


@wf.step
async def charge_card(order_id: str) -> str:
    # A step that raises is retried (3 retries by default). Fail the first
    # attempt on purpose to show the retry.
    if workflow.get_step_metadata().attempt == 1:
        raise RuntimeError("simulated transient payment error")
    return f"charged card for {order_id}"


@wf.step
async def send_receipt(order_id: str) -> str:
    return f"receipt for {order_id} sent at {datetime.now(UTC).isoformat()}"


# The workflow body orchestrates the steps. Every time the run wakes up (after
# a step, after the sleep) the body is replayed from the start against the
# event log: completed steps return their recorded result immediately.
# So the body must be deterministic: no I/O, no time.time(), no random here
# (workflow.now() / workflow.random() are the safe replacements).
@wf.workflow
async def process_order(order_id: str, delay_seconds: int = 10) -> dict:
    reserved = await reserve_inventory(order_id)
    charged = await charge_card(order_id)

    slept_at = workflow.now()
    # Durable sleep: nothing runs while waiting. A delayed queue message wakes
    # the run up, so this could be "7 days" and survive deploys.
    await workflow.sleep(delay_seconds)
    woke_at = workflow.now()

    receipt = await send_receipt(order_id)
    return {
        "steps": [reserved, charged, receipt],
        "slept_at": slept_at.isoformat(),
        "woke_at": woke_at.isoformat(),
    }
