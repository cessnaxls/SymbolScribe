import sys,io,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import analyze,score_xml,make_mxl,make_pdf,render_upload
from PIL import Image,ImageDraw
from xml.etree import ElementTree as ET

def test_exports():
    events=[{'label':'breve','pitch':'C4','beat':0,'staff':0,'measure':1,'page':0,'id':'n1'}, {'label':'long','pitch':'G4','beat':8,'staff':0,'measure':1,'page':0,'id':'n2'}]
    xml=score_xml(events,'test')
    root=ET.fromstring(xml)
    assert [n.text for n in root.findall('.//type')]==['breve','long']
    mxl=make_mxl(xml)
    with zipfile.ZipFile(io.BytesIO(mxl)) as z:
        assert z.read('mimetype')==b'application/vnd.recordare.musicxml'
        assert ET.fromstring(z.read('score.musicxml')).find('.//movement-title').text=='test'
    pdf=make_pdf(events,'test')
    assert pdf.startswith(b'%PDF')
    print('PASS: note value MusicXML, valid MXL and PDF output')

def test_image():
    im=Image.new('RGB',(800,240),'white');d=ImageDraw.Draw(im)
    for y in (45,60,75,90,105):d.line((30,y,760,y),fill='black',width=2)
    a=analyze(im);assert a['width']==800;assert len(a['staves'])>=1
    f=io.BytesIO();im.save(f,format='PNG');assert len(render_upload(f.getvalue(),'test.png'))==1
    print('PASS: image input, detected staff coordinates')

def test_complete_glyphs():
    im=Image.new('RGB',(900,270),'white');d=ImageDraw.Draw(im)
    for y in (70,82,94,106,118):d.line((30,y,870,y),fill='black',width=1)
    for x in (130,230):
        d.ellipse((x,88,x+16,98),outline='black',width=2)
        d.line((x+15,92,x+15,57),fill='black',width=2)
    d.line((350,68,350,120),fill='black',width=2)
    result=analyze(im)
    for x in (130,230):
        found=[c for c in result['candidates'] if c['box'][0]<=x<=c['box'][0]+c['box'][2] and c['box'][1]<=58 and c['box'][1]+c['box'][3]>=98]
        assert len(found)==1, f'Expected one complete notehead+stem for x={x}, got {found}'
    assert any(c['stage']=='barlines' for c in result['candidates'])
    print('PASS: complete stemmed glyph candidates and barline pass')

if __name__=='__main__':
    test_exports();test_image();test_complete_glyphs()

def test_no_staff_fragments():
    im=Image.new('RGB',(1000,280),'white');d=ImageDraw.Draw(im)
    for y in (85,100,115,130,145):d.line((20,y,980,y),fill='black',width=2)
    result=analyze(im)
    assert len(result['staves'])==1
    # A completely empty ruled staff should not generate a box for every line.
    assert len(result['candidates'])<=3, result['candidates']
    print('PASS: empty staff not mistaken for multiple musical glyphs')
