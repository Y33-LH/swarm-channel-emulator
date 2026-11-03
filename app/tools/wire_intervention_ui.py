from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/'start.ps1';s=p.read_text('utf-8-sig').replace('HttpPort=8880','HttpPort=8881').replace('$url/#link','$url/#causal');p.write_text(s,encoding='utf-8-sig')
p=r/'ui/index.html';s=p.read_text()
s=s.replace('</head>','<link rel="stylesheet" href="network-intervention.css"></head>')
s=s.replace('</body>','<script src="network-intervention.js"></script></body>')
p.write_text(s,encoding='utf-8')
print('Workflow is default home mode')
