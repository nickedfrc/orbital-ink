"""Optional Tk front end to the same renderer used by the CLI."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import ImageTk
from .cli import save_image
from .cube import read_cube
from .demo import write_demo
from .render import render,PALETTES,STYLE_NAMES

def launch():
    root=tk.Tk()
    root.title("Orbital Ink")
    root.columnconfigure(1,weight=1)
    root.rowconfigure(0,weight=1)
    form=ttk.Frame(root,padding=15)
    form.grid(row=0,column=0,sticky="ns")
    preview=ttk.Label(root,text="Open a Cube or try the example.",anchor="center",width=45)
    preview.grid(row=0,column=1,sticky="nsew",padx=12,pady=12)
    path=tk.StringVar()
    status=tk.StringVar(value="Ready")
    temp=tempfile.TemporaryDirectory()
    executor=ThreadPoolExecutor(max_workers=1)
    view={"image":None,"preview":None}
    def browse():
        name=filedialog.askopenfilename(filetypes=[("Cube files","*.cube *.cub"),("All files","*")])
        if name:path.set(name)
    def example():
        name=Path(temp.name)/"demo.cube"
        write_demo(name)
        path.set(str(name))
        run()
    ttk.Button(form,text="Open Cube…",command=browse).grid(row=0,column=0,sticky="ew")
    ttk.Button(form,text="Try example",command=example).grid(row=0,column=1,sticky="ew")
    ttk.Entry(form,textvariable=path,width=35).grid(row=1,column=0,columnspan=2,sticky="ew",pady=8)
    fields={}
    for row,(label,default,choices) in enumerate([
        ("Isovalue","0.05",None),("Style","matte",STYLE_NAMES),("Palette","sage",tuple(PALETTES)),
        ("Yaw (°)","0",None),("Pitch (°)","0",None),("Width (pixels)","720",None)],start=2):
        var=fields[label]=tk.StringVar(value=default)
        ttk.Label(form,text=label).grid(row=row,column=0,sticky="w",pady=3)
        widget=ttk.Combobox(form,textvariable=var,values=choices,state="readonly",width=14) if choices else ttk.Entry(form,textvariable=var,width=14)
        widget.grid(row=row,column=1,sticky="ew")
    def run():
        if not path.get():return browse()
        if go.instate(["disabled"]):return
        try:
            args=(float(fields["Isovalue"].get()),fields["Style"].get(),fields["Palette"].get(),int(fields["Width (pixels)"].get()),float(fields["Yaw (°)"].get()),float(fields["Pitch (°)"].get()))
        except ValueError:
            return messagebox.showerror("Orbital Ink","Enter numbers for isovalue, angle and width.")
        source=path.get()
        go.state(["disabled"]);save.state(["disabled"]);status.set("Rendering…")
        future=executor.submit(lambda:render(read_cube(source),*args))
        def finish():
            if not future.done():
                root.after(100,finish)
                return
            go.state(["!disabled"])
            try:
                image=future.result()
                shown=image.copy();shown.thumbnail((520,520))
                photo=ImageTk.PhotoImage(shown)
                preview.configure(image=photo,text="",width=0)
                view.update(image=image,preview=photo);save.state(["!disabled"])
                status.set(f"{Path(source).name}  ·  {image.width} px")
            except Exception as exc:
                status.set("Render failed");messagebox.showerror("Orbital Ink",str(exc))
        root.after(80,finish)
    def export():
        chosen=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png"),("TIFF","*.tiff")])
        if chosen:
            try:save_image(view["image"],chosen);status.set("Saved "+Path(chosen).name)
            except (OSError,ValueError) as exc:messagebox.showerror("Orbital Ink",str(exc))
    go=ttk.Button(form,text="Render",command=run);go.grid(row=8,column=0,pady=9,sticky="ew")
    save=ttk.Button(form,text="Save image…",command=export);save.grid(row=8,column=1,pady=9,sticky="ew");save.state(["disabled"])
    ttk.Label(form,textvariable=status,wraplength=240).grid(row=9,column=0,columnspan=2,sticky="w")
    try:root.mainloop()
    finally:executor.shutdown();temp.cleanup()
