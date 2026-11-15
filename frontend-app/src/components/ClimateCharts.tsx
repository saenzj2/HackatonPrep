import type { MonthlyClimate, SeasonSummary } from "../api/client";
import { capitalize, monthName } from "../format";
import { useI18n } from "../i18n";

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
  const { lang } = useI18n();
  return (
    <>
      {Array.from({ length: 12 }, (_, i) => (
        <text key={i} x={x(i + 1) + slot / 2} y={H - 8} textAnchor="middle" className="chart__tick">
          {monthName(i + 1, lang).charAt(0).toUpperCase()}
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
  const { tr, lang } = useI18n();
  const max = niceMax(Math.max(...monthly.map((m) => m.rainfall_mm)), 100);
  const wettest = monthly.reduce((a, b) => (b.rainfall_mm > a.rainfall_mm ? b : a));
  const driest = monthly.reduce((a, b) => (b.rainfall_mm < a.rainfall_mm ? b : a));
  const summary = tr(
    `Rain per month: wettest ${monthName(wettest.month, lang)} (${Math.round(wettest.rainfall_mm)} mm), driest ${monthName(driest.month, lang)} (${Math.round(driest.rainfall_mm)} mm).`,
    `Lluvia por mes: el más lluvioso es ${monthName(wettest.month, lang)} (${Math.round(wettest.rainfall_mm)} mm) y el más seco ${monthName(driest.month, lang)} (${Math.round(driest.rainfall_mm)} mm).`,
  );
  return (
    <figure className="chart">
      <figcaption className="chart__title">{tr("Rain per month (mm)", "Lluvia por mes (mm)")}</figcaption>
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
              <title>{`${monthName(m.month, lang)}: ${Math.round(m.rainfall_mm)} mm`}</title>
            </rect>
          );
        })}
        <MonthAxis />
      </svg>
    </figure>
  );
}

export function TemperatureChart({ monthly, seasons }: { monthly: MonthlyClimate[]; seasons: SeasonSummary[] }) {
  const { tr, lang, num } = useI18n();
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
  const avgLo = Math.round(Math.min(...monthly.map((m) => m.temperature_c)));
  const avgHi = Math.round(Math.max(...monthly.map((m) => m.temperature_c)));
  const summary = tr(
    `Temperature: average ${avgLo} to ${avgHi} °C through the year; hottest hours up to ${num(hi, 1)} °C, coolest nights down to ${num(lo, 1)} °C.`,
    `Temperatura: promedio de ${avgLo} a ${avgHi} °C durante el año; las horas más calientes llegan a ${num(hi, 1)} °C y las noches más frescas bajan a ${num(lo, 1)} °C.`,
  );
  return (
    <figure className="chart">
      <figcaption className="chart__title">
        {tr("Temperature (°C)", "Temperatura (°C)")}{" "}
        <span className="chart__legend">
          {tr("line: average · band: coolest night to hottest hour", "línea: promedio · franja: de la noche más fresca a la hora más caliente")}
        </span>
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
            <title>
              {tr(
                `${monthName(m.month, lang)}: average ${num(m.temperature_c, 1)} °C (${num(m.temperature_min_c, 1)} to ${num(m.temperature_max_c, 1)})`,
                `${monthName(m.month, lang)}: promedio ${num(m.temperature_c, 1)} °C (${num(m.temperature_min_c, 1)} a ${num(m.temperature_max_c, 1)})`,
              )}
            </title>
          </circle>
        ))}
        <MonthAxis />
      </svg>
    </figure>
  );
}
