"""Conservative evidence-first staff/symbol proposals and notation exports."""
import io, math, zipfile, html, re
from collections import defaultdict
import numpy as np
import cv2
import fitz
from PIL import Image
from xml.etree import ElementTree as ET
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

LABELS={'quarter','eighth','16th','32nd','half','whole','breve','long','rest-quarter','rest-half','rest-whole','rest-eighth','sharp','flat','natural','clef-g','clef-f','clef-c','barline','dot','tie','other','text-letter'}
NOTE_DUR={'quarter':1,'eighth':0.5,'16th':0.25,'32nd':0.125,'half':2,'whole':4,'breve':8,'long':16}
REST_DUR={'rest-quarter':1,'rest-half':2,'rest-whole':4,'rest-eighth':0.5}

def render_upload(data, name):
    ext=name.lower().rsplit('.',1)[-1]
    if ext=='pdf':
        document=fitz.open(stream=data,filetype='pdf')
        if len(document)>12: raise ValueError('Maximum 12 PDF pages per upload')
        images=[]
        for page in document:
            pix=page.get_pixmap(matrix=fitz.Matrix(1.3,1.3),alpha=False)
            images.append(Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB'))
        return images
    if ext not in ('png','jpg','jpeg','webp','tif','tiff'): raise ValueError('Unsupported file type')
    image=Image.open(io.BytesIO(data)).convert('RGB')
    if image.width*image.height>35_000_000: raise ValueError('Image resolution too large')
    return [image]

def analyze(image):
    """Propose complete local glyphs, never isolated pieces of staff rules.

    These are conservative *review candidates*, not automatic music readings.
    A missed symbol can always be boxed manually in the browser.
    """
    gray=np.array(image.convert('L'))
    h,w=gray.shape
    bw=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    horizontal=cv2.morphologyEx(bw,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(18,w//32),1)))
    row_strength=np.count_nonzero(horizontal,axis=1)
    runs=[]
    for y in np.flatnonzero(row_strength>max(30,w*.13)):
        if not runs or y>runs[-1][-1]+1:runs.append([int(y)])
        else:runs[-1].append(int(y))
    mid=[int(np.median(run)) for run in runs]
    staves=[];i=0
    while i+4<len(mid):
        group=mid[i:i+5];d=np.diff(group)
        if min(d)>=5 and max(d)<=48 and max(d)-min(d)<=max(3,np.median(d)*.32):
            staves.append({'lines':group,'spacing':float(np.median(d))});i+=5
        else:i+=1
    spacing0=float(np.median([s['spacing'] for s in staves])) if staves else 12.
    # Split staff lines ONLY where long horizontal runs are present. Short vertical
    # stems and letter strokes remain; reconnect narrow interruptions below.
    removed=cv2.subtract(bw,horizontal)
    k=max(3,min(5,int(round(spacing0*.22))|1))
    joined=cv2.morphologyEx(removed,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(k,k)))
    count,_,stats,_=cv2.connectedComponentsWithStats(joined)
    components=[]
    for j in range(1,count):
        x,y,ww,hh,area=map(int,stats[j]);cx=x+ww/2;cy=y+hh/2
        if area<max(5,spacing0*.26) or ww<2 or hh<2:continue
        if ww>max(65,spacing0*6) or hh>max(85,spacing0*9):continue
        # Residual horizontal / vertical hairlines are never stand-alone glyphs.
        if ww>spacing0*1.35 and hh<max(3,spacing0*.28):continue
        if hh>spacing0*2.7 and ww<max(2,spacing0*.18):continue
        idx=-1
        if staves:
            offsets=[max(0,s['lines'][0]-cy,cy-s['lines'][-1]) for s in staves]
            closest=int(np.argmin(offsets))
            if offsets[closest]<=staves[closest]['spacing']*3.4:idx=closest
        components.append((x,y,x+ww,y+hh,area,idx))
    # Recombine pieces in *local* glyph-scale neighborhoods. Two noteheads at
    # separate horizontal positions may never be merged into a chord by proximity.
    # Text is not joined into a full title: one printed character is one glyph.
    groups=[]
    for comp in sorted(components,key=lambda c:(c[5],c[0],c[1])):
        x1,y1,x2,y2,area,staff=comp
        assigned=None;best=1e9
        for group in groups:
            if group['staff']!=staff:continue
            gx1,gy1,gx2,gy2=group['bounds']
            dx=max(0,gx1-x2,x1-gx2);dy=max(0,gy1-y2,y1-gy2)
            horizontal_overlap=max(0,min(gx2,x2)-max(gx1,x1))
            # Prefer vertically separated pieces sharing the same x (i-dot,
            # separated glyph strokes); permit very small cuts through staves.
            if dx>spacing0*.16 or dy>spacing0*.36:continue
            if not (horizontal_overlap>0 or dx<=spacing0*.08):continue
            xx1=min(gx1,x1); yy1=min(gy1,y1);xx2=max(gx2,x2);yy2=max(gy2,y2)
            if xx2-xx1>spacing0*3.1 or yy2-yy1>spacing0*6.5:continue
            d=dx+dy
            if d<best:best=d;assigned=group
        if assigned is None:groups.append({'bounds':[x1,y1,x2,y2],'staff':staff,'ink':area,'fragments':1})
        else:
            old=assigned['bounds'];assigned['bounds']=[min(old[0],x1),min(old[1],y1),max(old[2],x2),max(old[3],y2)]
            assigned['ink']+=area;assigned['fragments']+=1
    proposals=[]
    for group in groups:
        x,y,x2,y2=group['bounds'];ww=x2-x;hh=y2-y;idx=group['staff']
        spacing=staves[idx]['spacing'] if idx>=0 else spacing0
        if group['ink']<max(7,spacing*.40):continue
        if ww>spacing*1.35 and hh<spacing*.4:continue
        if hh>spacing*3.2 and ww<spacing*.23:continue
        # Limit candidate proposal to plausible symbol sizes. Small pieces of
        # staff ruling should not be presented as a separate training symbol.
        if idx>=0:
            if ww<spacing*.28 or hh<spacing*.35:continue
            if ww<spacing*.60 and hh<spacing*.60 and group['ink']<spacing*1.2:continue
            if hh>=spacing*2.7 and ww<=spacing*.55:stage='barlines'
            elif ww>=spacing*1.55 and hh<=spacing*.73:stage='rests'
            elif ww<=spacing*2.9 and hh<=spacing*5.8:stage='noteheads'
            else:stage='rests'
        else:
            # The five-pass letter review only needs plausible text character
            # shapes, not every isolated dot or scanning artifact.
            if not (spacing*.42<=ww<=spacing*2.7 and spacing*.62<=hh<=spacing*3.9):continue
            stage='letters'
        pad=max(3,int(spacing*.25))
        proposals.append({'box':[max(0,x-pad),max(0,y-pad),min(w,x2+pad)-max(0,x-pad),min(h,y2+pad)-max(0,y-pad)],'staff':idx,'stage':stage,'status':'unreviewed','fragments':group['fragments']})
    # Detect actual barlines from the ORIGINAL picture, not from disconnected
    # pieces. Keep only strokes that cross almost the whole five-line staff.
    vertical=cv2.morphologyEx(bw,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(13,int(spacing0*3.25)))))
    vn,_,vs,_=cv2.connectedComponentsWithStats(vertical)
    for j in range(1,vn):
        x,y,ww,hh,area=map(int,vs[j])
        if ww>max(5,spacing0*.4):continue
        for idx,staff in enumerate(staves):
            top,bottom=staff['lines'][0],staff['lines'][-1]
            if y>top+staff['spacing']*.35 or y+hh<bottom-staff['spacing']*.35:continue
            box=[max(0,x-3),max(0,top-3),min(w,x+ww+3)-max(0,x-3),bottom-top+6]
            proposals.append({'box':box,'staff':idx,'stage':'barlines','status':'unreviewed','fragments':1})
    # De-duplicate nested candidates, particularly staff-line crossings. A
    # proper barline takes precedence over a vertical fragment at its x location.
    def iou(a,b):
        x=max(a[0],b[0]);y=max(a[1],b[1]);xx=min(a[0]+a[2],b[0]+b[2]);yy=min(a[1]+a[3],b[1]+b[3])
        inter=max(0,xx-x)*max(0,yy-y)
        return inter/(a[2]*a[3]+b[2]*b[3]-inter+1e-9)
    proposals.sort(key=lambda c:(c['stage']!='barlines',-(c['box'][2]*c['box'][3])))
    kept=[]
    for proposal in proposals:
        if any(p['staff']==proposal['staff'] and (iou(p['box'],proposal['box'])>.40 or
               (proposal['stage']=='barlines' and p['stage']=='barlines' and abs(p['box'][0]-proposal['box'][0])<spacing0*.35)) for p in kept):continue
        kept.append(proposal)
    kept.sort(key=lambda c:(c['staff']<0,c['box'][1],c['box'][0]))
    for i,c in enumerate(kept):c['id']=f'c{i}'
    return {'width':w,'height':h,'staves':staves,'candidates':kept[:1100],
       'warning':'Only full-sized candidate glyphs are suggested. Some may be missed; use Draw missing symbol and proofread every staff.'}

def verify(events):
    if not isinstance(events,list) or len(events)>10000:raise ValueError('Invalid symbol event list')
    out=[]
    for index,e in enumerate(events):
        if e.get('decision')=='ignore' or e.get('label')=='text-letter': continue
        label=e.get('label')
        if label not in LABELS:raise ValueError(f'Symbol {index+1} needs a valid label')
        if label=='other':raise ValueError(f'Symbol {index+1} remains unresolved')
        page=int(e.get('page',0));staff=int(e.get('staff',0));measure=int(e.get('measure',1))
        if page<0 or staff<0 or measure<1 or measure>9999: raise ValueError(f'Invalid location for symbol {index+1}')
        if label in NOTE_DUR:
            pitch=str(e.get('pitch','')).strip().upper()
            if not re.fullmatch(r'[A-G](?:#|B)?[0-8]',pitch):raise ValueError(f'Pitch missing/invalid for note {index+1}')
        else:pitch=None
        beat=float(e.get('beat',0))
        if not math.isfinite(beat) or beat<0 or beat>256:raise ValueError(f'Invalid beat for symbol {index+1}')
        out.append(dict(e,page=page,staff=staff,measure=measure,beat=beat,label=label,pitch=pitch))
    return out

def score_xml(events, title='Transcribed score'):
    accepted=verify(events)
    parts=sorted(set((e['page'],e['staff']) for e in accepted if e['label'] in NOTE_DUR or e['label'] in REST_DUR))
    if not parts:raise ValueError('No labeled notes or rests to export')
    root=ET.Element('score-partwise',version='4.0')
    ET.SubElement(root,'work');ET.SubElement(root,'movement-title').text=title
    plist=ET.SubElement(root,'part-list')
    # staff identity is preserved by order on each page; future pages map to same staff index
    staves=sorted(set(s for _,s in parts))
    for staff in staves:
        sp=ET.SubElement(plist,'score-part',id=f'P{staff+1}');ET.SubElement(sp,'part-name').text=f'Staff {staff+1}'
    for staff in staves:
        p=ET.SubElement(root,'part',id=f'P{staff+1}')
        measures=sorted(set((e['page'],e['measure']) for e in accepted if e['staff']==staff and e['label'] in NOTE_DUR|REST_DUR))
        for count,(page,mnum) in enumerate(measures,1):
            m=ET.SubElement(p,'measure',number=str(count))
            att=ET.SubElement(m,'attributes');ET.SubElement(att,'divisions').text='10080'
            # These values must be manually verified in visual review; default treble only for visualization.
            c=ET.SubElement(att,'clef');ET.SubElement(c,'sign').text='G';ET.SubElement(c,'line').text='2'
            sequence=sorted((e for e in accepted if e['staff']==staff and e['page']==page and e['measure']==mnum and e['label'] in NOTE_DUR|REST_DUR),key=lambda e:(e['beat'],e.get('id','')))
            cursor=0.0
            for e in sequence:
                if e['beat']>cursor+1e-6:
                    f=ET.SubElement(m,'forward');ET.SubElement(f,'duration').text=str(round((e['beat']-cursor)*10080));cursor=e['beat']
                elif e['beat']<cursor-1e-6:
                    b=ET.SubElement(m,'backup');ET.SubElement(b,'duration').text=str(round((cursor-e['beat'])*10080));cursor=e['beat']
                note=ET.SubElement(m,'note')
                if e['label'] in REST_DUR:
                    ET.SubElement(note,'rest');duration=REST_DUR[e['label']];kind=e['label'][5:]
                else:
                    pitch=e['pitch'];pn=ET.SubElement(note,'pitch');ET.SubElement(pn,'step').text=pitch[0]
                    if len(pitch)==3:ET.SubElement(pn,'alter').text='1' if pitch[1]=='#' else '-1'
                    ET.SubElement(pn,'octave').text=pitch[-1];duration=NOTE_DUR[e['label']];kind=e['label']
                ET.SubElement(note,'duration').text=str(int(duration*10080));ET.SubElement(note,'type').text=kind
                if e.get('id'):ET.SubElement(note,'notations').append(ET.Element('other-notation',type='single',text=str(e['id'])))
                cursor=e['beat']+duration
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def make_mxl(xml):
    f=io.BytesIO()
    with zipfile.ZipFile(f,'w') as z:
        z.writestr('mimetype','application/vnd.recordare.musicxml',compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml','<?xml version="1.0"?><container><rootfiles><rootfile full-path="score.musicxml" media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>')
        z.writestr('score.musicxml',xml)
    return f.getvalue()

def make_pdf(events,title='Transcribed score'):
    """Simple treble-clef staff engraving of *user-confirmed* events; not a full music engraver."""
    accepted=verify(events)
    data=defaultdict(list)
    for e in accepted:
        if e['label'] in NOTE_DUR or e['label'] in REST_DUR:
            data[(e['page'],e['staff'],e['measure'])].append(e)
    if not data:raise ValueError('No notes or rests')
    f=io.BytesIO();c=Canvas(f,pagesize=A4);W,H=A4;c.setTitle(title)
    y=H-85
    c.setFont('Helvetica-Bold',16);c.drawString(40,H-44,title[:75])
    scaleSteps={'C':0,'D':1,'E':2,'F':3,'G':4,'A':5,'B':6}
    def step_of(pitch):
        # E4 at bottom line (treble), every diatonic step is half a staff-space.
        return ((int(pitch[-1])-4)*7+scaleSteps[pitch[0]])-2
    for (page,staff,measure),items in sorted(data.items()):
        if y<115:
            c.showPage();y=H-85
        c.setFont('Helvetica',9)
        c.drawString(41,y+19,f'Page {page+1} · Staff {staff+1} · Measure {measure}')
        left=65;right=W-50;gap=9
        for line in range(5):c.line(left,y+line*gap,right,y+line*gap)
        c.setFont('Helvetica-Bold',22);c.drawString(left+5,y+3,'G')  # clef indicator (not authoritative)
        items=sorted(items,key=lambda e:(e['beat'],e.get('id','')))
        maxbeat=max([e['beat']+(NOTE_DUR.get(e['label']) or REST_DUR.get(e['label']) or 1) for e in items]+[4])
        for e in items:
            x=left+42+min(1,e['beat']/maxbeat)*(right-left-65)
            if e['label'] in REST_DUR:
                c.setFont('Helvetica',9);c.drawCentredString(x,y+19,'REST');continue
            step=step_of(e['pitch']);ny=y+step*gap/2
            # Ledger lines every second diatonic step beyond five staff lines.
            if step<0:
                for ledger in range(-2,step-1,-2):c.line(x-9,y+ledger*gap/2,x+9,y+ledger*gap/2)
            if step>8:
                for ledger in range(10,step+1,2):c.line(x-9,y+ledger*gap/2,x+9,y+ledger*gap/2)
            typ=e['label'];c.saveState()
            if len(e['pitch'])==3:
                c.setFont('Helvetica',12);c.drawRightString(x-11,ny-4,'#' if e['pitch'][1]=='#' else 'b')
            if typ in ('breve','long'):
                c.rect(x-7,ny-5,14,10,fill=0,stroke=1)
                if typ=='long':c.line(x+7,ny+5,x+7,ny-20)
            else:
                c.translate(x,ny);c.rotate(-17)
                path=c.beginPath();path.ellipse(-7,-4,7,4)
                c.drawPath(path,fill=int(typ not in ('whole','half')),stroke=1)
                c.rotate(17)
                if typ!='whole':
                    c.line(7,0,7,29)
                    if typ in ('eighth','16th','32nd'):
                        c.line(7,29,16,20)
            c.restoreState()
        y-=95
    c.setFont('Helvetica-Oblique',8)
    c.drawString(38,24,'Provisional treble-clef visualization. Verify clefs, timing, rests and accidentals against the source.')
    c.save();return f.getvalue()
