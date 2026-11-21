import type { EvaluationReport } from '../../types/sentrax';

export function ScorecardRibbon({ report }: { report: EvaluationReport }) {
  const { adversarial_suite: cases, total_payloads: total } = report;
  const scores = [
    { label: 'Baseline bypass', rate: report.baseline_bypass_rate, count: cases.filter((item) => item.baseline_bypassed).length },
    { label: 'Sentra-X bypass', rate: report.sentrax_bypass_rate, count: cases.filter((item) => item.sentrax_bypassed).length },
  ];

  return (
    <dl className="grid grid-cols-1 gap-3 min-[380px]:grid-cols-2">
      {scores.map(({ label, rate, count }) => {
        const hasCount = rate !== null && total > 0 && cases.length === total
          && ((count / total) * 100).toFixed(1) === rate.toFixed(1);
        return (
          <div key={label} className="surface p-4 sm:p-5">
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="mt-1 text-2xl font-semibold tabular-nums">
              {rate === null ? 'Unavailable' : `${rate.toFixed(1)}%`}
            </dd>
            <dd className="mt-1 text-sm text-muted-foreground">
              {rate === null ? 'Case results are incomplete.' : hasCount ? `${count} of ${total} bypassed` : 'Case count unavailable.'}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
