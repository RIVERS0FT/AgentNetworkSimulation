/**
 * Generates a procedural paper texture canvas.
 * Used as the background layer for the tactical map.
 */
export function generatePaperTexture(
  width: number, height: number, seed: number
): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;

  // Base paper color
  ctx.fillStyle = '#f5f0e8';
  ctx.fillRect(0, 0, width, height);

  // Subtle grain noise
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;

  let s = seed + 55555;
  const rng = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  for (let i = 0; i < data.length; i += 4) {
    const noise = (rng() - 0.5) * 6;
    data[i] += noise;     // R
    data[i + 1] += noise; // G
    data[i + 2] += noise; // B
    // Alpha unchanged
  }

  ctx.putImageData(imageData, 0, 0);

  // Subtle horizontal fold marks (like a folded paper map)
  ctx.strokeStyle = 'rgba(180, 170, 150, 0.15)';
  ctx.lineWidth = 0.5;
  const numFolds = 3 + Math.floor(rng() * 3);
  for (let i = 0; i < numFolds; i++) {
    const y = height * (0.2 + rng() * 0.6);
    ctx.beginPath();
    ctx.moveTo(0, y);
    // Slightly wavy fold line
    for (let x = 0; x < width; x += 20) {
      ctx.lineTo(x, y + Math.sin(x * 0.01) * 4);
    }
    ctx.stroke();
  }

  // Vertical fold
  const vx = width * (0.3 + rng() * 0.4);
  ctx.beginPath();
  ctx.moveTo(vx, 0);
  for (let y = 0; y < height; y += 20) {
    ctx.lineTo(vx + Math.sin(y * 0.008) * 3, y);
  }
  ctx.stroke();

  // Edge darkening (vignette)
  const gradient = ctx.createRadialGradient(width / 2, height / 2, Math.min(width, height) * 0.3, width / 2, height / 2, Math.max(width, height) * 0.7);
  gradient.addColorStop(0, 'transparent');
  gradient.addColorStop(1, 'rgba(180, 160, 120, 0.25)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  return canvas;
}
