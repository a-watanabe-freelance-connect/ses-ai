"""v0-C: マッチ用に 案件台帳 を全件読む（v0は絞り込み無し）。

ヘッダー行をキーにした dict のリストを返す・出力する。
案件台帳の列構成が変わっても（列追加・削除・リネーム・順序変更）そのまま追従する。
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

from auth import get_credentials

REPO_ROOT = Path(__file__).resolve().parent.parent
SHEET_NAME = "案件台帳"


def read_anken(sheets, sheet_id: str) -> list:
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{SHEET_NAME}!A1:Z"
    ).execute()
    values = resp.get("values", [])
    if not values:
        return []

    headers = values[0]
    records = []
    for row in values[1:]:
        padded = row + [""] * (len(headers) - len(row))
        records.append(dict(zip(headers, padded)))
    return records


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    sheet_id = os.environ["SHEET_ID"]

    creds = get_credentials()
    sheets = build("sheets", "v4", credentials=creds)

    records = read_anken(sheets, sheet_id)
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
