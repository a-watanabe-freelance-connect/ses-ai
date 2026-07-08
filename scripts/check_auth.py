"""認証疎通の診断スクリプト（Routine環境変数テスト用）。

`get_credentials()` で取得した認証情報で Gmail / Sheets / Drive の各 API に
軽いリクエストを1回ずつ投げ、到達できるかだけを確認する。要員プロフィール等の
PII には一切アクセスせず、出力も共有メールボックスのアドレスと各APIのOK/NGのみ。

Routine（無人実行）で環境変数 GOOGLE_OAUTH_TOKEN_JSON 経由のトークンが
サンドボックス内で正しく認証に使えるかの疎通確認に使う（Routine化ロードマップ フェーズ3-5）。
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

from auth import get_credentials

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")

    # トークンの供給元を表示（値そのものは出さない）
    if os.environ.get("GOOGLE_OAUTH_TOKEN_JSON"):
        print("[source] GOOGLE_OAUTH_TOKEN_JSON（環境変数）から認証情報を読み込みます")
    elif os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY"):
        print("[source] GOOGLE_SERVICE_ACCOUNT_KEY（サービスアカウント鍵）から読み込みます")
    else:
        print("[source] secrets/token.json（ローカルOAuthファイル）から読み込みます")

    creds = get_credentials()
    print(f"[scopes] {getattr(creds, 'scopes', None)}")

    ok = True

    # Gmail: getProfile（返るのは共有メールボックスのアドレスと総数のみ）
    try:
        gmail = build("gmail", "v1", credentials=creds)
        profile = gmail.users().getProfile(userId="me").execute()
        print(f"[Gmail] OK: {profile.get('emailAddress')} (messagesTotal={profile.get('messagesTotal')})")
    except Exception as e:
        ok = False
        print(f"[Gmail] NG: {e}", file=sys.stderr)

    # Sheets: SHEET_ID があればタイトルだけ取得（無ければスキップ）
    sheet_id = os.environ.get("SHEET_ID")
    if sheet_id:
        try:
            sheets = build("sheets", "v4", credentials=creds)
            meta = sheets.spreadsheets().get(
                spreadsheetId=sheet_id, fields="properties.title"
            ).execute()
            print(f"[Sheets] OK: title={meta['properties']['title']}")
        except Exception as e:
            ok = False
            print(f"[Sheets] NG: {e}", file=sys.stderr)
    else:
        print("[Sheets] SKIP: SHEET_ID 未設定")

    # Drive: about.get（返るのは認証ユーザー情報のみ・ファイルには触れない）
    try:
        drive = build("drive", "v3", credentials=creds)
        about = drive.about().get(fields="user(emailAddress)").execute()
        print(f"[Drive] OK: {about['user']['emailAddress']}")
    except Exception as e:
        ok = False
        print(f"[Drive] NG: {e}", file=sys.stderr)

    print("RESULT:", "ALL_OK" if ok else "HAS_FAILURE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
