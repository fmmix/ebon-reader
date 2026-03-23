<script lang="ts">
	import {
		Chart,
		BarController,
		BarElement,
		LineController,
		LineElement,
		PointElement,
		CategoryScale,
		LinearScale,
		Tooltip,
		Legend
	} from 'chart.js';
	import type { PointStyle } from 'chart.js';
	import type { MonthlyBonusByShopStat, MonthlyBonusStat } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { formatMonth, formatCurrency, formatPercent } from '$lib/utils/format';
	import { resolveCssVarColor, withAlpha } from '$lib/utils/chart-colors';

	Chart.register(
		BarController,
		BarElement,
		LineController,
		LineElement,
		PointElement,
		CategoryScale,
		LinearScale,
		Tooltip,
		Legend
	);

	type BonusChartMode = 'total' | 'perShop';

	let {
		data = [],
		dataByShop = [],
		mode = 'total'
	}: {
		data: MonthlyBonusStat[];
		dataByShop: MonthlyBonusByShopStat[];
		mode: BonusChartMode;
	} = $props();

	let canvas = $state<HTMLCanvasElement>();
	let chart: Chart | null = null;

	function destroyChart(): void {
		if (chart) {
			chart.destroy();
			chart = null;
		}
	}

	const MAX_STORE_SERIES = 4;
	const BRAND_COLORS: Record<string, string> = {
		'REWE Markt GmbH': '#CC081F',
		Kaufland: '#FFD9DF',
		Lidl: '#0050AA',
		EDEKA: '#004C96'
	};
	const FALLBACK_COLOR = '#64748b';

	function brandColorForStore(storeName: string): string {
		return BRAND_COLORS[storeName] ?? FALLBACK_COLOR;
	}

	function flatRectangleMarker(color: string): HTMLCanvasElement | PointStyle {
		if (typeof document === 'undefined') return 'rect';

		const marker = document.createElement('canvas');
		marker.width = 16;
		marker.height = 10;

		const markerCtx = marker.getContext('2d');
		if (!markerCtx) return 'rect';

		markerCtx.clearRect(0, 0, marker.width, marker.height);
		markerCtx.fillStyle = color;
		markerCtx.fillRect(1, 2, 14, 6);
		return marker;
	}

	function seriesStyleForStore(storeName: string): {
		color: string;
		pointStyle: PointStyle | HTMLCanvasElement;
	} {
		const color = brandColorForStore(storeName);

		if (storeName === 'REWE Markt GmbH') {
			return { color, pointStyle: flatRectangleMarker(color) };
		}

		if (storeName === 'Kaufland') {
			return { color, pointStyle: 'rect' };
		}

		if (storeName === 'Lidl') {
			return { color, pointStyle: 'circle' };
		}

		return { color, pointStyle: 'circle' };
	}

	function buildPerShopSeries(): {
		labels: string[];
		datasets: {
			type: 'bar' | 'line';
			label: string;
			data: Array<number | null>;
			metric: 'savings' | 'rate';
			yAxisID: 'yAmount' | 'yRate';
			borderColor: string;
			backgroundColor: string;
			pointBackgroundColor: string;
			pointStyle: PointStyle | HTMLCanvasElement;
			borderRadius?: number;
			borderSkipped?: false;
			order: number;
			borderDash: number[];
			borderWidth: number;
			pointRadius: number;
			pointHoverRadius: number;
			tension: number;
			fill: boolean;
			spanGaps: boolean;
		}[];
	} {
		type StoreMonthAggregate = {
			programSavings: number;
			rateNumerator: number;
			rateWeight: number;
		};

		const monthKeys = Array.from(
			new Set([...data.map((row) => row.month), ...dataByShop.map((row) => row.month)])
		).sort();
		const storeTotals = new Map<string, number>();
		const monthStoreMetrics = new Map<string, Map<string, StoreMonthAggregate>>();

		for (const row of dataByShop) {
			if (row.total_spent <= 0 && row.receipt_count <= 0) continue;

			const weight = row.total_spent > 0 ? row.total_spent : Math.max(row.receipt_count, 1);
			storeTotals.set(row.store_name, (storeTotals.get(row.store_name) ?? 0) + row.program_savings);

			const monthMap = monthStoreMetrics.get(row.month) ?? new Map<string, StoreMonthAggregate>();
			const aggregate = monthMap.get(row.store_name) ?? {
				programSavings: 0,
				rateNumerator: 0,
				rateWeight: 0
			};

			aggregate.programSavings += row.program_savings;
			aggregate.rateNumerator += row.bonus_rate * weight;
			aggregate.rateWeight += weight;

			monthMap.set(row.store_name, aggregate);
			monthStoreMetrics.set(row.month, monthMap);
		}

		const rankedStores = Array.from(storeTotals.entries())
			.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
			.map(([store]) => store);

		const visibleStores = rankedStores.slice(0, MAX_STORE_SERIES);
		const hiddenStores = new Set(rankedStores.slice(MAX_STORE_SERIES));

		const datasets: {
			type: 'bar' | 'line';
			label: string;
			data: Array<number | null>;
			metric: 'savings' | 'rate';
			yAxisID: 'yAmount' | 'yRate';
			borderColor: string;
			backgroundColor: string;
			pointBackgroundColor: string;
			pointStyle: PointStyle | HTMLCanvasElement;
			borderRadius?: number;
			borderSkipped?: false;
			order: number;
			borderDash: number[];
			borderWidth: number;
			pointRadius: number;
			pointHoverRadius: number;
			tension: number;
			fill: boolean;
			spanGaps: boolean;
		}[] = [];

		for (const storeName of visibleStores) {
			const style = seriesStyleForStore(storeName);
			const savingsData = monthKeys.map((month) => {
				const aggregate = monthStoreMetrics.get(month)?.get(storeName);
				return aggregate ? aggregate.programSavings : null;
			});
			const rateData = monthKeys.map((month) => {
				const aggregate = monthStoreMetrics.get(month)?.get(storeName);
				if (!aggregate || aggregate.rateWeight <= 0) return null;
				return aggregate.rateNumerator / aggregate.rateWeight;
			});

			datasets.push({
				type: 'bar',
				label: `${storeName} · ${t('analytics.program_savings')}`,
				data: savingsData,
				metric: 'savings',
				yAxisID: 'yAmount',
				borderColor: withAlpha(style.color, 0.5, FALLBACK_COLOR),
				backgroundColor: withAlpha(style.color, 0.24, FALLBACK_COLOR),
				pointBackgroundColor: style.color,
				pointStyle: style.pointStyle,
				borderRadius: 5,
				borderSkipped: false,
				order: 2,
				borderDash: [],
				borderWidth: 1,
				pointRadius: 0,
				pointHoverRadius: 0,
				tension: 0,
				fill: false,
				spanGaps: false
			});

			datasets.push({
				type: 'line',
				label: `${storeName} · ${t('analytics.program_savings_rate')}`,
				data: rateData,
				metric: 'rate',
				yAxisID: 'yRate',
				borderColor: style.color,
				backgroundColor: withAlpha(style.color, 0.15, FALLBACK_COLOR),
				pointBackgroundColor: style.color,
				pointStyle: style.pointStyle,
				order: 1,
				borderDash: [6, 4],
				borderWidth: 1.6,
				pointRadius: 2.5,
				pointHoverRadius: 4,
				tension: 0.24,
				fill: false,
				spanGaps: false
			});
		}

		if (hiddenStores.size > 0) {
			const otherColor = FALLBACK_COLOR;
			const otherStyle = seriesStyleForStore(t('analytics.bonus_other'));

			const otherSavings = monthKeys.map((month) => {
				const monthMap = monthStoreMetrics.get(month);
				if (!monthMap) return null;

				let total = 0;
				let hasValue = false;
				for (const [storeName, aggregate] of monthMap.entries()) {
					if (!hiddenStores.has(storeName)) continue;
					hasValue = true;
					total += aggregate.programSavings;
				}

				return hasValue ? total : null;
			});

			const otherRates = monthKeys.map((month) => {
				const monthMap = monthStoreMetrics.get(month);
				if (!monthMap) return null;

				let numerator = 0;
				let weight = 0;
				for (const [storeName, aggregate] of monthMap.entries()) {
					if (!hiddenStores.has(storeName)) continue;
					numerator += aggregate.rateNumerator;
					weight += aggregate.rateWeight;
				}

				if (weight <= 0) return null;
				return numerator / weight;
			});

			datasets.push({
				type: 'bar',
				label: `${t('analytics.bonus_other')} · ${t('analytics.program_savings')}`,
				data: otherSavings,
				metric: 'savings',
				yAxisID: 'yAmount',
				borderColor: withAlpha(otherColor, 0.5, FALLBACK_COLOR),
				backgroundColor: withAlpha(otherColor, 0.24, FALLBACK_COLOR),
				pointBackgroundColor: otherColor,
				pointStyle: otherStyle.pointStyle,
				borderRadius: 5,
				borderSkipped: false,
				order: 2,
				borderDash: [4, 3],
				borderWidth: 1,
				pointRadius: 0,
				pointHoverRadius: 0,
				tension: 0,
				fill: false,
				spanGaps: false
			});

			datasets.push({
				type: 'line',
				label: `${t('analytics.bonus_other')} · ${t('analytics.program_savings_rate')}`,
				data: otherRates,
				metric: 'rate',
				yAxisID: 'yRate',
				borderColor: otherColor,
				backgroundColor: withAlpha(otherColor, 0.12, FALLBACK_COLOR),
				pointBackgroundColor: otherColor,
				pointStyle: otherStyle.pointStyle,
				order: 1,
				borderDash: [7, 4],
				borderWidth: 1.5,
				pointRadius: 2.25,
				pointHoverRadius: 3.75,
				tension: 0.24,
				fill: false,
				spanGaps: false
			});
		}

		return {
			labels: monthKeys.map((month) => formatMonth(month)),
			datasets
		};
	}

	function buildChart(): void {
		destroyChart();
		if (!canvas) return;
		if (mode === 'total' && data.length === 0) return;
		if (mode === 'perShop' && dataByShop.length === 0) return;

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const mutedForeground = resolveCssVarColor('--muted-foreground', 'rgb(203, 213, 225)');
		const border = resolveCssVarColor('--border', 'rgb(71, 85, 105)');
		const popover = resolveCssVarColor('--popover', 'rgb(15, 23, 42)');
		const popoverForeground = resolveCssVarColor('--popover-foreground', 'rgb(248, 250, 252)');

		if (mode === 'perShop') {
			const perShop = buildPerShopSeries();
			chart = new Chart(canvas, {
				type: 'bar',
				data: {
					labels: perShop.labels,
					datasets: perShop.datasets
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					interaction: {
						mode: 'index',
						intersect: false
					},
					plugins: {
						legend: {
							labels: {
								color: mutedForeground,
								boxWidth: 10,
								boxHeight: 10,
								usePointStyle: true
							}
						},
						tooltip: {
							backgroundColor: popover,
							titleColor: popoverForeground,
							bodyColor: popoverForeground,
							borderColor: border,
							borderWidth: 1,
							padding: 10,
							cornerRadius: 8,
							callbacks: {
								label: (tooltipCtx) => {
									const datasetLabel = tooltipCtx.dataset.label ?? '';
									const value = typeof tooltipCtx.parsed.y === 'number' ? tooltipCtx.parsed.y : 0;
									const metric = (tooltipCtx.dataset as { metric?: 'savings' | 'rate' }).metric;
									return `${datasetLabel}: ${metric === 'rate' ? formatPercent(value) : formatCurrency(value)}`;
								}
							}
						}
					},
					scales: {
						x: {
							grid: { display: false },
							ticks: {
								color: mutedForeground,
								font: { size: 11 }
							},
							border: { display: false }
						},
						yAmount: {
							type: 'linear',
							position: 'left',
							grid: {
								color: withAlpha(border, 0.25, 'rgb(71, 85, 105)')
							},
							ticks: {
								color: mutedForeground,
								font: { size: 11 },
								callback: (value) => {
									const numericValue = typeof value === 'number' ? value : Number(value);
									return formatCurrency(Number.isFinite(numericValue) ? numericValue : 0);
								}
							},
							border: { display: false }
						},
						yRate: {
							type: 'linear',
							position: 'right',
							grid: { drawOnChartArea: false },
							ticks: {
								color: mutedForeground,
								font: { size: 11 },
								callback: (value) => {
									const numericValue = typeof value === 'number' ? value : Number(value);
									return formatPercent(Number.isFinite(numericValue) ? numericValue : 0);
								}
							},
							border: { display: false }
						}
					}
				}
			});
			return;
		}

		const barColor = resolveCssVarColor('--chart-2', 'rgb(45, 212, 191)');
		const lineColor = resolveCssVarColor('--chart-1', 'rgb(56, 189, 248)');

		const barGradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
		barGradient.addColorStop(0, withAlpha(barColor, 0.9, 'rgb(45, 212, 191)'));
		barGradient.addColorStop(1, withAlpha(barColor, 0.35, 'rgb(45, 212, 191)'));

		chart = new Chart(canvas, {
			type: 'bar',
			data: {
				labels: data.map((d) => formatMonth(d.month)),
				datasets: [
					{
						type: 'bar',
						label: t('analytics.program_savings'),
						data: data.map((d) => d.program_savings),
						backgroundColor: barGradient,
						borderColor: withAlpha(barColor, 0.75, 'rgb(45, 212, 191)'),
						borderWidth: 1.25,
						borderRadius: 6,
						borderSkipped: false,
						yAxisID: 'yAmount'
					},
					{
						type: 'line',
						label: t('analytics.program_savings_rate'),
						data: data.map((d) => d.bonus_rate),
						borderColor: lineColor,
						backgroundColor: withAlpha(lineColor, 0.25, 'rgb(56, 189, 248)'),
						pointBackgroundColor: lineColor,
						pointBorderWidth: 0,
						pointRadius: 3,
						pointHoverRadius: 5,
						tension: 0.3,
						borderWidth: 2.5,
						yAxisID: 'yRate'
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: {
					mode: 'index',
					intersect: false
				},
				plugins: {
					legend: {
						labels: {
							color: mutedForeground,
							boxWidth: 10,
							boxHeight: 10,
							usePointStyle: true,
							pointStyle: 'circle'
						}
					},
					tooltip: {
						backgroundColor: popover,
						titleColor: popoverForeground,
						bodyColor: popoverForeground,
						borderColor: border,
						borderWidth: 1,
						padding: 10,
						cornerRadius: 8,
						callbacks: {
							label: (tooltipCtx) => {
								const point = data[tooltipCtx.dataIndex];
								if (!point) return '';

								if (tooltipCtx.dataset.type === 'line') {
									return `${t('analytics.program_savings_rate')}: ${formatPercent(point.bonus_rate)}`;
								}

								return `${t('analytics.program_savings')}: ${formatCurrency(point.program_savings)}`;
							},
							afterBody: (items) => {
								const point = data[items[0]?.dataIndex ?? -1];
								if (!point) return [];
								return [
									`${t('analytics.earned_bonus')}: ${formatCurrency(point.earned_bonus)}`,
									`${t('analytics.instant_discount')}: ${formatCurrency(point.instant_discount)}`,
									`${t('analytics.redeemed_bonus')}: ${formatCurrency(point.redeemed_bonus)}`,
									`${t('analytics.total_spent')}: ${formatCurrency(point.total_spent)}`
								];
							}
						}
					}
				},
				scales: {
					x: {
						grid: { display: false },
						ticks: {
							color: mutedForeground,
							font: { size: 11 }
						},
						border: { display: false }
					},
					yAmount: {
						type: 'linear',
						position: 'left',
						grid: {
							color: withAlpha(border, 0.25, 'rgb(71, 85, 105)')
						},
						ticks: {
							color: mutedForeground,
							font: { size: 11 },
							callback: (value) => {
								const numericValue = typeof value === 'number' ? value : Number(value);
								return formatCurrency(Number.isFinite(numericValue) ? numericValue : 0);
							}
						},
						border: { display: false }
					},
					yRate: {
						type: 'linear',
						position: 'right',
						grid: { drawOnChartArea: false },
						ticks: {
							color: mutedForeground,
							font: { size: 11 },
							callback: (value) => {
								const numericValue = typeof value === 'number' ? value : Number(value);
								return formatPercent(Number.isFinite(numericValue) ? numericValue : 0);
							}
						},
						border: { display: false }
					}
				}
			}
		});
	}

	$effect(() => {
		void mode;
		void data;
		void dataByShop;
		if (canvas) {
			buildChart();
		}

		return () => {
			destroyChart();
		};
	});

	let isEmpty = $derived(mode === 'total' ? data.length === 0 : dataByShop.length === 0);
</script>

<div class="relative h-72 w-full">
	{#if isEmpty}
		<div class="flex h-full items-center justify-center text-sm text-muted-foreground">
			{mode === 'total' ? t('analytics.bonus_empty') : t('analytics.bonus_per_shop_empty')}
		</div>
	{:else}
		<canvas bind:this={canvas}></canvas>
	{/if}
</div>
