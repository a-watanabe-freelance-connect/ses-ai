"""H-1: 本人タブ（台帳book内・タブ名＝要員名）から共有可の列だけを、
当該要員の共有book（Drive「稼働中」/<要員名>/ 内）へ射影する。

方針（資料/共有book切り出しロードマップ.md）:
- 共有列は「列名」で選ぶ（位置固定 A:I にしない）＝ SHARE_COLUMNS。
  - fail-safe①: SHARE_COLUMNS が MATCH_HEADERS に無ければ起動時に停止（コード整合エラー）。
  - fail-safe②: 本人タブに該当ヘッダーが無ければ警告してその列だけスキップ（本体は壊さない）。
- dedup は本人タブ側（`案件row_key(messageId)` 保持）に一本化。共有bookは row_key 等の
  秘匿列を落とした派生物なので、毎回 本人タブを読んで全行 rebuild する（冪等）。
- 共有bookは 稼働中/<要員名>/ 内に「<要員名>_案件マッチ」を get-or-create（命名規約）。
- 権限付与は手動（本スクリプトは book の生成/更新まで）。末尾に共有用URLを出力する。

使い方:
  python scripts/export_share_book.py <要員名>   # 1名
  python scripts/export_share_book.py            # 稼働中の全員
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

from auth import get_credentials
from read_profile import list_person_folders
from write_match import MATCH_HEADERS

REPO_ROOT = Path(__file__).resolve().parent.parent
SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"
BOOK_SUFFIX = "_案件マッチ"

# 共有book へ射影する列（本人タブのヘッダー名で指定・位置に依存しない）。
# ＝ 先頭〜「適合理由」。除外＝懸念/ステータス/案件row_key(messageId)/リンク。
SHARE_COLUMNS = [
    "記載日", "適合度", "案件名", "単価", "勤務地",
    "リモート", "商流", "必須スキル", "適合理由",
]

# fail-safe①: コード整合チェック（実データに触る前に落とす）。
_unknown = [c for c in SHARE_COLUMNS if c not in MATCH_HEADERS]
if _unknown:
    raise SystemExit(
        f"[fatal] SHARE_COLUMNS が本人タブの MATCH_HEADERS に存在しません: {_unknown}. "
        f"write_match.MATCH_HEADERS と整合を取ってください。"
    )


def _drive_q(value: str) -> str:
    """Drive v3 クエリの文字列リテラル用エスケープ（\\ と ' をエスケープ）。"""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _range_tab(value: str) -> str:
    """A1 記法のシート名用エスケープ（シングルクォートは '' に二重化）。"""
    return value.replace("'", "''")


def find_person_folder_id(drive, root_folder_id: str, person_name: str) -> str:
    folders = [f for f in list_person_folders(drive, root_folder_id) if f["name"] == person_name]
    if not folders:
        raise FileNotFoundError(f"人員フォルダが見つかりません: {person_name}（folder={root_folder_id}）")
    return folders[0]["id"]


def get_or_create_book(drive, folder_id: str, book_name: str):
    """(book_id, created) を返す。フォルダ内に同名 spreadsheet があれば再利用。"""
    resp = drive.files().list(
        q=(f"'{folder_id}' in parents and name = '{_drive_q(book_name)}' "
           f"and mimeType = '{SPREADSHEET_MIME}' and trashed = false"),
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="allDrives",
    ).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"], False
    meta = drive.files().create(
        body={"name": book_name, "mimeType": SPREADSHEET_MIME, "parents": [folder_id]},
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return meta["id"], True


def tab_exists(sheets, sheet_id: str, person_name: str) -> bool:
    meta = sheets.spreadsheets().get(
        spreadsheetId=sheet_id, fields="sheets.properties.title"
    ).execute()
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    return person_name in titles


def read_person_tab(sheets, sheet_id: str, person_name: str) -> list:
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"'{_range_tab(person_name)}'!A:Z"
    ).execute()
    return resp.get("values", [])


def project(rows: list):
    """本人タブの全行を SHARE_COLUMNS へ列名で射影。(header, data_rows) を返す。"""
    if not rows:
        return [], []
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    missing = [c for c in SHARE_COLUMNS if c not in idx]
    if missing:
        print(f"[warn] 本人タブに無い共有列をスキップ: {missing}", file=sys.stderr)
    cols = [c for c in SHARE_COLUMNS if c in idx]
    data = [[r[idx[c]] if idx[c] < len(r) else "" for c in cols] for r in rows[1:]]
    return cols, data


def rebuild_book(sheets, book_id: str, header: list, data: list) -> None:
    """共有book の先頭シートを全書き換え（clear → header+data を書込）。冪等。"""
    sheets.spreadsheets().values().clear(spreadsheetId=book_id, range="A:Z").execute()
    if not header:
        return
    sheets.spreadsheets().values().update(
        spreadsheetId=book_id, range="A1",
        valueInputOption="RAW", body={"values": [header] + data},
    ).execute()


def export_one(drive, sheets, sheet_id: str, root_folder_id: str, person_name: str) -> str:
    folder_id = find_person_folder_id(drive, root_folder_id, person_name)
    if not tab_exists(sheets, sheet_id, person_name):
        print(f"[skip] 本人タブが台帳にありません: {person_name}（先にマッチを実行）", file=sys.stderr)
        return ""
    header, data = project(read_person_tab(sheets, sheet_id, person_name))
    book_name = f"{person_name}{BOOK_SUFFIX}"
    book_id, created = get_or_create_book(drive, folder_id, book_name)
    rebuild_book(sheets, book_id, header, data)
    url = f"https://docs.google.com/spreadsheets/d/{book_id}/edit"
    print(f"[{'created' if created else 'updated'}] {book_name}: {len(data)}行 → {url}")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="本人タブ→共有bookへ列射影（H-1）")
    parser.add_argument("person_name", nargs="?", help="要員名（省略時は稼働中フォルダの全員）")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    sheet_id = os.environ["SHEET_ID"]
    root_folder_id = os.environ["PROFILE_FOLDER_ID"]

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)

    if args.person_name:
        export_one(drive, sheets, sheet_id, root_folder_id, args.person_name)
    else:
        for folder in list_person_folders(drive, root_folder_id):
            try:
                export_one(drive, sheets, sheet_id, root_folder_id, folder["name"])
            except Exception as e:  # 1名の失敗で全体を止めない（ses-match と同方針）
                print(f"[error] {folder['name']}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()