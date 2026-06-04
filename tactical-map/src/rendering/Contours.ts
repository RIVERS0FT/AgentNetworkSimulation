import type { Heightmap } from '../types';

/**
 * Optimized contour renderer — renders in the CURRENT coordinate space.
 *
 * Called from MapRenderer.render() after ctx.translate+scale to world coords,
 * so all drawing happens in world units [0, worldWidth] × [0, worldHeight].
 *
 * Key optimizations:
 * 1. Uses ctx.fillRect() instead of beginPath/arc/fill — avoids path-command overflow
 * 2. Caches previous bilinear sample as prev for next iteration — no double-sampling
 * 3. Adaptive sample density based on world dimensions
 * 4. isMajor uses 0.1 interval (every other 0.05 level)
 */
export function renderContours(
  ctx: CanvasRenderingContext2D,
  heightmap: Heightmap,
  worldWidth: number,
  worldHeight: number,
): void {
  const { data, width: hw, height: hh } = heightmap;

  // ── Sample step: target ~250–400 samples per axis ──
  const sampleDensity = 350;
  const step = Math.max(0.25, worldWidth / sampleDensity);

  // ── Contour levels: every 0.05 ──
  const levels: number[] = [];
  for (let l = 0.05; l < 0.975; l += 0.05) {
    levels.push(l);
  }

  for (const targetLevel of levels) {
    // ── isMajor: every 0.1 (i.e. every other level) → thicker & darker ──
    const isMajor = Math.abs(targetLevel / 0.1 - Math.round(targetLevel / 0.1)) < 0.001;

    if (isMajor) {
      ctx.fillStyle = 'rgba(45, 30, 15, 0.55)';
    } else {
      ctx.fillStyle = 'rgba(58, 42, 25, 0.28)';
    }
    const dotR = isMajor ? 0.9 : 0.55;

    // ═══════════════════════════════════════════
    // 1. HORIZONTAL SCAN — check crossings between columns
    // ═══════════════════════════════════════════
    for (let wy = 0; wy <= worldHeight; wy += step) {
      const hy = (wy / worldHeight) * hh;
      const iy = Math.min(hh - 1, Math.floor(hy));
      const fy = hy - iy;
      const iy2 = Math.min(hh - 1, iy + 1);

      // Cache: prevElev carries over from previous column in this row
      let prevElev: number | null = null;

      for (let wx = 0; wx <= worldWidth; wx += step) {
        const hx = (wx / worldWidth) * hw;
        const ix = Math.min(hw - 1, Math.floor(hx));
        const fx = hx - ix;
        const ix2 = Math.min(hw - 1, ix + 1);

        // Bilinear interpolation (only computed ONCE per pixel)
        const v00 = data[iy * hw + ix];
        const v10 = data[iy * hw + ix2];
        const v01 = data[iy2 * hw + ix];
        const v11 = data[iy2 * hw + ix2];
        const curr =
          (v00 * (1 - fx) + v10 * fx) * (1 - fy) +
          (v01 * (1 - fx) + v11 * fx) * fy;

        if (prevElev !== null) {
          // Check if contour level lies between prev and curr
          if (
            (prevElev < targetLevel && curr >= targetLevel) ||
            (prevElev >= targetLevel && curr < targetLevel)
          ) {
            const t = (targetLevel - prevElev) / (curr - prevElev || 0.001);
            const cx = wx - step + t * step;
            // Use fillRect instead of beginPath/arc/fill — prevents path-command overflow
            ctx.fillRect(cx - dotR, wy - dotR, dotR * 2, dotR * 2);
          }
        }
        // Cache current as prev for next column (requirement 4)
        prevElev = curr;
      }
    }

    // ═══════════════════════════════════════════
    // 2. VERTICAL SCAN — check crossings between rows
    // ═══════════════════════════════════════════
    for (let wx = 0; wx <= worldWidth; wx += step) {
      const hx = (wx / worldWidth) * hw;
      const ix = Math.min(hw - 1, Math.floor(hx));
      const fx = hx - ix;
      const ix2 = Math.min(hw - 1, ix + 1);

      let prevElev: number | null = null;

      for (let wy = 0; wy <= worldHeight; wy += step) {
        const hy = (wy / worldHeight) * hh;
        const iy = Math.min(hh - 1, Math.floor(hy));
        const fy = hy - iy;
        const iy2 = Math.min(hh - 1, iy + 1);

        // Bilinear interpolation (only computed ONCE per pixel)
        const v00 = data[iy * hw + ix];
        const v10 = data[iy * hw + ix2];
        const v01 = data[iy2 * hw + ix];
        const v11 = data[iy2 * hw + ix2];
        const curr =
          (v00 * (1 - fx) + v10 * fx) * (1 - fy) +
          (v01 * (1 - fx) + v11 * fx) * fy;

        if (prevElev !== null) {
          if (
            (prevElev < targetLevel && curr >= targetLevel) ||
            (prevElev >= targetLevel && curr < targetLevel)
          ) {
            const t = (targetLevel - prevElev) / (curr - prevElev || 0.001);
            const cy = wy - step + t * step;
            ctx.fillRect(wx - dotR, cy - dotR, dotR * 2, dotR * 2);
          }
        }
        prevElev = curr;
      }
    }

    // ═══════════════════════════════════════════
    // 3. ELEVATION LABELS on major contours
    // ═══════════════════════════════════════════
    if (isMajor) {
      const elevLabel = Math.round(targetLevel * 1500);
      ctx.font = "bold 9px 'JetBrains Mono', monospace";
      ctx.textAlign = 'start';

      for (let wy = 20; wy < worldHeight - 20; wy += 60) {
        for (let wx = 20; wx < worldWidth - 30; wx += 60) {
          const ix = Math.min(hw - 1, Math.floor((wx / worldWidth) * hw));
          const iy = Math.min(hh - 1, Math.floor((wy / worldHeight) * hh));
          const cElev = data[iy * hw + ix];
          if (Math.abs(cElev - targetLevel) < 0.04) {
            // White halo for readability
            ctx.fillStyle = 'rgba(245,240,232,0.5)';
            ctx.fillText(`${elevLabel}`, wx - 1, wy - 1);
            ctx.fillText(`${elevLabel}`, wx + 1, wy + 1);
            ctx.fillStyle = 'rgba(55, 35, 18, 0.6)';
            ctx.fillText(`${elevLabel}`, wx, wy);
            break;
          }
        }
      }
    }
  }
}

/** Stub kept for API compatibility — labels are drawn inline above */
export function renderContourLabels(
  ctx: CanvasRenderingContext2D,
  _width: number,
  _height: number,
  _heightmap: Heightmap,
): void {
  void ctx;
  void _width;
  void _height;
  void _heightmap;
}
