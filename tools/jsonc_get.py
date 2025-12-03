import json, sys, pathlib
if len(sys.argv) < 3:
    print("")
    raise SystemExit(0)
key = sys.argv[1]
cfg_path = sys.argv[2]
try:
    cfg_text = pathlib.Path(cfg_path).read_text(encoding='utf-8')
except Exception:
    print("")
    raise SystemExit(0)

def strip_line(line: str) -> str:
    in_str = False
    esc = False
    out = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"' and not esc:
            in_str = not in_str
        if not in_str and i + 1 < len(line) and line[i:i+2] == "//":
            break
        esc = (ch == '\\') and not esc
        out.append(ch)
        i += 1
    return ''.join(out)

clean = '\n'.join(strip_line(l) for l in cfg_text.splitlines())
try:
    data = json.loads(clean or '{}')
except Exception:
    data = {}
cur = data
for part in key.split('.'):
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    else:
        cur = None
        break
if isinstance(cur, bool):
    print('true' if cur else 'false')
elif isinstance(cur, (int, float)):
    print(cur)
elif isinstance(cur, str):
    print(cur)
else:
    print('')
