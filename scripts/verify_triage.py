"""v0: data/inbox と data/triage のファイルペアで messageId 集合が一致するか確認する。

OS非依存（PowerShell の Get-Content|Measure-Object 等の手動カウントを使わない。
レビュー2026-07-06 指摘 #9: SKILL.md の実行コマンドがWindows/PowerShell専用だった）。
append_sheet.py 実行前の必須チェック（DECISIONS §8）をスクリプト化したもの。
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = REPO_ROOT / "data" / "inbox"
TRIAGE_DIR = REPO_ROOT / "data" / "triage"


VALID_CATEGORIES = {"案件", "人材", "その他"}


def _load_message_ids(path: Path) -> list:
    ids = []
    if not path.exists():
        return ids
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.append(json.loads(line)["messageId"])
    return ids


def _load_triage_records(path: Path) -> list:
    records = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def verify_pair(name: str) -> bool:
    inbox_path = INBOX_DIR / f"{name}.jsonl"
    triage_path = TRIAGE_DIR / f"{name}.jsonl"

    if not inbox_path.exists():
        print(f"[{name}] NG: inbox ファイルが見つかりません: {inbox_path}")
        return False
    if not triage_path.exists():
        print(f"[{name}] NG: triage ファイルが見つかりません（未仕分け）: {triage_path}")
        return False

    inbox_ids = _load_message_ids(inbox_path)
    triage_ids = _load_message_ids(triage_path)
    inbox_set, triage_set = set(inbox_ids), set(triage_ids)

    ok = True
    if len(inbox_ids) != len(inbox_set):
        print(f"[{name}] NG: inbox 側に重複 messageId あり")
        ok = False
    if len(triage_ids) != len(triage_set):
        print(f"[{name}] NG: triage 側に重複 messageId が {len(triage_ids) - len(triage_set)} 件")
        ok = False
    missing = inbox_set - triage_set
    if missing:
        print(f"[{name}] NG: triage に無い messageId が {len(missing)} 件: {sorted(missing)[:5]}...")
        ok = False
    extra = triage_set - inbox_set
    if extra:
        print(f"[{name}] NG: inbox に無い messageId が triage に {len(extra)} 件: {sorted(extra)[:5]}...")
        ok = False

    bad_category = []
    empty_reason = []
    for r in _load_triage_records(triage_path):
        if r.get("分類") not in VALID_CATEGORIES:
            bad_category.append((r.get("messageId", "?"), r.get("分類")))
        if not str(r.get("理由", "")).strip():
            empty_reason.append(r.get("messageId", "?"))
    if bad_category:
        print(f"[{name}] NG: 分類が不正な行が {len(bad_category)} 件: {bad_category[:5]}...")
        ok = False
    if empty_reason:
        print(f"[{name}] NG: 理由が空の行が {len(empty_reason)} 件: {empty_reason[:5]}...")
        ok = False

    if ok:
        print(f"[{name}] OK: inbox={len(inbox_ids)}件 triage={len(triage_ids)}件 一致")
    return ok


def main() -> None:
    names = [sys.argv[1]] if len(sys.argv) > 1 else sorted(p.stem for p in INBOX_DIR.glob("*.jsonl"))
    if not names:
        print("data/inbox にファイルがありません。")
        return

    all_ok = all([verify_pair(name) for name in names])
    print()
    print("全ファイル突合OK" if all_ok else "突合NG（上記参照。append_sheet.py 実行前に解消してください）")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
