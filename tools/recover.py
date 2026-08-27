#!/usr/bin/env python3
"""デプロイ済み index.html を復号し、roomy.html（骨格）＋ js_*.js 7分割に展開。鍵素材は ROOMY_GATE_KEY。"""
import re, base64, gzip, os, sys
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
km = os.environ.get('ROOMY_GATE_KEY')
if not km: sys.exit('ROOMY_GATE_KEY 未設定')
html = open('index.html', encoding='utf-8').read()
blob = base64.b64decode(re.search(r'const BLOB="([^"]+)"', html).group(1))
salt, iv, ct = blob[:16], blob[16:28], blob[28:]
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200000).derive(km.encode())
doc = gzip.decompress(AESGCM(key).decrypt(iv, ct, None)).decode('utf-8')
lines = doc.split('\n')
markers = [(i, m.group(1)) for i, ln in enumerate(lines) if (m := re.match(r'/\* ===== (js_\w+\.js) ===== \*/', ln))]
boot_i = next(i for i, ln in enumerate(lines) if ln.strip() == 'boot();')
open('roomy.html','w',encoding='utf-8').write('\n'.join(lines[:markers[0][0]]) + '\n/*JS*/\n' + '\n'.join(lines[boot_i:]))
bounds = [x[0] for x in markers] + [boot_i]
for k, (start, name) in enumerate(markers):
    open(name, 'w', encoding='utf-8').write('\n'.join(lines[start:bounds[k+1]]))
# 検証
parts = ['js_data.js','js_core.js','js_render1.js','js_render2.js','js_render3.js','js_render4.js','js_render5.js','js_render6.js']
sk = open('roomy.html', encoding='utf-8').read(); h, t = sk.split('/*JS*/\n')
assert h + '\n'.join(open(p, encoding='utf-8').read() for p in parts) + '\n' + t == doc
print('recovered 7 files + skeleton (lossless)')
