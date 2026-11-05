"""An analytic, p-shaped demonstration field in bohr. No research data required."""
from pathlib import Path
import numpy as np
def write_demo(path):
    axis=np.linspace(-5,5,51)
    x,y,z=np.meshgrid(axis,axis,axis,indexing="ij")
    field=.38*x*np.exp(-.50*(x*x+y*y+z*z))
    with Path(path).open("w",encoding="ascii") as handle:
        handle.write("Orbital Ink analytic demo\nf(x,y,z) = 0.38 x exp(-r^2 / 2); bohr\n")
        handle.write("1 -5 -5 -5\n51 .2 0 0\n51 0 .2 0\n51 0 0 .2\n6 6 0 0 0\n")
        for row in field.reshape(-1,len(axis)):
            for i in range(0,len(row),6):
                handle.write(" ".join(f"{v:.7e}" for v in row[i:i+6])+"\n")
