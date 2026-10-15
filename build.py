"""用語ドリル（yogo-drill.com）の入り口のサイトを docs/ に書き出す。

使い方:  python build.py
入力:    sites.json（サイトの一覧と設定）、static/（CSS・アイコン）
出力:    docs/（GitHub Pages でそのまま公開できる）

サイトを公開したら、sites.json のそのサイトの "public" を true にして、もう一度実行する。
"""
import json
import shutil
import sys
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
OUT = ROOT / "docs"
config = json.loads((ROOT / "sites.json").read_text(encoding="utf-8"))
BASE = config["base_url"].rstrip("/")
SITE = config["site_name"]
SITES = config["sites"]
TODAY = date.today().isoformat()


def head_extras():
    ga = config.get("google_analytics_id")
    if not ga:
        return ""
    return (f'<script async src="https://www.googletagmanager.com/gtag/js?id={escape(ga)}"></script>'
            f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
            f"gtag('js',new Date());gtag('config','{escape(ga)}');</script>")


def page(name, title, desc, body, ld=None, noindex=False):
    rel = "/" if noindex else ""  # 404 はどの住所でも出るので、先頭の「/」から書く
    url = f"{BASE}/" if name == "index.html" else f"{BASE}/{name}"
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (ld or []))
    stripe = "".join(f'<i style="background:{s["color"]}"></i>' for s in SITES)
    html = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
{'<meta name="robots" content="noindex">' if noindex else f'<link rel="canonical" href="{escape(url)}">'}
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{escape(url)}">
<meta property="og:site_name" content="{escape(SITE)}">
<meta name="theme-color" content="#1d2a2e">
<link rel="icon" href="{rel}favicon.ico" sizes="48x48">
<link rel="icon" href="{rel}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{rel}apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;500;700&display=swap">
<link rel="stylesheet" href="{rel}assets/style.css">
{head_extras()}
{ld_html}
</head>
<body>
<div class="stripe" aria-hidden="true">{stripe}</div>
<header class="site-head">
  <a class="brand" href="{rel}index.html"><img src="{rel}favicon.svg" alt="" width="28" height="28">{escape(SITE)}</a>
  <nav aria-label="メニュー"><a href="{rel}index.html#sites">サイト一覧</a><a href="{rel}about.html">運営者情報</a></nav>
</header>
{body}
<footer class="site-foot">
  <nav aria-label="フッター">
    <a href="{rel}index.html#sites">サイト一覧</a>
    <a href="{rel}about.html">運営者情報・プライバシーポリシー</a>
    <a href="{escape(config['contact'])}">お問い合わせ</a>
  </nav>
  {"".join(f"<p>{escape(n)}</p>" for n in config.get("notes", []))}
  <p>© {date.today().year} {escape(config["operator"])}</p>
</footer>
</body>
</html>
"""
    (OUT / name).write_text(html, encoding="utf-8")


def site_card(s):
    style = f'--cl:{s["color"]};--cd:{s["color_dark"]}'
    points = "".join(f"<li>{escape(p)}</li>" for p in s["points"])
    head = f'<img src="icons/{s["key"]}.svg" alt="" width="44" height="44"><div><h3>{escape(s["name"])}</h3><p class="exam">{escape(s["exam"])}</p></div>'
    if s["public"]:
        foot = f'<span class="count"><b>{s["terms"]}</b>語</span><span class="go">サイトを開く →</span>'
        return (f'<a class="card" href="{escape(s["url"])}" style="{style}"><div class="card-head">{head}</div>'
                f'<p class="desc">{escape(s["desc"])}</p><ul class="points">{points}</ul><div class="card-foot">{foot}</div></a>')
    foot = f'<span class="count"><b>{s["terms"]}</b>語</span><span class="soon">準備中</span>'
    return (f'<div class="card is-soon" style="{style}"><div class="card-head">{head}</div>'
            f'<p class="desc">{escape(s["desc"])}</p><ul class="points">{points}</ul><div class="card-foot">{foot}</div></div>')


def build_index():
    n_public = sum(s["public"] for s in SITES)
    total = sum(s["terms"] for s in SITES if s["public"])
    groups = []
    for g in config["groups"]:
        cards = [s for s in SITES if s["group"] == g["key"]]
        cards.sort(key=lambda s: not s["public"])
        if cards:
            groups.append(f'<section class="group"><h2>{escape(g["name"])}</h2><div class="cards">{"".join(site_card(s) for s in cards)}</div></section>')
    body = f"""
<main>
  <section class="hero">
    <h1>{escape(SITE)}<small>{escape(config["tagline"])}</small></h1>
    <p>資格の試験に出てくる用語を、カードと4択クイズで覚える単語帳のサイトです。どのサイトも<b>無料・登録不要</b>で、スマホでもパソコンでも使えます。いま{n_public}つのサイトで、あわせて{total}語の用語を公開しています。</p>
    <ul class="features">
      <li><b>カード</b>意味を読んで用語を思い出し、裏返して確かめる</li>
      <li><b>4択クイズ</b>同じ分野のまぎらわしい用語から選ぶ</li>
      <li><b>書いて答える</b>説明を読んで、用語を入力する</li>
      <li><b>復習</b>まちがえた用語だけを集めて解き直す</li>
    </ul>
  </section>
  <div id="sites">{"".join(groups)}</div>
  <section class="prose">
    <h2>このサイトについて</h2>
    <p>{escape(SITE)}は、個人で開発・運営している学習サイトの入り口です。用語の説明は、運営者が AI の支援を受けて作成し、内容を確認したうえで掲載しています。試験の範囲や日程などの最新の情報は、各試験の実施団体のサイトで確認してください。</p>
    <p>進み具合は、使っているブラウザの中にだけ保存されます。サイトごとに別々に記録されます。</p>
  </section>
</main>
"""
    public = [s for s in SITES if s["public"]]
    ld = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": BASE + "/", "description": config["description"]},
        {"@context": "https://schema.org", "@type": "ItemList", "name": f"{SITE}のサイト一覧",
         "itemListElement": [{"@type": "ListItem", "position": i, "name": s["name"], "url": s["url"]} for i, s in enumerate(public, 1)]},
    ]
    page("index.html", f"{SITE}｜{config['tagline']}", config["description"], body, ld)


def build_about():
    contact = escape(config["contact"])
    ga = config.get("google_analytics_id")
    ga_text = ("<p>このサイトでは、利用状況を知るために Google アナリティクスを使っています。Google アナリティクスは Cookie を使って、"
               "個人を特定しない形でアクセスの情報を集めます。ブラウザの設定で Cookie を無効にすると、集めないようにできます。"
               "くわしくは Google のポリシーと規約をご覧ください。</p>") if ga else \
              "<p>このページ（入り口のサイト）では、アクセス解析や広告の仕組みを使っていません。</p>"
    body = f"""
<main class="prose">
  <h1>運営者情報・プライバシーポリシー</h1>
  <h2>運営者情報</h2>
  <table class="info">
    <tr><th>サイト名</th><td>{escape(SITE)}</td></tr>
    <tr><th>運営者</th><td>{escape(config["operator"])}</td></tr>
    <tr><th>開設日</th><td>{escape(config["established"])}</td></tr>
    <tr><th>お問い合わせ</th><td><a href="{contact}">お問い合わせフォーム</a></td></tr>
  </table>
  <h2>プライバシーポリシー</h2>
  {ga_text}
  <p>各学習サイトのアクセス解析・広告・学習の記録の扱いは、それぞれのサイトの「プライバシーポリシー・免責事項」に書いています。</p>
  <p>お問い合わせフォームでいただいた内容は、お返事と、サイトの改善のためだけに使います。</p>
  <h2>免責事項</h2>
  <p>掲載している内容は、できるかぎり正確になるよう努めていますが、正確さや最新であることを保証するものではありません。このサイトや各学習サイトの利用で生じた損害について、運営者は責任を負いかねます。</p>
  <h2>著作権</h2>
  <p>掲載している文章の著作権は運営者に帰属します。無断での転載はご遠慮ください。</p>
</main>
"""
    page("about.html", f"運営者情報・プライバシーポリシー｜{SITE}", f"{SITE}の運営者情報とプライバシーポリシーです。", body)


def build_404():
    body = """
<main class="prose">
  <h1>ページが見つかりません</h1>
  <p>お探しのページは、移動したか、なくなった可能性があります。<a href="/">サイトの一覧</a>から探してください。</p>
</main>
"""
    page("404.html", f"ページが見つかりません｜{SITE}", "ページが見つかりません。", body, noindex=True)


def build_meta():
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    urls = [f"{BASE}/", f"{BASE}/about.html"]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    host = urlparse(BASE).hostname
    if host and not host.endswith("github.io"):
        (OUT / "CNAME").write_text(host + "\n", encoding="utf-8")


def check():
    errors = []
    keys = {g["key"] for g in config["groups"]}
    for s in SITES:
        if s["group"] not in keys:
            errors.append(f'{s["name"]}: group "{s["group"]}" が groups にありません')
        if not (ROOT / "static" / "icons" / f'{s["key"]}.svg').exists():
            errors.append(f'{s["name"]}: static/icons/{s["key"]}.svg がありません')
    text = json.dumps(config, ensure_ascii=False)
    for w in ["公式", "必ず合格", "ここだけ"]:
        if w in text:
            errors.append(f"sites.json に「{w}」が入っています（使わない言葉）")
    return errors


def main():
    errors = check()
    if errors:
        print("\n".join("エラー: " + e for e in errors))
        sys.exit(1)
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    build_index()
    build_about()
    build_404()
    build_meta()
    n = sum(s["public"] for s in SITES)
    print(f"docs/ に書き出しました（サイト {len(SITES)} 件、うち公開中 {n} 件）")


if __name__ == "__main__":
    main()
