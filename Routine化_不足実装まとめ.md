# リモートタスク(/schedule = claude.ai Routines)採用にあたって不足している実装内容

作成日: 2026-07-06

`/schedule`スキルの実仕様（`RemoteTrigger`ツール定義・接続済みMCPコネクタ一覧など、実データから確認したもの。以前セッションで発生した「架空の回答」の再発防止として、推測ではなく実ツール仕様から整理）に基づく。

## 前提として判明したRoutineの仕組み

Routine（`/schedule`）は、実行のたびに**指定したgit repo URLをクラウドサンドボックスにクローン**し、ゼロコンテキストの単一プロンプト＋`allowed_tools`＋任意の`mcp_connections`（MCPサーバー）だけでClaude Codeセッションを1回走らせる仕組み。**ローカルファイル・ローカル環境変数には一切アクセスできない**（スキル本文に明記）。

## 不足している実装（優先度の高い順）

1. **gitリポジトリ化**
   現在このプロジェクトは未git初期化。Routineはgit repo以外からコードを持ち込む手段がないため、`.claude/skills/`・`scripts/`・`CLAUDE.md`一式をどこか（例: プライベートGitHub repo）へpushする必要がある。`secrets/`・`.env`は絶対に含めないこと。

2. **認証方式の刷新（最大の障壁）**
   現行のGmail/Sheetsアクセスは`secrets/credentials.json`＋`secrets/token.json`のローカルOAuthユーザートークン前提。Routine作成APIのボディには秘密情報を注入するフィールドが存在せず（`environment_id`/`session_context`/`events`のみ）、**外部サービスへ到達する経路は実質MCPコネクタのみ**。

3. **Gmail/Sheets用MCPコネクタが未接続**
   現在接続済みのMCPコネクタは**Google Driveのみ**。Gmail・Google Sheets用のコネクタは接続されておらず、そもそもAnthropicのコネクタディレクトリに存在するかも未確認（`https://claude.ai/customize/connectors` で確認・接続が必要）。

4. **既存v0設計との衝突**
   `CLAUDE.md`は「Gmail取込はMCP不採用・自作スクリプトが第一選択」「Sheets MCPは対話時の軽い読取のみ」と明記済み（1日5,455通規模の本文をMCP越しに読むのは非現実的という判断）。MCP経由に倒すなら`fetch_gmail.py`/`append_sheet.py`/`read_sheet.py`/`write_match.py`の入出力層を再設計する規模の変更になる。`/ses-match`（台帳を全件読むだけ）は比較的相性が良いが、`/ses-triage`＋`/ses-structure`（1日5,455通のfetch）はMCP不採用の理由がそのまま残る。

5. **無人実行に耐えるGoogle認証形態への切替**
   Routineは対話的なOAuth同意画面を通せない。現行のExternal+Testing OAuthはrefresh tokenが約7日で失効するため、Routineで動かすなら**サービスアカウント（委任アクセス）またはInternal OAuth化**が前提条件になる（元はbacklog項目だが前倒しが必要）。

6. **スケジュール粒度**
   Routineの最小cron間隔は**1時間**（30分刻み等は拒否される）。実測規模（案件約1,850通/日）を1時間毎起動で捌けるかは、無人化バッチ処理＋Haiku化（既存backlogの優先課題）の実装状況次第。

7. **スキル呼び出し方式の未検証**
   クローンしたrepo内に`.claude/skills/`があれば`/ses-triage`等をプロンプト内で呼べる可能性は高いが、実際にRoutine環境でスキルが展開されるかは未検証。

8. **複数実行主体の整合**
   フェーズ1で作った`_state`/`_runlog`（ロック・キルスイッチ・監査ログ）はSheetsベースなので理論上共有できるが、「ローカル複数PC」に加えて「クラウドRoutine」という第3の実行主体が増えることになり、その整合は未検証。

## 次に決めること

上記は相互依存が強い（特に2・3・4）。まずどこから着手するかを一つ決めてから進める。候補例:
- まずGmail/SheetsのMCPコネクタが実在するか確認する
- まずgit化だけ進める
- まず認証方式（サービスアカウント化）の検討から始める
