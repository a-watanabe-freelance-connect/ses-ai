"""差分マッチの入力を一括生成（一括モード用・DECISIONS §9）。

稼働中フォルダ(Drive)の**全要員**について、各自の `match_cursor` 以降の差分案件を
案件台帳から切り出して1回で束ねる。**人員を名指ししない**＝Driveの「稼働中」に登録された
全員が自動対象（人が増減してもコマンドは不変）。案件台帳は1回だけ読み、要員ごとに
`ingested_at > その要員のカーソル` で分割する（要員ごとのSheets読みを避ける）。

出力(stdout, JSON):
{
  "high_water": "<台帳全体の最新 ingested_at。全員のカーソル前進に使う共通値>",
  "targets": [
    {"person_name": "...", "cursor": "<現在のカーソル・空=初回全件>",
     "delta_count": N, "profile": "<md本文>", "delta": [ {案件dict}, ... ]},
    ...
  ]
}
- 各 `delta` はその要員のカーソル基準（＝要員ごとに範囲が違う）。`profile` は本人条件。
  `high_water` は全員共通で、評価後に各要員のカーソルを進める先に使う。
- `<人員名>.md` が無い人員フォルダは `iter_all_profiles` が `[skip]` を stderr に出してスキップ。
- `--full`: 全要員をカーソル無視で全件（スキル編集後の全員再マッチ。通常は state.py match-cursor reset を使う）。

使い方（一括マッチ・SKILL.md 手順）:
  1. このスクリプトで {high_water, targets} を得る
  2. 各 target の `delta`（差分案件）を `profile`（本人条件）と照合して評価
     → data/matches/<person_name>.jsonl（1行1案件）
  3. write_match.py <person_name> --advance-cursor <high_water> で本人タブへ反映＋カーソル前進
"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

import state as st
from auth import get_credentials
from read_profile import iter_all_profiles
from read_sheet import filter_since, high_water, read_anken

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_targets(sheets, drive, sheet_id: str, folder_id: str, full: bool = False):
    """(high_water, targets) を返す。台帳を1回読み、稼働中全員ぶんの差分を切り出す。"""
    records = read_anken(sheets, sheet_id)
    hw = high_water(records)

    targets = []
    for person_name, content in iter_all_profiles(drive, folder_id):
        cursor = "" if full else st.get_match_cursor(sheets, sheet_id, person_name)
        delta = filter_since(records, cursor)
        targets.append({
            "person_name": person_name,
            "cursor": cursor,
            "delta_count": len(delta),
            "profile": content,
            "delta": delta,
        })
    return hw, targets


def main() -> None:
    parser = argparse.ArgumentParser(
        description="稼働中フォルダ全要員の差分マッチ入力を一括生成（DECISIONS §9）"
    )
    parser.add_argument(
        "--full", action="store_true",
        help="全要員をカーソル無視で全件にする（スキル編集後の全員再マッチ）",
    )
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    sheet_id = os.environ["SHEET_ID"]
    folder_id = os.environ["PROFILE_FOLDER_ID"]

    creds = get_credentials()
    sheets = build("sheets", "v4", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    hw, targets = build_targets(sheets, drive, sheet_id, folder_id, full=args.full)

    total_delta = sum(t["delta_count"] for t in targets)
    print(
        f"[match_prepare] targets={len(targets)} high_water={hw} "
        f"total_delta_ankens={total_delta}{' (--full)' if args.full else ''}",
        file=sys.stderr,
    )
    for t in targets:
        print(
            f"[match_prepare]   {t['person_name']}: delta={t['delta_count']} "
            f"cursor={t['cursor'] or '(未設定=初回全件)'}",
            file=sys.stderr,
        )

    print(json.dumps({"high_water": hw, "targets": targets}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()