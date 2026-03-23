<script lang="ts">
	import { Chart, DoughnutController, ArcElement, Tooltip, Legend } from 'chart.js';
	import type { CategorySpend } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { formatCurrency } from '$lib/utils/format';
	import { resolveCssVarColor, resolveFontFamily } from '$lib/utils/chart-colors';

	Chart.register(DoughnutController, ArcElement, Tooltip, Legend);

	let { data = [] }: { data: CategorySpend[] } = $props();

	let canvas = $state<HTMLCanvasElement>();
	let chart: Chart<'doughnut'> | null = null;

	function destroyChart() {
		if (chart) {
			chart.destroy();
			chart = null;
		}
	}

	function buildChart() {
		destroyChart();
		if (!canvas || data.length === 0) return;

		const total = data.reduce((s, d) => s + d.total_spent, 0);
		const mutedForeground = resolveCssVarColor('--muted-foreground', 'rgb(203, 213, 225)');
		const foreground = resolveCssVarColor('--foreground', 'rgb(248, 250, 252)');
		const popover = resolveCssVarColor('--popover', 'rgb(255, 255, 255)');
		const popoverForeground = resolveCssVarColor('--popover-foreground', 'rgb(15, 23, 42)');
		const border = resolveCssVarColor('--border', 'rgb(226, 232, 240)');
		const card = resolveCssVarColor('--card', 'rgb(255, 255, 255)', true);
		const fontFamily = resolveFontFamily('sans-serif');

		const centerTotalPlugin = {
			id: 'centerTotal',
			afterDraw(chartInstance: Chart<'doughnut'>) {
				const { ctx, chartArea } = chartInstance;
				if (!chartArea) return;

				const centerX = (chartArea.left + chartArea.right) / 2;
				const centerY = (chartArea.top + chartArea.bottom) / 2;
				const dataset = chartInstance.data.datasets[0];
				const selectedTotal = dataset?.data.reduce((sum, value) => sum + Number(value), 0) ?? 0;

				ctx.save();
				ctx.textAlign = 'center';
				ctx.textBaseline = 'middle';
				ctx.fillStyle = mutedForeground;
				ctx.font = `500 12px ${fontFamily}`;
				ctx.fillText(t('dashboard.selected_total'), centerX, centerY - 12);

				ctx.fillStyle = foreground;
				ctx.font = `600 18px ${fontFamily}`;
				ctx.fillText(formatCurrency(selectedTotal), centerX, centerY + 10);
				ctx.restore();
			}
		};

		chart = new Chart(canvas, {
			type: 'doughnut',
			plugins: [centerTotalPlugin],
			data: {
				labels: data.map((d) => `${d.icon} ${d.category_name}`),
				datasets: [
					{
						data: data.map((d) => d.total_spent),
						backgroundColor: data.map((d) => d.color),
						borderColor: card,
						borderWidth: 2,
						hoverOffset: 6
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: true,
				cutout: '65%',
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
								const val = ctx.parsed;
								const pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0';
								return ` ${formatCurrency(val)} (${pct}%)`;
							}
						}
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

<div class="relative mx-auto aspect-square w-full max-w-64">
	{#if data.length === 0}
		<div class="flex h-full items-center justify-center text-sm text-muted-foreground">
			{t('dashboard.no_category_data')}
		</div>
	{:else}
		<canvas class="h-full w-full" bind:this={canvas}></canvas>
	{/if}
</div>
