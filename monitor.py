import json, os, time, re, subprocess, urllib.request, urllib.parse, html, secrets
from html.parser import HTMLParser
from pathlib import Path

BASE='https://www.chromehearts.com'
ROOT=Path('.monitor_state')
ROOT.mkdir(parents=True,exist_ok=True)
STATE=ROOT/'state.json'; LOG=ROOT/'history.txt'; HOME_STATE=ROOT/'home_links.json'; TOPIC=ROOT/'phone_topic.txt'
TOPIC_NAME=os.environ['NTFY_TOPIC']
DEFAULT=['/baccarat','/scents','/boxers-leggings','/intimates','/socks']
class Parser(HTMLParser):
 def __init__(self): super().__init__(); self.products={}; self.categories=set(); self.home_products=set()
 def handle_starttag(self, tag, attrs):
  a=dict(attrs)
  if tag!='a': return
  href=urllib.parse.urljoin(BASE,a.get('href','')); u=urllib.parse.urlparse(href)
  if u.hostname not in ('www.chromehearts.com','chromehearts.com'): return
  classes=a.get('class','').split()
  if re.search(r'/[0-9][A-Za-z0-9_-]{5,}\.html$',u.path): self.home_products.add(u.path)
  if 'dropdown-link' in classes and u.path not in ('','/') and not u.path.endswith('.html'): self.categories.add(u.path)
  if a.get('aria-label','').lower().startswith('price-') and u.path.endswith('.html'):
   label=a.get('aria-label',''); m=re.match(r'price-([^–-]+)-(.*)',label,re.I)
   if m: self.products[u.path]={'name':html.unescape(m.group(2)).strip(),'price':m.group(1).strip(),'url':BASE+u.path}
def fetch(path):
 req=urllib.request.Request(BASE+path,headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36'})
 with urllib.request.urlopen(req,timeout=35) as resp:
  if resp.geturl().split('/')[2] not in ('www.chromehearts.com','chromehearts.com'): raise ValueError('unexpected redirect')
  p=Parser(); p.feed(resp.read().decode('utf-8',errors='replace')); return p
def note(title, message, link=None):
 print(title+': '+message,flush=True)
 try:
  headers={'Title':'Chrome Hearts monitor', 'Content-Type':'text/plain; charset=utf-8'}
  if link: headers['Click']=link
  req=urllib.request.Request('https://ntfy.sh/'+TOPIC_NAME, data=(title+'\n'+message).encode('utf-8'),headers=headers,method='POST')
  with urllib.request.urlopen(req,timeout=15) as resp: resp.read()
 except Exception as e: print('手机推送失败：'+str(e),flush=True)
 if os.uname().sysname=='Darwin':
  script='display notification '+json.dumps(message,ensure_ascii=False)+' with title '+json.dumps(title,ensure_ascii=False)+' sound name "Glass"'
  subprocess.run(['osascript','-e',script],capture_output=True)
def log(msg):
 s=time.strftime('%Y-%m-%d %H:%M:%S')+' '+msg
 print(s,flush=True)
 with LOG.open('a',encoding='utf-8') as f: f.write(s+'\n')
def check():
 old=json.loads(STATE.read_text()) if STATE.exists() else None
 home=fetch('/')
 home_current=sorted(home.home_products | home.categories)
 previous_home=json.loads(HOME_STATE.read_text()) if HOME_STATE.exists() else None
 home_new=[] if previous_home is None else sorted(set(home_current)-set(previous_home))
 if home_new:
  for path in home_new: log('首页新链接：'+BASE+path)
  note('Chrome Hearts 首页出现新链接','可能有新商品或分类：'+BASE+home_new[0],BASE+home_new[0])
 HOME_STATE.write_text(json.dumps(home_current))
 cats=sorted(set(DEFAULT)|home.categories|set((old or {}).get('categories',[])))
 found={}; failed=[]
 for cat in cats:
  try:
   p=fetch(cat)
   if not p.products: raise ValueError('没有识别到商品（页面可能变化、无商品或被限制）')
   found.update(p.products)
  except Exception as e: failed.append(cat+': '+str(e))
 if failed:
  log('部分页面读取失败，未更新记录：'+'; '.join(failed)); note('Chrome Hearts 检查失败','部分页面无法读取，请看终端或检查记录。'); return
 if not found: raise ValueError('没有识别到商品')
 new=[] if old is None else [x for k,x in found.items() if k not in old['products']]
 newcats=[] if old is None else sorted(set(cats)-set(old.get('categories',[])))
 STATE.write_text(json.dumps({'categories':cats,'products':found},ensure_ascii=False,indent=2),encoding='utf-8')
 if old is None: log('首次检查完成：记录了 '+str(len(found))+' 件现有商品。以后出现新商品才会提醒。'); note('Chrome Hearts 提醒已启动','首次检查完成，开始监测上新。')
 else:
  log('检查完成：'+str(len(found))+' 件商品；新商品 '+str(len(new))+' 件；新分类 '+str(len(newcats))+' 个。')
  for p in new: log('上新：'+p['name']+' '+p['price']+' '+p['url'])
  for c in newcats: log('新分类：'+BASE+c)
  if new or newcats: note('Chrome Hearts 可能上新了',str(len(new))+' 件新商品，'+str(len(newcats))+' 个新分类。'+('；'.join(p['name']+' '+p['price']+' '+p['url'] for p in new[:3]) if new else '请查看终端或记录。'), new[0]['url'] if new else BASE)
if __name__ == '__main__':
 try: check()
 except Exception as e:
  log('检查失败：'+str(e)); note('Chrome Hearts 检查失败','无法读取官网，请查看 GitHub Actions 运行记录。'); raise
