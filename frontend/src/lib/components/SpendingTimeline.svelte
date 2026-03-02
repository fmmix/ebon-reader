<script lang="ts">
	import { onMount } from 'svelte';
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

	Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Filler);

	let { data = [] }: { data: MonthlySpend[] } = $props();

	let canvas = $state<HTMLCanvasElement>();
	let chart: Chart<'bar'> | null = null;
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

	function buildChart() {
		if (chart) chart.destroy();
		if (!canvas || data.length === 0) return;

		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const chartBar = resolveCssVarColor('--chart-2', 'rgb(45, 212, 191)');
		const mutedForeground = resolveCssVarColor('--muted-foreground', 'rgb(203, 213, 225)');
		const border = resolveCssVarColor('--border', 'rgb(71, 85, 105)');
		const popover = resolveCssVarColor('--popover', 'rgb(15, 23, 42)');
		const popoverForeground = resolveCssVarColor('--popover-foreground', 'rgb(248, 250, 252)');

		// Gradient fill
		const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
		gradient.addColorStop(0, withAlpha(chartBar, 0.95, 'rgb(45, 212, 191)'));
		gradient.addColorStop(1, withAlpha(chartBar, 0.45, 'rgb(45, 212, 191)'));

		chart = new Chart(canvas, {
			type: 'bar',
			data: {
				labels: data.map((d) => formatMonth(d.month)),
				datasets: [
					{
						data: data.map((d) => d.total_spent),
						backgroundColor: gradient,
						borderColor: withAlpha(chartBar, 0.75, 'rgb(45, 212, 191)'),
						borderWidth: 1.5,
						borderRadius: 6,
						borderSkipped: false
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
							label: (ctx) => ` €${(ctx.parsed.y ?? 0).toFixed(2)}`
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
							callback: (val) => `€${val}`
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

<div class="relative h-64 w-full">
	{#if data.length === 0}
		<div class="flex h-full items-center justify-center text-sm text-muted-foreground">
			No spending data yet
		</div>
	{:else}
		<canvas bind:this={canvas}></canvas>
	{/if}
</div>
