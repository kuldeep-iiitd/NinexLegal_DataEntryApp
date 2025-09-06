import pathlib
p=pathlib.Path(r'k:\legalapp\cases\views.py')
raw=p.read_bytes()
if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
    try:
        text=raw.decode('utf-16')
    except Exception as e:
        print('utf-16 decode failed', e)
        text=raw.decode('utf-8','ignore')
else:
    raw=raw.replace(b'\x00', b'')
    try:
        text=raw.decode('utf-8')
    except Exception:
        text=raw.decode('latin-1')
text=text.replace('\x00','')
lines=[ln.rstrip() for ln in text.splitlines()]
clean='\n'.join(lines)+'\n'
p.write_text(clean, encoding='utf-8')
print('Rewritten to UTF-8, chars:', len(clean))
