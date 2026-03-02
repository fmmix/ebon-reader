<script lang="ts">
	import { onMount } from 'svelte';
	import { Chart, DoughnutController, ArcElement, Tooltip, Legend } from 'chart.js';
	import type { CategorySpend } from '$lib/api';

	Chart.register(DoughnutController, ArcElement, Tooltip, Legend);

	let { data = [] }: { data: CategorySpend[] } = $props();

	let canvas = $state<HTMLCanvasElement>();
	let chart: Chart<'doughnut'> | null = null;
	let colorCtx: CanvasRenderingContext2D | null = null;
	let fontProbe: HTMLElement | null = null;

	function toCanvasColor(color: string, fallback: string): string {
		if (typeof document === 'undefined') return fallback;

		if (!colorCtx) {
			const colorCanvas = document.createElement('canvas');
			colorCtx = colorCanvas.getContext('2d');
		}

		if (!colorCtx) return fallback;

		colorCtx.fillStyle = fallback;
		const baseline = colorCtx.fillStyle;
		colorCtx.fillStyle = color;

		const normalized = colorCtx.fillStyle;
		return normalized && normalized !== baseline ? normalized : baseline;
	}

	function resolveCssVarColor(varName: string, fallback: string, useHslVar = false): string {
		if (typeof document === 'undefined') return fallback;

		const el = document.createElement('span');
		el.style.position = 'absolute';
		el.style.visibility = 'hidden';
		el.style.pointerEvents = 'none';
		el.style.color = useHslVar ? `hsl(var(${varName}))` : `var(${varName})`;

		document.body.appendChild(el);

		try {
			const resolved = getComputedStyle(el).color.trim();
			return toCanvasColor(resolved || fallback, fallback);
		} finally {
			el.remove();
		}
	}

	function resolveFontFamily(fallback: string): string {
		if (typeof document === 'undefined') return fallback;

		if (!fontProbe) {
			fontProbe = document.createElement('span');
			fontProbe.style.position = 'absolute';
			fontProbe.style.visibility = 'hidden';
			fontProbe.style.pointerEvents = 'none';
			document.body.appendChild(fontProbe);
		}

		const family = getComputedStyle(fontProbe).fontFamily.trim();
		return family || fallback;
	}

	function buildChart() {
		if (chart) chart.destroy();
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
				ctx.fillText('Selected total', centerX, centerY - 12);

				ctx.fillStyle = foreground;
				ctx.font = `600 18px ${fontFamily}`;
				ctx.fillText(`${selectedTotal.toFixed(2)} €`, centerX, centerY + 10);
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
								return ` €${val.toFixed(2)} (${pct}%)`;
							}
						}
					}
				}
			}
		});
	}

	onMount(() => {
		buildChart();
	});

	$effect(() => {
		// Re-render when data changes
		if (data && canvas) buildChart();
	});
</script>

<div class="relative mx-auto aspect-square w-full max-w-64">
	{#if data.length === 0}
		<div class="flex h-full items-center justify-center text-sm text-muted-foreground">
			No category data yet
		</div>
	{:else}
		<canvas class="h-full w-full" bind:this={canvas}></canvas>
	{/if}
</div>
