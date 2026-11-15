import { useEffect, useState } from "react";
import { api, type Rotation } from "../api/client";
import { capitalize, monthSpan, signed } from "../format";

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

function columnsOf(rotations: Rotation[], current: Rotation | null): Column[] {
  const cols = rotations.map((r) => ({
    key: `opt-${r.rank}`,
    title: r.is_current ? "Your current rotation" : `Option ${r.rank}`,
    rotation: r,
  }));
  if (current && !rotations.some((r) => r.is_current)) {
    cols.push({ key: "current", title: "Your current rotation", rotation: current });
  }
  return cols;
}

export function CompareTable({ lat, lon, rotations, current }: { lat: number; lon: number; rotations: Rotation[]; current: Rotation | null }) {
  const cols = columnsOf(rotations, current);
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
  const num = (v: number | null) => (v == null ? "Not scored" : v.toFixed(2));

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
      label: `${capitalize(s.name)} (${monthSpan(s.months)})`,
      cells: cols.map((c) => c.rotation.sequence[i]?.crop_name ?? "–"),
      bestIndex: [],
    })),
    { label: "Overall score (0 to 1)", cells: score.map((v) => v.toFixed(2)), bestIndex: best(score) },
    { label: "Climate", cells: climate.map(num), bestIndex: best(climate) },
    { label: "Water", cells: water.map(num), bestIndex: best(water) },
    { label: "Soil", cells: soil.map(num), bestIndex: best(soil) },
    ...(current
      ? [
          {
            label: "Compared with what you grow now",
            cells: cols.map((c) =>
              c.rotation.is_current || c.key === "current" ? "Baseline" : c.rotation.score_delta_vs_current != null ? signed(c.rotation.score_delta_vs_current) : "–",
            ),
            bestIndex: [],
          },
        ]
      : []),
    {
      label: "Past seasons with a failed crop",
      hint: "Worst crop of the rotation in NASA daily weather since 2000, sown on the 15th of each season's first month",
      cells: cols.map((c) => {
        if (!failures) return "Checking…";
        const f = failures[c.key];
        return f ? `${f.failed} of ${f.of}` : "Not available";
      }),
      bestIndex: failures ? best(failed, false) : [],
    },
    { label: "Benefits", cells: benefits.map(String), bestIndex: best(benefits) },
    { label: "Things to watch", cells: risks.map(String), bestIndex: best(risks, false) },
  ];

  return (
    <section className="panel stack compare" aria-labelledby="compare-title">
      <div>
        <span className="eyebrow">Compare</span>
        <h2 id="compare-title">Options side by side</h2>
        <p className="muted small">The best value in each row is marked with ✓.</p>
      </div>
      <div className="table-scroll">
        <table className="compare__table">
          <thead>
            <tr>
              <td />
              {cols.map((c, i) => (
                <th key={c.key} scope="col" className={i === 0 ? "compare__col--best" : undefined}>
                  {c.title}
                  {i === 0 && !c.rotation.is_current && <span className="tag compare__tag">Recommended</span>}
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
                    {row.bestIndex.includes(i) && <span className="visually-hidden"> (best)</span>}
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
