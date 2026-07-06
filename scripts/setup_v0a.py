"""v0-A 基盤最小のセットアップ（一度だけ実行。再実行しても安全＝冪等）。

- Gmail に SES-AI/processed ラベルを作成（無ければ）
- 案件台帳・人員一覧タブを持つスプレッドシートを新規作成（SHEET_ID未設定時のみ）
- 発行された SHEET_ID を .env に書き込む
- 既存の SHEET_ID がある場合は新規作成をスキップし、_state/_runlog タブだけを
  冪等に用意する（cron化フェーズ1）
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

from auth import get_credentials
from state import ensure_state_tabs

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

PROCESSED_LABEL = "SES-AI/processed"

ANKEN_HEADERS = [
    "row_key", "ingested_at", "received_at", "source_from", "source_email",
    "案件名", "商流", "必須スキル", "尚可スキル", "必要経験年数", "単価", "精算幅",
    "勤務地_県", "勤務地_詳細", "リモート", "開始時期", "期間", "面談回数", "募集人数",
    "国籍_年齢制限", "契約形態", "ステータス", "案件メールリンク", "生文抜粋", "備考",
]
JININ_HEADERS = ["名前", "タブリンク", "件数"]


def ensure_gmail_label(creds) -> None:
    gmail = build("gmail", "v1", credentials=creds)
    labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
    if any(label["name"] == PROCESSED_LABEL for label in labels):
        print(f"Gmail label already exists: {PROCESSED_LABEL}")
        return
    gmail.users().labels().create(
        userId="me",
        body={
            "name": PROCESSED_LABEL,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    print(f"Gmail label created: {PROCESSED_LABEL}")


def create_spreadsheet(creds) -> str:
    sheets = build("sheets", "v4", credentials=creds)
    body = {
        "properties": {"title": "SES-AI 案件台帳"},
        "sheets": [
            {"properties": {"title": "案件台帳"}},
            {"properties": {"title": "人員一覧"}},
        ],
    }
    result = sheets.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    sheet_id = result["spreadsheetId"]

    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="案件台帳!A1",
        valueInputOption="RAW",
        body={"values": [ANKEN_HEADERS]},
    ).execute()
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="人員一覧!A1",
        valueInputOption="RAW",
        body={"values": [JININ_HEADERS]},
    ).execute()

    print(f"Spreadsheet created: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    return sheet_id


def write_sheet_id_to_env(sheet_id: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("SHEET_ID="):
            lines[i] = f"SHEET_ID={sheet_id}"
            updated = True
            break
    if not updated:
        lines.append(f"SHEET_ID={sheet_id}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f".env updated: SHEET_ID={sheet_id}")


def main() -> None:
    creds = get_credentials()
    ensure_gmail_label(creds)

    load_dotenv(REPO_ROOT / ".env")
    sheet_id = os.environ.get("SHEET_ID")
    if sheet_id:
        print(f"Existing SHEET_ID detected: {sheet_id}（新規スプレッドシート作成はスキップ）")
    else:
        sheet_id = create_spreadsheet(creds)
        write_sheet_id_to_env(sheet_id)

    sheets = build("sheets", "v4", credentials=creds)
    ensure_state_tabs(sheets, sheet_id)


if __name__ == "__main__":
    main()
