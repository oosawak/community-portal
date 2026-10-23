# まちのつながり — 分散型JSON統合ポータル

**このリポジトリには4サイトのMarkdown原稿や店舗画像はありません。** 各サイトが公開する共通JSON v1.1を、ビルド時にHTTPSで取得・検証・統合します。

## 最初の公開手順

1. GitHubで**空のPublicリポジトリ**を作成してください（READMEの自動作成は選ばない）。
2. このZIPを解凍し、**解凍フォルダの中身**をそのリポジトリの直下に配置します。
3. `main` ブランチへpushします。
4. GitHubの **Settings → Pages → Build and deployment → Source = GitHub Actions** を選択します。
5. **Actions → Build and publish... / Merge feeds...** が成功したらPagesのURLを確認します。

```bash
git init
git add .
git commit -m "Initial independent JSON site"
git branch -M main
git remote add origin https://github.com/<OWNER>/<REPOSITORY>.git
git push -u origin main
```

> `<OWNER>` と `<REPOSITORY>` は自分のGitHub情報へ置換します。標準の公開URLは `https://OWNER.github.io/REPOSITORY/` です。個人トップの `OWNER.github.io` リポジトリでは末尾パスを付けません。非公開リポジトリでのPages公開可否はプランに依存します。

## 4サイトと接続する

**先に4つの独立サイトをGitHub Pagesで公開**してください。その後、このポータル側で次を実行します。

```bash
python scripts/configure_sources.py --owner OWNER
# 独自リポジトリ名を使った場合：
# python scripts/configure_sources.py --owner OWNER --bakery custom-bakery --town custom-town --fruit custom-fruit --gourmet custom-gourmet
cat data/sources.json
git add data/sources.json
git commit -m "Connect four site feeds"
git push
```

**注意**：`OWNER` はGitHubユーザー名に置き換えてください。各リポジトリ名は `haru-no-tane-bakery`、`midorino-town`、`kajitsu-biyori`、`yamagata-gourmet` をデフォルトとして想定しています。

`data/sources.json` の各ソースには `id`、`homepage`、`url`（`data/sites/ID.json`）、`allowed_hosts` が入ります。カスタムドメインを使うサイトはこのファイル内のHTTPS URLとホスト名を実際のものへ変更してください。

## 更新タイミング

- 各サイトのMarkdownコミット → **そのサイトのActions**が記事JSONを更新・Pages公開。
- ポータルのActionsは**毎日 03:17 UTC** に各サイトを再取得。手動なら **Actions → Merge feeds and publish portal → Run workflow**。
- 新しいソース設定をcommitすると即時ビルドを実行。ブラウザ上で他ドメインのJSONを直接fetchしないため、CORS設定は不要。
- 取得に失敗したサイトについてはActions Cacheの**検証済み直近データ**にフォールバックします（キャッシュが未保存の場合は表示対象から外れます）。

## ローカル実行

```bash
python -m pip install -r requirements.txt
python scripts/build.py
python scripts/merge_feeds.py
python -m unittest discover -s scripts -p 'test_*.py' -v
python scripts/export_preview.py
python -m http.server 8000 --directory dist
```

未公開の間は `data/sources.json` が空なので、ポータルは案内画面だけ表示します。付属の `demo-preview.html` は4サイトの静的JSONを連携したサンプル表示です（データはデモ用で、定期取得結果ではありません）。

## 安全性

- 管理者が明示的に許可したHTTPSホストのみ取得。記事URLも許可ホストに限定。
- JSON検証は `scripts/merge_feeds.py` に実装。HTMLやMarkdownは受け付けず、Base64 WebPのみ許可。
- リダイレクトを拒否。1フィード4MB、記事100件、カバー画像150KB等の上限を設定。
- GitHub Actionsは読み取り・Pages公開権限を別ジョブに分離。
- GitHubの実公開・外部サイトとの連携は**各リポジトリをpushしてから要確認**です。
- 詳細は `docs/FEED_SPEC_V1_1.md` と `docs/SECURITY_HARDENING.md` を参照。
