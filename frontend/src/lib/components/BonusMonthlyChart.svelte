<script lang="ts">
	import { onMount } from 'svelte';
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
	import type { MonthlyBonusStat } from '$lib/api';

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

	let { data = [] }: { data: MonthlyBonusStat[] } = $props();

	let canvas = $state<HTMLCanvasElement>();
	let chart: Chart | null = null;
	let colorCtx: CanvasRenderingContext2D | null = null;

	function formatMonth(ym: string): string {
		const [y, m] = ym.split('-');
		const months = [
			'Jan',
			'Feb',
			'Mar',
			'Apr',
			'May',
			'Jun',
			'Jul',
			'Aug',
			'Sep',
			'Oct',
			'Nov',
			'Dec'
		];
		return `${months[parseInt(m) - 1]} ${y.slice(2)}`;
	}

	function formatEuro(value: number): string {
		return `€${value.toFixed(2)}`;
	}

	function formatPercent(value: number): string {
		return `${value.toFixed(2)}%`;
	}

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

	function resolveCssVarColor(varName: string, fallback: string): string {
		if (typeof document === 'undefined') return fallback;

		const el = document.createElement('span');
		el.style.position = 'absolute';
		el.style.visibility = 'hidden';
		el.style.pointerEvents = 'none';
		el.style.color = `var(${varName})`;

		document.body.appendChild(el);

		try {
			const resolved = getComputedStyle(el).color.trim();
			return toCanvasColor(resolved || fallback, fallback);
		} finally {
			el.remove();
		}
	}

	function withAlpha(color: string, alpha: number, fallback: string): string {
		const normalized = toCanvasColor(color, fallback).trim();
		let r = 0;
		let g = 0;
		let b = 0;

		const hex = normalized.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
		if (hex) {
			const value = hex[1];
			if (value.length === 3) {
				r = parseInt(value[0] + value[0], 16);
				g = parseInt(value[1] + value[1], 16);
				b = parseInt(value[2] + value[2], 16);
			} else {
				r = parseInt(value.slice(0, 2), 16);
				g = parseInt(value.slice(2, 4), 16);
				b = parseInt(value.slice(4, 6), 16);
			}
		} else {
			const rgb = normalized.match(
				/^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*(?:\d*\.?\d+))?\s*\)$/i
			);
			if (!rgb) {
				const fallbackNormalized = toCanvasColor(fallback, fallback).trim();
				const fallbackRgb = fallbackNormalized.match(
					/^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*(?:\d*\.?\d+))?\s*\)$/i
				);
				if (!fallbackRgb) return `rgba(59, 130, 246, ${Math.max(0, Math.min(1, alpha))})`;
				r = Number(fallbackRgb[1]);
				g = Number(fallbackRgb[2]);
				b = Number(fallbackRgb[3]);
			} else {
				r = Number(rgb[1]);
				g = Number(rgb[2]);
				b = Number(rgb[3]);
			}
		}

		const clampedAlpha = Math.max(0, Math.min(1, alpha));
		return `rgba(${r}, ${g}, ${b}, ${clampedAlpha})`;
	}

	function buildChart(): void {
		if (chart) chart.destroy();
		if (!canvas || data.length === 0) return;

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const barColor = resolveCssVarColor('--chart-2', 'rgb(45, 212, 191)');
		const lineColor = resolveCssVarColor('--chart-1', 'rgb(56, 189, 248)');
		const mutedForeground = resolveCssVarColor('--muted-foreground', 'rgb(203, 213, 225)');
		const border = resolveCssVarColor('--border', 'rgb(71, 85, 105)');
		const popover = resolveCssVarColor('--popover', 'rgb(15, 23, 42)');
		const popoverForeground = resolveCssVarColor('--popover-foreground', 'rgb(248, 250, 252)');

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
						label: 'Earned bonus',
						data: data.map((d) => d.earned_bonus),
						backgroundColor: barGradient,
						borderColor: withAlpha(barColor, 0.75, 'rgb(45, 212, 191)'),
						borderWidth: 1.25,
						borderRadius: 6,
						borderSkipped: false,
						yAxisID: 'yAmount'
					},
					{
						type: 'line',
						label: 'Bonus rate',
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
							label: (ctx) => {
								const point = data[ctx.dataIndex];
								if (!point) return '';

								if (ctx.dataset.type === 'line') {
									return `Bonus rate: ${formatPercent(point.bonus_rate)}`;
								}

								return `Earned bonus: ${formatEuro(point.earned_bonus)}`;
							},
							afterBody: (items) => {
								const point = data[items[0]?.dataIndex ?? -1];
								if (!point) return [];
								return [
									`Redeemed bonus: ${formatEuro(point.redeemed_bonus)}`,
									`Total spent: ${formatEuro(point.total_spent)}`
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
								return formatEuro(Number.isFinite(numericValue) ? numericValue : 0);
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

	onMount(() => {
		buildChart();
	});

	$effect(() => {
		if (data && canvas) buildChart();
	});
</script>

<div class="relative h-72 w-full">
	{#if data.length === 0}
		<div class="flex h-full items-center justify-center text-sm text-muted-foreground">
			No monthly bonus data yet
		</div>
	{:else}
		<canvas bind:this={canvas}></canvas>
	{/if}
</div>
