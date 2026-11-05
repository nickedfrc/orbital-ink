"""Orthographic rendering of signed fields. All world coordinates are in bohr."""
import numpy as np
from PIL import Image, ImageFilter
from .cube import BOHR_ANGSTROM

PALETTES = {
    "sage": [(105,154,136), (148,134,174)],
    "blue-orange": [(70,122,166), (207,139,85)],
    "indigo-rose": [(69,93,142), (202,135,155)],
    "teal-wheat": [(38,121,115), (209,183,118)],
    "graphite": [(80,89,101), (200,202,206)],
}
STYLES = {"mesh": (.58,0,.96,1.9), "hybrid": (.50,.32,.74,1.45), "contours": (.42,.13,.93,2.05)}
STYLE_NAMES = ("matte", "cartoon", *STYLES)
atom_colors = {1:(226,230,233),6:(79,85,94),7:(65,100,165),8:(188,68,70),9:(91,167,136),16:(190,160,65),17:(85,150,90)}
radii = {1:.32,6:.46,7:.46,8:.48,9:.46,16:.55,17:.55}
cov = {1:.31,6:.76,7:.71,8:.66,9:.57,15:1.07,16:1.05,17:1.02}
def unit(v):
    return v/np.linalg.norm(v)

def lighting(n,base):
    # Broad diffuse light and a small amount of edge contrast give a matte finish.
    light=unit(np.array([-.36,.68,.64]))
    diffuse=np.clip(n@light,0,1)
    facing=np.clip(n[...,2],0,1)
    shade=.75+.16*diffuse+.09*facing
    return np.clip(np.asarray(base)*shade[...,None]+12*diffuse[...,None],0,255)
def _raycast(V, iso, axes, pos, syms, box, w, h, phase_colors, style):
    spacing = axes[0][1] - axes[0][0]
    xmin,xmax,ymin,ymax=box
    X,Y=np.meshgrid(np.linspace(xmin,xmax,w),np.linspace(ymax,ymin,h))
    depth=np.full((h,w),-1e4); mol=np.full((h,w,3),255.)
    def place(z,n,color,mask):
        keep=mask&(z>depth)
        depth[keep]=z[keep];mol[keep]=lighting(n[keep],color)
    for i,a in enumerate(pos):
        for j in range(i):
            b=pos[j]; length=np.linalg.norm(b-a)
            if length*BOHR_ANGSTROM>1.20*(cov.get(syms[i],.90)+cov.get(syms[j],.90)):continue
            v=(b-a)/length;vxy=v[0]**2+v[1]**2
            if vxy<1e-7:continue
            rx=X-a[0];ry=Y-a[1];proj=rx*v[0]+ry*v[1]
            # Ray intersection with a finite circular cylinder.
            disc=(proj*v[2])**2-vxy*(rx*rx+ry*ry-proj*proj-.16**2)
            rz=(proj*v[2]+np.sqrt(np.maximum(disc,0)))/vxy
            t=proj+rz*v[2]
            normal=np.stack([rx-t*v[0],ry-t*v[1],rz-t*v[2]],-1)/.16
            place(a[2]+rz,normal,(139,145,150),(disc>0)&(t>=0)&(t<=length))
    for a,sym in zip(pos,syms):
        rad=radii.get(sym,.5);dx=X-a[0];dy=Y-a[1];disc=rad**2-dx**2-dy**2
        dz=np.sqrt(np.maximum(disc,0));place(a[2]+dz,np.stack([dx,dy,dz],-1)/rad,atom_colors.get(sym,(130,135,145)),disc>0)
    # Bilinear interpolation in each grid plane; interpolate the front isovalue crossing along the ray.
    u=(X[0]-axes[0][0])/spacing;v=(Y[:,0]-axes[1][0])/spacing
    ix=np.clip(u.astype(int),0,len(axes[0])-2);iy=np.clip(np.floor(v).astype(int),0,len(axes[1])-2)
    fx=np.clip(u-ix,0,1);fy=np.clip(v-iy,0,1)[:,None]
    def interp(plane):
        tmp=plane[ix,:]*(1-fx[:,None])+plane[ix+1,:]*fx[:,None]
        return tmp[:,iy].T*(1-fy)+tmp[:,iy+1].T*fy
    draws=[]
    prev=interp(V[:,:,-1]); entry=[np.full((h,w),-1e4),np.full((h,w),-1e4)]
    for iz in range(V.shape[2]-2,-1,-1):
        cur=interp(V[:,:,iz])
        for k,sign in enumerate([1,-1]):
            cross=(cur*sign>=iso)&(prev*sign<iso)&(entry[k]<-999)
            if cross.any():
                dist=(iso*sign-cur[cross])/(prev[cross]-cur[cross])
                entry[k][cross]=axes[2][iz]+spacing*dist
        prev=cur
    gradients=np.gradient(V,spacing)
    normals=[]
    for side,(z,col) in enumerate(zip(entry,phase_colors)):
        mask=z>-999
        yy,xx=np.where(mask)
        coords=(z[mask]-axes[2][0])/spacing
        iz=np.clip(np.floor(coords).astype(int),0,V.shape[2]-2)
        fz=np.clip(coords-iz,0,1);normal=np.zeros((len(iz),3))
        for dx,wx in enumerate([1-fx[xx],fx[xx]]):
            for dy,wy in enumerate([1-fy[yy,0],fy[yy,0]]):
                for dz,wz in enumerate([1-fz,fz]):
                    inds=(ix[xx]+dx,iy[yy]+dy,iz+dz)
                    normal+=np.stack([g[inds] for g in gradients],-1)*(wx*wy*wz)[:,None]
        normal*=(-1 if side==0 else 1)/np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-15)
        normals.append(normal)
        shaded=np.zeros((*mask.shape,3));shaded[mask]=lighting(normal,col);draws.append(shaded)
    pixel=(xmax-xmin)/(w-1)
    if style in ("matte","cartoon"):
        out=mol.copy()
        for k in (0,1):
            other=1-k
            front=(entry[k]>=entry[other]) & (entry[k]>depth)
            behind=front & (entry[other]>depth)
            base=mol.copy()
            base[behind]=.73*draws[other][behind]+.27*mol[behind]
            if style=="cartoon":
                # Quantize directional lighting while retaining the exact isosurface shape.
                mask=entry[k]>-999
                diffuse=normals[k] @ unit(np.array([-.36,.68,.64]))
                band=np.select([diffuse>.68,diffuse>.18],[1.10,1.0],default=.85)
                draws[k][mask]=np.clip(np.asarray(phase_colors[k])*band[:,None]+3,0,255)
            out[front]=.74*draws[k][front]+.26*base[front]
            if style=="cartoon":
                core=np.asarray(Image.fromarray(front.astype('uint8')*255).filter(ImageFilter.MinFilter(3)))>0
                out[front & ~core]=np.asarray(phase_colors[k])*.48
        return Image.fromarray(np.clip(out,0,255).astype('uint8'))
    interval,fill,ink,thickness = STYLES[style]
    layers=[];alphas=[]
    for side,z in enumerate(entry):
        mask=z>-999; N=normals[side]
        points=np.column_stack((X[mask],Y[mask],z[mask]))
        directions=[unit(np.array(v)) for v in [(0.76,0.22,0.61),(-0.36,0.91,0.19)]]
        if style=='contours': directions=[unit(np.array([-.24,.78,.58]))]
        coverage=np.zeros(len(points));nz=np.maximum(N[:,2],.11)
        for direction in directions:
            signed=points@direction
            distance=np.abs((signed+.5*interval)%interval-.5*interval)
            rate=np.hypot(direction[0]-direction[2]*N[:,0]/nz,
                          direction[1]-direction[2]*N[:,1]/nz)
            px_dist=distance/(pixel*np.clip(rate,.10,5.0))
            coverage=np.maximum(coverage,np.clip(thickness/2+.5-px_dist,0,1))
        silhouette=np.asarray(Image.fromarray(mask.astype('uint8')*255).filter(ImageFilter.MinFilter(3)))==0
        coverage=np.maximum(coverage,.88*silhouette[mask])
        line=ink*coverage
        opacity=fill+(1-fill)*line
        al=np.zeros_like(z);al[mask]=opacity;alphas.append(al)
        rgb=np.zeros((*z.shape,3))
        # Premultiplied surface color with separate fill and line opacity.
        rgb[mask]=(line[:,None]*np.array(phase_colors[side])*.75+
                   ((1-line)*fill)[:,None]*draws[side][mask])
        layers.append(rgb)
    out=mol.copy()
    for side in (0,1):
        other=1-side
        front=(entry[side]>=entry[other])&(entry[side]>depth)
        behind=front&(entry[other]>depth)
        base=mol.copy()
        base[behind]=layers[other][behind]+(1-alphas[other][behind,None])*mol[behind]
        out[front]=layers[side][front]+(1-alphas[side][front,None])*base[front]
    return Image.fromarray(np.clip(out,0,255).astype("uint8"))

def render(cube, isovalue=.05, style="matte", palette="sage", width=720, yaw=0., pitch=0.):
    """Return an RGB PIL image. Yaw and pitch rotate the geometry in degrees."""
    if style not in STYLE_NAMES or palette not in PALETTES:
        raise ValueError("Unknown style or palette.")
    if not np.isfinite([isovalue,yaw,pitch]).all() or isovalue<=0 or not 96<=width<=2400:
        raise ValueError("Use a positive finite isovalue and a width between 96 and 2400 pixels.")
    if max(float(cube.values.max()),-float(cube.values.min()))<=isovalue:
        raise ValueError("No surface at this threshold. Try a smaller isovalue.")
    y,p=np.radians([yaw,pitch])
    rotate_y=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
    rotate_x=np.array([[1,0,0],[0,np.cos(p),-np.sin(p)],[0,np.sin(p),np.cos(p)]])
    transform=rotate_x @ rotate_y
    pos=cube.positions @ transform.T
    diagonal=np.diag(cube.steps)
    if yaw==0 and pitch==0 and diagonal[0]>0 and np.allclose(cube.steps,np.eye(3)*diagonal[0]):
        axes=[cube.origin[i]+np.arange(n)*diagonal[0] for i,n in enumerate(cube.values.shape)]
        values=cube.values
    else:
        corners=np.array(list(np.ndindex(2,2,2)))*(np.array(cube.values.shape)-1)
        corners=(corners @ cube.steps + cube.origin) @ transform.T
        step=max(np.linalg.svd(cube.steps,compute_uv=False).min(),np.ptp(corners,axis=0).max()/230)
        axes=[np.arange(lo-step,hi+2*step,step) for lo,hi in zip(corners.min(0),corners.max(0))]
        values=np.empty(tuple(map(len,axes)),np.float32)
        for i,z in enumerate(axes[2]):
            points=np.stack(np.meshgrid(axes[0],axes[1],[z],indexing="ij"),axis=-1).reshape(-1,3)
            values[:,:,i]=cube.sample(points @ transform).reshape(values.shape[:2])
    occupied=np.where(np.any(np.abs(values)>=isovalue,axis=2))
    if not occupied[0].size:
        raise ValueError("No visible surface after view interpolation. Reduce the isovalue.")
    bounds=[]
    for i,idx in enumerate(occupied):
        extent=axes[i][[idx.min(),idx.max()]]
        if len(pos):extent=np.r_[extent,pos[:,i]]
        bounds.append([extent.min()-.85,extent.max()+.85])
    (xmin,xmax),(ymin,ymax)=bounds
    span=max(xmax-xmin,ymax-ymin)*1.03
    cx=(xmin+xmax)/2
    cy=(ymin+ymax)/2
    box=(cx-span/2,cx+span/2,cy-span/2,cy+span/2)
    return _raycast(values,isovalue,axes,pos,cube.elements,box,width,width,PALETTES[palette],style)
