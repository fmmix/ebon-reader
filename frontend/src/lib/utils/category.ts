/**
 * Canonical uncategorized category names (English + German).
 */
export const UNCATEGORIZED_NAMES = new Set(['uncategorized', 'unkategorisiert']);

/**
 * Check whether a category name represents the "uncategorized" fallback.
 */
export function isUncategorizedName(name: string): boolean {
	return UNCATEGORIZED_NAMES.has(name.trim().toLowerCase());
}

/**
 * Find the ID of the uncategorized category from a list of categories.
 * Returns the numeric ID, or '' if not found (for use with select element values).
 */
export function findUncategorizedId(categories: { id: number; name: string }[]): number | '' {
	return categories.find((c) => isUncategorizedName(c.name))?.id ?? '';
}
