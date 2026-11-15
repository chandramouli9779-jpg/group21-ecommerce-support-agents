"""Isolated Ollama probes; never import or modify application agents."""
import argparse
import json
import time
from pathlib import Path

import httpx
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama


@tool
def lookup_records(case_id: str) -> dict:
    """Get delivery records for a support case."""
    assert case_id == "A"
    return {"case_id": "A", "days_since_delivery": 3, "receipt_denied": True}


@tool
def lookup_policy(case_id: str) -> dict:
    """Get the policy for a support case."""
    assert case_id == "A"
    return {"case_id": "A", "investigate_within_days": 7, "refund_allowed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--reasoning", choices=["false", "true", "none"], default="none")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--tokens", type=int, default=1800)
    args = parser.parse_args()
    reasoning = {"false": False, "true": True, "none": None}[args.reasoning]
    trace = {"model": args.model, "reasoning": reasoning, "num_predict": args.tokens, "rounds": []}
    started = time.monotonic()
    if args.raw:
        payload = {"model": args.model, "messages": [{"role": "user", "content": "Reply with the single word OK."}],
                   "stream": False, "options": {"temperature": 0, "num_predict": args.tokens, "num_ctx": 4096}}
        if reasoning is not None:
            payload["think"] = reasoning
        response = httpx.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=100, trust_env=False)
        trace.update(request=payload, status=response.status_code, headers=dict(response.headers), body=response.text)
    else:
        tools = {t.name: t for t in (lookup_records, lookup_policy)}
        llm = ChatOllama(model=args.model, base_url="http://127.0.0.1:11434", temperature=0,
                         reasoning=reasoning, num_predict=args.tokens, num_ctx=4096,
                         client_kwargs={"timeout": 100, "trust_env": False})
        bound = llm.bind_tools(list(tools.values()))
        messages = [
            SystemMessage(content=(
                "Call lookup_records and lookup_policy for the requested case before deciding. "
                'The action must be "investigate" when receipt_denied is true and '
                'days_since_delivery <= investigate_within_days; otherwise use "no_action". '
                "Copy refund_allowed from policy independently of the action. "
                "After BOTH results, output only JSON with case_id (string), action (string), "
                "and refund_allowed (boolean). Derive all values from the tool results.")),
            HumanMessage(content="Check case A. Use both tools now."),
        ]
        trace["client_params"] = llm._chat_params(messages)
        try:
            successful = set()
            for _ in range(4):
                result = bound.invoke(messages)
                record = result.model_dump(mode="json")
                trace["rounds"].append(record)
                print(json.dumps(record), flush=True)
                messages.append(result)
                if not result.tool_calls:
                    assert successful == set(tools), f"Missing tools: {set(tools) - successful}"
                    final = json.loads(result.content)
                    trace["valid_json"] = True
                    assert final == {"case_id": "A", "action": "investigate", "refund_allowed": False}, f"Incorrect decision: {final}"
                    trace["success"] = True
                    break
                for call in result.tool_calls:
                    value = tools[call["name"]].invoke(call["args"])
                    successful.add(call["name"])
                    trace.setdefault("executed_tools", []).append({"name": call["name"], "args": call["args"], "result": value})
                    messages.append(ToolMessage(content=json.dumps(value), tool_call_id=call["id"]))
        except Exception as exc:
            trace["error"] = repr(exc)
    trace["elapsed_seconds"] = round(time.monotonic() - started, 3)
    model_slug = args.model.replace(":", "-")
    probe_mode = "raw" if args.raw else "tools"
    filename = f"diagnostic-{model_slug}-{args.reasoning}-{probe_mode}-{args.tokens}-{time.time_ns()}.json"
    destination = Path(__file__).parent / "evidence" / filename
    destination.write_text(json.dumps(trace, indent=2) + "\n")
    print(json.dumps(trace, indent=2), flush=True)


if __name__ == "__main__":
    main()
