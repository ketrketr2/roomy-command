#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ID/PW付きボードを Actions 上でだけ復号し、平文HTMLを作業フォルダに書く（コミットしない）。
鍵素材（"id:pw"）は環境変数 GK（GitHub Secrets）からだけ読む。ログ・ファイルに鍵を出さない。
使い方: decrypt_boards.py <出力フォルダ>  → <出力>/<board>.html と <出力>/report.json
"""
import base64, gzip, json, os, re, sys, urllib.request
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PAGES = {
    "roomy_aio":     "https://ketrketr2.github.io/roomy-aio/",
    "roomy_command": "https://ketrketr2.github.io/roomy-command/",
    "car_signal":    "https://ketrketr2.github.io/toyota-car-board/signal.html",
    "car_deepdive":  "https://ketrketr2.github.io/toyota-car-board/",
    "ucar_signal":   "https://ketrketr2.github.io/toyota-ucar-board/",
    "ga4_command":   "https://ketrketr2.github.io/toyota-ga-board/",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dataman-digest/1", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def parse_gate(html):
    it = re.search(r"ITER\s*=\s*(\d+)", html) or re.search(r"iterations\s*:\s*(\d+)", html)
    iters = int(it.group(1)) if it else 200000
    m = re.search(r'const BLOB\s*=\s*"([A-Za-z0-9+/=]+)"', html)
    if m:
        raw = base64.b64decode(m.group(1))
        return iters, raw[:16], raw[16:28], raw[28:]
    def grab(name):
        mm = re.search(name + r"\s*=\s*Uint8Array\.from\(atob\('([A-Za-z0-9+/=]+)'\)", html)
        return base64.b64decode(mm.group(1)) if mm else None
    salt, iv, ct = grab("SALT"), grab("IV"), grab("CT")
    if salt and iv and ct:
        return iters, salt, iv, ct
    raise ValueError("ゲートの形式を読めない")


def main():
    out = sys.argv[1]
    km = os.environ.get("GK", "")
    if not km:
        sys.exit("GK（鍵素材）が未設定")
    os.makedirs(out, exist_ok=True)
    rep = {}
    for name, url in PAGES.items():
        try:
            iters, salt, iv, ct = parse_gate(fetch(url))
            key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters).derive(km.encode())
            plain = gzip.decompress(AESGCM(key).decrypt(iv, ct, None))
            open(os.path.join(out, name + ".html"), "wb").write(plain)
            rep[name] = {"ok": True, "bytes": len(plain)}
            print(f"OK   {name}: {len(plain):,} bytes")
        except Exception as e:  # noqa: BLE001
            rep[name] = {"ok": False, "error": type(e).__name__}
            print(f"FAIL {name}: {type(e).__name__}")
    json.dump(rep, open(os.path.join(out, "report.json"), "w"), ensure_ascii=False)
    return 0 if any(v["ok"] for v in rep.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
