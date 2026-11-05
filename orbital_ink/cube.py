"""Read single-field Gaussian Cube files. Coordinates are stored in bohr."""
from dataclasses import dataclass
from pathlib import Path
import numpy as np

BOHR_ANGSTROM = 0.529177210903

@dataclass
class Cube:
    origin: np.ndarray
    steps: np.ndarray
    positions: np.ndarray
    elements: list[int]
    values: np.ndarray

    def sample(self, points):
        """Trilinear interpolation at world coordinates, zero outside the grid."""
        indices = (points - self.origin) @ self.inverse
        top = np.array(self.values.shape) - 1
        valid = np.all((indices >= 0) & (indices <= top), axis=1)
        indices = np.clip(indices, 0, top)
        lower = np.minimum(indices.astype(int), top - 1)
        frac = indices - lower
        result = np.zeros(len(points))
        for delta in np.ndindex(2, 2, 2):
            weights = np.prod(np.where(delta, frac, 1 - frac), axis=1)
            result += weights * self.values[tuple((lower + delta).T)]
        return np.where(valid, result, 0)

    def __post_init__(self):
        if abs(np.linalg.det(self.steps)) < 1e-12:
            raise ValueError("Grid vectors must be linearly independent.")
        self.inverse = np.linalg.inv(self.steps)

def read_cube(path):
    with Path(path).open(encoding="ascii", errors="replace") as handle:
        handle.readline()
        handle.readline()
        def tokens():
            return handle.readline().replace("D", "E").replace("d", "e").split()
        header = tokens()
        if len(header) < 4:
            raise ValueError("Incomplete Cube origin record.")
        nat = int(header[0])
        if len(header) > 4 and int(header[4]) != 1:
            raise ValueError("Choose a Cube containing a single scalar field.")
        origin = np.array(header[1:4], float)
        axes = [tokens() for _ in range(3)]
        counts = np.array([int(a[0]) for a in axes])
        if np.any(abs(counts) < 2) or not np.all(np.sign(counts) == np.sign(counts[0])):
            raise ValueError("Expected three grid counts with consistent signs and magnitudes >= 2.")
        scale = 1 / BOHR_ANGSTROM if counts[0] < 0 else 1
        steps = np.array([a[1:4] for a in axes], float)
        atoms = [tokens() for _ in range(abs(nat))]
        xyz = np.array([a[2:5] for a in atoms], float).reshape(-1, 3)
        if nat < 0:
            ids = tokens()
            if ids != [] and int(ids[0]) == 1:
                if len(ids) == 1:
                    ids.extend(tokens())
            if len(ids) != 2 or int(ids[0]) != 1:
                raise ValueError("Select one orbital before exporting a multi-orbital Cube.")
        data = handle.read().replace("D", "E").replace("d", "e")
        values = np.fromstring(data, sep=" ", dtype=np.float32)
    if values.size != np.prod(abs(counts)) or not np.all(np.isfinite(values)):
        raise ValueError("Cube data count or numeric values disagree with the grid header.")
    if not all(np.isfinite(a).all() for a in (origin, steps, xyz)):
        raise ValueError("Non-finite Cube coordinates.")
    return Cube(origin*scale, steps*scale, xyz*scale, [int(a[0]) for a in atoms], values.reshape(abs(counts)))
