import type { ShapeKey } from "../schema/nodeDefaults";

// SVG geometry per Section 5 (semantic cheat sheet) + Section 1.5 (expanded shape
// table). One <ShapeGeometry> renders the correct silhouette for every ShapeKey inside
// a 0 0 w h viewBox; WorkflowNode.tsx layers the label and port handles on top.

export interface GeometryProps {
  shapeKey: ShapeKey;
  w: number;
  h: number;
  fill: string;
  stroke: string;
  strokeWidth: number;
}

function Rect({ w, h, rx, fill, stroke, strokeWidth, inset = 0 }: { w: number; h: number; rx: number; fill: string; stroke: string; strokeWidth: number; inset?: number }) {
  return (
    <rect
      x={inset + strokeWidth / 2}
      y={inset + strokeWidth / 2}
      width={Math.max(1, w - strokeWidth - inset * 2)}
      height={Math.max(1, h - strokeWidth - inset * 2)}
      rx={rx}
      fill={fill}
      stroke={stroke}
      strokeWidth={strokeWidth}
    />
  );
}

export function ShapeGeometry({ shapeKey, w, h, fill, stroke, strokeWidth }: GeometryProps) {
  const sw = strokeWidth;
  const common = { fill, stroke, strokeWidth: sw };

  switch (shapeKey) {
    case "rect":
      return <Rect w={w} h={h} rx={4} {...common} />;

    case "rounded":
      return <Rect w={w} h={h} rx={16} {...common} />;

    case "stadium":
      return <Rect w={w} h={h} rx={h / 2} {...common} />;

    case "circle":
    case "sm-circ": {
      const r = Math.min(w, h) / 2 - sw;
      return <circle cx={w / 2} cy={h / 2} r={Math.max(2, r)} {...common} />;
    }

    case "dbl-circ": {
      const r = Math.min(w, h) / 2 - sw;
      return (
        <>
          <circle cx={w / 2} cy={h / 2} r={Math.max(2, r)} {...common} />
          <circle cx={w / 2} cy={h / 2} r={Math.max(1, r - 5)} fill="none" stroke={stroke} strokeWidth={sw} />
        </>
      );
    }

    case "fr-circ": {
      const r = Math.min(w, h) / 2 - sw;
      return (
        <>
          <circle cx={w / 2} cy={h / 2} r={Math.max(2, r)} {...common} strokeWidth={sw * 1.6} />
          <circle cx={w / 2} cy={h / 2} r={Math.max(1, r - 4)} fill="none" stroke={stroke} strokeWidth={sw * 0.6} />
        </>
      );
    }

    case "diam":
      return <polygon points={`${w / 2},${sw} ${w - sw},${h / 2} ${w / 2},${h - sw} ${sw},${h / 2}`} {...common} />;

    case "hex": {
      const cut = Math.min(24, w * 0.18);
      return (
        <polygon
          points={`${cut},${sw} ${w - cut},${sw} ${w - sw},${h / 2} ${w - cut},${h - sw} ${cut},${h - sw} ${sw},${h / 2}`}
          {...common}
        />
      );
    }

    case "fr-rect":
      return (
        <>
          <Rect w={w} h={h} rx={4} {...common} />
          <Rect w={w} h={h} rx={2} fill="none" stroke={stroke} strokeWidth={sw} inset={6} />
        </>
      );

    case "lean-r": {
      const skew = w * 0.18;
      return <polygon points={`${skew},${sw} ${w - sw},${sw} ${w - skew},${h - sw} ${sw},${h - sw}`} {...common} />;
    }

    case "lean-l": {
      const skew = w * 0.18;
      return <polygon points={`${sw},${sw} ${w - skew},${sw} ${w - sw},${h - sw} ${skew},${h - sw}`} {...common} />;
    }

    case "cyl": {
      const ry = Math.min(14, h * 0.2);
      return (
        <path
          d={`M ${sw},${ry} a ${w / 2 - sw},${ry} 0 0 1 ${w - sw * 2},0 v ${h - ry * 2 - sw} a ${w / 2 - sw},${ry} 0 0 1 ${-(w - sw * 2)},0 Z M ${sw},${ry} a ${w / 2 - sw},${ry} 0 0 0 ${w - sw * 2},0`}
          {...common}
        />
      );
    }

    case "h-cyl": {
      const rx = Math.min(14, w * 0.2);
      return (
        <path
          d={`M ${rx},${sw} h ${w - rx * 2 - sw} a ${rx},${h / 2 - sw} 0 0 1 0,${h - sw * 2} h ${-(w - rx * 2 - sw)} a ${rx},${h / 2 - sw} 0 0 1 0,${-(h - sw * 2)} Z`}
          {...common}
        />
      );
    }

    case "lin-cyl": {
      const ry = Math.min(14, h * 0.2);
      return (
        <>
          <path
            d={`M ${sw},${ry} a ${w / 2 - sw},${ry} 0 0 1 ${w - sw * 2},0 v ${h - ry * 2 - sw} a ${w / 2 - sw},${ry} 0 0 1 ${-(w - sw * 2)},0 Z`}
            {...common}
          />
          <line x1={sw} y1={ry * 2.4} x2={w - sw} y2={ry * 2.4} stroke={stroke} strokeWidth={sw * 0.7} />
        </>
      );
    }

    case "datastore":
      return (
        <>
          <line x1={sw} y1={sw} x2={w - sw} y2={sw} stroke={stroke} strokeWidth={sw} />
          <line x1={sw} y1={h - sw} x2={w - sw} y2={h - sw} stroke={stroke} strokeWidth={sw} />
          <rect x={sw / 2} y={sw / 2} width={w - sw} height={h - sw} fill={fill} stroke="none" />
        </>
      );

    case "bow-rect": {
      const pinch = h * 0.18;
      return (
        <path
          d={`M ${sw},${sw} H ${w - sw} V ${h - sw} H ${sw} C ${sw + 10},${h - pinch} ${sw + 10},${pinch} ${sw},${sw} Z`}
          {...common}
        />
      );
    }

    case "win-pane":
      return (
        <>
          <Rect w={w} h={h} rx={2} {...common} />
          <line x1={sw} y1={12} x2={w - sw} y2={12} stroke={stroke} strokeWidth={sw * 0.6} />
          <line x1={12} y1={sw} x2={12} y2={h - sw} stroke={stroke} strokeWidth={sw * 0.6} />
        </>
      );

    case "doc": {
      const wave = h * 0.12;
      return (
        <path
          d={`M ${sw},${sw} H ${w - sw} V ${h - wave} Q ${w * 0.75},${h} ${w / 2},${h - wave} Q ${w * 0.25},${h - wave * 2} ${sw},${h - wave} Z`}
          {...common}
        />
      );
    }

    case "docs": {
      const wave = h * 0.12;
      const docPath = (ox: number, oy: number) =>
        `M ${sw + ox},${sw + oy} H ${w - sw} V ${h - wave} Q ${w * 0.75},${h} ${w / 2},${h - wave} Q ${w * 0.25 + ox / 2},${h - wave * 2} ${sw + ox},${h - wave} Z`;
      return (
        <>
          <path d={docPath(8, -8)} fill={fill} stroke={stroke} strokeWidth={sw} opacity={0.6} />
          <path d={docPath(0, 0)} {...common} />
        </>
      );
    }

    case "lin-doc": {
      const wave = h * 0.12;
      return (
        <>
          <path
            d={`M ${sw},${sw} H ${w - sw} V ${h - wave} Q ${w * 0.75},${h} ${w / 2},${h - wave} Q ${w * 0.25},${h - wave * 2} ${sw},${h - wave} Z`}
            {...common}
          />
          <line x1={sw} y1={h * 0.4} x2={w - sw} y2={h * 0.4} stroke={stroke} strokeWidth={sw * 0.5} />
        </>
      );
    }

    case "tag-doc": {
      const wave = h * 0.12;
      const notch = 12;
      return (
        <>
          <path
            d={`M ${sw},${sw} H ${w - sw - notch} L ${w - sw},${sw + notch} V ${h - wave} Q ${w * 0.75},${h} ${w / 2},${h - wave} Q ${w * 0.25},${h - wave * 2} ${sw},${h - wave} Z`}
            {...common}
          />
        </>
      );
    }

    case "st-rect":
      return (
        <>
          <Rect w={w} h={h} rx={4} fill={fill} stroke={stroke} strokeWidth={sw} inset={0} />
          <g transform="translate(6,-6)">
            <Rect w={w} h={h} rx={4} fill={fill} stroke={stroke} strokeWidth={sw} />
          </g>
        </>
      );

    case "div-rect":
      return (
        <>
          <Rect w={w} h={h} rx={4} {...common} />
          <line x1={sw} y1={h * 0.34} x2={w - sw} y2={h * 0.34} stroke={stroke} strokeWidth={sw * 0.6} />
        </>
      );

    case "lin-rect":
      return (
        <>
          <Rect w={w} h={h} rx={4} {...common} />
          <line x1={14} y1={sw} x2={14} y2={h - sw} stroke={stroke} strokeWidth={sw * 0.6} />
        </>
      );

    case "tag-rect": {
      const notch = 14;
      return (
        <path
          d={`M ${sw},${sw} H ${w - sw - notch} L ${w - sw},${sw + notch} V ${h - sw} H ${sw} Z`}
          {...common}
        />
      );
    }

    case "trap-t": {
      const inset = w * 0.14;
      return <polygon points={`${sw},${sw} ${w - sw},${sw} ${w - inset},${h - sw} ${inset},${h - sw}`} {...common} />;
    }

    case "sl-rect":
      return <polygon points={`${sw},${h * 0.25} ${w - sw},${sw} ${w - sw},${h - sw} ${sw},${h - sw}`} {...common} />;

    case "flip-tri":
      return <polygon points={`${sw},${sw} ${w - sw},${sw} ${w / 2},${h - sw}`} {...common} />;

    case "trap-b": {
      const inset = w * 0.14;
      return <polygon points={`${inset},${sw} ${w - inset},${sw} ${w - sw},${h - sw} ${sw},${h - sw}`} {...common} />;
    }

    case "delay":
      return (
        <path
          d={`M ${sw},${sw} H ${w * 0.65} A ${w * 0.35 - sw},${h / 2 - sw} 0 0 1 ${w * 0.65},${h - sw} H ${sw} Z`}
          {...common}
        />
      );

    case "curv-trap": {
      const inset = w * 0.12;
      return (
        <path
          d={`M ${inset},${sw} H ${w - inset} L ${w - sw},${h * 0.7} Q ${w / 2},${h - sw} ${sw},${h * 0.7} Z`}
          {...common}
        />
      );
    }

    case "notch-pent": {
      const notch = 10;
      return (
        <path
          d={`M ${notch},${sw} H ${w - notch} L ${w - sw},${h * 0.4} L ${w / 2},${h - sw} L ${sw},${h * 0.4} Z`}
          {...common}
        />
      );
    }

    case "tri":
      return <polygon points={`${w / 2},${sw} ${w - sw},${h - sw} ${sw},${h - sw}`} {...common} />;

    case "hourglass":
      return (
        <polygon
          points={`${sw},${sw} ${w - sw},${sw} ${sw},${h - sw} ${w - sw},${h - sw}`}
          {...common}
        />
      );

    case "fork":
      return <rect x={w * 0.3} y={sw} width={w * 0.4} height={h - sw * 2} fill={stroke} stroke={stroke} strokeWidth={sw} />;

    case "f-circ": {
      const r = Math.min(w, h) / 2 - sw;
      return <circle cx={w / 2} cy={h / 2} r={Math.max(2, r)} fill={stroke} stroke={stroke} strokeWidth={sw} />;
    }

    case "cross-circ": {
      const r = Math.min(w, h) / 2 - sw;
      const cx = w / 2;
      const cy = h / 2;
      return (
        <>
          <circle cx={cx} cy={cy} r={Math.max(2, r)} {...common} />
          <line x1={cx - r * 0.6} y1={cy - r * 0.6} x2={cx + r * 0.6} y2={cy + r * 0.6} stroke={stroke} strokeWidth={sw} />
          <line x1={cx + r * 0.6} y1={cy - r * 0.6} x2={cx - r * 0.6} y2={cy + r * 0.6} stroke={stroke} strokeWidth={sw} />
        </>
      );
    }

    case "notch-rect": {
      const notch = 14;
      return (
        <path
          d={`M ${sw + notch},${sw} H ${w - sw} V ${h - sw} H ${sw} V ${sw + notch} Z`}
          {...common}
        />
      );
    }

    case "flag":
      return <polygon points={`${sw},${sw} ${w - sw},${sw} ${w - sw},${h - sw} ${sw},${h - sw} ${sw + 10},${h / 2}`} {...common} />;

    case "bolt":
      return (
        <polygon
          points={`${w * 0.55},${sw} ${w * 0.2},${h * 0.55} ${w * 0.45},${h * 0.55} ${w * 0.35},${h - sw} ${w * 0.85},${h * 0.4} ${w * 0.55},${h * 0.4}`}
          {...common}
        />
      );

    case "brace":
      return (
        <path
          d={`M ${w * 0.7},${sw} Q ${w * 0.3},${sw} ${w * 0.3},${h * 0.4} Q ${w * 0.3},${h / 2} ${sw},${h / 2} Q ${w * 0.3},${h / 2} ${w * 0.3},${h * 0.6} Q ${w * 0.3},${h - sw} ${w * 0.7},${h - sw}`}
          fill="none"
          stroke={stroke}
          strokeWidth={sw}
        />
      );

    case "cloud":
      return (
        <path
          d={`M ${w * 0.25},${h * 0.7} a ${w * 0.15},${h * 0.22} 0 1 1 ${w * 0.05},${-h * 0.28} a ${w * 0.2},${h * 0.25} 0 1 1 ${w * 0.4},${-h * 0.05} a ${w * 0.18},${h * 0.22} 0 1 1 ${w * 0.12},${h * 0.33} Z`}
          {...common}
        />
      );

    case "bang": {
      const cx = w / 2;
      const cy = h / 2;
      const spikes = 10;
      const rOuter = Math.min(w, h) / 2 - sw;
      const rInner = rOuter * 0.65;
      const pts: string[] = [];
      for (let i = 0; i < spikes * 2; i++) {
        const r = i % 2 === 0 ? rOuter : rInner;
        const angle = (Math.PI * i) / spikes;
        pts.push(`${cx + r * Math.sin(angle)},${cy - r * Math.cos(angle)}`);
      }
      return <polygon points={pts.join(" ")} {...common} />;
    }

    case "odd":
      return <Rect w={w} h={h} rx={10} {...common} />;

    case "text":
      return <rect x={0} y={0} width={w} height={h} fill="transparent" stroke="none" />;

    case "icon":
      return <Rect w={w} h={h} rx={h / 2} {...common} />;

    case "image":
      return (
        <>
          <Rect w={w} h={h} rx={4} {...common} />
          <path
            d={`M ${w * 0.2},${h * 0.7} L ${w * 0.4},${h * 0.45} L ${w * 0.55},${h * 0.6} L ${w * 0.75},${h * 0.35} L ${w * 0.85},${h * 0.7} Z`}
            fill={stroke}
            opacity={0.5}
          />
        </>
      );

    case "pentagon-tab":
      return (
        <polygon
          points={`${sw},${sw} ${w * 0.75},${sw} ${w - sw},${h / 2} ${w * 0.75},${h - sw} ${sw},${h - sw}`}
          {...common}
        />
      );

    default:
      return <Rect w={w} h={h} rx={4} {...common} />;
  }
}
