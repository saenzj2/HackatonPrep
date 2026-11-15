import type { MonthlyClimate, SeasonSummary } from "../api/client";
import { capitalize, monthName } from "../format";

// Small hand-drawn SVG charts (no chart library). Month labels on x; the growing seasons are
// shaded so the farmer sees which months matter. Each chart has a text summary for screen readers.
const W = 360;
const H = 150;
const PAD = { left: 34, right: 8, top: 10, bottom: 24 };
const innerW = W - PAD.left - PAD.right;
const innerH = H - PAD.top - PAD.bottom;
const slot = innerW / 12;
const x = (month: number) => PAD.left + (month - 1) * slot;

function niceMax(value: number, step: number): number {
  return Math.max(step, Math.ceil(value / step) * step);
}

function SeasonBands({ seasons }: { seasons: SeasonSummary[] }) {
  return (
    <>
      {seasons.map((s) => (
        <g key={s.name}>
          <rect
            x={x(s.months[0])}
            y={PAD.top}
            width={slot * s.months.length}
            height={innerH}
            className="chart__season"
          />
          <text x={x(s.months[0]) + 3} y={PAD.top + 10} className="chart__season-label">
            {capitalize(s.name)}
          </text>
        </g>
      ))}
    </>
  );
}

function MonthAxis() {
  return (
    <>
      {Array.from({ length: 12 }, (_, i) => (
        <text key={i} x={x(i + 1) + slot / 2} y={H - 8} textAnchor="middle" className="chart__tick">
          {monthName(i + 1).charAt(0)}
        </text>
      ))}
    </>
  );
}

function YAxis({ max, unit, steps = 2 }: { max: number; unit: string; steps?: number }) {
  return (
    <>
      {Array.from({ length: steps + 1 }, (_, i) => {
        const value = (max / steps) * i;
        const y = PAD.top + innerH - (value / max) * innerH;
        return (
          <g key={i}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} className="chart__grid" />
            <text x={PAD.left - 4} y={y + 3} textAnchor="end" className="chart__tick">
              {Math.round(value)}
              {i === steps ? ` ${unit}` : ""}
            </text>
          </g>
        );
      })}
    </>
  );
}

export function RainChart({ monthly, seasons }: { monthly: MonthlyClimate[]; seasons: SeasonSummary[] }) {
  const max = niceMax(Math.max(...monthly.map((m) => m.rainfall_mm)), 100);
  const wettest = monthly.reduce((a, b) => (b.rainfall_mm > a.rainfall_mm ? b : a));
  const driest = monthly.reduce((a, b) => (b.rainfall_mm < a.rainfall_mm ? b : a));
  const summary = `Rain per month: wettest ${monthName(wettest.month)} (${Math.round(wettest.rainfall_mm)} mm), driest ${monthName(driest.month)} (${Math.round(driest.rainfall_mm)} mm).`;
  return (
    <figure className="chart">
      <figcaption className="chart__title">Rain per month (mm)</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
        <SeasonBands seasons={seasons} />
        <YAxis max={max} unit="mm" />
        {monthly.map((m) => {
          const h = (m.rainfall_mm / max) * innerH;
          return (
            <rect
              key={m.month}
              x={x(m.month) + slot * 0.18}
              y={PAD.top + innerH - h}
              width={slot * 0.64}
              height={h}
              rx={2}
              className="chart__bar"
            >
              <title>{`${monthName(m.month)}: ${Math.round(m.rainfall_mm)} mm`}</title>
            </rect>
          );
        })}
        <MonthAxis />
      </svg>
    </figure>
  );
}

export function TemperatureChart({ monthly, seasons }: { monthly: MonthlyClimate[]; seasons: SeasonSummary[] }) {
  const hi = Math.max(...monthly.map((m) => m.temperature_max_c));
  const lo = Math.min(...monthly.map((m) => m.temperature_min_c));
  const min = Math.floor(lo / 5) * 5;
  const max = Math.ceil(hi / 5) * 5;
  const y = (v: number) => PAD.top + innerH - ((v - min) / (max - min)) * innerH;
  const cx = (month: number) => x(month) + slot / 2;
  const band =
    monthly.map((m) => `${cx(m.month)},${y(m.temperature_max_c)}`).join(" ") +
    " " +
    [...monthly].reverse().map((m) => `${cx(m.month)},${y(m.temperature_min_c)}`).join(" ");
  const line = monthly.map((m) => `${cx(m.month)},${y(m.temperature_c)}`).join(" ");
  const summary = `Temperature: average ${Math.round(Math.min(...monthly.map((m) => m.temperature_c)))} to ${Math.round(Math.max(...monthly.map((m) => m.temperature_c)))} °C through the year; hottest hours up to ${hi.toFixed(1)} °C, coolest nights down to ${lo.toFixed(1)} °C.`;
  return (
    <figure className="chart">
      <figcaption className="chart__title">
        Temperature (°C) <span className="chart__legend">line: average · band: coolest night to hottest hour</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
        <SeasonBands seasons={seasons} />
        {[min, (min + max) / 2, max].map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className="chart__grid" />
            <text x={PAD.left - 4} y={y(v) + 3} textAnchor="end" className="chart__tick">
              {Math.round(v)}
            </text>
          </g>
        ))}
        <polygon points={band} className="chart__band" />
        <polyline points={line} className="chart__line" />
        {monthly.map((m) => (
          <circle key={m.month} cx={cx(m.month)} cy={y(m.temperature_c)} r={2.5} className="chart__dot">
            <title>{`${monthName(m.month)}: average ${m.temperature_c.toFixed(1)} °C (${m.temperature_min_c.toFixed(1)} to ${m.temperature_max_c.toFixed(1)})`}</title>
          </circle>
        ))}
        <MonthAxis />
      </svg>
    </figure>
  );
}
