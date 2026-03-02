export function formatVatClass(vatClass: string): string {
	const normalized = vatClass.trim().toUpperCase();

	if (normalized === 'A') {
		return '19%';
	}

	if (normalized === 'B') {
		return '7%';
	}

	return vatClass;
}
