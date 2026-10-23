#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""資料フォルダを tar.gz にまとめ、データマン（Mac mini）の公開鍵で封をする。
使い方: pack_and_seal.py <資料フォルダ> <公開鍵ファイルまたはURL> <出力 .bin>
形式: 送り手の一時公開鍵(32) + nonce(12) + AES-256-GCM暗号文（平文=gzip(tar.gz)、付随データ=b"boards"）
     鍵 = HKDF-SHA256(X25519共有秘密, salt=送り手公開鍵+受け手公開鍵, info=b"dataman-seal-v1")
     開けるのは toyota-geo-board/tools/dataman_open_sealed.py（Mac mini の秘密鍵）だけ
"""
import base64, gzip, io, os, sys, tarfile, urllib.request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

src, pub_src, out = sys.argv[1:4]
if pub_src.startswith("http"):
    with urllib.request.urlopen(urllib.request.Request(pub_src, headers={"Cache-Control": "no-cache"}), timeout=30) as r:
        pub_b64 = r.read().decode().strip()
else:
    pub_b64 = open(pub_src).read().strip()
rp = base64.b64decode(pub_b64)
if len(rp) != 32:
    sys.exit("公開鍵の形式が不正")
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as t:
    t.add(src, arcname="boards")
eph = X25519PrivateKey.generate()
eph_pub = eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
key = HKDF(algorithm=hashes.SHA256(), length=32, salt=eph_pub + rp, info=b"dataman-seal-v1").derive(eph.exchange(X25519PublicKey.from_public_bytes(rp)))
nonce = os.urandom(12)
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
open(out, "wb").write(eph_pub + nonce + AESGCM(key).encrypt(nonce, gzip.compress(buf.getvalue(), 9), b"boards"))
print(f"sealed {src} -> {out} ({os.path.getsize(out):,} bytes)")
