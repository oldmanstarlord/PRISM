import { useEffect, useRef } from "react";

type Point = { x: number; y: number; z: number };
const GREEN = "103,245,142",
  GOLD = "255,205,89",
  RED = "255,102,110";
const clamp = (n: number) => Math.max(0, Math.min(1, n));
const ease = (n: number) => {
  const x = clamp(n);
  return x * x * (3 - 2 * x);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const rotationClock = (time: number) => {
  const ramp = 0.8;
  const u = clamp(time / ramp);
  return time <= ramp ? ramp * (u ** 3 - 0.5 * u ** 4) : time - ramp / 2;
};
const curvePoint = (
  a: Point,
  b: Point,
  c: Point,
  d: Point,
  p: number,
): Point => {
  const q = 1 - p;
  return {
    x: q ** 3 * a.x + 3 * q * q * p * b.x + 3 * q * p * p * c.x + p ** 3 * d.x,
    y: q ** 3 * a.y + 3 * q * q * p * b.y + 3 * q * p * p * c.y + p ** 3 * d.y,
    z: 0,
  };
};
const noise = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

/** Projected glass geometry and procedural data, drawn at the display's pixel density. */
export default function PrismScene({
  motionAllowed,
  settled,
}: {
  motionAllowed: boolean;
  settled: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const settledRef = useRef(settled);
  useEffect(() => {
    settledRef.current = settled;
  }, [settled]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas) return;
    if (!ctx) {
      canvas.parentElement?.setAttribute("data-scene-fallback", "true");
      return;
    }
    canvas.parentElement?.removeAttribute("data-scene-fallback");
    let width = 0,
      height = 0,
      frameId = 0;
    const started = performance.now();
    let lastReveal = "";
    let lastFrame = started;
    const pointer = { x: 0, y: 0, targetX: 0, targetY: 0 };
    const followPointer = (event: PointerEvent) => {
      if (event.pointerType === "touch") return;
      pointer.targetX = Math.max(
        -1,
        Math.min(1, (event.clientX / width) * 2 - 1),
      );
      pointer.targetY = Math.max(
        -1,
        Math.min(1, (event.clientY / height) * 2 - 1),
      );
    };
    const resetPointer = () => {
      pointer.targetX = 0;
      pointer.targetY = 0;
    };
    if (motionAllowed) {
      window.addEventListener("pointermove", followPointer, { passive: true });
      document.documentElement.addEventListener("pointerleave", resetPointer);
      window.addEventListener("blur", resetPointer);
    }
    const resize = () => {
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    resize();
    const glow = (
      x: number,
      y: number,
      radius: number,
      color: string,
      alpha: number,
    ) => {
      const g = ctx.createRadialGradient(x, y, 0, x, y, radius);
      g.addColorStop(0, `rgba(${color},${alpha})`);
      g.addColorStop(1, `rgba(${color},0)`);
      ctx.fillStyle = g;
      ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
    };
    const stroke = (
      points: { x: number; y: number }[],
      color: string,
      lineWidth = 1,
    ) => {
      ctx.beginPath();
      points.forEach((p, i) =>
        i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y),
      );
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    };
    const trace = (
      points: Point[],
      progress: number,
      color: string,
      lineWidth: number,
    ) => {
      const lengths = points
        .slice(1)
        .map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y));
      let remaining =
        lengths.reduce((sum, length) => sum + length, 0) * clamp(progress);
      const drawn = [points[0]];
      let head = points[0];
      for (let i = 0; i < lengths.length && remaining > 0; i++) {
        const p = Math.min(1, remaining / lengths[i]);
        head = {
          x: mix(points[i].x, points[i + 1].x, p),
          y: mix(points[i].y, points[i + 1].y, p),
          z: 0,
        };
        drawn.push(head);
        remaining -= lengths[i];
      }
      stroke(drawn, color, lineWidth);
      return head;
    };
    const draw = (now: number) => {
      // Time-based damping keeps cursor response smooth at any refresh rate.
      const damping =
        1 - Math.exp(-Math.min((now - lastFrame) / 1000, 0.05) * 8);
      lastFrame = now;
      pointer.x = mix(pointer.x, pointer.targetX, damping);
      pointer.y = mix(pointer.y, pointer.targetY, damping);
      const elapsed = (now - started) / 1000;
      const t = motionAllowed ? elapsed : 0;
      const timeline =
        settledRef.current || !motionAllowed ? Math.max(3.8, elapsed) : elapsed;
      const mobile = width < 760;
      const cx = width * (mobile ? 0.5 : 0.505),
        cy = height * (mobile ? 0.445 : 0.49);
      const scale = mobile
        ? Math.min(width * 0.205, height * 0.105)
        : Math.min(width * 0.115, height * 0.225);
      const floor = cy + scale * 1.09;
      const edgeProgress = ease((timeline - 1.12) / 1.12);
      const glass = ease((timeline - 1.48) / 0.85);
      const fan = ease((timeline - 2.21) / 0.65);
      const signalY = cy + scale * 0.02;
      const entry: Point = { x: cx - scale * 0.42, y: signalY, z: 0 };
      const origin: Point = { x: cx + scale * 0.1, y: signalY, z: 0 };
      const through = ease((timeline - 1.23) / 0.94);
      const beamProgress = [0, 0.045, 0.09].map((delay) =>
        ease((timeline - 2.24 - delay) / 0.93),
      );
      const brandProgress = ease((timeline - 2.84) / 0.65);
      const panelProgress = [0, 0.045, 0.09].map((delay) =>
        ease((timeline - 2.95 - delay) / 0.58),
      );
      const root = canvas.parentElement;
      const revealKey = [brandProgress, ...panelProgress].join(",");
      if (root && revealKey !== lastReveal) {
        lastReveal = revealKey;
        root.style.setProperty("--intro-brand", String(brandProgress));
        root.style.setProperty(
          "--intro-brand-visible",
          brandProgress > 0 ? "visible" : "hidden",
        );
        panelProgress.forEach((progress, index) =>
          root.style.setProperty(`--intro-panel-${index}`, String(progress)),
        );
        root.style.setProperty(
          "--intro-panels-visible",
          panelProgress[0] > 0 ? "visible" : "hidden",
        );
      }
      ctx.clearRect(0, 0, width, height);
      glow(cx, floor, scale * 1.9, "42,140,106", 0.1);

      // Quiet market texture, behind the readable interface.
      ctx.save();
      ctx.globalAlpha = 0.17;
      const spacing = mobile ? 22 : 30;
      for (let i = -2; i < width / spacing + 2; i++) {
        const x = i * spacing - ((t * 3) % spacing);
        const y =
          height *
          (0.31 + 0.12 * Math.sin(i * 0.21) + 0.07 * Math.cos(i * 0.7));
        const size = 12 + noise(i) * 32,
          up = noise(i + 7) > 0.4;
        ctx.strokeStyle = up ? "#285b3c" : "#5b3c28";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, y - size * 0.8);
        ctx.lineTo(x, y + size * 1.7);
        ctx.stroke();
        ctx.fillStyle = up ? "#225a38" : "#594125";
        ctx.fillRect(x - 3, y, 6, size);
      }
      ctx.restore();

      // Perspective floor and softly lit intersections.
      ctx.save();
      const horizon = mobile ? floor - 20 : height * 0.62;
      const floorGradient = ctx.createLinearGradient(0, horizon, 0, height);
      floorGradient.addColorStop(0, "rgba(89,177,141,0)");
      floorGradient.addColorStop(1, "rgba(89,177,141,.17)");
      ctx.strokeStyle = floorGradient;
      ctx.lineWidth = 0.65;
      for (let i = -16; i <= 16; i++) {
        ctx.beginPath();
        ctx.moveTo(cx + i * 10, horizon);
        ctx.lineTo(cx + i * width * 0.12, height);
        ctx.stroke();
      }
      for (let j = 0; j < 16; j++) {
        const p = ((j + t * 0.12) % 16) / 16,
          y = horizon + (height - horizon) * p * p;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
        if (j % 3 === 0)
          for (let k = -4; k <= 4; k++) {
            const x = cx + k * width * 0.12 * p * p;
            ctx.fillStyle = "rgba(136,236,188,.28)";
            ctx.beginPath();
            ctx.arc(x, y, 1.2, 0, Math.PI * 2);
            ctx.fill();
          }
      }
      ctx.restore();

      // The signal always ends at the same contact point; it never retracts.
      const signalReveal = ease(timeline / 1.12);
      const start = mobile ? -20 : -30;
      const incoming: Point[] = [];
      for (let i = 0; i <= 180; i++) {
        const p = i / 180;
        const attenuation = 1 - ease((p - 0.78) / 0.22);
        const wave =
          (Math.sin(i * 0.24 + t * 0.6) * 18 +
            Math.sin(i * 0.93) * 6 +
            Math.sin(i * 2.3) * 3) *
          attenuation;
        incoming.push({ x: mix(start, entry.x, p), y: signalY + wave, z: 0 });
      }
      ctx.save();
      ctx.globalAlpha = (mobile ? 0.8 : 1) * (1 - brandProgress * 0.82);
      ctx.shadowColor = `rgb(${GREEN})`;
      ctx.shadowBlur = 8;
      const signalHead = trace(
        incoming,
        signalReveal,
        `rgba(${GREEN},.9)`,
        1.5,
      );
      ctx.shadowBlur = 0;
      glow(signalHead.x, signalHead.y, 15, GREEN, 0.55);
      ctx.restore();
      if (timeline > 1.12) {
        // Energy enters the glass before it can leave as three streams.
        const innerHead = {
          x: mix(entry.x, origin.x, through),
          y: signalY,
          z: 0,
        };
        stroke([entry, innerHead], `rgba(${GREEN},${0.25 + glass * 0.5})`, 1.1);
        glow(innerHead.x, innerHead.y, scale * 0.16, GREEN, 0.25);
      }

      // Fixed chart geometry is uncovered by a moving wavefront, never stretched.
      const beamEnd = mobile ? width * 0.91 : width * 0.764;
      const beamYs = mobile
        ? [cy - scale * 0.64, cy, cy + scale * 0.65]
        : [height * 0.307, height * 0.5, height * 0.693];
      [GREEN, GOLD, RED].forEach((color, index) => {
        const front = beamProgress[index];
        if (front <= 0) return;
        const ey = mix(signalY, beamYs[index], fan);
        const half = (mobile ? scale * 0.24 : height * 0.054) * fan;
        const end: Point = { x: beamEnd, y: ey, z: 0 };
        const controlA: Point = { x: cx + scale * 0.7, y: signalY, z: 0 };
        const controlB: Point = { x: beamEnd - scale * 0.55, y: ey, z: 0 };
        const point = (p: number) =>
          curvePoint(origin, controlA, controlB, end, p);
        const upper: Point[] = [],
          lower: Point[] = [];
        for (let i = 0; i <= 60; i++) {
          const p = (i / 60) * front,
            center = point(p),
            spread = half * p;
          upper.push({ ...center, y: center.y - spread });
          lower.push({ ...center, y: center.y + spread });
        }
        ctx.save();
        ctx.globalAlpha = ease((timeline - 2.24) / 0.22);
        ctx.beginPath();
        [...upper, ...lower.reverse()].forEach((p, i) =>
          i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y),
        );
        ctx.closePath();
        const gradient = ctx.createLinearGradient(
          origin.x,
          origin.y,
          beamEnd,
          ey,
        );
        gradient.addColorStop(0, `rgba(${color},.24)`);
        gradient.addColorStop(1, `rgba(${color},.025)`);
        ctx.fillStyle = gradient;
        ctx.fill();
        ctx.strokeStyle = `rgba(${color},.45)`;
        ctx.lineWidth = 0.7;
        ctx.stroke();
        ctx.save();
        ctx.clip();
        if (index === 0) {
          const prices: Point[] = [];
          for (let i = 0; i <= 110; i++) {
            const p = i / 110,
              center = point(p);
            prices.push({
              ...center,
              y:
                center.y +
                half *
                  p *
                  (0.18 -
                    Math.sin(i * 0.43 + t * 0.7) * 0.33 -
                    Math.sin(i * 1.8) * 0.12),
            });
          }
          ctx.shadowColor = `rgb(${color})`;
          ctx.shadowBlur = 4;
          stroke(prices, `rgba(${color},.9)`, 1.3);
        } else if (index === 1) {
          for (let i = 0; i < 25; i++) {
            const p = (i + 1) / 26,
              center = point(p),
              baseline = center.y + half * p * 0.75;
            const h =
              p * half * (0.3 + noise(i + 12) * 1.1 + 0.12 * Math.sin(t + i));
            const bar = ctx.createLinearGradient(0, baseline - h, 0, baseline);
            bar.addColorStop(0, `rgba(${color},.9)`);
            bar.addColorStop(1, `rgba(${color},.12)`);
            ctx.fillStyle = bar;
            ctx.fillRect(
              center.x,
              baseline - h,
              Math.max(2, (beamEnd - origin.x) / 45),
              h,
            );
          }
        } else {
          const nodes = Array.from({ length: 15 }, (_, i) => {
            const p = 0.16 + i * 0.055,
              center = point(p);
            return {
              ...center,
              y: center.y + Math.sin(i * 2.4 + t * 0.3) * half * p * 0.8,
            };
          });
          nodes.forEach((p, i) => {
            if (i) stroke([nodes[i - 1], p], `rgba(${color},.7)`, 0.85);
            if (i > 2) stroke([nodes[i - 3], p], `rgba(${color},.2)`, 0.5);
            ctx.beginPath();
            ctx.arc(p.x, p.y, 1.2 + i * 0.08, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${color},.95)`;
            ctx.fill();
          });
        }
        ctx.restore();
        const centerline = Array.from({ length: 65 }, (_, i) =>
          point((i / 64) * front),
        );
        stroke(centerline, `rgba(${color},.5)`, 0.75);
        // One leading pulse opens each stream; later pulses keep it alive.
        const pulse =
          front < 1 ? front : ((t - 3.17) * 0.17 + index * 0.32 + 100) % 1;
        const head = point(pulse);
        glow(head.x, head.y, front < 1 ? 10 : 5, color, front < 1 ? 0.65 : 0.5);
        ctx.restore();
      });

      // Rotating tetrahedron, with depth-sorted glass faces and highlights.
      if (edgeProgress > 0) {
        const interaction = motionAllowed ? ease((timeline - 2.3) / 0.9) : 0;
        const angle =
          0.52 +
          0.19 * rotationClock(Math.max(0, t - 2.3)) +
          pointer.x * 0.95 * interaction;
        const pitch = pointer.y * 0.42 * interaction;
        const vertices: Point[] = [
          { x: 0, y: -1.5, z: 0 },
          { x: -1, y: 1, z: 0.65 },
          { x: 1, y: 1, z: 0.65 },
          { x: 0, y: 1, z: -1.1 },
        ];
        const project = (p: Point): Point => {
          const x = p.x * Math.cos(angle) + p.z * Math.sin(angle),
            yawZ = -p.x * Math.sin(angle) + p.z * Math.cos(angle),
            z = p.y * Math.sin(pitch) + yawZ * Math.cos(pitch);
          const y =
              (p.y * Math.cos(pitch) - yawZ * Math.sin(pitch)) * 0.98 -
              z * 0.12,
            depth = 5.8 / (5.8 + z);
          return {
            x: cx + x * scale * depth,
            y: cy + y * scale * depth,
            z,
          };
        };
        const projected = vertices.map(project);
        const faces = [
          [0, 1, 2],
          [0, 2, 3],
          [0, 3, 1],
          [1, 3, 2],
        ].sort(
          (a, b) =>
            b.reduce((v, i) => v + projected[i].z, 0) -
            a.reduce((v, i) => v + projected[i].z, 0),
        );
        const drawGlass = (reflection: boolean) => {
          ctx.save();
          ctx.globalAlpha = glass * (reflection ? 0.14 : 1);
          if (reflection) {
            ctx.translate(0, floor * 1.28);
            ctx.scale(1, -0.28);
          }
          faces.forEach((face, fi) => {
            const [a, b, c] = face.map((i) => projected[i]);
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.lineTo(c.x, c.y);
            ctx.closePath();
            const g = ctx.createLinearGradient(a.x, a.y, c.x, c.y);
            g.addColorStop(0, `rgba(201,248,255,${0.08 + fi * 0.025})`);
            g.addColorStop(0.4, `rgba(42,128,145,${0.025 + fi * 0.015})`);
            g.addColorStop(0.78, `rgba(126,221,228,${0.06 + fi * 0.025})`);
            g.addColorStop(1, `rgba(210,249,255,${0.11 + fi * 0.025})`);
            ctx.fillStyle = g;
            ctx.fill();
            ctx.strokeStyle = `rgba(182,238,243,${(0.17 + fi * 0.12) * ease((timeline - 2.05) / 0.35)})`;
            ctx.lineWidth = fi === 3 ? 1.25 : 0.8;
            ctx.stroke();
            ctx.save();
            ctx.clip();
            for (let j = 1; j < 7; j++) {
              const p = j / 7,
                e = { x: mix(a.x, b.x, p), y: mix(a.y, b.y, p) },
                f = { x: mix(a.x, c.x, 1 - p), y: mix(a.y, c.y, 1 - p) };
              stroke(
                [e, f],
                `rgba(157,230,238,${fi === 3 ? 0.13 : 0.065})`,
                0.6,
              );
            }
            const shine = ctx.createLinearGradient(
                cx - scale,
                0,
                cx + scale,
                0,
              ),
              sweep = 0.5 + Math.sin(t * 0.3 + fi) * 0.3;
            shine.addColorStop(0, "rgba(130,231,255,0)");
            shine.addColorStop(
              Math.max(0.01, sweep - 0.12),
              "rgba(130,231,255,0)",
            );
            shine.addColorStop(
              sweep,
              `rgba(194,247,255,${fi === 3 ? 0.23 : 0.07})`,
            );
            shine.addColorStop(
              Math.min(0.99, sweep + 0.12),
              "rgba(130,231,255,0)",
            );
            shine.addColorStop(1, "rgba(130,231,255,0)");
            ctx.fillStyle = shine;
            ctx.fillRect(
              cx - scale * 1.5,
              cy - scale * 2,
              scale * 3,
              scale * 4,
            );
            ctx.restore();
          });
          if (!reflection) {
            projected.forEach((p, i) =>
              glow(p.x, p.y, i ? 12 : 8, "175,239,249", i ? 0.27 : 0.35),
            );
            stroke(
              [projected[0], projected[1]],
              `rgba(225,255,255,${0.72 * ease((timeline - 2.05) / 0.35)})`,
              1.15,
            );
          }
          ctx.restore();
        };
        drawGlass(true);
        drawGlass(false);
        // A single connected energy path builds the full-size edges in place.
        const outline = [
          entry,
          projected[1],
          projected[0],
          projected[2],
          projected[3],
          projected[0],
          projected[3],
          projected[1],
          projected[2],
        ];
        ctx.save();
        ctx.globalAlpha = 1 - ease((timeline - 2.23) / 0.35);
        ctx.shadowColor = "#b3f8ed";
        ctx.shadowBlur = 7;
        const head = trace(outline, edgeProgress, "rgba(186,255,238,.9)", 1.3);
        ctx.shadowBlur = 0;
        glow(head.x, head.y, 11, "186,255,238", 0.7);
        ctx.restore();
        glow(cx, floor, scale * 0.62, "93,197,211", 0.11 * glass);
        glow(origin.x, signalY, scale * 0.32, GREEN, 0.25 * through);
        glow(origin.x, signalY, scale * 0.19, GOLD, 0.42 * fan);
        glow(origin.x, signalY, 7, "255,255,215", 0.95 * fan);
      }

      for (let i = 0; i < 32; i++) {
        const x = noise(i + 100) * width,
          y =
            (noise(i + 200) * height - t * (2 + noise(i) * 4) + height * 10) %
            height;
        ctx.fillStyle = `rgba(156,237,202,${0.04 + noise(i + 2) * 0.16})`;
        ctx.beginPath();
        ctx.arc(x, y, noise(i) * 1.1 + 0.35, 0, Math.PI * 2);
        ctx.fill();
      }
    };
    const frame = (now: number) => {
      if (!document.hidden) draw(now);
      if (motionAllowed) frameId = requestAnimationFrame(frame);
    };
    const observer = new ResizeObserver(() => {
      resize();
      if (!motionAllowed) draw(performance.now());
    });
    observer.observe(canvas);
    frame(performance.now());
    return () => {
      cancelAnimationFrame(frameId);
      observer.disconnect();
      window.removeEventListener("pointermove", followPointer);
      document.documentElement.removeEventListener(
        "pointerleave",
        resetPointer,
      );
      window.removeEventListener("blur", resetPointer);
    };
  }, [motionAllowed]);

  return (
    <canvas
      className="intro-scene"
      ref={canvasRef}
      aria-hidden="true"
      data-renderer="native"
    />
  );
}
