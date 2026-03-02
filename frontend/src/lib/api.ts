function resolveApiBase(): string {
	if (typeof window === 'undefined') {
		return 'http://127.0.0.1:8000';
	}

	const { protocol, hostname, origin } = window.location;
	const isTauriHost = hostname === 'tauri.localhost' || hostname.endsWith('.tauri.localhost');
	const isDesktopProtocol = protocol === 'tauri:' || protocol === 'file:';

	if (isTauriHost || isDesktopProtocol) {
		return 'http://127.0.0.1:8000';
	}

	if (protocol === 'http:' || protocol === 'https:') {
		return '';
	}

	console.info('[api] resolved base for unknown protocol', { protocol, hostname, origin });
	return '';
}

const BASE = resolveApiBase();

if (typeof window !== 'undefined') {
	console.info('[api] resolved API base', {
		base: BASE,
		origin: window.location.origin
	});
}

function resolveApiUrl(path: string): string {
	return `${BASE}${path}`;
}

function apiFetch(path: string, options?: RequestInit): Promise<Response> {
	return fetch(resolveApiUrl(path), options);
}

interface ApiError {
	status: number;
	message: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
	const res = await apiFetch(path, {
		headers: { 'Content-Type': 'application/json', ...options?.headers },
		...options
	});
	if (!res.ok) {
		const error: ApiError = { status: res.status, message: await res.text() };
		throw error;
	}
	return res.json();
}

// --- Health ---

export function healthCheck() {
	return request<{ status: string; app: string }>('/api/health');
}

// --- Settings ---

export interface HardResetSummary {
	message: string;
	deleted?: Record<string, number>;
}

export interface DebugImportTextResponse {
	text: string;
	pages: number;
	characters: number;
}

export function hardResetData() {
	return request<HardResetSummary>('/api/settings/hard-reset', {
		method: 'POST'
	});
}

export async function extractDebugImportText(file: File): Promise<DebugImportTextResponse> {
	const form = new FormData();
	form.append('file', file);
	const res = await apiFetch('/api/settings/debug-import-text', { method: 'POST', body: form });
	if (!res.ok) throw { status: res.status, message: await res.text() };
	return res.json();
}

// --- Categories ---

export interface ProductCategory {
	id: number;
	name: string;
	icon: string;
	color: string;
	is_default: boolean;
	item_count?: number;
	total_spend?: number;
}

export function fetchCategories() {
	return request<ProductCategory[]>('/api/categories/');
}

export function createCategory(data: { name: string; icon: string; color: string }) {
	return request<ProductCategory>('/api/categories/', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function updateCategory(
	id: number,
	data: { name?: string; icon?: string; color?: string }
) {
	return request<ProductCategory>(`/api/categories/${id}`, {
		method: 'PATCH',
		body: JSON.stringify(data)
	});
}

export async function deleteCategory(id: number) {
	const res = await apiFetch(`/api/categories/${id}`, { method: 'DELETE' });
	if (!res.ok) throw { status: res.status, message: await res.text() };
}

// --- Import (Feature 2/3) ---

export interface ParsedItem {
	raw_name: string;
	display_name: string;
	unit_price: number;
	quantity: number;
	total_price: number;
	vat_class: string;
	is_deposit: boolean;
	category_id: number | null;
	confidence: number;
	method: string;
	matched_rule_keyword: string | null;
	matched_rule_match_type: string | null;
	matched_rule_priority: number | null;
}

export interface BonusInfo {
	type: string;
	description: string;
	amount: number;
}

export interface PreviewResponse {
	store_name: string;
	store_address: string;
	store_id: string | null;
	register_nr: number | null;
	bon_nr: string | null;
	beleg_nr: string | null;
	purchased_at: string;
	total_amount: number;
	tse_transaction: string | null;
	is_duplicate: boolean;
	items: ParsedItem[];
	bonus_entries: BonusInfo[];
	total_bonus: number;
	bonus_balance: number | null;
	computed_total: number;
}

export async function uploadForPreview(file: File): Promise<PreviewResponse> {
	const form = new FormData();
	form.append('file', file);
	const res = await apiFetch('/api/import/preview', { method: 'POST', body: form });
	if (!res.ok) throw { status: res.status, message: await res.text() };
	return res.json();
}

export interface DebugTextResponse {
	raw_text: string;
}

export async function uploadForDebugText(file: File): Promise<DebugTextResponse> {
	const form = new FormData();
	form.append('file', file);
	const res = await apiFetch('/api/import/debug-text', { method: 'POST', body: form });
	if (!res.ok) throw { status: res.status, message: await res.text() };
	return res.json();
}

export interface ConfirmItem {
	raw_name: string;
	display_name: string;
	unit_price: number;
	quantity: number;
	total_price: number;
	vat_class: string;
	is_deposit: boolean;
	category_id: number | null;
	is_manual_assignment: boolean;
}

export interface ConfirmRequest {
	store_name: string;
	store_address: string;
	store_id: string | null;
	register_nr: number | null;
	bon_nr: string | null;
	beleg_nr: string | null;
	purchased_at: string;
	total_amount: number;
	tse_transaction: string | null;
	source_filename: string;
	items: ConfirmItem[];
	bonus_entries: BonusInfo[];
	total_bonus: number;
	bonus_balance: number | null;
}

export interface ConfirmResponse {
	id: number;
	message: string;
}

export function confirmImport(body: ConfirmRequest) {
	return request<ConfirmResponse>('/api/import/confirm', {
		method: 'POST',
		body: JSON.stringify(body)
	});
}

// --- Receipts (Feature 6) ---

export interface Receipt {
	id: number;
	purchased_at: string;
	store_name: string;
	store_address: string;
	total_amount: number;
	total_bonus: number;
	source_filename: string;
	item_count: number;
}

export interface ReceiptItemDetail {
	id: number;
	raw_name: string;
	display_name: string;
	unit_price: number;
	quantity: number;
	total_price: number;
	vat_class: string;
	is_deposit: boolean;
	is_manual_assignment: boolean;
	category_id: number | null;
	category_name: string | null;
	category_icon: string | null;
}

export interface ReceiptBonusEntry {
	id: number;
	type: string;
	description: string;
	amount: number;
}

export interface ReceiptDetail {
	id: number;
	purchased_at: string;
	store_name: string;
	store_address: string;
	total_amount: number;
	total_bonus: number;
	bonus_balance: number | null;
	source_filename: string;
	tse_transaction: string | null;
	bon_nr: string | null;
	store_id: string | null;
	register_nr: number | null;
	imported_at: string;
	items: ReceiptItemDetail[];
	bonus_entries: ReceiptBonusEntry[];
}

export function fetchReceipts() {
	return request<Receipt[]>('/api/receipts/');
}

export function fetchReceiptDetail(id: number) {
	return request<ReceiptDetail>(`/api/receipts/${id}`);
}

export async function deleteReceipt(id: number) {
	const res = await apiFetch(`/api/receipts/${id}`, { method: 'DELETE' });
	if (!res.ok) throw { status: res.status, message: await res.text() };
}

export function updateItemCategory(receiptId: number, itemId: number, categoryId: number | null) {
	return request<{ id: number; category_id: number | null; is_manual_assignment: boolean; category_name: string | null; category_icon: string | null }>(
		`/api/receipts/${receiptId}/items/${itemId}`,
		{
			method: 'PATCH',
			body: JSON.stringify({ category_id: categoryId })
		}
	);
}

// --- Rules (Feature 5) ---

export interface CategorizeRule {
	id: number;
	keyword: string;
	match_type: string;
	category_id: number;
	category_name: string;
	priority: number;
}

export function fetchRules(categoryId?: number) {
	const params = categoryId ? `?category_id=${categoryId}` : '';
	return request<CategorizeRule[]>(`/api/rules/${params}`);
}

export function createRule(data: {
	keyword: string;
	match_type: string;
	category_id: number;
	priority?: number;
}) {
	return request<CategorizeRule>('/api/rules/', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function updateRule(id: number, data: Partial<Omit<CategorizeRule, 'id' | 'category_name'>>) {
	return request<CategorizeRule>(`/api/rules/${id}`, {
		method: 'PATCH',
		body: JSON.stringify(data)
	});
}

export async function deleteRule(id: number) {
	const res = await apiFetch(`/api/rules/${id}`, { method: 'DELETE' });
	if (!res.ok) throw { status: res.status, message: await res.text() };
}

export function deleteAllRules() {
	return request<{ deleted: number }>('/api/rules/all', {
		method: 'DELETE'
	});
}

export interface ReCategorizeResponse {
	total_items: number;
	processed_items: number;
	updated_items: number;
	unchanged_items: number;
	skipped_manual_items: number;
	overridden_manual_items: number;
	categorized_items: number;
	uncategorized_items: number;
}

export interface ReCategorizeChange {
	from_category_id: number | null;
	from_category_name: string;
	to_category_id: number | null;
	to_category_name: string;
	item_count: number;
}

export interface ReCategorizePreviewResponse extends ReCategorizeResponse {
	changes: ReCategorizeChange[];
}

export interface TaxonomyCategoryPayload {
	name: string;
	icon: string;
	color: string;
	is_default: boolean;
}

export interface TaxonomyRulePayload {
	keyword: string;
	match_type: string;
	category_name: string;
	priority: number;
}

export interface TaxonomyBundle {
	version: number;
	exported_at: string | null;
	categories: TaxonomyCategoryPayload[];
	rules: TaxonomyRulePayload[];
}

export interface TaxonomyReplacePreviewResponse {
	incoming_categories: number;
	incoming_rules: number;
	normalized_categories: number;
	normalized_rules: number;
	existing_categories: number;
	existing_rules: number;
	receipt_items_total: number;
	remap_matched_items: number;
	fallback_uncategorized_items: number;
	skipped_rules_missing_category: number;
	will_ensure_uncategorized: boolean;
}

export interface TaxonomyReplaceApplyResponse extends TaxonomyReplacePreviewResponse {
	backup_id: number;
}

export interface TaxonomyBackupInfo {
	id: number;
	created_at: string;
	categories_count: number;
	rules_count: number;
}

export function reCategorizeItems(overrideManual = false) {
	return request<ReCategorizeResponse>('/api/rules/re-categorize', {
		method: 'POST',
		body: JSON.stringify({ override_manual: overrideManual })
	});
}

export function previewReCategorizeItems(overrideManual = false) {
	return request<ReCategorizePreviewResponse>('/api/rules/re-categorize/preview', {
		method: 'POST',
		body: JSON.stringify({ override_manual: overrideManual })
	});
}

export function exportTaxonomy() {
	return request<TaxonomyBundle>('/api/rules/taxonomy/export');
}

export function previewTaxonomyReplace(bundle: TaxonomyBundle) {
	return request<TaxonomyReplacePreviewResponse>('/api/rules/taxonomy/replace/preview', {
		method: 'POST',
		body: JSON.stringify(bundle)
	});
}

export function applyTaxonomyReplace(bundle: TaxonomyBundle) {
	return request<TaxonomyReplaceApplyResponse>('/api/rules/taxonomy/replace/apply', {
		method: 'POST',
		body: JSON.stringify(bundle)
	});
}

export function fetchTaxonomyBackups() {
	return request<TaxonomyBackupInfo[]>('/api/rules/taxonomy/backups');
}

export function fetchTaxonomyBackupBundle(id: number) {
	return request<TaxonomyBundle>(`/api/rules/taxonomy/backups/${id}`);
}

// --- Stats (Feature 7/8) ---

export interface OverviewStats {
	total_spent: number;
	receipt_count: number;
	item_count: number;
	avg_basket: number;
	total_bonus: number;
	redeemed_bonus: number;
}

export interface CategorySpend {
	category_id: number | null;
	category_name: string;
	icon: string;
	color: string;
	total_spent: number;
	item_count: number;
}

export interface MonthlySpend {
	month: string; // YYYY-MM
	total_spent: number;
	receipt_count: number;
}

export interface MonthlyBonusStat {
	month: string; // YYYY-MM
	total_spent: number;
	earned_bonus: number;
	redeemed_bonus: number;
	bonus_rate: number;
	receipt_count: number;
}

export interface CategoryMonthlySpend {
	month: string; // YYYY-MM
	category_id: number | null;
	category_name: string;
	icon: string;
	color: string;
	total_spent: number;
}

export interface TopItemStat {
	item_name: string;
	purchase_count: number;
	total_quantity: number;
	total_spent: number;
	avg_unit_price: number;
}

export interface ItemPricePoint {
	month: string; // YYYY-MM
	avg_unit_price: number;
	min_unit_price: number;
	max_unit_price: number;
	purchase_count: number;
}

export function fetchOverview() {
	return request<OverviewStats>('/api/stats/overview');
}

export function fetchCategoryBreakdown(includeDeposit = false) {
	const params = new URLSearchParams({ include_deposit: String(includeDeposit) });
	return request<CategorySpend[]>(`/api/stats/category-breakdown?${params.toString()}`);
}

export function fetchMonthlyTrend() {
	return request<MonthlySpend[]>('/api/stats/monthly-trend');
}

export function fetchMonthlyBonus() {
	return request<MonthlyBonusStat[]>('/api/stats/monthly-bonus');
}

export function fetchCategoryMonthly() {
	return request<CategoryMonthlySpend[]>('/api/stats/category-monthly');
}

export function fetchTopItems(limit = 20) {
	return request<TopItemStat[]>(`/api/stats/top-items?limit=${limit}`);
}

export function fetchItemPriceTrend(itemName: string) {
	const params = new URLSearchParams({ item_name: itemName });
	return request<ItemPricePoint[]>(`/api/stats/item-price-trend?${params.toString()}`);
}
