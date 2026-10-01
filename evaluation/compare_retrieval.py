"""One-pass paired retrieval comparison; writes no project or database data."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import yaml

from app.RAG.reranker import rerank
from app.RAG.retriever import retriever
from app.RAG.vector_store import create_embedding_model, init_milvus
from app.config import COLLECTION_NAME, JINA_API_KEY, RERANK_CANDIDATE_K, TOP_K
from evaluation.evaluate import load_questions, retrieval_metrics, unique_doc_ids


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / 'data/knowledge/starbridge-rag-starter/evaluation/questions.jsonl'
KNOWLEDGE_BASE = ROOT / 'data/knowledge/starbridge-rag-starter/knowledge_base'


def summarize(rows: list[dict], mode: str) -> dict:
    m = [row[mode]['metrics'] for row in rows]
    return {
        'total': len(rows),
        f'hit_at_{TOP_K}': round(statistics.fmean(float(x['hit_at_k']) for x in m), 4),
        f'macro_recall_at_{TOP_K}': round(statistics.fmean(x['recall_at_k'] for x in m), 4),
        'mrr': round(statistics.fmean(x['reciprocal_rank'] for x in m), 4),
        'all_gold_found_rate': round(statistics.fmean(float(x['all_gold_found']) for x in m), 4),
        'avg_total_seconds': round(statistics.fmean(
            row['retrieval_seconds'] + (row['rerank_seconds'] if mode == 'reranked' else 0)
            for row in rows
        ), 4),
        'avg_rerank_seconds': round(statistics.fmean(row['rerank_seconds'] for row in rows), 4) if mode == 'reranked' else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output is None:
        stamp = datetime.now().astimezone().strftime('%Y%m%d_%H%M%S')
        args.output = ROOT / 'evaluation' / 'results' / f'retrieval_compare_{stamp}.json'
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if not JINA_API_KEY or JINA_API_KEY == 'replace-me':
        raise RuntimeError('JINA_API_KEY is not configured')
    questions = [q for q in load_questions(QUESTIONS) if q['gold_doc_ids']]
    if args.limit:
        questions = questions[:args.limit]

    allowed_doc_ids = set()
    for path in KNOWLEDGE_BASE.rglob('*.md'):
        front_matter = yaml.safe_load(path.read_text(encoding='utf-8').split('---', 2)[1])
        if front_matter.get('source') != 'synthetic':
            raise RuntimeError(f'Non-synthetic knowledge document: {path}')
        allowed_doc_ids.add(front_matter['doc_id'])

    client = init_milvus()
    try:
        row_count = int(client.get_collection_stats(COLLECTION_NAME).get('row_count', 0))
        model = create_embedding_model()
        rows = []
        for i, question in enumerate(questions, 1):
            t0 = time.perf_counter()
            candidates = retriever(
                client=client,
                collection_name=COLLECTION_NAME,
                query=question['question'],
                embedding_model=model,
                limit=RERANK_CANDIDATE_K,
                role=question.get('role', 'customer'),
            )
            retrieval_seconds = time.perf_counter() - t0
            # Mirror the tool's second permission check before external reranking.
            candidates = [hit for hit in candidates if question.get('role', 'customer') in hit['entity'].get('audience', [])]
            for hit in candidates:
                entity = hit['entity']
                if entity.get('doc_id') not in allowed_doc_ids or not str(entity.get('source', '')).startswith(str(KNOWLEDGE_BASE) + '/'):
                    raise RuntimeError('Candidate outside the synthetic built-in knowledge base; refusing external rerank')
            baseline = candidates[:TOP_K]
            t1 = time.perf_counter()
            ranked = rerank(question['question'], candidates, top_k=TOP_K)
            rerank_seconds = time.perf_counter() - t1

            row = {
                'id': question['id'],
                'category': question['category'],
                'role': question.get('role', 'customer'),
                'gold_doc_ids': question['gold_doc_ids'],
                'candidate_count': len(candidates),
                'retrieval_seconds': round(retrieval_seconds, 4),
                'rerank_seconds': round(rerank_seconds, 4),
            }
            for key, hits in [('vector_only', baseline), ('reranked', ranked)]:
                doc_ids = unique_doc_ids([{'doc_id': h['entity'].get('doc_id')} for h in hits])
                row[key] = {
                    'doc_ids': doc_ids,
                    'metrics': retrieval_metrics(question['gold_doc_ids'], doc_ids, TOP_K),
                }
            row['rerank_applied'] = bool(ranked and 'rerank_score' in ranked[0])
            rows.append(row)
            print(f"[{i}/{len(questions)}] {question['id']} baseline={row['vector_only']['metrics']['hit_at_k']} rerank={row['reranked']['metrics']['hit_at_k']} applied={row['rerank_applied']}", flush=True)

        report = {
            'metadata': {
                'run_at': datetime.now().astimezone().isoformat(),
                'question_sha256': hashlib.sha256(QUESTIONS.read_bytes()).hexdigest(),
                'questions_file': str(QUESTIONS),
                'collection': COLLECTION_NAME,
                'collection_row_count': row_count,
                'candidate_k': RERANK_CANDIDATE_K,
                'top_k': TOP_K,
                'rerank_model': 'jina-reranker-v3.5',
                'rerank_applied_count': sum(row['rerank_applied'] for row in rows),
                'fallback_ids': [row['id'] for row in rows if not row['rerank_applied'] and row['candidate_count']],
                'no_candidate_count': sum(row['candidate_count'] == 0 for row in rows),
            },
            'vector_only': summarize(rows, 'vector_only'),
            'reranked': summarize(rows, 'reranked'),
            'results': rows,
        }
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('SUMMARY', json.dumps({k: report[k] for k in ['metadata', 'vector_only', 'reranked']}, ensure_ascii=False), flush=True)
    finally:
        client.close()


if __name__ == '__main__':
    main()
