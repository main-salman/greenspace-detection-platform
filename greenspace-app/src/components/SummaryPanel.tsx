'use client';

import { CityAnnualSummary } from '@/types';

interface SummaryPanelProps {
  summaries: CityAnnualSummary[];
}

export default function SummaryPanel({ summaries }: SummaryPanelProps) {
  if (!summaries || summaries.length === 0) return null;

  const downloadCSV = () => {
    const headers = [
      'city','country','baselineYear','compareYear','baselineVegetation','compareVegetation','percentChange','vegetationPct','cloudExcludedPct','highPct','medPct','lowPct'
    ];
    const rows = summaries.map(s => [
      s.city.city, s.city.country, s.baselineYear, s.compareYear,
      s.baselineVegetation?.toFixed(3), s.compareVegetation?.toFixed(3), s.percentChange?.toFixed(3),
      (s.vegetationPct ?? 0).toFixed(3), (s.cloudExcludedPct ?? 0).toFixed(3), (s.highPct ?? 0).toFixed(3), (s.medPct ?? 0).toFixed(3), (s.lowPct ?? 0).toFixed(3)
    ].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'greenspace_summary.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const Chart = ({ s }: { s: CityAnnualSummary }) => {
    const months = Array.from({length:12}, (_,i)=>i);
    const ndviBase = s.monthlyNdviMeanBaseline || [];
    const ndviComp = s.monthlyNdviMeanCompare || [];
    const maxNdvi = Math.max(0.01, ...ndviBase, ...ndviComp);
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <span>Monthly NDVI mean</span>
          <span>{s.baselineYear} vs {s.compareYear}</span>
        </div>
        <div className="grid grid-cols-12 gap-1">
          {months.map(m => (
            <div key={m} className="flex flex-col h-24 justify-end">
              <div title={`Compare ${s.compareYear}-${m+1}: ${ndviComp[m]?.toFixed?.(2) ?? '—'}`}
                className="bg-blue-400 w-full"
                style={{ height: `${Math.max(0, (ndviComp[m]||0) / maxNdvi * 90)}%` }} />
              <div title={`Baseline ${s.baselineYear}-${m+1}: ${ndviBase[m]?.toFixed?.(2) ?? '—'}`}
                className="bg-green-400 w-full mt-0.5"
                style={{ height: `${Math.max(0, (ndviBase[m]||0) / maxNdvi * 90)}%` }} />
            </div>
          ))}
        </div>
        <div className="text-xs text-gray-500">Bars show NDVI mean by month: blue={s.compareYear}, green={s.baselineYear}</div>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-800">📈 Multi‑City Annual Summary</h3>
        <button onClick={downloadCSV} className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">Download CSV</button>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-gray-600 border-b">
              <th className="py-2 pr-4">City</th>
              <th className="py-2 pr-4">Baseline %</th>
              <th className="py-2 pr-4">Compare %</th>
              <th className="py-2 pr-4">Change</th>
              <th className="py-2 pr-4">High</th>
              <th className="py-2 pr-4">Med</th>
              <th className="py-2 pr-4">Low</th>
              <th className="py-2 pr-4">Cloud Excl. %</th>
            </tr>
          </thead>
          <tbody>
            {summaries.map((s, idx) => (
              <tr key={idx} className="border-b hover:bg-gray-50">
                <td className="py-2 pr-4 whitespace-nowrap font-medium text-gray-800">{s.city.city}, {s.city.country}</td>
                <td className="py-2 pr-4">{(s.baselineVegetation ?? 0).toFixed(1)}%</td>
                <td className="py-2 pr-4">{(s.compareVegetation ?? 0).toFixed(1)}%</td>
                <td className={`py-2 pr-4 ${((s.percentChange ?? 0) >= 0) ? 'text-green-600' : 'text-red-600'}`}>{(s.percentChange ?? 0).toFixed(1)}%</td>
                <td className="py-2 pr-4">{(s.highPct ?? 0).toFixed(1)}%</td>
                <td className="py-2 pr-4">{(s.medPct ?? 0).toFixed(1)}%</td>
                <td className="py-2 pr-4">{(s.lowPct ?? 0).toFixed(1)}%</td>
                <td className="py-2 pr-4">{(s.cloudExcludedPct ?? 0).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
        {summaries.map((s, idx) => (
          <div key={idx} className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold text-gray-800">{s.city.city}, {s.city.country}</div>
              <div className={`${(s.percentChange ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'} text-sm font-semibold`}>
                {(s.percentChange ?? 0) >= 0 ? '▲' : '▼'} {(s.percentChange ?? 0).toFixed(1)}%
              </div>
            </div>
            <Chart s={s} />
          </div>
        ))}
      </div>
    </div>
  );
}


