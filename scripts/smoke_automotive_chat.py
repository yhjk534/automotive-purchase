"""Run an end-to-end automotive fitment query through the live Agent."""

from __future__ import annotations

import json
import uuid

import httpx


def main() -> None:
    payload = {
        "message": "查询2021款丰田凯美瑞2.0L适用的前制动片，列出OE号和供应商报价。",
        "thread_id": str(uuid.uuid4()),
        "user_id": "automotive-smoke",
        "username": "汽车采购管理员",
    }
    event_names: list[str] = []
    tool_names: list[str] = []
    text: list[str] = []
    error_message: str | None = None
    current_event = ""

    with httpx.Client(timeout=240.0) as client:
        with client.stream(
            "POST",
            "http://127.0.0.1:8000/api/chat/stream",
            json=payload,
        ) as response:
            print("STATUS", response.status_code)
            for line in response.iter_lines():
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                    event_names.append(current_event)
                elif line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if current_event == "token":
                        text.append(data.get("content", ""))
                    elif current_event == "tool_start":
                        tool_names.append(data.get("name", ""))
                    elif current_event == "error":
                        error_message = data.get("message")
                if current_event == "done":
                    break

    answer = "".join(text)
    print("EVENTS", ",".join(event_names))
    print("TOOLS", ",".join(dict.fromkeys(tool_names)))
    print("HAS_OE_NUMBER", "04465-06120" in answer)
    print("ANSWER_CHARS", len(answer))
    if error_message:
        print("ERROR", error_message)
        raise SystemExit(1)
    if "vehicle_search" not in tool_names or "part_search" not in tool_names:
        print("ERROR automotive tool chain was not used")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
