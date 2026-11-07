"""Leak check for the judge packets. Fails if any packet contains a task id, a state name, a generator label token,
or a key other than the five packet fields, or if a packet file name does not match its blind id.

The task and state names are read from the private blind_map.json at run time; they are not written here.
Usage: leak_check.py
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = {'blind_id', 'request', 'before_state', 'after_state', 'diff'}


def main():
    bmap = json.load(open(os.path.join(HERE, 'blind_map.json'), encoding='utf-8'))
    needles = set()
    for m in bmap.values():
        needles.add(m['task'].lower())
        needles.add(m['task'][:8].lower())
        needles.add(m['state'].lower())
    needles |= {'wrong_', 'correct_', 'generator', 'exp6', 'exp5', 'blind_map'}
    bad, n = [], 0
    for path in sorted(glob.glob(os.path.join(HERE, 'judge_packets', '*.json'))):
        n += 1
        text = open(path, encoding='utf-8').read()
        low = text.lower()
        packet = json.loads(text)
        if set(packet) != KEYS:
            bad.append((os.path.basename(path), 'keys', sorted(set(packet) ^ KEYS)))
        if os.path.splitext(os.path.basename(path))[0] != packet.get('blind_id'):
            bad.append((os.path.basename(path), 'file name != blind_id', None))
        for needle in needles:
            if needle and needle in low:
                bad.append((os.path.basename(path), 'contains', needle[:10]))
                break
    print(f'packets checked: {n}; leaks or key errors: {len(bad)}')
    for b in bad[:20]:
        print('  ', b)
    sys.exit(1 if bad or n != len(bmap) else 0)


if __name__ == '__main__':
    main()
