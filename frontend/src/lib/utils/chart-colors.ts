/**
 * Shared color helpers for Chart.js components.
 *
 * Provides CSS-variable-aware color resolution, alpha blending,
 * and font detection — all backed by a singleton canvas context.
 */

let colorCtx: CanvasRenderingContext2D | null = null;
let fontProbe: HTMLElement | null = null;

/**
 * Normalize a CSS color string to a canvas-recognized format.
 * Returns the fallback if the color is not recognized.
 */
export function toCanvasColor(color: string, fallback: string): string {
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

/**
 * Resolve a CSS custom property to a canvas-compatible color string.
 * Supports both `var(--name)` and `hsl(var(--name))` via the `useHslVar` flag.
 */
export function resolveCssVarColor(
	varName: string,
	fallback: string,
	useHslVar = false
): string {
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

/**
 * Apply an alpha channel to a CSS color string.
 * Parses hex (#rgb / #rrggbb) and rgb/rgba formats.
 */
export function withAlpha(color: string, alpha: number, fallback: string): string {
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
			if (!fallbackRgb) return `rgba(100, 116, 139, ${Math.max(0, Math.min(1, alpha))})`;
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

/**
 * Resolve the computed font-family from the document body.
 * Used for rendering text on canvas (e.g. chart center labels).
 */
export function resolveFontFamily(fallback: string): string {
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
