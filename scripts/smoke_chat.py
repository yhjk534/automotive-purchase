"""Run a minimal SSE smoke test against the running FastAPI backend."""

from __future__ import annotations

import json
import uuid

import httpx


def main() -> None:
    payload = {
        "message": "你好，请用一句话介绍你能处理的汽车零部件采购任务",
        "thread_id": str(uuid.uuid4()),
        "user_id": "automotive-smoke",
        "username": "汽车采购管理员",
    }
    event_names: list[str] = []
    text: list[str] = []
    current_event = ""
    error_message: str | None = None

    with httpx.Client(timeout=180.0) as client:
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
                elif line.startswith("data:") and current_event == "token":
                    data = json.loads(line[5:].strip())
                    text.append(data.get("content", ""))
                elif line.startswith("data:") and current_event == "error":
                    error_message = json.loads(line[5:].strip()).get("message")
                if current_event == "done":
                    break

    print("EVENTS", ",".join(event_names))
    print("ASSISTANT", "".join(text)[:1000])
    if error_message:
        print("ERROR", error_message)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
