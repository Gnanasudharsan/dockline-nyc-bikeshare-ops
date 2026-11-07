"use client";

import { useEffect, useRef } from "react";
import type { Finding, TokenColor } from "@/lib/types";

function token(name: TokenColor | "ink" | "line"): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
}

/** ECharts rendering of a finding's chart, in Dockline tokens, with direct value labels. */
export function Chart({ chart, title }: { chart: NonNullable<Finding["chart"]>; title: string }) {
  const element = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let instance:
      { dispose: () => void; resize: () => void; setOption: (o: unknown) => void } | undefined;

    async function render() {
      const echarts = await import("echarts");
      if (disposed || !element.current) return;
      instance?.dispose();
      instance = echarts.init(element.current, undefined, { renderer: "svg" });
      const percent = chart.unit === "percent";
      const format = (value: number) =>
        percent ? `${(value * 100).toFixed(1)}%` : value.toLocaleString("en-US");
      const horizontal = chart.kind === "bar";
      // On narrow screens the bars carry their own labels; axis and dense value labels collide.
      const narrow = element.current.clientWidth < 560;
      const categoryAxis = {
        type: "category",
        data: chart.categories,
        axisLabel: { color: token("slate") },
        axisLine: { lineStyle: { color: token("line") } },
        axisTick: { show: false },
      };
      const valueAxis = {
        type: "value",
        axisLabel: { color: token("slate"), formatter: format, show: !(narrow && horizontal) },
        splitLine: { lineStyle: { color: token("line") } },
      };
      instance.setOption({
        aria: { enabled: true, label: { description: title } },
        animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        textStyle: {
          // ECharts measures text itself, so it needs the resolved family, not a CSS variable.
          fontFamily: getComputedStyle(document.body).fontFamily,
          color: token("ink"),
        },
        grid: {
          left: horizontal ? 110 : 48,
          right: 56,
          top: chart.series.length > 1 ? 36 : 12,
          bottom: 28,
        },
        legend:
          chart.series.length > 1
            ? { top: 0, left: 0, itemGap: 20, textStyle: { color: token("ink"), fontSize: 12 } }
            : undefined,
        tooltip: { trigger: "axis", valueFormatter: (value: number) => format(value) },
        xAxis: horizontal ? valueAxis : categoryAxis,
        yAxis: horizontal ? { ...categoryAxis, inverse: true } : valueAxis,
        series: chart.series.map((series) => ({
          name: series.name,
          type: chart.kind === "line" ? "line" : "bar",
          data: series.values,
          itemStyle: { color: token(series.color) },
          barMaxWidth: 22,
          label: {
            show: chart.categories.length <= (narrow ? 6 : 10),
            position: horizontal ? "right" : "top",
            color: token("ink"),
            formatter: ({ value }: { value: number | null }) =>
              value === null ? "" : format(value),
            fontSize: 11,
          },
        })),
      });
    }

    void render();
    const resize = () => instance?.resize();
    const rerender = () => void render();
    window.addEventListener("resize", resize);
    window.addEventListener("dockline-theme", rerender);
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", rerender);
    return () => {
      disposed = true;
      window.removeEventListener("resize", resize);
      window.removeEventListener("dockline-theme", rerender);
      media.removeEventListener("change", rerender);
      instance?.dispose();
    };
  }, [chart, title]);

  const height = chart.kind === "bar" ? Math.max(180, chart.categories.length * 34 + 60) : 280;
  return <div ref={element} style={{ height }} className="w-full" role="img" aria-label={title} />;
}
