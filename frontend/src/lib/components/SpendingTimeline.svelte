<script lang="ts">
	import {
		Chart,
		BarController,
		BarElement,
		CategoryScale,
		LinearScale,
		Tooltip,
		Filler
	} from 'chart.js';
	import type { MonthlySpend } from '$lib/api';
	import { formatMonth, formatCurrency } from '$lib/utils/format';
	import { resolveCssVarColor, withAlpha } from '$lib/utils/chart-colors';
	import { t } from '$lib/i18n/index.svelte';

	Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Filler);

	let { data = [] }: { data: MonthlySpend[] } = $props();

	let canvas = $state<HTMLCanvasElement>();
	let chart: Chart<'bar'> | null = null;

	function capitalizeLabel(label: string) {
		return label.length > 0 ? `${label[0].toUpperCase()}${label.slice(1)}` : label;
	}

	function destroyChart() {
		if (chart) {
			chart.destroy();
			chart = null;
		}
	}

	function buildChart() {
		destroyChart();
		if (!canvas || data.length === 0) return;

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const paidBar = resolveCssVarColor('--chart-1', 'rgb(59, 130, 246)');
		const deductionBar = resolveCssVarColor('--chart-2', 'rgb(45, 212, 191)');
		const paidTooltipMarker = withAlpha(paidBar, 0.72, 'rgb(59, 130, 246)');
		const deductionFill = withAlpha(deductionBar, 0.22, 'rgb(45, 212, 191)');
		const deductionStroke = withAlpha(deductionBar, 0.38, 'rgb(45, 212, 191)');
		const mutedForeground = resolveCssVarColor('--muted-foreground', 'rgb(203, 213, 225)');
		const border = resolveCssVarColor('--border', 'rgb(71, 85, 105)');
		const popover = resolveCssVarColor('--popover', 'rgb(15, 23, 42)');
		const popoverForeground = resolveCssVarColor('--popover-foreground', 'rgb(248, 250, 252)');
		const paidTooltipLabel = capitalizeLabel(t('dashboard.paid_label'));

		// Per-month deductions
		const deductions = data.map(
			(d) => (d.redeemed_bonus ?? 0) + (d.instant_discount ?? 0) + (d.basket_discount ?? 0)
		);
		const hasDeductions = deductions.some((d) => d > 0);

		// Paid = basket value minus deductions
		const paid = data.map((d, i) => d.total_spent - deductions[i]);

		// Gradient fill for paid portion
		const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
		gradient.addColorStop(0, withAlpha(paidBar, 0.92, 'rgb(59, 130, 246)'));
		gradient.addColorStop(0.55, withAlpha(paidBar, 0.72, 'rgb(59, 130, 246)'));
		gradient.addColorStop(1, withAlpha(paidBar, 0.42, 'rgb(59, 130, 246)'));

		const datasets: any[] = [
			{
				label: t('dashboard.paid_label'),
				tooltipLabel: paidTooltipLabel,
				data: paid,
				backgroundColor: gradient,
				borderColor: withAlpha(paidBar, 0.8, 'rgb(59, 130, 246)'),
				borderWidth: 1.5,
				borderRadius: hasDeductions ? { bottomLeft: 6, bottomRight: 6 } : 6,
				borderSkipped: false
			}
		];

		if (hasDeductions) {
				datasets.push({
					label: t('dashboard.deductions'),
					tooltipLabel: t('dashboard.deductions'),
					data: deductions,
					backgroundColor: deductionFill,
					borderColor: deductionStroke,
					borderWidth: 1,
					borderRadius: { topLeft: 6, topRight: 6 },
					borderSkipped: false
			});
		}

		chart = new Chart(canvas, {
			type: 'bar',
			data: {
				labels: data.map((d) => formatMonth(d.month)),
				datasets
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: {
					mode: 'index',
					intersect: false
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: popover,
						titleColor: popoverForeground,
						bodyColor: popoverForeground,
						borderColor: border,
						borderWidth: 1,
						padding: 10,
						cornerRadius: 8,
						multiKeyBackground: 'transparent',
						displayColors: true,
						usePointStyle: true,
						itemSort: (a, b) => b.datasetIndex - a.datasetIndex,
						callbacks: {
							beforeBody: (tooltipItems) => {
								const idx = tooltipItems[0]?.dataIndex;
								if (idx === undefined) return [];
								return [`${t('dashboard.basket_total')}: ${formatCurrency(data[idx].total_spent)}`];
							},
							label: (tooltipCtx) => {
								const dataset = tooltipCtx.dataset as { tooltipLabel?: string };
								const value = typeof tooltipCtx.parsed.y === 'number' ? tooltipCtx.parsed.y : 0;
								const formattedValue =
									tooltipCtx.datasetIndex === 1
										? `-${formatCurrency(value)}`
										: formatCurrency(value);
								return `${dataset.tooltipLabel ?? tooltipCtx.dataset.label}: ${formattedValue}`;
							},
							labelColor: (tooltipCtx) => ({
								borderColor:
									tooltipCtx.datasetIndex === 1
										? deductionStroke
										: withAlpha(paidBar, 0.8, 'rgb(59, 130, 246)'),
								backgroundColor:
									tooltipCtx.datasetIndex === 1 ? deductionFill : paidTooltipMarker,
								borderWidth: 1,
								borderRadius: 3
							}),
							labelPointStyle: () => ({
								pointStyle: 'rectRounded',
								rotation: 0
							})
						}
					}
				},
				scales: {
					x: {
						stacked: true,
						grid: { display: false },
						ticks: {
							color: mutedForeground,
							font: { size: 11 }
						},
						border: { display: false }
					},
					y: {
						stacked: true,
						grid: {
							color: withAlpha(border, 0.25, 'rgb(71, 85, 105)')
						},
						ticks: {
							color: mutedForeground,
							font: { size: 11 },
							callback: (val) => formatCurrency(typeof val === 'number' ? val : Number(val))
						},
						border: { display: false }
					}
				}
			}
		});
	}

	$effect(() => {
		void data;
		if (canvas) {
			buildChart();
		}

		return () => {
			destroyChart();
		};
	});
</script>

<div class="relative h-64 w-full">
	{#if data.length === 0}
		<div class="flex h-full items-center justify-center text-sm text-muted-foreground">
			{t('dashboard.no_spending_data')}
		</div>
	{:else}
		<canvas bind:this={canvas}></canvas>
	{/if}
</div>
