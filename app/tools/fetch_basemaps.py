"""Small, reproducible offline imagery excerpts; never used as propagation data.

Source/license are taken from the saved service capability document. Coordinates
are WGS84 and use a local equirectangular approximation, not GCJ02/BD09 tiles.
"""
from pathlib import Path
import urllib.request,urllib.parse,math,json,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'ui/maps'
LAYER='s2cloudless-2024'
areas=[(1,'旷野',116.0,43.0),(2,'乡村',109.6,34.5),(3,'郊区',108.85,34.1),
       (4,'城市',108.95,34.26),(5,'山地',108.77,33.95),(6,'丘陵',109.4,36.4),(7,'高原',100.3,36.9)]
def main():
    cap=ET.parse(DEST/'wms_capabilities.xml')
    layer=next(x for x in cap.findall('.//Layer') if x.findtext('Name')==LAYER)
    assert 'creativecommons.org/licenses/by-nc-sa/4.0/' in layer.findtext('Abstract')
    manifest=dict(schema=1,source='https://maps.eox.at/',license='https://creativecommons.org/licenses/by-nc-sa/4.0/',
        attribution='EOxCloudless by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2024)',
        attribution_url='https://cloudless.eox.at/',map_only=True,
        note='历史卫星影像，仅作场景背景；没有将地形遮挡、建筑或影像像素输入信道模型。不是实时航拍或实时气象。',
        local_extent_m=[-3000,0,13000,10000],crs='WGS84 / local equirectangular approximation',areas=[])
    for env,name,lon,lat in areas:
        dx=8000/(111320*math.cos(math.radians(lat)));dy=5000/111320
        bbox=[lon-dx,lat-dy,lon+dx,lat+dy]
        params=dict(service='WMS',version='1.1.1',request='GetMap',layers=LAYER,styles='',srs='EPSG:4326',bbox=','.join(f'{v:.8f}' for v in bbox),width=1280,height=800,format='image/jpeg')
        url='https://tiles.maps.eox.at/wms?'+urllib.parse.urlencode(params);file=DEST/f'env_{env}.jpg'
        from PIL import Image,ImageStat
        valid=False
        if file.exists():
            with Image.open(file) as im:valid=im.size==(1280,800) and max(ImageStat.Stat(im).stddev)>3
        if not valid:
            req=urllib.request.Request(url,headers={'User-Agent':'Academic-Swarm-Channel-Demo/1.0'})
            with urllib.request.urlopen(req,timeout=45) as r:data=r.read()
            assert data[:2]==b'\xff\xd8',data[:200]
            file.write_bytes(data)
        with Image.open(file) as im:assert im.size==(1280,800) and max(ImageStat.Stat(im).stddev)>3, 'Empty imagery response'
        manifest['areas'].append(dict(environment=env,name=name,file=file.name,center_wgs84=[lon,lat],bbox_wgs84=bbox,url=url,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
        print('BASEMAP_SAVED',name,len(file.read_bytes()),flush=True)
        (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
