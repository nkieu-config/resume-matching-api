import argparse
import json
from pathlib import Path

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("resume", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("private/analysis-result.json"),
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.resume.suffix.lower() != ".pdf":
        raise SystemExit("resume path must end with .pdf")
    if not args.resume.is_file():
        raise SystemExit("resume file does not exist")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.resume.open("rb") as resume_file:
        response = httpx.post(
            f"{args.base_url}/v1/resume-analyses",
            files={"file": (args.resume.name, resume_file, "application/pdf")},
            timeout=120,
        )
    response.raise_for_status()
    payload = response.json()
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
