import io,base64,json
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,HTTPException
from fastapi.responses import HTMLResponse,Response
from fastapi.staticfiles import StaticFiles
from engine import render_upload,analyze,score_xml,make_mxl,make_pdf
from pydantic import BaseModel

app=FastAPI(title='SymbolScribe OMR')
app.mount('/static',StaticFiles(directory=str(Path(__file__).parent/'static')),name='static')

class Export(BaseModel):
    events:list
    title:str='Transcribed score'

@app.get('/',response_class=HTMLResponse)
def index():return (Path(__file__).parent/'static'/'index.html').read_text()

@app.post('/api/import')
async def import_files(files:list[UploadFile]=File(...)):
    if not files or len(files)>12:raise HTTPException(400,'Upload 1–12 image/PDF files')
    images=[]
    for file in files:
        data=await file.read()
        if len(data)>12_000_000:raise HTTPException(413,'Each file must be under 12 MB')
        try:images+=render_upload(data,file.filename or 'unknown')
        except Exception as e:raise HTTPException(400,str(e))
    if len(images)>12:raise HTTPException(400,'Maximum 12 pages/images in one job')
    pages=[]
    for page,image in enumerate(images):
        # shrink huge raster for practical browser review
        if image.width>1600 or image.height>2200:image.thumbnail((1600,2200))
        out=io.BytesIO();image.save(out,format='PNG')
        a=analyze(image)
        a.update({'page':page,'image':'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode('ascii')})
        pages.append(a)
    return {'pages':pages}

@app.post('/api/export/{kind}')
def export(kind:str,req:Export):
    try:
        if kind=='mxl':raw=make_mxl(score_xml(req.events,req.title));mime='application/vnd.recordare.musicxml';ext='mxl'
        elif kind=='musicxml':raw=score_xml(req.events,req.title);mime='application/xml';ext='musicxml'
        elif kind=='pdf':raw=make_pdf(req.events,req.title);mime='application/pdf';ext='pdf'
        else:raise HTTPException(404,'Unknown format')
    except ValueError as exc:raise HTTPException(422,str(exc))
    return Response(content=raw,media_type=mime,headers={'Content-Disposition':f'attachment; filename="transcription.{ext}"'})

@app.get('/health')
def health():return {'status':'ok'}
