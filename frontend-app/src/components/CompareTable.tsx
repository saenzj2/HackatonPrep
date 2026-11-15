import { useEffect, useState } from "react";
import { api, type Rotation } from "../api/client";
import { useCropName } from "../cropNames";
import { capitalize, monthSpan, signed } from "../format";
import { useI18n } from "../i18n";

// Side-by-side comparison of the recommended options and the farmer's current rotation: one column
// per option, one row per measure. The best value in each row is marked with a check and bold text
// (never color alone). Past-weather failures come from POST /plan-risk, one call per option.

interface Column {
  key: string;
  title: string;
  rotation: Rotation;
}

/** Worst crop of a rotation in the past-weather check: failed years out of evaluated years. */
type Failures = { failed: number; of: number } | null;

type Tr = (en: string, es: string) => string;

function columnsOf(rotations: Rotation[], current: Rotation | null, tr: Tr): Column[] {
  const cols = rotations.map((r) => ({
    key: `opt-${r.rank}`,
    title: r.is_current ? tr("Your current rotation", "Su rotación actual") : tr(`Option ${r.rank}`, `Opción ${r.rank}`),
    rotation: r,
  }));
  if (current && !rotations.some((r) => r.is_current)) {
    cols.push({ key: "current", title: tr("Your current rotation", "Su rotación actual"), rotation: current });
  }
  return cols;
}

export function CompareTable({ lat, lon, rotations, current }: { lat: number; lon: number; rotations: Rotation[]; current: Rotation | null }) {
  const { tr, lang, num } = useI18n();
  const cropName = useCropName();
  const cols = columnsOf(rotations, current, tr);
  const [failures, setFailures] = useState<Record<string, Failures> | null>(null);
  const key = JSON.stringify({ lat, lon, cols: cols.map((c) => c.rotation.sequence.map((s) => s.crop_id)) });

  useEffect(() => {
    let active = true;
    setFailures(null);
    Promise.all(
      cols.map((c) =>
        api
          .planRisk({
            lat,
            lon,
            // Same default as the past-weather section: the 15th of each season's first month.
            plantings: c.rotation.sequence.map((s) => ({ crop: s.crop_id, sowing_month: s.months[0], sowing_day: 15 })),
          })
          .then((r): Failures => {
            const worst = r.plantings.reduce((a, b) => (b.failed_years > a.failed_years ? b : a));
            return { failed: worst.failed_years, of: worst.years.length };
          })
          .catch((): Failures => null),
      ),
    ).then((list) => {
      if (active) setFailures(Object.fromEntries(cols.map((c, i) => [c.key, list[i]])));
    });
    return () => {
      active = false;
    };
  }, [key]);

  if (cols.length < 2) return null;

  const seasons = cols[0].rotation.sequence.map((s) => ({ name: s.season, months: s.months }));
  const score2 = (v: number | null) => (v == null ? tr("Not scored", "Sin puntaje") : num(v));

  // Columns with the best value in a row (ties all count); empty when every column ties.
  const best = (values: (number | null)[], higherIsBetter = true): number[] => {
    const known = values.filter((v): v is number => v != null);
    if (known.length < 2 || known.every((v) => v === known[0])) return [];
    const target = higherIsBetter ? Math.max(...known) : Math.min(...known);
    return values.flatMap((v, i) => (v === target ? [i] : []));
  };

  type Row = { label: string; cells: string[]; bestIndex: number[]; hint?: string };
  const score = cols.map((c) => c.rotation.score);
  const climate = cols.map((c) => c.rotation.breakdown.climate);
  const water = cols.map((c) => c.rotation.breakdown.water);
  const soil = cols.map((c) => c.rotation.breakdown.soil);
  const benefits = cols.map((c) => c.rotation.benefits.length);
  const risks = cols.map((c) => c.rotation.risks.length);
  const failed = cols.map((c) => failures?.[c.key]?.failed ?? null);

  const rows: Row[] = [
    ...seasons.map((s, i) => ({
      label: `${capitalize(s.name)} (${monthSpan(s.months, lang)})`,
      cells: cols.map((c) => {
        const step = c.rotation.sequence[i];
        return step ? cropName(step.crop_id, step.crop_name) : "–";
      }),
      bestIndex: [],
    })),
    { label: tr("Overall score (0 to 1)", "Puntaje total (0 a 1)"), cells: score.map((v) => num(v)), bestIndex: best(score) },
    { label: tr("Climate", "Clima"), cells: climate.map(score2), bestIndex: best(climate) },
    { label: tr("Water", "Agua"), cells: water.map(score2), bestIndex: best(water) },
    { label: tr("Soil", "Suelo"), cells: soil.map(score2), bestIndex: best(soil) },
    ...(current
      ? [
          {
            label: tr("Compared with what you grow now", "Comparada con lo que siembra hoy"),
            cells: cols.map((c) =>
              c.rotation.is_current || c.key === "current" ? tr("Baseline", "Punto de partida") : c.rotation.score_delta_vs_current != null ? signed(c.rotation.score_delta_vs_current, lang) : "–",
            ),
            bestIndex: [],
          },
        ]
      : []),
    {
      label: tr("Past seasons with a failed crop", "Temporadas pasadas con un cultivo perdido"),
      hint: tr(
        "Worst crop of the rotation in NASA daily weather since 2000, sown on the 15th of each season's first month",
        "Cultivo con peor resultado de la rotación según el clima diario de la NASA desde el 2000, sembrado el 15 del primer mes de cada época",
      ),
      cells: cols.map((c) => {
        if (!failures) return tr("Checking…", "Revisando…");
        const f = failures[c.key];
        return f ? tr(`${f.failed} of ${f.of}`, `${f.failed} de ${f.of}`) : tr("Not available", "No disponible");
      }),
      bestIndex: failures ? best(failed, false) : [],
    },
    { label: tr("Benefits", "Beneficios"), cells: benefits.map(String), bestIndex: best(benefits) },
    { label: tr("Things to watch", "Aspectos a vigilar"), cells: risks.map(String), bestIndex: best(risks, false) },
  ];

  return (
    <section className="panel stack compare" aria-labelledby="compare-title">
      <div>
        <span className="eyebrow">{tr("Compare", "Comparar")}</span>
        <h2 id="compare-title">{tr("Options side by side", "Opciones lado a lado")}</h2>
        <p className="muted small">{tr("The best value in each row is marked with ✓.", "El mejor valor de cada fila lleva ✓.")}</p>
      </div>
      <div className="table-scroll">
        <table className="compare__table">
          <thead>
            <tr>
              <td />
              {cols.map((c, i) => (
                <th key={c.key} scope="col" className={i === 0 ? "compare__col--best" : undefined}>
                  {c.title}
                  {i === 0 && !c.rotation.is_current && <span className="tag compare__tag">{tr("Recommended", "Recomendada")}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <th scope="row">
                  {row.label}
                  {row.hint && <span className="compare__hint">{row.hint}</span>}
                </th>
                {row.cells.map((cell, i) => (
                  <td key={cols[i].key} className={[i === 0 ? "compare__col--best" : "", row.bestIndex.includes(i) ? "compare__best" : ""].join(" ").trim() || undefined}>
                    {row.bestIndex.includes(i) && (
                      <span aria-hidden="true" className="compare__check">
                        ✓{" "}
                      </span>
                    )}
                    {cell}
                    {row.bestIndex.includes(i) && <span className="visually-hidden">{tr(" (best)", " (mejor)")}</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
