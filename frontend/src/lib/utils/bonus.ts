/**
 * All known bonus entry types used across the application.
 */
export const KNOWN_BONUS_TYPES = new Set([
	'action',
	'coupon',
	'redeemed',
	'instant_discount',
	'basket_discount'
]);

/**
 * Bonus types that represent deductions (money taken off the receipt total).
 */
export const DEDUCTION_BONUS_TYPES = new Set(['redeemed', 'instant_discount', 'basket_discount']);

/**
 * Return the translated label for a bonus type, falling back to the raw type string.
 */
export function bonusTypeLabel(type: string, t: (key: string) => string): string {
	return KNOWN_BONUS_TYPES.has(type) ? t(`common.bonus_${type}`) : type;
}

/**
 * Check whether a bonus type represents a deduction.
 */
export function isDeductionBonusType(type: string): boolean {
	return DEDUCTION_BONUS_TYPES.has(type);
}

/**
 * Compute total program savings from bonus entries and the earned bonus total.
 * Program savings = earned bonus + instant discount amounts.
 */
export function computeProgramSavings(
	bonusEntries: { type: string; amount: number }[],
	totalBonus: number
): number {
	const instantDiscountSum = bonusEntries
		.filter((bonus) => bonus.type === 'instant_discount')
		.reduce((sum, bonus) => sum + bonus.amount, 0);
	return totalBonus + instantDiscountSum;
}
