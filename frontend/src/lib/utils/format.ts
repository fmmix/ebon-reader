import { getLocale } from '$lib/i18n/index.svelte';

/**
 * Format a monetary amount with currency symbol.
 * Defaults to EUR (€). Uses symbol-last format: "1.23 €".
 */
export function formatCurrency(amount: number, currency = '€'): string {
	return `${amount.toFixed(2)} ${currency}`;
}

/**
 * Format a YYYY-MM string into a locale-aware short month + year label.
 * e.g. "2025-01" → "Jan 2025" (en) or "Jan. 2025" (de).
 */
export function formatMonth(ym: string, locale = getLocale()): string {
	const [year, month] = ym.split('-');
	const monthIndex = Number.parseInt(month, 10) - 1;
	const date = new Date(Number(year), monthIndex);
	const monthName = new Intl.DateTimeFormat(locale, { month: 'short' }).format(date);
	return `${monthName} ${year}`;
}

/**
 * Format a numeric value as a percentage string: "1.23%".
 */
export function formatPercent(value: number): string {
	return `${value.toFixed(2)}%`;
}
