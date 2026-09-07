from pathlib import Path
from html import escape
import xml.etree.ElementTree as ET
OUT=Path(__file__).parent
B='#0b1015'; WHITE='#f1f4f8'; MUTED='#9ba9b7'; BLUE='#7894ff'; GREEN='#86efac'; PURPLE='#b399ff'
parts=[]
def text(x,y,s,size=26,color=WHITE,weight=400,anchor='start'):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(s)}</text>')
def rect(x,y,w,h,stroke='#344152',fill='#121b26',r=18):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
def line(d,color=BLUE,arrow=False,dash=False):
    parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3"'+(' marker-end="url(#arrow)"' if arrow else '')+(' stroke-dasharray="8 8"' if dash else '')+'/>')
def start(num,title,sub):
    parts.clear()
    parts.extend(['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">','<style>text {font-family: "PingFang SC", "Microsoft YaHei", sans-serif;}</style>',f'<defs><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 H 0 V 40" fill="none" stroke="#ffffff" stroke-opacity="0.035"/></pattern><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{BLUE}"/></marker></defs>',f'<rect width="1600" height="900" fill="{B}"/>','<rect width="1600" height="900" fill="url(#grid)"/>'])
    text(72,76,'AGENT-FIRST SOFTWARE  /  '+num,19,MUTED,600)
    text(72,143,title,44,WHITE,600)
    text(72,191,sub,25,MUTED)
def footer(s):
    line('M 72 790 H 1528','#293440')
    text(72,843,s,27,GREEN,600)
def save(name):
    parts.append('</svg>')
    p=OUT/(name+'.svg');p.write_text('\n'.join(parts));ET.parse(p)

start('01','把核心能力放在服务层','人表达目标，Agent 组织请求，数据库服务负责可靠执行')
rect(72,280,330,400,BLUE)
text(108,339,'人 + Agent',32,WHITE,600)
text(108,389,'运营 · 增长 · 数据分析',23,MUTED)
for i,s in enumerate(['提出业务问题','理解数据语义','组织查询请求']): text(108,477+i*63,s,27)
rect(560,260,480,440,PURPLE,'#191625')
text(598,325,'Chat2DB 服务',34,WHITE,600)
text(598,370,'MCP / API',23,PURPLE)
for i,s in enumerate(['连接与表结构','身份与权限校验','查询执行与结果','访问记录与审计']):text(598,445+i*62,s,28)
rect(1198,280,330,400,'#3d886a','#111e1a')
text(1234,341,'数据库',32,WHITE,600)
for i,s in enumerate(['业务数据库','数仓 / 分析库','受控数据范围']):text(1234,454+i*66,s,27)
line('M 402 479 H 560',arrow=True);text(481,453,'请求',22,MUTED,anchor='middle')
line('M 1040 479 H 1198',arrow=True);text(1119,453,'执行',22,MUTED,anchor='middle')
footer('稳定的能力、清楚的边界，比完整复刻一个客户端更优先。')
save('service-layer')

start('02','权限在执行边界落实','模型提出请求，身份与授权决定请求能否执行')
for x,w,title,sub in [(72,280,'Agent 请求','携带所代表的用户身份'),(472,400,'服务端校验','身份 · 数据范围 · 操作类型'),(1080,448,'数据库执行','使用受限数据库凭证')]:
    rect(x,292,w,188,PURPLE if x==472 else BLUE)
    text(x+30,352,title,30,WHITE,600);text(x+30,408,sub,23,MUTED)
line('M 352 390 H 472',arrow=True)
line('M 872 390 H 1080',arrow=True);text(976,362,'授权通过',23,GREEN,anchor='middle')
rect(472,570,400,102,'#ad6070','#25171d');text(672,631,'越权请求：拒绝执行',27,'#f4a1af',600,'middle')
line('M 672 480 V 570',arrow=True);text(694,532,'校验失败',22,MUTED)
rect(1080,570,448,102,'#4c6559','#111e1a');text(1304,632,'记录访问与执行结果',27,GREEN,600,'middle')
line('M 1304 480 V 570',arrow=True)
text(72,731,'访问留痕覆盖允许与拒绝；权限变更、撤销也需要及时生效。',24,MUTED)
footer('应用层检查与数据库最小权限共同约束执行；LLM 不负责授予权限。')
save('permission-boundary')

start('03','一套稳定服务，多种轻量界面','默认壳子完成基本任务，自定义界面适配各自的工作方式')
for x,title,sub in [(72,'Agent 入口','提问 · 调用 · 获取结果'),(590,'默认管理页面','连接 · 授权 · 审计'),(1108,'用户自建工作台','分析 · 图表 · 团队流程')]:
    rect(x,268,420,228,BLUE)
    line(f'M {x} 312 H {x+420}','#344152')
    for dx in [24,42,60]:parts.append(f'<circle cx="{x+dx}" cy="290" r="4" fill="{MUTED}"/>')
    text(x+30,378,title,31,WHITE,600);text(x+30,432,sub,24,MUTED)
    line(f'M {x+210} 496 V 610',arrow=True)
rect(72,610,1456,134,PURPLE,'#191625')
text(108,665,'统一服务与治理',31,WHITE,600)
text(108,710,'身份认证     权限策略     业务规则     数据访问     操作审计',27,PURPLE)
footer('入口可以替换，所有请求都遵守同一套服务规则。')
save('replaceable-interfaces')
print('Generated 3 valid SVGs')
