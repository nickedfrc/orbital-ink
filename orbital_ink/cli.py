import argparse
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from .cube import read_cube
from .demo import write_demo
from .render import PALETTES, STYLE_NAMES, render

def save_image(image,path,dpi=450):
    dest=Path(path)
    fmt={".png":"PNG",".tif":"TIFF",".tiff":"TIFF"}.get(dest.suffix.lower())
    if not fmt:
        raise ValueError("Choose a .png, .tif or .tiff output file.")
    opts={"dpi":(dpi,dpi)}
    if fmt=="TIFF":
        opts["compression"]="tiff_lzw"
    dest.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile(dir=dest.parent,delete=False) as tmp:
        temp=Path(tmp.name)
    try:
        image.save(temp,format=fmt,**opts)
        os.replace(temp,dest)
    finally:
        temp.unlink(missing_ok=True)

def main(argv=None):
    parser=argparse.ArgumentParser(description="Draw orbital isosurfaces from a Gaussian Cube.")
    subs=parser.add_subparsers(dest="command",required=True)
    demo=subs.add_parser("demo",help="Create a small synthetic example Cube.")
    demo.add_argument("output",type=Path)
    gui=subs.add_parser("gui",help="Open the graphical file picker and preview.")
    cmd=subs.add_parser("render",help="Render one orbital as PNG or TIFF.")
    cmd.add_argument("input",type=Path)
    cmd.add_argument("output",type=Path)
    cmd.add_argument("--iso",type=float,default=.05,help="Positive orbital-amplitude threshold (default 0.05).")
    cmd.add_argument("--style",choices=STYLE_NAMES,default="matte")
    cmd.add_argument("--palette",choices=PALETTES,default="sage")
    cmd.add_argument("--width",type=int,default=720,help="Square image width in pixels.")
    cmd.add_argument("--yaw",type=float,default=0,help="Y-axis rotation in degrees.")
    cmd.add_argument("--pitch",type=float,default=0,help="X-axis rotation after yaw, in degrees.")
    args=parser.parse_args(argv)
    try:
        if args.command=="gui":
            from .gui import launch
            launch()
        elif args.command=="demo":
            if args.output.exists():
                raise ValueError("Demo output already exists. Choose another file.")
            write_demo(args.output)
        else:
            image=render(read_cube(args.input),args.iso,args.style,args.palette,args.width,args.yaw,args.pitch)
            save_image(image,args.output)
            print(args.output)
    except (OSError,ValueError,ImportError,IndexError) as error:
        parser.exit(2,f"orbital-ink: {error}\n")
