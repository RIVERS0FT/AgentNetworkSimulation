/**
 * Simplex Noise 2D — pure TypeScript implementation.
 * Based on Stefan Gustavson's algorithm.
 */

const F2 = 0.5 * (Math.sqrt(3) - 1);
const G2 = (3 - Math.sqrt(3)) / 6;

const GRAD3: [number, number][] = [
  [1, 1], [-1, 1], [1, -1], [-1, -1],
  [1, 0], [-1, 0], [0, 1], [0, -1],
];

function dot2(g: [number, number], x: number, y: number): number {
  return g[0] * x + g[1] * y;
}

export class SimplexNoise {
  private perm: Uint8Array;
  private permMod12: Uint8Array;

  constructor(seed: number) {
    this.perm = new Uint8Array(512);
    this.permMod12 = new Uint8Array(512);

    // Fill with identity
    const p = new Uint8Array(256);
    for (let i = 0; i < 256; i++) p[i] = i;

    // Fisher-Yates shuffle with seeded RNG
    let s = seed | 0;
    for (let i = 255; i > 0; i--) {
      s = (s + 0x6d2b79f5) | 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      const r = ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      const j = (r * (i + 1)) | 0;
      [p[i], p[j]] = [p[j], p[i]];
    }

    // Double the permutation table
    for (let i = 0; i < 512; i++) {
      this.perm[i] = p[i & 255];
      this.permMod12[i] = this.perm[i] % 12;
    }
  }

  noise2D(xin: number, yin: number): number {
    // Skew
    const s = (xin + yin) * F2;
    const i = Math.floor(xin + s);
    const j = Math.floor(yin + s);
    const t = (i + j) * G2;
    const X0 = i - t;
    const Y0 = j - t;
    const x0 = xin - X0;
    const y0 = yin - Y0;

    // Determine simplex corner order
    let i1: number, j1: number;
    if (x0 > y0) { i1 = 1; j1 = 0; }
    else { i1 = 0; j1 = 1; }

    const x1 = x0 - i1 + G2;
    const y1 = y0 - j1 + G2;
    const x2 = x0 - 1 + 2 * G2;
    const y2 = y0 - 1 + 2 * G2;

    // Hash
    const ii = i & 255;
    const jj = j & 255;

    const gi0 = this.permMod12[ii + this.perm[jj]] % 8;
    const gi1 = this.permMod12[ii + i1 + this.perm[jj + j1]] % 8;
    const gi2 = this.permMod12[ii + 1 + this.perm[jj + 1]] % 8;

    // Contributions
    let n0 = 0, n1 = 0, n2 = 0;

    let t0 = 0.5 - x0 * x0 - y0 * y0;
    if (t0 > 0) { t0 *= t0; n0 = t0 * t0 * dot2(GRAD3[gi0], x0, y0); }

    let t1 = 0.5 - x1 * x1 - y1 * y1;
    if (t1 > 0) { t1 *= t1; n1 = t1 * t1 * dot2(GRAD3[gi1], x1, y1); }

    let t2 = 0.5 - x2 * x2 - y2 * y2;
    if (t2 > 0) { t2 *= t2; n2 = t2 * t2 * dot2(GRAD3[gi2], x2, y2); }

    // Scale to [-1, 1]
    return 70 * (n0 + n1 + n2);
  }
}

/** Generate a noise value at (x,y) using a simple seed-based hashing.
 *  This is faster than Simplex for single-value lookups in hydrology.
 */
export function hashNoise(x: number, y: number, seed: number): number {
  const h = ((x * 374761393 + y * 668265263 + seed * 1274126177) | 0) >>> 0;
  return (h & 0x7fffffff) / 0x7fffffff - 0.5;
}
