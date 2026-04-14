"""
Append a structured lesson to .agent_memory/lessons.jsonl
Usage: python .agent_scripts/log_lesson.py --task TASK_ID --outcome success|failure --lesson "text"
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--outcome", choices=["success", "failure"], required=True)
    parser.add_argument("--lesson", required=True)
    parser.add_argument("--model-used", default="unknown")
    args = parser.parse_args()

    memory_dir = Path(".agent_memory")
    memory_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "task_id": args.task,
        "date": datetime.now().isoformat(),
        "outcome": args.outcome,
        "lesson": args.lesson,
        "model_used": args.model_used,
    }

    lessons_path = memory_dir / "lessons.jsonl"
    with open(lessons_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"[lesson] Saved to {lessons_path}: {args.lesson}")


if __name__ == "__main__":
    main()
