#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault-rag — 保存先を「意味の地図」に置いて、言葉が違っても引けるようにする（fox-kit）

なぜ要るか:
  ファイル名や本文の言葉で探す（grep）と、書かれている言葉に一致しないと見つからない。
  例：質問「来客の人数を自動で数える装置」→ ノート側には「人流カメラ」としか書いていない。これを埋める。

仕組み（RAG の検索側）:
  1. 保存先の .md を数百字ごとに切る（chunk）
  2. 各 chunk を Gemini の埋め込みで 768 次元の座標に変換して保存＝意味の地図
  3. 質問も同じ地図に置き、近い chunk を上位 k 件だけ返す
  → 全部を読ませるのではなく、近い数ページだけ渡す。

設計上の判断:
  - 索引は差分更新。ファイルの内容ハッシュが変わった分だけ再埋め込みする（毎日回しても課金は増えない）。
  - Google Drive のストリーミングは未取得ファイルで EDEADLK を投げるので、読めないファイルは飛ばして続行する。
  - 目次（_目次.md）や機械的なログは索引しない。探したいのは人が書いたノートだから。
  - 埋め込みは文書用と質問用でタスク種別を分ける（Gemini の taskType）。精度がはっきり変わる。

使い方:
  python3 rag.py index            # 差分索引（初回は全件）
  python3 rag.py index --full     # 全件作り直し
  python3 rag.py search "来客の人数を自動で数える装置"
  python3 rag.py stats
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

def _default_vault() -> str:
    """fox-kit の保存先（~/.config/fox-kit/storage.json の base）。無ければ ~/Documents。"""
    try:
        return json.loads((Path.home() / ".config/fox-kit/storage.json").read_text())["base"]
    except (OSError, ValueError, KeyError):
        return str(Path.home() / "Documents")


# 索引はキットの外に置く（キットを更新しても消えない）
BASE = Path(os.getenv("RAG_DATA", str(Path.home() / ".local/share/fox-kit/rag")))
BASE.mkdir(parents=True, exist_ok=True)
VAULT = Path(os.getenv("FOX_VAULT", _default_vault()))

# 埋め込みの出し手を差し替えられるようにする。
#   gemini … Gemini API（キーは Mac のキーチェーン：fox-kit / gemini）
#   local  … 端末内で完結する多言語モデル（文書を外に出さない・鍵不要。sentence-transformers が要る）
# 会社の文書を外部の API に出したくない場合は local にする。
BACKEND = os.getenv("RAG_BACKEND", "gemini")
LOCAL_MODEL = os.getenv("RAG_LOCAL_MODEL", "intfloat/multilingual-e5-small")
INDEX = BASE / "index.npz"
CHUNKS = BASE / "chunks.jsonl"
MANIFEST = BASE / "manifest.json"          # ファイル→内容ハッシュ（差分判定の真実源）

MODEL = "gemini-embedding-001"
DIMS = 384 if BACKEND == "local" else 768   # multilingual-e5-small は384次元
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"

# 索引するフォルダ（人が読むノート）。"." を指定すると VAULT 直下すべてを対象にする。
INCLUDE_DIRS = [d for d in os.getenv(
    "RAG_INCLUDE_DIRS", ".").split(",") if d]
# 機械ログ・日次スナップショット（量が多くノイズになる）
EXCLUDE_PARTS = {"claude-logs", "limitless", "AIニュース", "コード検証", "Transcripts",
                 "_整理ログ", "_整理提案", "_auto_backups", ".obsidian", ".trash", "assets"}
EXCLUDE_NAME = re.compile(r"(^_目次\.md$|^_全体の目次\.md$|\.bak$|\.new-[0-9.]+$)")

# 索引する拡張子。個人 vault は .md だけだが、法人の本棚は PDF/Word が主なので足せるようにする。
EXTS = tuple(e if e.startswith(".") else "." + e
             for e in os.getenv("RAG_EXTS", ".md").split(",") if e)

CHUNK_CHARS = 500
CHUNK_OVERLAP = 100
BATCH = 50                                  # 1リクエストに載せる chunk 数


# ---------------------------------------------------------------- 鍵

def api_key() -> str:
    if BACKEND == "local":
        return ""                                           # 端末内で完結するので鍵は要らない
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    import subprocess
    r = subprocess.run(["security", "find-generic-password", "-s", "fox-kit", "-a", "gemini", "-w"],
                       capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    sys.exit("Gemini の API キーがありません（fox-kit packs key で登録）")


# ---------------------------------------------------------------- 収集・分割

def iter_notes() -> list[Path]:
    out: list[Path] = []
    for d in INCLUDE_DIRS:
        root = VAULT / d
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [x for x in dirnames if x not in EXCLUDE_PARTS]
            for f in filenames:
                if f.endswith(EXTS) and not EXCLUDE_NAME.search(f):
                    out.append(Path(dirpath) / f)
    return sorted(out)


# 生の文字起こし判定。02_PLAUD_Logs/Summaries には「議事録」と「話者ラベル付きの
# 生文字起こし」が同じ拡張子で同居している。後者は言い直し・相槌だらけで意味が薄く、
# 実測で索引の15%を占めて検索結果を占領していた（2026-08-27）。ファイル名ではなく
# 中身で弾く（命名規則が揺れているため）。
#
# 2026-08-29 追加: 話者ラベルが無い生文字起こしも紛れていた。こちらはタイムスタンプ
# だけの行（00:00:00）が延々と続く形式で、話者名では捕まらない。実測で、この形式の
# 3本が「多様な質問12問の上位5件×12問=60枠」のうち15枠（25%）を占めていた。
# 話題が散らかった長い雑談は、どの質問にも中くらいに近いので全部の結果に居座る。
_SPEAKER_RE = re.compile(r"Speaker \d+\s+\d\d:\d\d")
_TIMESTAMP_LINE_RE = re.compile(r"^\s*\d{1,2}:\d{2}:\d{2}\s*$", re.M)


def _pdf_text(p: Path) -> str:
    from pypdf import PdfReader
    return "\n\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)


def _docx_text(p: Path) -> str:
    import docx
    return "\n\n".join(par.text for par in docx.Document(str(p)).paragraphs if par.text.strip())


def _doc_text(p: Path) -> str:
    """旧 .doc は macOS 標準の textutil に任せる（追加の依存を入れない）。"""
    import subprocess
    r = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(p)],
                       capture_output=True, timeout=120)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""


_EXTRACTORS = {".pdf": _pdf_text, ".docx": _docx_text, ".doc": _doc_text}


def read_note(p: Path) -> str | None:
    """本文を取り出す。読めないものは飛ばす（Drive の未取得ファイルは EDEADLK を投げる）。

    PDF/Word は抽出に失敗しても索引全体を止めない。ライブラリが無い環境では
    その形式を黙って飛ばすだけにして、.md しか無い機械でも同じコードが動くようにする。
    """
    ext = p.suffix.lower()
    if ext in _EXTRACTORS:
        try:
            text = _EXTRACTORS[ext](p)
        except Exception:
            return None
        return text if text and text.strip() else None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def is_raw_transcript(text: str) -> bool:
    return (len(_SPEAKER_RE.findall(text)) >= 3
            or len(_TIMESTAMP_LINE_RE.findall(text)) >= 5)


def split(text: str) -> list[str]:
    """段落境界を優先しつつ CHUNK_CHARS 前後で切る。前後を少し重ねて文脈落ちを防ぐ。"""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    chunks, buf = [], ""
    for para in text.split("\n\n"):
        if len(buf) + len(para) + 2 <= CHUNK_CHARS:
            buf = f"{buf}\n\n{para}" if buf else para
            continue
        if buf:
            chunks.append(buf)
        while len(para) > CHUNK_CHARS:                     # 1段落が長すぎる場合は機械的に切る
            chunks.append(para[:CHUNK_CHARS])
            para = para[CHUNK_CHARS - CHUNK_OVERLAP:]
        buf = para
    if buf:
        chunks.append(buf)
    return [c.strip() for c in chunks if c.strip()]


# ---------------------------------------------------------------- 埋め込み

def _post(url: str, payload: dict, key: str, tries: int = 4) -> dict:
    body = json.dumps(payload).encode()
    for attempt in range(tries):
        req = urllib.request.Request(
            f"{url}?key={key}", data=body,
            headers={"Content-Type": "application/json", "User-Agent": "fox-vault-rag/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < tries - 1:
                time.sleep(2 ** attempt * 3)               # レート制限は待って再試行
                continue
            raise
        except Exception:
            if attempt < tries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise
    raise RuntimeError("unreachable")


_local_model = None


def _embed_local(texts: list[str], task: str) -> np.ndarray:
    """端末内で完結する埋め込み。外部にテキストを送らない。

    e5 系は「query: 」「passage: 」の接頭辞を付けて学習されている。
    付け忘れると精度がはっきり落ちるので、ここで必ず付ける。
    """
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(LOCAL_MODEL)
    prefix = "query: " if task == "RETRIEVAL_QUERY" else "passage: "
    arr = _local_model.encode([prefix + t for t in texts],
                              batch_size=32, normalize_embeddings=True,
                              show_progress_bar=sys.stdout.isatty() and len(texts) > 200)
    return np.asarray(arr, dtype=np.float32)


def embed(texts: list[str], key: str, task: str) -> np.ndarray:
    """task: RETRIEVAL_DOCUMENT（索引側）/ RETRIEVAL_QUERY（質問側）"""
    if BACKEND == "local":
        return _embed_local(texts, task)
    vecs: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        part = texts[i:i + BATCH]
        res = _post(f"{ENDPOINT}:batchEmbedContents", {
            "requests": [{
                "model": f"models/{MODEL}",
                "content": {"parts": [{"text": t}]},
                "taskType": task,
                "outputDimensionality": DIMS,
            } for t in part],
        }, key)
        vecs.extend(e["values"] for e in res["embeddings"])
        if len(texts) > BATCH:
            print(f"  embedded {min(i + BATCH, len(texts))}/{len(texts)}", flush=True)
    arr = np.asarray(vecs, dtype=np.float32)
    # 3072次元未満を指定したときは正規化が必要（Google のドキュメント通り）
    return arr / np.clip(np.linalg.norm(arr, axis=1, keepdims=True), 1e-8, None)


# ---------------------------------------------------------------- 索引

def load_index() -> tuple[np.ndarray, list[dict]]:
    if not INDEX.exists() or not CHUNKS.exists():
        return np.zeros((0, DIMS), dtype=np.float32), []
    vecs = np.load(INDEX)["v"]
    meta = [json.loads(l) for l in CHUNKS.read_text(encoding="utf-8").splitlines() if l.strip()]
    return vecs, meta


def build(full: bool = False) -> dict:
    key = api_key()
    old_manifest = {} if full else (
        json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {})
    old_vecs, old_meta = (np.zeros((0, DIMS), dtype=np.float32), []) if full else load_index()

    notes = iter_notes()
    manifest, fresh_texts, fresh_meta = {}, [], []
    unreadable = 0
    skipped_raw = 0
    reuse_files: set[str] = set()

    for p in notes:
        text = read_note(p)
        if text is None:
            unreadable += 1
            # 読めなかった回に索引から消すと、Drive が不調な日に検索結果が痩せる。
            # 前回のハッシュを持ち越して既存の chunk を温存する。
            rel = str(p.relative_to(VAULT))
            if rel in old_manifest:
                manifest[rel] = old_manifest[rel]
                reuse_files.add(rel)
            continue
        if is_raw_transcript(text):
            skipped_raw += 1
            continue
        rel = str(p.relative_to(VAULT))
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        manifest[rel] = h
        if old_manifest.get(rel) == h:
            reuse_files.add(rel)
            continue
        # 埋め込む前にタイトル（＝ファイル名と置き場所）を頭に足す。
        # chunk 単体だと「何の話か」が本文に書かれていないことが多く、
        # 「補助金ウォッチ」のような題名の情報が丸ごと失われるため。
        head = f"{Path(rel).parent}／{Path(rel).stem}"
        for i, c in enumerate(split(text)):
            fresh_texts.append(f"{head}\n\n{c}")
            fresh_meta.append({"file": rel, "i": i, "text": c, "h": h})

    keep = [(v, m) for v, m in zip(old_vecs, old_meta) if m["file"] in reuse_files]
    kept_vecs = (np.stack([v for v, _ in keep]) if keep
                 else np.zeros((0, DIMS), dtype=np.float32))
    kept_meta = [m for _, m in keep]

    if fresh_texts:
        print(f"embedding {len(fresh_texts)} chunks（変更のあった分だけ）", flush=True)
        new_vecs = embed(fresh_texts, key, "RETRIEVAL_DOCUMENT")
    else:
        new_vecs = np.zeros((0, DIMS), dtype=np.float32)

    vecs = np.concatenate([kept_vecs, new_vecs]) if len(kept_vecs) or len(new_vecs) else kept_vecs
    meta = kept_meta + fresh_meta

    np.savez_compressed(INDEX, v=vecs)
    CHUNKS.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in meta),
                      encoding="utf-8")
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=0), encoding="utf-8")

    return {"notes": len(notes), "chunks": len(meta), "new_chunks": len(fresh_texts),
            "reused_files": len(reuse_files), "unreadable": unreadable,
            "skipped_raw": skipped_raw}


# ---------------------------------------------------------------- 検索

# 「ハブ chunk」への減点の強さ。既定 0＝無効（下の実測の結論）。
#
# 症状（2026-08-29・多様な質問12問で計測）:
#   話題が散らかった長い雑談の要約ノート1本が、無関係な質問にも中くらいの近さで
#   居座り、上位5件×12問=60枠のうち 15枠（25%）・9問を占めていた。
#
# 試した対策と結果（全 chunk の平均ベクトルへの近さ＝どの質問にも薄く近い度合いを減点）:
#       λ=1.0 → ハブ占有 15→9枠。ただし「補助金」の質問で正解ノートが上位3件から脱落
#       λ=1.5 → ハブ占有 3枠。既知の正解4問中1位ゼロ（正解ごと潰れる）
#       λ=2.0 → ハブ占有 0枠。上位が完全に無関係なノートに入れ替わる
#   → 強くすればハブは消えるが、消しすぎると正解も消える。中間でも副作用が出た。
#     採用しない（既定 0）。根治は索引の中身の側＝話題が散らかった雑談の要約を
#     索引に入れないこと。検索式ではなく索引設計の問題だった。
HUB_PENALTY = float(os.getenv("RAG_HUB_PENALTY", "0"))


def search(question: str, k: int = 5, per_file: int = 2) -> list[dict]:
    vecs, meta = load_index()
    if not len(vecs):
        return []
    q = embed([question], api_key(), "RETRIEVAL_QUERY")[0]
    sims = vecs @ q
    rank = sims                                  # 並べ替えに使う値（表示は素の類似度のまま）
    if HUB_PENALTY:
        mu = vecs.mean(axis=0)
        mu /= max(float(np.linalg.norm(mu)), 1e-8)
        rank = sims - HUB_PENALTY * (vecs @ mu)
    hits, seen = [], {}
    for idx in np.argsort(-rank):
        m = meta[int(idx)]
        if seen.get(m["file"], 0) >= per_file:      # 1ファイルが結果を独占しないようにする
            continue
        seen[m["file"]] = seen.get(m["file"], 0) + 1
        hits.append({"score": round(float(sims[idx]), 4), "file": m["file"], "text": m["text"]})
        if len(hits) >= k:
            break
    return hits


def format_hits(hits: list[dict]) -> str:
    if not hits:
        return "該当なし（索引が空の可能性があります: python3 rag.py index）"
    out = []
    for h in hits:
        out.append(f"[{h['score']:.3f}] {h['file']}\n{h['text']}")
    return "\n\n---\n\n".join(out)


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("index"); b.add_argument("--full", action="store_true")
    s = sub.add_parser("search"); s.add_argument("question"); s.add_argument("-k", type=int, default=5)
    sub.add_parser("stats")
    a = ap.parse_args()

    if a.cmd == "index":
        r = build(full=a.full)
        print(f"ノート {r['notes']}本 / chunk {r['chunks']}件"
              f"（新規埋め込み {r['new_chunks']}件・据え置き {r['reused_files']}ファイル"
              f"・読めず {r['unreadable']}件・生文字起こし除外 {r['skipped_raw']}本）")
    elif a.cmd == "search":
        print(format_hits(search(a.question, k=a.k)))
    else:
        vecs, meta = load_index()
        files = {m["file"] for m in meta}
        print(f"chunk {len(meta)}件 / ファイル {len(files)}本 / 次元 {vecs.shape[1] if len(vecs) else 0}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
