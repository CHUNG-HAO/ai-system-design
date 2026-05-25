"use client";

import { Vital } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from "recharts";

export default function VitalsChart({ vitals }: { vitals: Vital[] }) {
  if (!vitals.length)
    return <div className="text-sm text-slate-400">無生命徵象資料</div>;

  const data = vitals.map((v) => ({
    name: `seq${v.sequence_no}\n${v.phase}`,
    SBP: v.sbp,
    HR: v.hr,
    RR: v.rr,
    SpO2: v.spo2,
    GCS: v.gcs,
  }));

  return (
    <div className="w-full h-64">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" fontSize={11} />
          <YAxis fontSize={11} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="SBP" stroke="#dc2626" strokeWidth={2} dot />
          <Line type="monotone" dataKey="HR" stroke="#2563eb" strokeWidth={2} dot />
          <Line type="monotone" dataKey="RR" stroke="#16a34a" strokeWidth={2} dot />
          <Line type="monotone" dataKey="SpO2" stroke="#9333ea" strokeWidth={2} dot />
          <Line type="monotone" dataKey="GCS" stroke="#ea580c" strokeWidth={2} dot />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
