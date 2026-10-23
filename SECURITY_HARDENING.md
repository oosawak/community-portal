# 運用時セキュリティチェックリスト

## GitHubリポジトリ

1. 2FA/パスキーを有効化。共同編集者の権限は最小限にする。
2. mainブランチにルールセットを作り、PRレビュー/Status checks を要求する（運用方針に応じて設定）。
3. Settings → Actions → Generalでワークフロー実行権限と既定の `GITHUB_TOKEN` を Read repository contents に制限する。
4. Actionsのパッケージ依存はSHA固定、またはGitHub推奨のワークフロー依存ロックファイルを導入し、定期的に更新・レビュー。
5. DeepL APIキーは `DEEPL_AUTH_KEY` Secretへ。公開HTMLやMarkdownには書かない。
6. Settings → Environments → `github-pages` にデプロイ許可ブランチ `main` を設定。
7. GitHub Actionsのキャッシュは信頼できるmainへのpushやスケジュール実行だけに使用する。外部からのPRコードに秘密情報を渡さない。

## 外部フィード

1. 新規サイトを登録する前に管理者・ドメイン・フィードURLを確認する。
2. `data/sources.json` の `id/url/homepage/allowed_hosts` を変更管理する。
3. 取得した外部本文HTMLを**表示しない**。外部記事は正規URLに送る。
4. 翻訳済みの文字列にもHTMLが混入しないようにエスケープする。
5. 大量のBase64画像は一覧JSONを巨大化させるため、小さいWebPだけを許可する。
6. 失敗時は最後に検証できたフィードを使うが、キャッシュの永続性や完全性を保証しない。必要ならバックアップを別保管する。

## リスクが完全には消えない箇所

- GitHubアカウント侵害、配信元サイト改ざん、翻訳APIの誤訳やHTML変形、ビルド依存パッケージの問題。
- URL許可とDNS事前検証は、HTTP通信の最終接続先をネットワーク層で拘束しないため、強いSSRF防御を保証しない。
- GitHub PagesではHTTPレスポンスヘッダーのCSP設定が難しいため、生成HTMLのCSPメタタグを使う。`frame-ancestors` など一部CSPディレクティブはメタ指定できない。
- 再現性の高い完全固定ビルドを目指す場合はrequirementsのハッシュ付きロック、依存の脆弱性検査、アーティファクト署名も検討する。

## 参考

- https://docs.github.com/en/actions/reference/security/secure-use
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html

GitHub Pages向けの公開成果物からはインラインスクリプトを含むオフラインプレビュー `dist/preview.html` を除外しています。ZIPのプレビューはローカル専用です。
