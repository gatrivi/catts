"""Put chapterized books from data/books/inbox into the work queue."""
import json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INBOX=ROOT/'data/books/inbox'; WQ=ROOT/'data/workqueue'; Q=WQ/'queue.jsonl'

def slug(s): return re.sub(r'[^a-z0-9]+','_',s.lower()).strip('_')
def main():
    INBOX.mkdir(parents=True, exist_ok=True); WQ.mkdir(parents=True, exist_ok=True)
    rows=[]; existing=[]
    if Q.exists():
        for line in Q.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.lstrip().startswith('#'): existing.append(json.loads(line))
    ids={r.get('id') for r in existing}; added=0
    for book in sorted(p for p in INBOX.iterdir() if p.is_dir()):
        chapters=book/'chapters'
        files=sorted(chapters.glob('*.txt')) if chapters.is_dir() else []
        if not files: continue
        jid='folder_'+slug(book.name)
        if jid in ids: continue
        keep='KEEP_'+re.sub(r'[^A-Za-z0-9]+','_',book.name).strip('_')+'_Fish'
        row={'id':jid,'argv':['scripts/bake_book_fish_resume.py','--keep',keep,'--chapters-dir',str(chapters.relative_to(ROOT)),'--lang','en','--abort-on-first-fail'],'note':f'{book.name} ({len(files)} chapters)','stop_on_fail':True}
        rows.append(row); added+=1
    if rows:
        with Q.open('a',encoding='utf-8') as f:
            for row in rows: f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(f'added={added} queue={Q}')
    for row in rows: print(row['id'],row['note'])
if __name__=='__main__': main()
