/**
 * Lightweight i18n module with reactive locale.
 * Uses .svelte.ts extension to enable $state rune in module scope.
 */

import { de } from './de';
import { en } from './en';

import { browser } from '$app/environment';

export type Locale = 'de' | 'en';

const translations: Record<Locale, Record<string, string>> = { de, en };

function normalizeLocale(value: string | null | undefined): Locale {
	return value === 'en' ? 'en' : 'de';
}

function syncDocumentLanguage(nextLocale: Locale): void {
	if (!browser) return;
	document.documentElement.lang = nextLocale;
}

let locale = $state<Locale>(browser ? normalizeLocale(localStorage.getItem('locale')) : 'de');

if (browser) {
	syncDocumentLanguage(locale);
}

/**
 * Reactive translation function with interpolation.
 * Replaces {key} placeholders with values from params.
 */
export function t(key: string, params?: Record<string, string | number>): string {
	let result = translations[locale]?.[key] ?? translations['en']?.[key] ?? key;
	if (params) {
		for (const [k, v] of Object.entries(params)) {
			result = result.replaceAll(`{${k}}`, String(v));
		}
	}
	return result;
}

/** Get the current locale reactively. */
export function getLocale(): Locale {
	return locale;
}

/** Switch locale and persist to localStorage. */
export function setLocale(l: Locale): void {
	const nextLocale = normalizeLocale(l);
	locale = nextLocale;
	if (browser) {
		localStorage.setItem('locale', nextLocale);
		syncDocumentLanguage(nextLocale);
	}
}

/** Available locales with display labels. */
export const AVAILABLE_LOCALES: { value: Locale; label: string }[] = [
	{ value: 'de', label: 'Deutsch' },
	{ value: 'en', label: 'English' }
];
