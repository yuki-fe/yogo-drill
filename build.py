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
    cur = ' aria-current="page"'   # 今いる場所のメニューに下線
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
<meta property="og:image" content="{BASE}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#1d2a2e">
<link rel="icon" href="{rel}favicon.ico" sizes="48x48">
<link rel="icon" href="{rel}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{rel}apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap">
<link rel="stylesheet" href="{rel}assets/style.css">
{head_extras()}
{ld_html}
</head>
<body>
<a class="skip" href="#content">本文へ移動</a>
<div class="stripe" aria-hidden="true">{stripe}</div>
<header class="site-head">
  <div class="site-head-in">
    <a class="brand" href="{rel}index.html"><img src="{rel}favicon.svg" alt="" width="28" height="28">{escape(SITE)}</a>
    <nav class="site-nav" aria-label="メニュー">
      <a href="{rel}index.html#sites"{cur if name == "index.html" else ""}>サイト一覧</a>
      <a href="{rel}about.html"{cur if name == "about.html" else ""}>運営者情報</a>
    </nav>
  </div>
</header>
<div id="content"></div>
{body}
<footer class="site-foot">
  <nav aria-label="フッター">
    <a href="{rel}index.html#sites">サイト一覧</a>
    <a href="{rel}about.html">運営者情報・プライバシーポリシー</a>
    <a href="{escape(config['contact'])}">お問い合わせ</a>
    {"".join(f'<a href="{escape(x["url"])}" rel="noopener">{escape(x["name"])}</a>' for x in config.get("sns", []))}
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
            groups.append(f'<section class="group"><h3>{escape(g["name"])}</h3><div class="cards">{"".join(site_card(s) for s in cards)}</div></section>')
    public = [s for s in SITES if s["public"]]
    quick = "".join(f'<li><a href="{escape(s["url"])}" style="--cl:{s["color"]};--cd:{s["color_dark"]}">'
                    f'<img src="icons/{s["key"]}.svg" alt="" width="36" height="36"><span><b>{escape(s["name"])}</b>'
                    f'<small>{escape(s["exam"])}</small></span><em>{s["terms"]}語</em></a></li>' for s in public)
    how = [
        ("cards", "カード", "意味を読んで用語を思い出し、裏返して確かめる"),
        ("check", "4択クイズ", "同じ分野のまぎらわしい用語から選ぶ"),
        ("pencil", "書いて答える", "説明を読んで、用語を入力する"),
        ("keyboard", "用語タイピング", "用語と意味をキーボードで打って、手で覚える"),
        ("redo", "復習", "まちがえた用語だけを集めて解き直す"),
    ]
    how_html = "".join(f'<li>{icon(i)}<b>{t}</b><span>{d}</span></li>' for i, t, d in how)
    body = f"""
<main>
  <section class="hero" aria-labelledby="hero-h">
    <div class="hero-text">
      <p class="hero-eyebrow">資格の用語の単語帳・無料・登録なし</p>
      <h1 id="hero-h"><span>資格の用語を、</span><span>すきま時間に</span><span>覚える。</span></h1>
      <p class="hero-lead">試験に出てくる用語を、カード・4択クイズ・タイピングで覚える単語帳のサイトです。どのサイトも無料・登録不要で、スマホでもパソコンでも使えます。</p>
      <div class="hero-cta">
        <a class="btn primary" href="#sites">サイトを選ぶ</a>
        <a class="btn" href="#how">使い方を見る</a>
      </div>
      <ul class="hero-stats" aria-label="公開の数">
        <li><b>{n_public}</b><span>サイト</span></li>
        <li><b>{total:,}</b><span>用語</span></li>
        <li><b>0円</b><span>登録なし</span></li>
      </ul>
    </div>
    <aside class="quick" aria-labelledby="quick-h">
      <h2 id="quick-h">{n_public}つのサイト</h2>
      <ul>{quick}</ul>
    </aside>
  </section>

  <section class="block" id="sites" aria-labelledby="sites-h">
    <h2 id="sites-h" class="sec-title">サイトを選ぶ</h2>
    {"".join(groups)}
  </section>

  <section class="block" id="how" aria-labelledby="how-h">
    <h2 id="how-h" class="sec-title">どのサイトでも、同じ使い方</h2>
    <ul class="how">{how_html}</ul>
  </section>
  <section class="prose about-block">
    <h2 class="sec-title">このサイトについて</h2>
    <p>{escape(SITE)}は、個人で開発・運営している学習サイトの入り口です。用語の説明は、運営者が AI の支援を受けて作成し、内容を確認したうえで掲載しています。試験の範囲や日程などの最新の情報は、各試験の実施団体のサイトで確認してください。</p>
    <p>進み具合は、使っているブラウザの中にだけ保存されます。サイトごとに別々に記録されます。</p>
    <p>IT の知識やサイトの新しい機能は、{"・".join(f'<a href="{escape(x["url"])}" rel="noopener">{escape(x["name"])}</a>' for x in config.get("sns", []))}でも発信しています。</p>
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


# 線のアイコン（Lucide の形をもとに、そのまま SVG で入れる。各サイトの build.py と同じ）
ICONS = {
    "cards": '<rect x="3" y="6" width="14" height="14" rx="2"/><path d="M7 2h12a2 2 0 0 1 2 2v12"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "pencil": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "keyboard": '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
    "redo": '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
}


def icon(name):
    return f'<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


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
