#!/usr/bin/env python3
"""plain.html → AES-GCM暗号化して index.html を生成。鍵素材は環境変数 ROOMY_GATE_KEY（"id:pw"）。"""
import os, base64, gzip, sys
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
km = os.environ.get('ROOMY_GATE_KEY')
if not km: sys.exit('ROOMY_GATE_KEY 未設定（"id:pw" 形式）')
doc = open('plain.html','rb').read()
salt, iv = os.urandom(16), os.urandom(12)
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200000).derive(km.encode())
ct = AESGCM(key).encrypt(iv, gzip.compress(doc, 9), None)
blob = base64.b64encode(salt+iv+ct).decode()
gate = open('tools/gate_template.html', encoding='utf-8').read()
open('index_new.html','w',encoding='utf-8').write(gate.replace('__BLOB__', blob))
print('encrypted -> index_new.html')
