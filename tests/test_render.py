import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from orbital_ink.cube import read_cube
from orbital_ink.cli import save_image
from orbital_ink.demo import write_demo
from orbital_ink.render import render, STYLE_NAMES

class CubeRenderTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name)/"example.cube"
        write_demo(self.path)
        self.cube = read_cube(self.path)

    def test_interpolation_and_polarity(self):
        sampled = self.cube.sample(np.array([[1,0,0],[-1,0,0],[0,0,0],[15,0,0]]))
        expected = .38 * np.exp(-.5)
        np.testing.assert_allclose(sampled,[expected,-expected,0,0],rtol=1e-6)
        result=np.asarray(render(self.cube,.08,"matte","blue-orange",128),int)
        left,right=np.hsplit(result,2)
        self.assertGreater((left[:,:,0]-left[:,:,2]).sum(),0)
        self.assertLess((right[:,:,0]-right[:,:,2]).sum(),0)

    def test_styles_and_export(self):
        buffers=[]
        for style in STYLE_NAMES:
            img=render(self.cube,.08,style,"sage",120)
            buffers.append(img.tobytes())
            out=Path(self.dir.name)/(style+".tiff")
            save_image(img,out)
            with Image.open(out) as tif:self.assertEqual(img.tobytes(),tif.tobytes())
        self.assertEqual(len(set(buffers)),len(STYLE_NAMES))

    def test_rotated_view(self):
        img=render(self.cube,.08,width=96,yaw=35,pitch=20)
        self.assertGreater(np.asarray(img).std(),10)

    def test_negative_atom_single_orbital(self):
        lines=self.path.read_text().splitlines()
        lines[2]="-1 -5 -5 -5"
        lines.insert(7,"1 17")
        self.path.write_text("\n".join(lines))
        np.testing.assert_array_equal(read_cube(self.path).values,self.cube.values)
        lines[7]="2 17 18"
        self.path.write_text("\n".join(lines))
        with self.assertRaises(ValueError):read_cube(self.path)

    def test_failures(self):
        with self.assertRaises(ValueError):render(self.cube,2,width=120)
        self.path.write_text(self.path.read_text()[:500])
        with self.assertRaises(ValueError):read_cube(self.path)
