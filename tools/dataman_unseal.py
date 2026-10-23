#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ID/PWゲート付きボードを、Actions上でだけ復号し、受け取り手の公開鍵で封をして sealed/ に置く。

- 鍵素材（"id:pw"）は GitHub Secrets（環境変数 GK）にだけある。ログにもファイルにも出さない
- 復号した平文は、受け取り手の X25519 公開鍵（tools/dataman_recipient.pub, base64）で封をしてから書く。
  封を開けられるのは、対応する秘密鍵を持つ受け取り手だけ。公開リポジトリに置いても中身は読めない
- 形式: sealed/<name>.bin = 送り手の一時公開鍵(32) + nonce(12) + AES-256-GCM暗号文（平文はgzip）
  鍵 = HKDF-SHA256(X25519共有秘密, salt=送り手公開鍵+受け手公開鍵, info=b"dataman-seal-v1")
- 失敗したボードは名前と理由だけを出す（0件扱いにしない）
"""
import base64, gzip, json, os, re, sys, urllib.request
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

PAGES = {
    "roomy_aio":     "https://ketrketr2.github.io/roomy-aio/",
    "roomy_command": "https://ketrketr2.github.io/roomy-command/",
    "car_signal":    "https://ketrketr2.github.io/toyota-car-board/signal.html",
    "car_deepdive":  "https://ketrketr2.github.io/toyota-car-board/",
    "ucar_signal":   "https://ketrketr2.github.io/toyota-ucar-board/",
    "ga4_command":   "https://ketrketr2.github.io/toyota-ga-board/",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dataman-unseal/1", "Cache-Control": "no-cache"})
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


def decrypt(html, km):
    iters, salt, iv, ct = parse_gate(html)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters).derive(km.encode())
    return gzip.decompress(AESGCM(key).decrypt(iv, ct, None)), iters


def seal(plain: bytes, recipient_pub: bytes, name: str) -> bytes:
    eph = X25519PrivateKey.generate()
    eph_pub = eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    shared = eph.exchange(X25519PublicKey.from_public_bytes(recipient_pub))
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=eph_pub + recipient_pub, info=b"dataman-seal-v1").derive(shared)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, gzip.compress(plain, 9), name.encode())
    return eph_pub + nonce + ct


def main():
    km = os.environ.get("GK", "")
    if not km:
        sys.exit("GK（鍵素材）が未設定")
    rp = base64.b64decode(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataman_recipient.pub")).read().strip())
    out = os.environ.get("SEALED_DIR", "sealed")
    os.makedirs(out, exist_ok=True)
    report = {}
    for name, url in PAGES.items():
        try:
            html = fetch(url)
            plain, iters = decrypt(html, km)
            open(os.path.join(out, f"{name}.bin"), "wb").write(seal(plain, rp, name))
            report[name] = {"ok": True, "plain_bytes": len(plain), "iter": iters}
            print(f"OK   {name}: {len(plain):,} bytes (iter {iters})")
        except Exception as e:  # noqa: BLE001
            report[name] = {"ok": False, "error": type(e).__name__}
            print(f"FAIL {name}: {type(e).__name__}")
    json.dump(report, open(os.path.join(out, "report.json"), "w"), ensure_ascii=False, indent=1)
    return 0 if any(v["ok"] for v in report.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
