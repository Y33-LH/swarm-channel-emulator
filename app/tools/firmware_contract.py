"""Current development firmware identity; historical records keep their own IDs."""
from pathlib import Path
import re
_main=(Path(__file__).resolve().parents[1]/'sw/main.c').read_text(encoding='utf-8')
VERSION=int(re.search(r'#define VERSION (0x[0-9a-fA-F]+)U',_main).group(1),16)
PROTOCOL=int(re.search(r'#define PROTOCOL (\d+)',_main).group(1))
VERSION_HEX=f'{VERSION:08x}'

BUILD=re.search(r'#define ARM_BUILD "([^"\n]+)"',_main).group(1)
