<script lang="ts">
	import {
		Chart,
		LineController,
		LineElement,
		PointElement,
		CategoryScale,
		LinearScale,
		Tooltip,
		Filler
	} from 'chart.js';
	import type { ItemPricePoint } from '$lib/api';
	import { formatMonth, formatCurrency } from '$lib/utils/format';
	import { resolveCssVarColor, withAlpha } from '$lib/utils/chart-colors';

	Chart.register(
		LineController,
		LineElement,
		PointElement,
		CategoryScale,
		LinearScale,
		Tooltip,
		Filler
	);

	let { data = [] }: { data: ItemPricePoint[] } = $props();

	let canvas = $state<HTMLCanvasElement>();
	let chart: Chart<'line'> | null = null;

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

		const lineColor = resolveCssVarColor('--chart-1', 'rgb(56, 189, 248)');
		const mutedForeground = resolveCssVarColor('--muted-foreground', 'rgb(203, 213, 225)');
		const border = resolveCssVarColor('--border', 'rgb(71, 85, 105)');
		const popover = resolveCssVarColor('--popover', 'rgb(15, 23, 42)');
		const popoverForeground = resolveCssVarColor('--popover-foreground', 'rgb(248, 250, 252)');

		const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
		gradient.addColorStop(0, withAlpha(lineColor, 0.3, 'rgb(56, 189, 248)'));
		gradient.addColorStop(1, withAlpha(lineColor, 0.02, 'rgb(56, 189, 248)'));

		chart = new Chart(canvas, {
			type: 'line',
			data: {
				labels: data.map((d) => formatMonth(d.month)),
				datasets: [
					{
						data: data.map((d) => d.avg_unit_price),
						borderColor: lineColor,
						backgroundColor: gradient,
						fill: true,
						borderWidth: 2.5,
						tension: 0,
						pointRadius: 3,
						pointHoverRadius: 5,
						pointBackgroundColor: lineColor,
						pointBorderWidth: 0
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
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
						callbacks: {
							label: (ctx) => {
								const index = ctx.dataIndex;
								const point = data[index];
								if (!point) return `Avg ${formatCurrency(0)}`;
								return `Avg ${formatCurrency(point.avg_unit_price)} (min ${formatCurrency(point.min_unit_price)}, max ${formatCurrency(point.max_unit_price)})`;
							},
							afterLabel: (ctx) => {
								const index = ctx.dataIndex;
								const point = data[index];
								if (!point) return '- Qty 0';
								return `- Qty ${point.purchase_count}`;
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
					y: {
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
			No price trend data for this item yet
		</div>
	{:else}
		<canvas bind:this={canvas}></canvas>
	{/if}
</div>
