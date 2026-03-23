const DEFAULT_PRIORITY = 20;

/**
 * Clamp a rule priority value to the valid range [0, 100].
 * Returns the default priority if the value is not a finite number.
 */
export function clampPriority(value: number, defaultVal = DEFAULT_PRIORITY): number {
	if (!Number.isFinite(value)) {
		return defaultVal;
	}
	return Math.min(100, Math.max(0, Math.round(value)));
}
