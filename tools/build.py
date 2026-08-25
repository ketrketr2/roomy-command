#!/usr/bin/env python3
import sys
parts = ['js_data.js','js_core.js','js_render1.js','js_render2.js','js_render3.js','js_render4.js','js_render5.js']
sk = open('roomy.html', encoding='utf-8').read()
head, tail = sk.split('/*JS*/\n')
js = '\n'.join(open(p, encoding='utf-8').read() for p in parts)
open('plain.html','w',encoding='utf-8').write(head + js + '\n' + tail)
print('built plain.html', len(head+js+tail))
