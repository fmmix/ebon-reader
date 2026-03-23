<script lang="ts">
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import * as Separator from '$lib/components/ui/separator';
	import {
		FileUp,
		FileText,
		Loader2,
		CheckCircle2,
		CheckCheck,
		AlertTriangle,
		Gift,
		Ticket,
		Sparkles,
		SkipForward,
		XCircle,
		CircleDollarSign
	} from '@lucide/svelte';
	import {
		uploadForPreview,
		confirmImport,
		createRule,
		fetchCategories,
		type PreviewResponse,
		type ParsedItem,
		type ProductCategory
	} from '$lib/api';
	import { formatDateTime } from '$lib/utils/date';
	import { formatVatClass } from '$lib/utils/vat';
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { formatCurrency } from '$lib/utils/format';
	import { bonusTypeLabel, isDeductionBonusType, computeProgramSavings } from '$lib/utils/bonus';
	import { findUncategorizedId } from '$lib/utils/category';
	import { clampPriority } from '$lib/utils/rules';

	// --- Types ---
	type ItemRuleCreateState = 'idle' | 'saving' | 'created' | 'exists' | 'error';
	type RuleMatchType = 'contains' | 'exact';

	interface ItemRuleCreateStatus {
		state: ItemRuleCreateState;
		message?: string;
	}

	interface ItemRuleDraft {
		keyword: string;
		matchType: RuleMatchType;
		priority: number;
	}

	interface QueueEntry {
		filename: string;
		preview: PreviewResponse;
		items: ParsedItem[];
		ruleCreateByItem: Record<number, ItemRuleCreateStatus>;
		ruleDraftByItem: Record<number, ItemRuleDraft>;
		editableTotalAmount: string;
		editablePurchasedAt: string;
		requiresReview: boolean;
		status: 'pending' | 'confirmed' | 'skipped' | 'error';
		errorMsg?: string;
	}

	interface RequiredFieldValidation {
		isValid: boolean;
		amountError: string | null;
		purchasedAtError: string | null;
		normalizedTotalAmount: number | null;
		normalizedPurchasedAt: string | null;
	}

	// --- State ---
	let categories = $state<ProductCategory[]>([]);
	let queue = $state<QueueEntry[]>([]);
	let currentIndex = $state(0);
	let confirming = $state(false);
	let dragOver = $state(false);
	let error = $state('');
	let parseProgress = $state({ done: 0, total: 0 });
	let parseErrors = $state<string[]>([]);

	// Phases: 'idle' | 'parsing' | 'reviewing' | 'done'
	let phase = $state<'idle' | 'parsing' | 'reviewing' | 'done'>('idle');

	onMount(async () => {
		categories = await fetchCategories();
	});

	// --- Derived ---
	let current = $derived(queue[currentIndex] as QueueEntry | undefined);
	let pendingCount = $derived(queue.filter((e) => e.status === 'pending').length);
	let confirmedCount = $derived(queue.filter((e) => e.status === 'confirmed').length);
	let skippedCount = $derived(queue.filter((e) => e.status === 'skipped').length);
	let errorCount = $derived(queue.filter((e) => e.status === 'error').length);
	let currentRequiredValidation = $derived(current ? validateRequiredFields(current) : null);
	let currentHasAnomaly = $derived(current ? hasEntryAnomaly(current) : false);
	let currentShowsReviewPanel = $derived(
		current ? current.requiresReview || currentHasAnomaly : false
	);
	let currentHasRequiredFieldEdits = $derived(current ? hasRequiredFieldEdits(current) : false);
	let currentReviewPanelState = $derived(current ? getReviewPanelState(current) : null);
	let uncategorizedId = $derived(findUncategorizedId(categories));

	const DEFAULT_RULE_PRIORITY = 20;

	function toDateTimeLocalValue(value: string): string {
		if (!value) return '';
		const parsed = new Date(value);
		if (Number.isNaN(parsed.getTime())) return '';

		const year = parsed.getFullYear();
		const month = String(parsed.getMonth() + 1).padStart(2, '0');
		const day = String(parsed.getDate()).padStart(2, '0');
		const hours = String(parsed.getHours()).padStart(2, '0');
		const minutes = String(parsed.getMinutes()).padStart(2, '0');

		return `${year}-${month}-${day}T${hours}:${minutes}`;
	}

	function parseAmountInput(value: string): number | null {
		const normalized = value.trim().replace(',', '.');
		if (!normalized) return null;
		const parsed = Number(normalized);
		return Number.isFinite(parsed) ? parsed : null;
	}

	function validateRequiredFields(entry: QueueEntry): RequiredFieldValidation {
		const parsedAmount = parseAmountInput(entry.editableTotalAmount);
		let amountError: string | null = null;
		if (!entry.editableTotalAmount.trim()) {
			amountError = t('import.err_amount_required');
		} else if (parsedAmount === null) {
			amountError = t('import.err_invalid_number');
		} else if (parsedAmount <= 0) {
			amountError = t('import.err_amount_positive');
		}

		const purchasedAtRaw = entry.editablePurchasedAt.trim();
		const parsedPurchasedAt = purchasedAtRaw ? new Date(purchasedAtRaw) : null;
		const purchasedAtInvalid = !parsedPurchasedAt || Number.isNaN(parsedPurchasedAt.getTime());
		const normalizedPurchasedAt = purchasedAtInvalid
			? null
			: purchasedAtRaw.length === 16
				? `${purchasedAtRaw}:00`
				: purchasedAtRaw;
		const purchasedAtError = !purchasedAtRaw
			? t('import.err_date_required')
			: purchasedAtInvalid
				? t('import.err_invalid_date')
				: null;

		return {
			isValid: !amountError && !purchasedAtError,
			amountError,
			purchasedAtError,
			normalizedTotalAmount: amountError ? null : parsedAmount,
			normalizedPurchasedAt: purchasedAtError ? null : normalizedPurchasedAt
		};
	}

	function getEffectiveTotalAmount(entry: QueueEntry): number {
		const validation = validateRequiredFields(entry);
		return validation.normalizedTotalAmount ?? entry.preview.total_amount;
	}

	function formatReceiptDate(entry: QueueEntry): string {
		const editablePurchasedAt = entry.editablePurchasedAt.trim();
		const editableDate = editablePurchasedAt ? new Date(editablePurchasedAt) : null;
		if (editableDate && !Number.isNaN(editableDate.getTime())) {
			return formatDateTime(editableDate);
		}

		const previewDate = new Date(entry.preview.purchased_at);
		if (!Number.isNaN(previewDate.getTime())) {
			return formatDateTime(previewDate);
		}

		return t('import.err_missing_date');
	}

	function hasTotalMismatch(entry: QueueEntry): boolean {
		return Math.abs(entry.preview.computed_total - getEffectiveTotalAmount(entry)) > 0.009;
	}

	function hasRequiredFieldEdits(entry: QueueEntry): boolean {
		const seededTotalAmount = Number.isFinite(entry.preview.total_amount)
			? entry.preview.total_amount.toFixed(2)
			: '';
		const seededPurchasedAt = toDateTimeLocalValue(entry.preview.purchased_at);

		return (
			entry.editableTotalAmount !== seededTotalAmount ||
			entry.editablePurchasedAt !== seededPurchasedAt
		);
	}

	function getReviewPanelState(entry: QueueEntry): 'error' | 'warning' | 'success' {
		const validation = validateRequiredFields(entry);
		if (!validation.isValid) return 'error';
		if (hasTotalMismatch(entry)) return 'warning';
		return 'success';
	}

	function hasEntryAnomaly(entry: QueueEntry): boolean {
		const validation = validateRequiredFields(entry);
		return hasTotalMismatch(entry) || !validation.isValid;
	}

	function getValidationErrorMessage(validation: RequiredFieldValidation): string {
		if (validation.amountError && validation.purchasedAtError) {
			return t('import.err_fields_invalid');
		}
		if (validation.amountError) {
			return t('import.err_amount_invalid');
		}
		return t('import.err_date_invalid');
	}

	function getDefaultRuleKeyword(item: ParsedItem | undefined): string {
		return (item?.matched_rule_keyword || item?.display_name || item?.raw_name || '').trim();
	}

	function getDefaultRuleMatchType(item: ParsedItem | undefined): RuleMatchType {
		return item?.matched_rule_match_type === 'contains' || item?.matched_rule_match_type === 'exact'
			? item.matched_rule_match_type
			: 'exact';
	}

	function getDefaultRulePriority(item: ParsedItem | undefined): number {
		return Number.isFinite(item?.matched_rule_priority)
			? (item?.matched_rule_priority as number)
			: DEFAULT_RULE_PRIORITY;
	}

	// --- Handlers ---
	async function handleFiles(files: FileList | File[]) {
		const supportedFiles = Array.from(files).filter((f) => {
			const lower = f.name.toLowerCase();
			return lower.endsWith('.pdf') || lower.endsWith('.json') || lower.endsWith('.txt');
		});
		if (supportedFiles.length === 0) {
			error = t('import.err_no_valid');
			return;
		}

		error = '';
		parseErrors = [];
		phase = 'parsing';
		parseProgress = { done: 0, total: supportedFiles.length };
		queue = [];
		currentIndex = 0;

		// Parse all in parallel (batched to avoid overwhelming the server)
		const batchSize = 5;
		for (let i = 0; i < supportedFiles.length; i += batchSize) {
			const batch = supportedFiles.slice(i, i + batchSize);
			const results = await Promise.allSettled(
				batch.map(async (file) => {
					const previews = await uploadForPreview(file);
					return { filename: file.name, previews };
				})
			);

			for (const res of results) {
				parseProgress.done++;
				if (res.status === 'fulfilled') {
					const { filename, previews } = res.value;
					if (previews.length === 0) {
						parseErrors.push(`${filename}: ${t('import.err_parse_failed')}`);
						continue;
					}

					for (let index = 0; index < previews.length; index++) {
						const result = previews[index];
						const ruleDraftByItem = result.items.reduce<Record<number, ItemRuleDraft>>(
							(acc, item, itemIndex) => {
								acc[itemIndex] = {
									keyword: getDefaultRuleKeyword(item),
									matchType: getDefaultRuleMatchType(item),
									priority: getDefaultRulePriority(item)
								};
								return acc;
							},
							{}
						);

						const entry: QueueEntry = {
							filename: previews.length > 1 ? `${filename} #${index + 1}` : filename,
							preview: result,
							items: [...result.items],
							ruleCreateByItem: {},
							ruleDraftByItem,
							editableTotalAmount: Number.isFinite(result.total_amount)
								? result.total_amount.toFixed(2)
								: '',
							editablePurchasedAt: toDateTimeLocalValue(result.purchased_at),
							requiresReview: false,
							status: 'pending'
						};
						entry.requiresReview = hasEntryAnomaly(entry);
						queue.push(entry);
					}
				} else {
					const errMsg = (res.reason as any)?.message || t('import.err_parse_failed');
					parseErrors.push(errMsg);
				}
			}
			// Trigger reactivity
			queue = [...queue];
		}

		if (queue.length === 0) {
			error = t('import.err_all_failed');
			phase = 'idle';
			return;
		}

		// Find first pending
		currentIndex = 0;
		phase = 'reviewing';
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		const files = e.dataTransfer?.files;
		if (files && files.length > 0) handleFiles(files);
	}

	function onDragOver(e: DragEvent) {
		e.preventDefault();
		dragOver = true;
	}

	function onDragLeave() {
		dragOver = false;
	}

	function onFileSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		const files = input.files;
		if (files && files.length > 0) handleFiles(files);
		input.value = '';
	}

	function updateCategory(index: number, categoryId: number | null) {
		if (!current) return;
		current.items[index] = { ...current.items[index], category_id: categoryId };
		setCurrentItemRuleStatus(index, 'idle');
		queue = [...queue]; // trigger reactivity
	}

	function getCurrentItemRuleStatus(index: number): ItemRuleCreateStatus {
		if (!current) return { state: 'idle' };
		return current.ruleCreateByItem[index] ?? { state: 'idle' };
	}

	function getCurrentItemRuleDraft(index: number): ItemRuleDraft {
		if (!current) return { keyword: '', matchType: 'exact', priority: DEFAULT_RULE_PRIORITY };
		return (
			current.ruleDraftByItem[index] ?? {
				keyword: getDefaultRuleKeyword(current.items[index]),
				matchType: getDefaultRuleMatchType(current.items[index]),
				priority: getDefaultRulePriority(current.items[index])
			}
		);
	}

	function hasRuleDraftChangesForItem(index: number): boolean {
		if (!current) return false;

		const previewItem = current.preview.items[index];
		const currentItem = current.items[index];
		if (!previewItem || !currentItem) return false;

		const draft = getCurrentItemRuleDraft(index);
		const defaultKeyword = getDefaultRuleKeyword(previewItem);
		const defaultMatchType = getDefaultRuleMatchType(previewItem);
		const defaultPriority = clampPriority(getDefaultRulePriority(previewItem));

		return (
			currentItem.category_id !== (previewItem.category_id ?? null) ||
			draft.keyword.trim() !== defaultKeyword ||
			draft.matchType !== defaultMatchType ||
			clampPriority(draft.priority) !== defaultPriority
		);
	}

	function isCreateRuleAllowedForItem(index: number): boolean {
		if (!current) return false;

		const previewItem = current.preview.items[index];
		const currentItem = current.items[index];
		if (!previewItem || !currentItem) return false;

		const previewCategoryId = previewItem.category_id ?? null;
		const wasUncategorized = previewItem.method === 'none' || previewCategoryId === null;
		if (wasUncategorized) return true;

		return hasRuleDraftChangesForItem(index);
	}

	function updateCurrentItemRuleDraft(index: number, patch: Partial<ItemRuleDraft>) {
		if (!current) return;
		const existing = getCurrentItemRuleDraft(index);
		current.ruleDraftByItem = {
			...current.ruleDraftByItem,
			[index]: {
				...existing,
				...patch
			}
		};
		current.ruleCreateByItem = {
			...current.ruleCreateByItem,
			[index]: { state: 'idle' }
		};
		queue = [...queue];
	}

	function setCurrentItemRuleStatus(index: number, state: ItemRuleCreateState, message?: string) {
		if (!current) return;
		current.ruleCreateByItem = {
			...current.ruleCreateByItem,
			[index]: message ? { state, message } : { state }
		};
		queue = [...queue];
	}

	async function handleCreateRuleForItem(index: number) {
		if (!current) {
			return;
		}

		const item = current.items[index];
		if (!item || item.category_id === null) {
			setCurrentItemRuleStatus(index, 'error', t('import.err_select_category'));
			return;
		}

		if (!isCreateRuleAllowedForItem(index)) {
			setCurrentItemRuleStatus(index, 'error', t('import.err_already_auto'));
			return;
		}

		const draft = getCurrentItemRuleDraft(index);
		const keyword = draft.keyword.trim();
		if (!keyword) {
			setCurrentItemRuleStatus(index, 'error', t('import.err_keyword_required'));
			return;
		}

		setCurrentItemRuleStatus(index, 'saving');

		try {
			await createRule({
				keyword,
				match_type: draft.matchType,
				category_id: item.category_id,
				priority: clampPriority(draft.priority)
			});
			setCurrentItemRuleStatus(index, 'created');
		} catch (e: any) {
			if (e?.status === 409) {
				setCurrentItemRuleStatus(index, 'exists');
				return;
			}
			setCurrentItemRuleStatus(index, 'error', t('import.err_rule_save_failed'));
		}
	}

	function moveToNext() {
		if (queue.length === 0) {
			phase = 'done';
			return;
		}

		// Circular scan for next pending entry across the whole queue
		for (let step = 1; step <= queue.length; step++) {
			const i = (currentIndex + step) % queue.length;
			if (queue[i].status === 'pending') {
				currentIndex = i;
				return;
			}
		}
		// No more pending → done
		phase = 'done';
	}

	async function handleConfirm() {
		if (confirming || !current || current.status !== 'pending') return;
		const validation = validateRequiredFields(current);
		if (!validation.isValid) {
			current.requiresReview = true;
			queue = [...queue];
			error = getValidationErrorMessage(validation);
			return;
		}

		confirming = true;
		error = '';

		try {
			await confirmImport({
				store_name: current.preview.store_name,
				store_address: current.preview.store_address,
				store_id: current.preview.store_id,
				register_nr: current.preview.register_nr,
				bon_nr: current.preview.bon_nr,
				beleg_nr: current.preview.beleg_nr,
				purchased_at: validation.normalizedPurchasedAt!,
				total_amount: validation.normalizedTotalAmount!,
				tse_transaction: current.preview.tse_transaction,
				source_filename: current.filename,
				items: current.items.map((i, index) => ({
					raw_name: i.raw_name,
					display_name: i.display_name,
					unit_price: i.unit_price,
					quantity: i.quantity,
					total_price: i.total_price,
					vat_class: i.vat_class,
					is_deposit: i.is_deposit,
					category_id: i.category_id,
					is_manual_assignment:
						i.category_id !== (current.preview.items[index]?.category_id ?? null)
				})),
				bonus_entries: current.preview.bonus_entries,
				total_bonus: current.preview.total_bonus,
				bonus_balance: current.preview.bonus_balance,
				template_id: current.preview.template_id ?? null
			});
			current.status = 'confirmed';
			queue = [...queue];
			moveToNext();
		} catch (e: any) {
			if (e?.status === 409) {
				current.status = 'skipped';
			} else {
				current.status = 'error';
				current.errorMsg = e?.message || t('import.err_failed_import');
			}
			queue = [...queue];
			moveToNext();
		} finally {
			confirming = false;
		}
	}

	async function handleConfirmAll() {
		if (confirming) return;
		confirming = true;
		error = '';

		try {
			for (let i = currentIndex; i < queue.length; i++) {
				const entry = queue[i];
				if (entry.status !== 'pending') continue;

				// Auto-skip known duplicates
				if (entry.preview.is_duplicate) {
					entry.status = 'skipped';
					queue = [...queue];
					continue;
				}

				const validation = validateRequiredFields(entry);
				if (!validation.isValid) {
					entry.requiresReview = true;
					currentIndex = i;
					error = `Stopped at ${entry.filename}: ${getValidationErrorMessage(validation)}`;
					queue = [...queue];
					return;
				}

				try {
					await confirmImport({
						store_name: entry.preview.store_name,
						store_address: entry.preview.store_address,
						store_id: entry.preview.store_id,
						register_nr: entry.preview.register_nr,
						bon_nr: entry.preview.bon_nr,
						beleg_nr: entry.preview.beleg_nr,
						purchased_at: validation.normalizedPurchasedAt!,
						total_amount: validation.normalizedTotalAmount!,
						tse_transaction: entry.preview.tse_transaction,
						source_filename: entry.filename,
						items: entry.items.map((it, index) => ({
							raw_name: it.raw_name,
							display_name: it.display_name,
							unit_price: it.unit_price,
							quantity: it.quantity,
							total_price: it.total_price,
							vat_class: it.vat_class,
							is_deposit: it.is_deposit,
							category_id: it.category_id,
							is_manual_assignment:
								it.category_id !== (entry.preview.items[index]?.category_id ?? null)
						})),
						bonus_entries: entry.preview.bonus_entries,
						total_bonus: entry.preview.total_bonus,
						bonus_balance: entry.preview.bonus_balance,
						template_id: entry.preview.template_id ?? null
					});
					entry.status = 'confirmed';
				} catch (e: any) {
					if (e?.status === 409) {
						entry.status = 'skipped';
					} else {
						entry.status = 'error';
						entry.errorMsg = e?.message || t('import.err_failed_import');
					}
				}
				queue = [...queue];
			}
		} finally {
			confirming = false;
		}

		moveToNext();
	}

	function handleSkip() {
		if (confirming || !current) return;
		current.status = 'skipped';
		queue = [...queue];
		moveToNext();
	}

	function handleCancelAll() {
		if (confirming) return;
		phase = 'done';
	}

	function resetAll() {
		queue = [];
		currentIndex = 0;
		phase = 'idle';
		error = '';
		parseErrors = [];
	}

	let fileInput = $state<HTMLInputElement>();
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-3xl font-bold text-foreground">{t('import.title')}</h1>
		<p class="mt-1 text-muted-foreground">{t('import.subtitle')}</p>
	</div>

	<!-- Error -->
	{#if error}
		<div
			class="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
		>
			<AlertTriangle class="h-4 w-4 shrink-0" />
			{error}
		</div>
	{/if}

	<!-- PHASE: IDLE — Upload zone -->
	{#if phase === 'idle'}
		<input
			type="file"
			accept=".pdf,.json,.txt"
			multiple
			class="hidden"
			bind:this={fileInput}
			onchange={onFileSelect}
		/>

		<div>
			<button class="w-full" onclick={() => fileInput?.click()}>
				<Card.Root
					class="flex min-h-[250px] flex-col items-center justify-center border-2 border-dashed transition-colors {dragOver
						? 'border-primary bg-accent/30'
						: 'hover:border-primary/50 hover:bg-accent/20'}"
					role="button"
					ondrop={onDrop}
					ondragover={onDragOver}
					ondragleave={onDragLeave}
				>
					<Card.Content class="flex flex-col items-center py-10">
						<FileUp class="mb-4 h-12 w-12 text-muted-foreground" />
						<p class="text-lg font-medium text-foreground">{t('import.drop_hint')}</p>
						<p class="mt-1 text-sm text-muted-foreground">
							{t('import.browse_hint')}
						</p>
						<div class="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
							<FileText class="h-3.5 w-3.5" />
							{t('import.supported')}
						</div>
					</Card.Content>
				</Card.Root>
			</button>
		</div>
	{/if}

	<!-- PHASE: PARSING — Progress -->
	{#if phase === 'parsing'}
		<Card.Root>
			<Card.Content class="flex flex-col items-center py-12">
				<Loader2 class="mb-4 h-12 w-12 animate-spin text-primary" />
				<p class="text-lg font-medium text-foreground">
					{t('import.parsing', { done: parseProgress.done, total: parseProgress.total })}
				</p>
				<div class="mt-4 h-2 w-64 overflow-hidden rounded-full bg-muted">
					<div
						class="h-full rounded-full bg-primary transition-all"
						style="width: {(parseProgress.done / Math.max(parseProgress.total, 1)) * 100}%"
					></div>
				</div>
				{#if parseErrors.length > 0}
					<p class="mt-3 text-sm text-destructive">
						{t('import.parse_failed', { count: parseErrors.length })}
					</p>
				{/if}
			</Card.Content>
		</Card.Root>
	{/if}

	<!-- PHASE: REVIEWING — One receipt at a time -->
	{#if phase === 'reviewing' && current}
		<!-- Queue status bar -->
		<Card.Root>
			<Card.Content class="flex items-center justify-between py-3">
				<div class="flex items-center gap-4">
					<span class="text-sm font-medium text-foreground">
						{t('import.receipt_of', { current: currentIndex + 1, total: queue.length })}
					</span>
					<Separator.Root orientation="vertical" class="h-4" />
					<div class="flex items-center gap-3 text-xs text-muted-foreground">
						<span>{t('import.pending', { count: pendingCount })}</span>
						{#if confirmedCount > 0}
							<span class="text-green-400">{t('import.imported', { count: confirmedCount })}</span>
						{/if}
						{#if skippedCount > 0}
							<span>{t('import.skipped', { count: skippedCount })}</span>
						{/if}
						{#if errorCount > 0}
							<span class="text-destructive">{t('import.failed', { count: errorCount })}</span>
						{/if}
					</div>
				</div>
				<div class="flex items-center gap-2">
					<Badge variant="outline" class="text-xs">{current.preview.template_name}</Badge>
					<Badge variant="outline" class="text-xs">{current.filename}</Badge>
				</div>
			</Card.Content>
		</Card.Root>

		<!-- Receipt header -->
		<Card.Root>
			<Card.Header>
				<div class="flex items-center justify-between">
					<div>
						<Card.Title>{current.preview.store_name}</Card.Title>
						<Card.Description>{current.preview.store_address}</Card.Description>
					</div>
					<div class="text-right">
						<p class="text-2xl font-bold text-foreground">
							{formatCurrency(getEffectiveTotalAmount(current))}
						</p>
						<p class="text-sm text-muted-foreground">
							{formatReceiptDate(current)}
						</p>
					</div>
				</div>
			</Card.Header>
			{#if currentShowsReviewPanel && currentRequiredValidation}
				<Card.Content>
					<div
						class="flex items-center gap-2 rounded-lg border p-3 text-sm {currentReviewPanelState ===
						'error'
							? 'border-destructive/50 bg-destructive/10 text-destructive'
							: currentReviewPanelState === 'warning'
								? 'border-amber-500/50 bg-amber-500/10 text-amber-400'
								: 'border-green-500/50 bg-green-500/10 text-green-400'}"
					>
						{#if currentReviewPanelState === 'success'}
							<CheckCircle2 class="h-4 w-4 shrink-0" />
						{:else}
							<AlertTriangle class="h-4 w-4 shrink-0" />
						{/if}
						<div>
							{#if currentReviewPanelState === 'error'}
								<p class="font-medium">{t('import.review_error')}</p>
								<p class="text-muted-foreground">{t('import.review_error_desc')}</p>
							{:else if currentReviewPanelState === 'warning'}
								<p class="font-medium">{t('import.review_warning')}</p>
								<p class="text-muted-foreground">
									{t('import.review_warning_desc')}
								</p>
							{:else}
								<p class="font-medium">{t('import.review_success')}</p>
								<p class="text-muted-foreground">
									{currentHasRequiredFieldEdits
										? t('import.review_success_edited')
										: t('import.review_success_ok')}
								</p>
							{/if}
						</div>
					</div>
					<div class="mt-4 grid gap-4 md:grid-cols-2">
						<div>
							<label
								class="mb-1 block text-sm font-medium text-foreground"
								for="required-total-amount"
							>
								{t('import.total_amount_label')}
							</label>
							<input
								id="required-total-amount"
								type="text"
								bind:value={current.editableTotalAmount}
								class="w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground transition-colors outline-none {currentRequiredValidation.amountError
									? 'border-destructive focus-visible:ring-1 focus-visible:ring-destructive'
									: 'border-input focus-visible:ring-1 focus-visible:ring-ring'}"
								placeholder="e.g. 12.34"
							/>
							{#if currentRequiredValidation.amountError}
								<p class="mt-1 text-xs text-destructive">{currentRequiredValidation.amountError}</p>
							{/if}
						</div>

						<div>
							<label
								class="mb-1 block text-sm font-medium text-foreground"
								for="required-purchased-at"
							>
								{t('import.purchase_date_label')}
							</label>
							<input
								id="required-purchased-at"
								type="datetime-local"
								bind:value={current.editablePurchasedAt}
								class="w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground transition-colors outline-none {currentRequiredValidation.purchasedAtError
									? 'border-destructive focus-visible:ring-1 focus-visible:ring-destructive'
									: 'border-input focus-visible:ring-1 focus-visible:ring-ring'}"
							/>
							{#if currentRequiredValidation.purchasedAtError}
								<p class="mt-1 text-xs text-destructive">
									{currentRequiredValidation.purchasedAtError}
								</p>
							{/if}
						</div>
					</div>

					{#if hasTotalMismatch(current)}
						<div
							class="mt-4 flex items-center gap-2 rounded-lg border p-3 text-sm {currentReviewPanelState ===
							'error'
								? 'border-destructive/50 bg-destructive/10 text-destructive'
								: 'border-amber-500/50 bg-amber-500/10 text-amber-400'}"
						>
							<CircleDollarSign class="h-4 w-4 shrink-0" />
							<p>
								{t('import.total_mismatch', {
									computed: formatCurrency(current.preview.computed_total),
									effective: formatCurrency(getEffectiveTotalAmount(current))
								})}
							</p>
						</div>
					{/if}

					{#if !currentRequiredValidation.amountError && !currentRequiredValidation.purchasedAtError}
						<p
							class="mt-3 text-xs {currentReviewPanelState === 'success'
								? 'text-green-400'
								: 'text-muted-foreground'}"
						>
							{currentReviewPanelState === 'success' && currentHasRequiredFieldEdits
								? t('import.review_ready_note')
								: t('import.review_valid_note')}
						</p>
					{/if}
				</Card.Content>
			{/if}
			{#if current.preview.is_duplicate}
				<Card.Content>
					<div
						class="flex items-center gap-2 rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-3 text-sm text-yellow-400"
					>
						<AlertTriangle class="h-4 w-4 shrink-0" />
						{t('import.duplicate_warning')}
					</div>
				</Card.Content>
			{/if}
		</Card.Root>

		<!-- Items table -->
		<Card.Root>
			<Card.Header>
				<Card.Title>{t('import.items_count', { count: current.items.length })}</Card.Title>
				<Card.Description>{t('import.items_desc')}</Card.Description>
			</Card.Header>
			<Card.Content>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-border text-left text-muted-foreground">
								<th class="pb-3 font-medium">{t('import.th_product')}</th>
								<th class="pb-3 text-center font-medium">{t('import.th_qty')}</th>
								<th class="pb-3 text-right font-medium">{t('import.th_unit')}</th>
								<th class="pb-3 text-right font-medium">{t('import.th_total')}</th>
								<th class="pb-3 font-medium">{t('import.th_vat')}</th>
								<th class="pb-3 font-medium">{t('import.th_category')}</th>
							</tr>
						</thead>
						<tbody>
							{#each current.items as item, i (i)}
								{@const ruleStatus = getCurrentItemRuleStatus(i)}
								{@const ruleDraft = getCurrentItemRuleDraft(i)}
								{@const ruleCreationAllowed = isCreateRuleAllowedForItem(i)}
								{@const previewItem = current.preview.items[i]}
								{@const previewCategoryId = previewItem?.category_id ?? null}
								{@const isPreviewUncategorized =
									previewItem?.method === 'none' || previewCategoryId === null}
								{@const isPreviewAutoCategorized = !isPreviewUncategorized}
								{@const helperPanelState =
									ruleStatus.state === 'created' || ruleStatus.state === 'exists'
										? 'saved'
										: isPreviewUncategorized
											? 'uncategorized'
											: 'auto'}
								<tr class="border-b border-border/50 transition-colors hover:bg-accent/20">
									<td class="py-3 pr-4">
										<div class="flex items-center gap-2">
											<span class="text-foreground">{item.raw_name}</span>
											{#if item.is_deposit}
												<Badge variant="outline" class="text-xs">PFAND</Badge>
											{/if}
										</div>
									</td>
									<td class="py-3 text-center text-muted-foreground">{item.quantity}</td>
									<td class="py-3 text-right text-muted-foreground">
										{formatCurrency(item.unit_price)}
									</td>
									<td class="py-3 text-right font-medium text-foreground">
										{formatCurrency(item.total_price)}
									</td>
									<td class="py-3">
										<Badge variant="secondary" class="text-xs"
											>{formatVatClass(item.vat_class)}</Badge
										>
									</td>
									<td class="py-3">
										<select
											class="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
											value={item.category_id ?? uncategorizedId}
											onchange={(e) => {
												const val = (e.target as HTMLSelectElement).value;
												updateCategory(i, val ? Number(val) : null);
											}}
										>
											{#each categories as cat (cat.id)}
												<option value={cat.id}>{cat.icon} {cat.name}</option>
											{/each}
										</select>
										<div
											class="mt-2 rounded-md border border-dashed p-2.5 {helperPanelState ===
											'saved'
												? 'border-sky-400/45 bg-sky-500/10'
												: helperPanelState === 'uncategorized'
													? 'border-amber-400/45 bg-amber-500/10'
													: 'border-emerald-400/40 bg-emerald-500/10'}"
										>
											<p
												class="mb-2 text-xs leading-snug {helperPanelState === 'saved'
													? 'text-sky-200/90'
													: helperPanelState === 'uncategorized'
														? 'text-amber-200/90'
														: 'text-emerald-200/90'}"
											>
												{#if helperPanelState === 'saved'}
													{t('import.rule_saved_future')}
												{:else if isPreviewUncategorized}
													{t('import.no_rule_matched')}
												{:else if previewItem?.matched_rule_keyword && previewItem?.matched_rule_match_type}
													{t('import.auto_categorized_by', {
														keyword: previewItem.matched_rule_keyword,
														matchType: t(`import.${previewItem.matched_rule_match_type}`)
													})}
												{:else}
													{t('import.auto_change_hint')}
												{/if}
											</p>
											<div class="space-y-1.5">
												<input
													type="text"
													class="w-full rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground"
													placeholder={t('import.rule_keyword')}
													value={ruleDraft.keyword}
													oninput={(e) =>
														updateCurrentItemRuleDraft(i, {
															keyword: (e.target as HTMLInputElement).value
														})}
												/>
												<div class="grid grid-cols-2 gap-1.5">
													<select
														class="w-full rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground"
														value={ruleDraft.matchType}
														onchange={(e) =>
															updateCurrentItemRuleDraft(i, {
																matchType: (e.target as HTMLSelectElement).value as RuleMatchType
															})}
													>
														<option value="contains">{t('import.contains')}</option>
														<option value="exact">{t('import.exact')}</option>
													</select>
													<input
														type="number"
														min="0"
														max="100"
														step="1"
														class="w-full rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground"
														placeholder={t('import.priority')}
														value={ruleDraft.priority}
														oninput={(e) =>
															updateCurrentItemRuleDraft(i, {
																priority: clampPriority(
																	(e.target as HTMLInputElement).valueAsNumber
																)
															})}
													/>
												</div>
											</div>
											<div class="mt-2 flex flex-col items-start gap-1">
												<button
													type="button"
													class="text-xs text-primary underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:text-muted-foreground"
													onclick={() => handleCreateRuleForItem(i)}
													disabled={ruleStatus.state === 'saving' ||
														item.category_id === null ||
														!ruleCreationAllowed}
												>
													{ruleStatus.state === 'saving'
														? t('import.saving')
														: t('import.create_rule')}
												</button>
												{#if isPreviewAutoCategorized && !ruleCreationAllowed}
													<p class="text-xs text-muted-foreground">
														{t('import.change_to_create')}
													</p>
												{/if}
												{#if ruleStatus.state === 'created'}
													<p class="text-xs text-green-500">{t('import.rule_saved')}</p>
												{:else if ruleStatus.state === 'exists'}
													<p class="text-xs text-muted-foreground">{t('import.rule_exists')}</p>
												{:else if ruleStatus.state === 'error'}
													<p class="text-xs text-destructive">
														{ruleStatus.message || t('import.err_rule_save_failed')}
													</p>
												{/if}
											</div>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</Card.Content>
		</Card.Root>

		<!-- Bonus card -->
		{#if current.preview.bonus_entries.length > 0}
			<Card.Root>
				{@const previewProgramSavings = computeProgramSavings(current.preview.bonus_entries, current.preview.total_bonus)}
				<Card.Header>
					<div class="flex items-center gap-2">
						<Sparkles class="h-4 w-4 text-yellow-400" />
						<Card.Title>{t('import.bonus_title')}</Card.Title>
					</div>
					<Card.Description
						>{t('import.total_savings', {
							amount: formatCurrency(previewProgramSavings)
						})}</Card.Description
					>
				</Card.Header>
				<Card.Content>
					<div class="space-y-3">
						{#each current.preview.bonus_entries as bonus, i (`${i}-${bonus.type}-${bonus.description}-${bonus.amount}`)}
							{@const isDeduction = isDeductionBonusType(bonus.type)}
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-3">
									{#if bonus.type === 'action'}
										<Gift class="h-4 w-4 text-emerald-400" />
									{:else}
										<Ticket class="h-4 w-4 text-blue-400" />
									{/if}
									<div>
										<p class="text-sm font-medium text-foreground">{bonus.description}</p>
										<Badge variant="secondary" class="text-xs">{bonusTypeLabel(bonus.type, t)}</Badge>
									</div>
								</div>
								<p class="font-medium {isDeduction ? 'text-destructive' : 'text-emerald-400'}">
									{isDeduction ? '-' : '+'}{formatCurrency(Math.abs(bonus.amount))}
								</p>
							</div>
						{/each}

						{#if current.preview.bonus_balance !== null}
							<Separator.Root />
							<div class="flex items-center justify-between text-sm">
								<span class="text-muted-foreground">{t('import.bonus_balance')}</span>
								<span class="font-medium text-foreground">
									{formatCurrency(current.preview.bonus_balance)}
								</span>
							</div>
						{/if}
					</div>
				</Card.Content>
			</Card.Root>
		{/if}

		<!-- Actions -->
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-2">
				<Button
					variant="outline"
					onclick={handleCancelAll}
					disabled={confirming}
					class="text-destructive hover:text-destructive"
				>
					<XCircle class="mr-2 h-4 w-4" />
					{t('import.cancel_all')}
				</Button>
				<Button variant="outline" onclick={handleSkip} disabled={confirming}>
					<SkipForward class="mr-2 h-4 w-4" />
					{t('import.skip')}
				</Button>
			</div>
			<div class="flex items-center gap-2">
				{#if pendingCount > 1}
					<Button variant="outline" onclick={handleConfirmAll} disabled={confirming}>
						<CheckCheck class="mr-2 h-4 w-4" />
						{t('import.confirm_all', { count: pendingCount })}
					</Button>
				{/if}
				<Button onclick={handleConfirm} disabled={confirming}>
					{#if confirming}
						<Loader2 class="mr-2 h-4 w-4 animate-spin" />
						{t('import.saving')}
					{:else}
						<CheckCircle2 class="mr-2 h-4 w-4" />
						{t('import.confirm', { count: current.items.length })}
					{/if}
				</Button>
			</div>
		</div>
	{/if}

	<!-- PHASE: DONE — Summary -->
	{#if phase === 'done'}
		<Card.Root>
			<Card.Header>
				<Card.Title>{t('import.complete')}</Card.Title>
			</Card.Header>
			<Card.Content>
				<div class="space-y-3">
					<div class="grid grid-cols-3 gap-4 text-center">
						<div class="rounded-lg bg-green-500/10 p-4">
							<p class="text-2xl font-bold text-green-400">{confirmedCount}</p>
							<p class="text-sm text-muted-foreground">{t('import.summary_imported')}</p>
						</div>
						<div class="rounded-lg bg-muted p-4">
							<p class="text-2xl font-bold text-foreground">{skippedCount}</p>
							<p class="text-sm text-muted-foreground">{t('import.summary_skipped')}</p>
						</div>
						<div class="rounded-lg bg-destructive/10 p-4">
							<p class="text-2xl font-bold text-destructive">{errorCount + parseErrors.length}</p>
							<p class="text-sm text-muted-foreground">{t('import.summary_failed')}</p>
						</div>
					</div>

					{#if parseErrors.length > 0}
						<div class="rounded-lg border border-destructive/30 p-3">
							<p class="mb-2 text-sm font-medium text-destructive">{t('import.parse_failures')}</p>
							{#each parseErrors as err, i (i)}
								<p class="text-xs text-muted-foreground">{err}</p>
							{/each}
						</div>
					{/if}

					{#if queue.filter((e) => e.status === 'error').length > 0}
						<div class="rounded-lg border border-destructive/30 p-3">
							<p class="mb-2 text-sm font-medium text-destructive">{t('import.import_failures')}</p>
							{#each queue.filter((e) => e.status === 'error') as entry, i (`${entry.filename}-${i}`)}
								<p class="text-xs text-muted-foreground">
									{entry.filename}: {entry.errorMsg}
								</p>
							{/each}
						</div>
					{/if}
				</div>
			</Card.Content>
		</Card.Root>

		<div class="flex items-center justify-between">
			<Button variant="outline" href="/receipts">{t('import.view_receipts')}</Button>
			<Button onclick={resetAll}>{t('import.import_more')}</Button>
		</div>
	{/if}
</div>
