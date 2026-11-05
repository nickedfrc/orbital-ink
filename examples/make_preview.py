from pathlib import Path
import sys
from PIL import Image,ImageDraw,ImageFont
import tempfile
from orbital_ink.demo import write_demo
from orbital_ink.cube import read_cube
from orbital_ink.render import render
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'demo.cube';write_demo(path)
    cube=read_cube(path)
sheet=Image.new("RGB",(1200,275),"white");draw=ImageDraw.Draw(sheet)
for index,style in enumerate(["matte","cartoon","mesh","hybrid","contours"]):
    img=render(cube,.08,style,"blue-orange",240,22,8)
    sheet.paste(img,(index*240,0))
    draw.text((index*240+120,247),style,fill="#303742",anchor="mm",font=ImageFont.load_default(size=21))
sheet.save('examples/styles.png')
