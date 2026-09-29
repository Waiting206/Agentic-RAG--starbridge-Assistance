#!/usr/bin/env python3
"""Starbridge Agentic RAG API evaluation runner.

The runner sends each JSONL question to the real streaming chat endpoint, records
the answer and cited sources, and calculates retrieval metrics from gold_doc_ids.
Answer correctness is intentionally left for manual review because expected_points
contains semantic requirements rather than exact answer strings.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS = (
    PROJECT_ROOT
    / "data"
    / "knowledge"
    / "starbridge-rag-starter"
    / "evaluation"
    / "questions.jsonl"
)
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="调用 Agentic RAG SSE 接口并生成检索评测报告"
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="FastAPI 地址，默认：http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS,
        help="questions.jsonl 路径",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="JSON 报告路径；不填写时自动保存到 evaluation/results",
    )
    parser.add_argument("--category", help="只运行一个题型，例如 fact")
    parser.add_argument("--limit", type=int, help="只运行前 N 道题，适合冒烟测试")
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="计算检索指标时使用前 K 个来源，默认 5",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="每道题的超时时间（秒），默认 180",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="题目之间的等待时间（秒），用于降低模型接口限流风险",
    )
    parser.add_argument(
        "--keep-threads",
        action="store_true",
        help="保留评测产生的 PostgreSQL 会话；默认完成后删除",
    )
    return parser.parse_args()


def load_questions(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"评测文件不存在：{path}")

    questions: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {line_number} 行不是合法 JSON：{exc}") from exc

            required = {"id", "category", "question", "gold_doc_ids"}
            missing = required.difference(item)
            if missing:
                raise ValueError(
                    f"第 {line_number} 行缺少字段：{', '.join(sorted(missing))}"
                )
            questions.append(item)
    return questions


def iter_sse(response: httpx.Response) -> Iterator[tuple[str, dict[str, Any]]]:
    """Parse SSE frames without depending on an extra SSE client package."""
    event_name = "message"
    data_lines: list[str] = []

    for raw_line in response.iter_lines():
        line = raw_line.rstrip("\r")
        if not line:
            if data_lines:
                raw_data = "\n".join(data_lines)
                try:
                    payload = json.loads(raw_data)
                except json.JSONDecodeError:
                    payload = {"raw": raw_data}
                yield event_name, payload
            event_name = "message"
            data_lines = []
            continue

        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if data_lines:
        raw_data = "\n".join(data_lines)
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            payload = {"raw": raw_data}
        yield event_name, payload


def unique_doc_ids(sources: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for source in sources:
        doc_id = source.get("doc_id")
        if doc_id and doc_id not in result:
            result.append(str(doc_id))
    return result


def retrieval_metrics(
    gold_doc_ids: list[str], source_doc_ids: list[str], top_k: int
) -> dict[str, float | bool | None]:
    if not gold_doc_ids:
        return {
            "hit_at_k": None,
            "recall_at_k": None,
            "reciprocal_rank": None,
            "all_gold_found": None,
        }

    ranked = source_doc_ids[:top_k]
    gold = set(gold_doc_ids)
    found = gold.intersection(ranked)
    first_rank = next(
        (index for index, doc_id in enumerate(ranked, start=1) if doc_id in gold),
        None,
    )
    return {
        "hit_at_k": bool(found),
        "recall_at_k": len(found) / len(gold),
        "reciprocal_rank": 1 / first_rank if first_rank else 0.0,
        "all_gold_found": found == gold,
    }


def run_question(
    client: httpx.Client,
    base_url: str,
    question: dict[str, Any],
    thread_id: str,
    top_k: int,
    keep_thread: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    first_token_at: float | None = None
    answer_parts: list[str] = []
    sources: list[dict[str, Any]] = []
    stream_error: str | None = None
    cleanup_error: str | None = None

    try:
        with client.stream(
            "POST",
            f"{base_url}/api/chat/stream",
            json={"message": question["question"], "thread_id": thread_id},
        ) as response:
            response.raise_for_status()
            for event_name, payload in iter_sse(response):
                if event_name == "message":
                    delta = payload.get("delta", "")
                    if delta:
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        answer_parts.append(str(delta))
                elif event_name == "sources":
                    event_sources = payload.get("sources", [])
                    if isinstance(event_sources, list):
                        sources = event_sources
                elif event_name == "error":
                    stream_error = str(
                        payload.get("message")
                        or payload.get("detail")
                        or payload.get("error")
                        or payload.get("raw")
                        or "未知流式错误"
                    )
                elif event_name == "done":
                    break
    except Exception as exc:  # Keep the remaining questions running.
        stream_error = f"{type(exc).__name__}: {exc}"
    finally:
        if not keep_thread:
            try:
                cleanup_response = client.delete(f"{base_url}/api/threads/{thread_id}")
                if cleanup_response.status_code >= 400:
                    cleanup_error = (
                        f"HTTP {cleanup_response.status_code}: {cleanup_response.text[:200]}"
                    )
            except Exception as exc:
                cleanup_error = f"{type(exc).__name__}: {exc}"

    finished = time.perf_counter()
    source_doc_ids = unique_doc_ids(sources)
    metrics = retrieval_metrics(question["gold_doc_ids"], source_doc_ids, top_k)

    return {
        "id": question["id"],
        "category": question["category"],
        "role": question.get("role"),
        "as_of_date": question.get("as_of_date"),
        "question": question["question"],
        "expected_behavior": question.get("expected_behavior"),
        "expected_points": question.get("expected_points"),
        "gold_doc_ids": question["gold_doc_ids"],
        "thread_id": thread_id,
        "status": "error" if stream_error else "ok",
        "error": stream_error,
        "cleanup_error": cleanup_error,
        "answer": "".join(answer_parts),
        "sources": sources,
        "source_doc_ids": source_doc_ids,
        "latency_seconds": round(finished - started, 3),
        "time_to_first_token_seconds": (
            round(first_token_at - started, 3) if first_token_at else None
        ),
        **metrics,
    }


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def rounded_mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 4) if values else None


def summarize(results: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    successful = [item for item in results if item["status"] == "ok"]
    scored = [item for item in successful if item["gold_doc_ids"]]
    latencies = [float(item["latency_seconds"]) for item in successful]
    first_tokens = [
        float(item["time_to_first_token_seconds"])
        for item in successful
        if item["time_to_first_token_seconds"] is not None
    ]

    return {
        "total": len(results),
        "completed": len(successful),
        "errors": len(results) - len(successful),
        "retrieval_scored": len(scored),
        f"hit_at_{top_k}": rounded_mean(
            [1.0 if item["hit_at_k"] else 0.0 for item in scored]
        ),
        f"macro_recall_at_{top_k}": rounded_mean(
            [float(item["recall_at_k"]) for item in scored]
        ),
        "mrr": rounded_mean([float(item["reciprocal_rank"]) for item in scored]),
        "all_gold_found_rate": rounded_mean(
            [1.0 if item["all_gold_found"] else 0.0 for item in scored]
        ),
        "average_latency_seconds": rounded_mean(latencies),
        "p95_latency_seconds": (
            round(percentile(latencies, 0.95), 4) if latencies else None
        ),
        "average_time_to_first_token_seconds": rounded_mean(first_tokens),
    }


def build_report(
    results: list[dict[str, Any]], args: argparse.Namespace, started_at: datetime
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        groups[result["category"]].append(result)

    return {
        "metadata": {
            "started_at": started_at.astimezone().isoformat(),
            "finished_at": datetime.now().astimezone().isoformat(),
            "base_url": args.base_url,
            "questions_file": str(args.questions.resolve()),
            "category_filter": args.category,
            "limit": args.limit,
            "top_k": args.top_k,
            "answer_scoring": (
                "manual_review_required: compare answer with expected_behavior "
                "and expected_points"
            ),
        },
        "summary": summarize(results, args.top_k),
        "by_category": {
            category: summarize(items, args.top_k)
            for category, items in sorted(groups.items())
        },
        "results": results,
    }


def write_csv(path: Path, results: list[dict[str, Any]]) -> None:
    fieldnames = [
        "id",
        "category",
        "role",
        "as_of_date",
        "question",
        "expected_behavior",
        "expected_points",
        "gold_doc_ids",
        "status",
        "error",
        "answer",
        "source_doc_ids",
        "hit_at_k",
        "recall_at_k",
        "reciprocal_rank",
        "all_gold_found",
        "latency_seconds",
        "time_to_first_token_seconds",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = {key: result.get(key) for key in fieldnames}
            row["gold_doc_ids"] = "|".join(result["gold_doc_ids"])
            row["source_doc_ids"] = "|".join(result["source_doc_ids"])
            writer.writerow(row)


def check_health(client: httpx.Client, base_url: str) -> None:
    response = client.get(f"{base_url}/health")
    response.raise_for_status()


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        print("错误：--limit 必须大于 0", file=sys.stderr)
        return 2
    if args.top_k < 1:
        print("错误：--top-k 必须大于 0", file=sys.stderr)
        return 2

    args.base_url = args.base_url.rstrip("/")
    started_at = datetime.now().astimezone()
    try:
        questions = load_questions(args.questions)
    except (OSError, ValueError) as exc:
        print(f"读取评测题失败：{exc}", file=sys.stderr)
        return 2

    if args.category:
        questions = [q for q in questions if q["category"] == args.category]
    if args.limit is not None:
        questions = questions[: args.limit]
    if not questions:
        print("没有符合条件的评测题。", file=sys.stderr)
        return 2

    timestamp = started_at.strftime("%Y%m%d_%H%M%S")
    output_path = args.output or DEFAULT_RESULTS_DIR / f"evaluation_{timestamp}.json"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = output_path.with_suffix(".csv")

    run_id = started_at.strftime("%Y%m%d%H%M%S")
    results: list[dict[str, Any]] = []
    timeout = httpx.Timeout(args.timeout)

    try:
        with httpx.Client(timeout=timeout) as client:
            check_health(client, args.base_url)
            print(f"后端连接正常，共运行 {len(questions)} 道题。")
            for index, question in enumerate(questions, start=1):
                print(
                    f"[{index:02d}/{len(questions):02d}] "
                    f"{question['id']} {question['category']} ... ",
                    end="",
                    flush=True,
                )
                thread_id = f"eval_{run_id}_{question['id'].lower()}"
                result = run_question(
                    client=client,
                    base_url=args.base_url,
                    question=question,
                    thread_id=thread_id,
                    top_k=args.top_k,
                    keep_thread=args.keep_threads,
                )
                results.append(result)
                print(
                    f"{result['status']} ({result['latency_seconds']:.2f}s, "
                    f"sources={len(result['source_doc_ids'])})"
                )
                if args.delay > 0 and index < len(questions):
                    time.sleep(args.delay)
    except (httpx.HTTPError, OSError) as exc:
        print(
            f"无法连接后端 {args.base_url}：{exc}\n"
            "请先启动 FastAPI，或用 --base-url 指定正确地址。",
            file=sys.stderr,
        )
        return 2

    report = build_report(results, args, started_at)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(csv_path, results)

    summary = report["summary"]
    print("\n评测完成")
    print(f"成功/总数：{summary['completed']}/{summary['total']}")
    print(f"Hit@{args.top_k}：{summary[f'hit_at_{args.top_k}']}")
    print(
        f"Macro Recall@{args.top_k}："
        f"{summary[f'macro_recall_at_{args.top_k}']}"
    )
    print(f"MRR：{summary['mrr']}")
    print(f"平均响应时间：{summary['average_latency_seconds']} 秒")
    print(f"P95 响应时间：{summary['p95_latency_seconds']} 秒")
    print("回答正确性：请在 CSV 中对照 expected_behavior/expected_points 人工检查")
    print(f"JSON：{output_path}")
    print(f"CSV：{csv_path}")
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
