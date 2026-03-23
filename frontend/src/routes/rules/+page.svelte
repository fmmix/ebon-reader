<script lang="ts">
	import {
		applyTaxonomyReplace,
		fetchTaxonomyBackupBundle,
		fetchTaxonomyBackups,
		fetchRules,
		createRule,
		updateRule,
		deleteRule,
		deleteAllRules,
		exportTaxonomy,
		previewReCategorizeItems,
		previewTaxonomyReplace,
		reCategorizeItems,
		fetchCategories,
		type CategorizeRule,
		type ProductCategory,
		type TaxonomyBundle,
		type TaxonomyReplaceApplyResponse,
		type TaxonomyReplacePreviewResponse,
		type TaxonomyBackupInfo,
		type ReCategorizePreviewResponse,
		type ReCategorizeResponse
	} from '$lib/api';
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Plus, Pencil, Trash2, Check, X, ListFilter, Search } from '@lucide/svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { clampPriority } from '$lib/utils/rules';

	let rules = $state<CategorizeRule[]>([]);
	let categories = $state<ProductCategory[]>([]);
	let loading = $state(true);
	let error = $state('');
	let previewingReCategorize = $state(false);
	let reCategorizing = $state(false);
	let overrideManualAssignments = $state(false);
	let reCategorizePreview = $state<ReCategorizePreviewResponse | null>(null);
	let previewOverrideManual = $state<boolean | null>(null);
	let reCategorizeGuardMessage = $state('');
	let reCategorizeResult = $state<ReCategorizeResponse | null>(null);
	let exportingTaxonomy = $state(false);
	let previewingTaxonomyReplace = $state(false);
	let applyingTaxonomyReplace = $state(false);
	let importedTaxonomyFileName = $state('');
	let importedTaxonomySignature = $state('');
	let importedTaxonomyBundle = $state<TaxonomyBundle | null>(null);
	let taxonomyPreview = $state<TaxonomyReplacePreviewResponse | null>(null);
	let taxonomyApplyResult = $state<TaxonomyReplaceApplyResponse | null>(null);
	let taxonomyPreviewSignature = $state('');
	let taxonomyGuardMessage = $state('');
	let taxonomyFileInput = $state<HTMLInputElement | null>(null);
	let taxonomyBackups = $state<TaxonomyBackupInfo[]>([]);
	let selectedTaxonomyBackupId = $state('');
	let loadingTaxonomyBackups = $state(false);
	let loadingTaxonomyBackupBundle = $state(false);

	// Filter
	let filterCategoryId = $state<number | ''>('');
	let searchQuery = $state('');

	// Add form
	let showAdd = $state(false);
	let newKeyword = $state('');
	let newMatchType = $state('contains');
	let newCategoryId = $state<number | ''>('');
	let newPriority = $state(20);

	// Edit state
	let editId = $state<number | null>(null);
	let editKeyword = $state('');
	let editMatchType = $state('');
	let editCategoryId = $state<number>(0);
	let editPriority = $state(20);
	let deleteAllConfirmation = $state('');
	let deletingAllRules = $state(false);
	let deleteAllSuccessMessage = $state('');

	onMount(async () => {
		categories = await fetchCategories();
		await Promise.all([loadRules(), loadTaxonomyBackups()]);
	});

	async function loadTaxonomyBackups() {
		loadingTaxonomyBackups = true;
		try {
			taxonomyBackups = await fetchTaxonomyBackups();
			if (
				selectedTaxonomyBackupId !== '' &&
				!taxonomyBackups.some((backup) => String(backup.id) === selectedTaxonomyBackupId)
			) {
				selectedTaxonomyBackupId = '';
			}
		} catch (e: any) {
			error = e?.message || t('rules.err_load_backups');
		} finally {
			loadingTaxonomyBackups = false;
		}
	}

	async function loadRules() {
		loading = true;
		try {
			const catId = filterCategoryId !== '' ? Number(filterCategoryId) : undefined;
			rules = await fetchRules(catId);
		} catch (e: any) {
			error = e?.message || t('rules.err_load');
		} finally {
			loading = false;
		}
	}

	async function handleCreate() {
		if (!newKeyword.trim() || newCategoryId === '') return;
		error = '';
		try {
			await createRule({
				keyword: newKeyword.trim(),
				match_type: newMatchType,
				category_id: Number(newCategoryId),
				priority: clampPriority(newPriority)
			});
			newKeyword = '';
			newMatchType = 'contains';
			newCategoryId = '';
			newPriority = 20;
			showAdd = false;
			await loadRules();
		} catch (e: any) {
			error = e?.message || t('rules.err_create');
		}
	}

	function startEdit(rule: CategorizeRule) {
		editId = rule.id;
		editKeyword = rule.keyword;
		editMatchType = rule.match_type;
		editCategoryId = rule.category_id;
		editPriority = rule.priority;
	}

	function cancelEdit() {
		editId = null;
	}

	async function saveEdit() {
		if (editId === null || !editKeyword.trim()) return;
		error = '';
		try {
			await updateRule(editId, {
				keyword: editKeyword.trim(),
				match_type: editMatchType,
				category_id: editCategoryId,
				priority: clampPriority(editPriority)
			});
			editId = null;
			await loadRules();
		} catch (e: any) {
			error = e?.message || t('rules.err_update');
		}
	}

	async function handleDelete(rule: CategorizeRule) {
		error = '';
		try {
			await deleteRule(rule.id);
			await loadRules();
		} catch (e: any) {
			error = e?.message || t('rules.err_delete');
		}
	}

	async function handleDeleteAllRules() {
		if (deleteAllConfirmation.trim() !== 'DELETE') return;

		error = '';
		deleteAllSuccessMessage = '';
		if (!window.confirm(t('rules.danger_confirm'))) {
			return;
		}

		deletingAllRules = true;
		try {
			const result = await deleteAllRules();
			deleteAllSuccessMessage = t('rules.danger_deleted', { count: String(result.deleted) });
			deleteAllConfirmation = '';
			await loadRules();
		} catch (e: any) {
			error = e?.message || t('rules.err_delete_all');
		} finally {
			deletingAllRules = false;
		}
	}

	async function handleReCategorize() {
		error = '';
		if (reCategorizePreview === null || previewOverrideManual !== overrideManualAssignments) {
			reCategorizeGuardMessage = t('rules.recat_guard_preview');
			return;
		}
		reCategorizeGuardMessage = '';

		if (overrideManualAssignments && !window.confirm(t('rules.recat_confirm'))) {
			return;
		}

		reCategorizing = true;
		try {
			reCategorizeResult = await reCategorizeItems(overrideManualAssignments);
		} catch (e: any) {
			error = e?.message || t('rules.err_recat');
		} finally {
			reCategorizing = false;
		}
	}

	async function handlePreviewReCategorize() {
		error = '';
		reCategorizeGuardMessage = '';
		previewingReCategorize = true;
		try {
			reCategorizePreview = await previewReCategorizeItems(overrideManualAssignments);
			previewOverrideManual = overrideManualAssignments;
		} catch (e: any) {
			error = e?.message || t('rules.err_preview_recat');
		} finally {
			previewingReCategorize = false;
		}
	}

	function handleOverrideManualChange() {
		if (reCategorizePreview !== null && previewOverrideManual !== overrideManualAssignments) {
			reCategorizePreview = null;
			previewOverrideManual = null;
			reCategorizeGuardMessage = t('rules.recat_guard_invalidated');
			return;
		}
		reCategorizeGuardMessage = '';
	}

	function getCategoryIcon(id: number): string {
		return categories.find((c) => c.id === id)?.icon ?? '🏷️';
	}

	function coerceTaxonomyBundle(payload: unknown): TaxonomyBundle {
		if (!payload || typeof payload !== 'object') {
			throw new Error('Invalid taxonomy JSON');
		}
		const candidate = payload as Record<string, unknown>;
		if (!Array.isArray(candidate.categories) || !Array.isArray(candidate.rules)) {
			throw new Error('Taxonomy JSON must include categories and rules arrays');
		}
		return {
			version: typeof candidate.version === 'number' ? candidate.version : 1,
			exported_at:
				typeof candidate.exported_at === 'string' || candidate.exported_at === null
					? candidate.exported_at
					: null,
			categories: candidate.categories.map((category) => {
				const row = category as Record<string, unknown>;
				return {
					name: typeof row.name === 'string' ? row.name : '',
					icon: typeof row.icon === 'string' ? row.icon : '🏷️',
					color: typeof row.color === 'string' ? row.color : '#6b7280',
					is_default: row.is_default === true
				};
			}),
			rules: candidate.rules.map((rule) => {
				const row = rule as Record<string, unknown>;
				return {
					keyword: typeof row.keyword === 'string' ? row.keyword : '',
					match_type: typeof row.match_type === 'string' ? row.match_type : 'contains',
					category_name: typeof row.category_name === 'string' ? row.category_name : '',
					priority: typeof row.priority === 'number' ? row.priority : 0
				};
			})
		};
	}

	async function handleTaxonomyFileChange(event: Event) {
		error = '';
		taxonomyGuardMessage = '';
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) {
			importedTaxonomyFileName = '';
			importedTaxonomySignature = '';
			importedTaxonomyBundle = null;
			taxonomyPreview = null;
			taxonomyApplyResult = null;
			taxonomyPreviewSignature = '';
			return;
		}

		try {
			const content = await file.text();
			const parsed = JSON.parse(content);
			importedTaxonomyBundle = coerceTaxonomyBundle(parsed);
			importedTaxonomyFileName = file.name;
			importedTaxonomySignature = `${file.name}:${file.size}:${file.lastModified}`;
			taxonomyPreview = null;
			taxonomyApplyResult = null;
			taxonomyPreviewSignature = '';
			taxonomyGuardMessage = t('rules.taxonomy_guard_preview');
		} catch (e: any) {
			importedTaxonomyBundle = null;
			taxonomyPreview = null;
			taxonomyApplyResult = null;
			taxonomyPreviewSignature = '';
			error = e?.message || t('rules.err_parse_json');
		}
	}

	async function handleExportTaxonomy() {
		error = '';
		exportingTaxonomy = true;
		try {
			const bundle = await exportTaxonomy();
			const stamp = new Date().toISOString().replace(/[:.]/g, '-');
			const fileName = `taxonomy-export-${stamp}.json`;
			const jsonContent = JSON.stringify(bundle, null, 2);

			const win = window as Window & {
				showSaveFilePicker?: (options?: {
					suggestedName?: string;
					types?: Array<{ description?: string; accept: Record<string, string[]> }>;
				}) => Promise<{
					createWritable: () => Promise<{
						write: (data: string) => Promise<void>;
						close: () => Promise<void>;
					}>;
				}>;
			};

			if (typeof win.showSaveFilePicker === 'function') {
				try {
					const handle = await win.showSaveFilePicker({
						suggestedName: fileName,
						types: [
							{
								description: 'JSON files',
								accept: { 'application/json': ['.json'] }
							}
						]
					});
					const writable = await handle.createWritable();
					await writable.write(jsonContent);
					await writable.close();
					return;
				} catch (e: any) {
					if (e?.name === 'AbortError') {
						return;
					}
					throw e;
				}
			}

			const blob = new Blob([jsonContent], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = fileName;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			URL.revokeObjectURL(url);
		} catch (e: any) {
			error = e?.message || t('rules.err_export');
		} finally {
			exportingTaxonomy = false;
		}
	}

	function triggerTaxonomyFilePicker() {
		taxonomyFileInput?.click();
	}

	async function handleLoadSelectedBackup() {
		error = '';
		taxonomyGuardMessage = '';
		if (selectedTaxonomyBackupId === '') {
			taxonomyGuardMessage = t('rules.taxonomy_guard_select');
			return;
		}

		loadingTaxonomyBackupBundle = true;
		try {
			const backupId = Number(selectedTaxonomyBackupId);
			importedTaxonomyBundle = await fetchTaxonomyBackupBundle(backupId);
			importedTaxonomyFileName = `Backup #${backupId}`;
			importedTaxonomySignature = `backup:${backupId}`;
			taxonomyPreview = null;
			taxonomyApplyResult = null;
			taxonomyPreviewSignature = '';
			taxonomyGuardMessage = t('rules.taxonomy_guard_preview_backup');
		} catch (e: any) {
			error = e?.message || t('rules.err_load_backup');
		} finally {
			loadingTaxonomyBackupBundle = false;
		}
	}

	async function handlePreviewTaxonomyReplace() {
		error = '';
		taxonomyGuardMessage = '';
		if (!importedTaxonomyBundle || !importedTaxonomySignature) {
			taxonomyGuardMessage = t('rules.taxonomy_guard_load');
			return;
		}
		previewingTaxonomyReplace = true;
		try {
			taxonomyPreview = await previewTaxonomyReplace(importedTaxonomyBundle);
			taxonomyPreviewSignature = importedTaxonomySignature;
			taxonomyApplyResult = null;
		} catch (e: any) {
			error = e?.message || t('rules.err_preview_taxonomy');
		} finally {
			previewingTaxonomyReplace = false;
		}
	}

	async function handleApplyTaxonomyReplace() {
		error = '';
		if (!importedTaxonomyBundle || !importedTaxonomySignature) {
			taxonomyGuardMessage = t('rules.taxonomy_guard_load');
			return;
		}
		if (!taxonomyPreview || taxonomyPreviewSignature !== importedTaxonomySignature) {
			taxonomyGuardMessage = t('rules.taxonomy_guard_preview_apply');
			return;
		}
		taxonomyGuardMessage = '';

		if (!window.confirm(t('rules.taxonomy_confirm'))) {
			return;
		}

		applyingTaxonomyReplace = true;
		try {
			taxonomyApplyResult = await applyTaxonomyReplace(importedTaxonomyBundle);
			const [nextCategories] = await Promise.all([
				fetchCategories(),
				loadRules(),
				loadTaxonomyBackups()
			]);
			categories = nextCategories;
		} catch (e: any) {
			error = e?.message || t('rules.err_apply_taxonomy');
		} finally {
			applyingTaxonomyReplace = false;
		}
	}

	function matchTypeLabel(mt: string): string {
		return mt === 'exact' ? t('rules.match_exact') : t('rules.match_contains');
	}

	let filteredRules = $derived(
		searchQuery
			? rules.filter((r) => r.keyword.toLowerCase().includes(searchQuery.toLowerCase()))
			: rules
	);
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold text-foreground">{t('rules.title')}</h1>
			<p class="mt-1 text-muted-foreground">{t('rules.subtitle')}</p>
		</div>
		<Button onclick={() => (showAdd = !showAdd)}>
			<Plus class="mr-2 h-4 w-4" />
			{t('rules.add')}
		</Button>
	</div>

	{#if error}
		<div
			class="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
		>
			{error}
		</div>
	{/if}

	<Card.Root>
		<Card.Header>
			<Card.Title>{t('rules.taxonomy_title')}</Card.Title>
			<Card.Description>
				{t('rules.taxonomy_desc')}
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
				<div class="flex-1 space-y-2">
					<label class="block text-sm text-muted-foreground" for="taxonomy-json-hidden">
						{t('rules.taxonomy_import_label')}
					</label>
					<input
						id="taxonomy-json-hidden"
						type="file"
						accept=".json"
						class="sr-only"
						bind:this={taxonomyFileInput}
						onchange={handleTaxonomyFileChange}
					/>
					<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
						<Button type="button" variant="outline" onclick={triggerTaxonomyFilePicker}>
							{t('rules.taxonomy_choose_file')}
						</Button>
						<div
							class="min-h-9 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm text-muted-foreground"
						>
							<span class="block truncate">
								{importedTaxonomyFileName || t('rules.taxonomy_no_file')}
							</span>
						</div>
					</div>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<Button variant="outline" onclick={handleExportTaxonomy} disabled={exportingTaxonomy}>
						{exportingTaxonomy ? t('rules.taxonomy_exporting') : t('rules.taxonomy_export')}
					</Button>
					<Button
						variant="outline"
						onclick={handlePreviewTaxonomyReplace}
						disabled={previewingTaxonomyReplace || !importedTaxonomyBundle}
					>
						{previewingTaxonomyReplace
							? t('rules.taxonomy_previewing')
							: t('rules.taxonomy_preview')}
					</Button>
					<Button
						onclick={handleApplyTaxonomyReplace}
						disabled={applyingTaxonomyReplace || !importedTaxonomyBundle}
					>
						{applyingTaxonomyReplace ? t('rules.taxonomy_applying') : t('rules.taxonomy_apply')}
					</Button>
				</div>
			</div>

			<div class="mt-4 rounded-md border border-border/60 bg-muted/20 p-3">
				<div class="mb-2 text-sm text-foreground">{t('rules.taxonomy_restore')}</div>
				<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
					<select
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground sm:flex-1"
						bind:value={selectedTaxonomyBackupId}
						disabled={loadingTaxonomyBackups || taxonomyBackups.length === 0}
					>
						<option value="">{t('rules.taxonomy_select_backup')}</option>
						{#each taxonomyBackups as backup (backup.id)}
							<option value={backup.id}>
								{new Date(backup.created_at).toLocaleString()} | {backup.categories_count} categories
								| {backup.rules_count} rules | #{backup.id}
							</option>
						{/each}
					</select>
					<Button
						type="button"
						variant="outline"
						onclick={handleLoadSelectedBackup}
						disabled={loadingTaxonomyBackupBundle || selectedTaxonomyBackupId === ''}
					>
						{loadingTaxonomyBackupBundle
							? t('rules.taxonomy_loading_backup')
							: t('rules.taxonomy_load_backup')}
					</Button>
				</div>
				{#if !loadingTaxonomyBackups && taxonomyBackups.length === 0}
					<p class="mt-2 text-xs text-muted-foreground">{t('rules.taxonomy_no_backups')}</p>
				{/if}
			</div>

			{#if taxonomyGuardMessage}
				<p class="mt-2 text-xs text-amber-700">{taxonomyGuardMessage}</p>
			{/if}

			{#if taxonomyPreview}
				<div class="mt-4">
					<p class="mb-2 text-xs text-muted-foreground">{t('rules.taxonomy_preview_note')}</p>
					<div class="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_incoming_cat')}</div>
							<div class="font-semibold text-foreground">{taxonomyPreview.incoming_categories}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_incoming_rules')}</div>
							<div class="font-semibold text-foreground">{taxonomyPreview.incoming_rules}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_norm_cat')}</div>
							<div class="font-semibold text-foreground">
								{taxonomyPreview.normalized_categories}
							</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_norm_rules')}</div>
							<div class="font-semibold text-foreground">{taxonomyPreview.normalized_rules}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_existing_cat')}</div>
							<div class="font-semibold text-foreground">{taxonomyPreview.existing_categories}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_existing_rules')}</div>
							<div class="font-semibold text-foreground">{taxonomyPreview.existing_rules}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_receipt_items')}</div>
							<div class="font-semibold text-foreground">{taxonomyPreview.receipt_items_total}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_skipped_rules')}</div>
							<div class="font-semibold text-foreground">
								{taxonomyPreview.skipped_rules_missing_category}
							</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_remap_matched')}</div>
							<div class="font-semibold text-foreground">{taxonomyPreview.remap_matched_items}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.taxonomy_fallback_uncat')}</div>
							<div class="font-semibold text-foreground">
								{taxonomyPreview.fallback_uncategorized_items}
							</div>
						</div>
						<div
							class="col-span-2 rounded-md border border-border/60 bg-muted/20 p-2 md:col-span-2"
						>
							<div class="text-xs text-muted-foreground">
								{t('rules.taxonomy_will_ensure_uncat')}
							</div>
							<div class="font-semibold text-foreground">
								{taxonomyPreview.will_ensure_uncategorized
									? t('rules.taxonomy_yes')
									: t('rules.taxonomy_no')}
							</div>
						</div>
					</div>
				</div>
			{/if}

			{#if taxonomyApplyResult}
				<p class="mt-3 text-sm text-foreground">
					{t('rules.taxonomy_applied')}
					<span class="font-mono">{taxonomyApplyResult.backup_id}</span>
				</p>
			{/if}
		</Card.Content>
	</Card.Root>

	<!-- Add form -->
	{#if showAdd}
		<Card.Root>
			<Card.Header>
				<Card.Title>{t('rules.new')}</Card.Title>
			</Card.Header>
			<Card.Content>
				<div class="flex items-end gap-3">
					<div class="flex-1">
						<label class="mb-1 block text-sm text-muted-foreground" for="new-kw"
							>{t('rules.label_keyword')}</label
						>
						<input
							id="new-kw"
							type="text"
							class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
							bind:value={newKeyword}
							placeholder={t('rules.placeholder_keyword')}
						/>
					</div>
					<div class="w-32">
						<label class="mb-1 block text-sm text-muted-foreground" for="new-match"
							>{t('rules.label_match')}</label
						>
						<select
							id="new-match"
							class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
							bind:value={newMatchType}
						>
							<option value="contains">{t('rules.match_contains')}</option>
							<option value="exact">{t('rules.match_exact')}</option>
						</select>
					</div>
					<div class="w-48">
						<label class="mb-1 block text-sm text-muted-foreground" for="new-cat"
							>{t('rules.label_category')}</label
						>
						<select
							id="new-cat"
							class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
							bind:value={newCategoryId}
						>
							<option value="">{t('rules.select')}</option>
							{#each categories as cat (cat.id)}
								<option value={cat.id}>{cat.icon} {cat.name}</option>
							{/each}
						</select>
					</div>
					<div class="w-28">
						<label class="mb-1 block text-sm text-muted-foreground" for="new-priority"
							>{t('rules.label_priority')}</label
						>
						<input
							id="new-priority"
							type="number"
							min="0"
							max="100"
							step="1"
							class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
							bind:value={newPriority}
						/>
					</div>
					<Button onclick={handleCreate} disabled={!newKeyword.trim() || newCategoryId === ''}>
						<Check class="mr-1 h-4 w-4" />
						{t('rules.create')}
					</Button>
					<Button variant="ghost" onclick={() => (showAdd = false)}>
						<X class="h-4 w-4" />
					</Button>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}

	<!-- Filters -->
	<div class="flex items-center gap-3">
		<div class="relative flex-1">
			<Search class="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
			<input
				type="text"
				placeholder={t('rules.search_placeholder')}
				class="w-full rounded-md border border-input bg-background py-2 pr-3 pl-10 text-sm text-foreground"
				bind:value={searchQuery}
			/>
		</div>
		<div class="flex items-center gap-2">
			<ListFilter class="h-4 w-4 text-muted-foreground" />
			<select
				class="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
				bind:value={filterCategoryId}
				onchange={() => loadRules()}
			>
				<option value="">{t('rules.all_categories')}</option>
				{#each categories as cat (cat.id)}
					<option value={cat.id}>{cat.icon} {cat.name}</option>
				{/each}
			</select>
		</div>
	</div>

	<Card.Root>
		<Card.Header>
			<Card.Title>{t('rules.recat_title')}</Card.Title>
			<Card.Description>{t('rules.recat_desc')}</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
				<label class="inline-flex items-center gap-2 text-sm text-foreground" for="override-manual">
					<input
						id="override-manual"
						type="checkbox"
						class="h-4 w-4 rounded border border-input"
						bind:checked={overrideManualAssignments}
						onchange={handleOverrideManualChange}
					/>
					<span>{t('rules.recat_override')}</span>
				</label>
				<div class="flex items-center gap-2">
					<Button
						variant="outline"
						onclick={handlePreviewReCategorize}
						disabled={previewingReCategorize}
					>
						{previewingReCategorize ? t('rules.recat_previewing') : t('rules.recat_preview')}
					</Button>
					<Button onclick={handleReCategorize} disabled={reCategorizing}>
						{reCategorizing ? t('rules.recat_running') : t('rules.recat_run')}
					</Button>
				</div>
			</div>

			{#if overrideManualAssignments}
				<p class="mt-2 text-xs text-amber-700">
					{t('rules.recat_override_warn')}
				</p>
			{/if}

			{#if reCategorizeGuardMessage}
				<p class="mt-2 text-xs text-amber-700">{reCategorizeGuardMessage}</p>
			{/if}

			{#if reCategorizePreview}
				<div class="mt-4">
					<p class="mb-2 text-xs text-muted-foreground">{t('rules.recat_preview_note')}</p>
					<div class="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.recat_total')}</div>
							<div class="font-semibold text-foreground">{reCategorizePreview.total_items}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.recat_processed')}</div>
							<div class="font-semibold text-foreground">{reCategorizePreview.processed_items}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.recat_updated')}</div>
							<div class="font-semibold text-foreground">{reCategorizePreview.updated_items}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.recat_unchanged')}</div>
							<div class="font-semibold text-foreground">{reCategorizePreview.unchanged_items}</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.recat_skipped_manual')}</div>
							<div class="font-semibold text-foreground">
								{reCategorizePreview.skipped_manual_items}
							</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.recat_overridden_manual')}</div>
							<div class="font-semibold text-foreground">
								{reCategorizePreview.overridden_manual_items}
							</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.recat_categorized')}</div>
							<div class="font-semibold text-foreground">
								{reCategorizePreview.categorized_items}
							</div>
						</div>
						<div class="rounded-md border border-border/60 bg-muted/20 p-2">
							<div class="text-xs text-muted-foreground">{t('rules.recat_uncategorized')}</div>
							<div class="font-semibold text-foreground">
								{reCategorizePreview.uncategorized_items}
							</div>
						</div>
					</div>

					{#if reCategorizePreview.changes.length === 0}
						<p class="mt-3 text-sm text-muted-foreground">{t('rules.recat_no_changes')}</p>
					{:else}
						<div class="mt-3 overflow-x-auto rounded-md border border-border/60">
							<table class="w-full text-sm">
								<thead>
									<tr class="border-b border-border text-left text-muted-foreground">
										<th class="px-3 py-2 font-medium">{t('rules.recat_from')}</th>
										<th class="px-3 py-2 font-medium">{t('rules.recat_to')}</th>
										<th class="px-3 py-2 text-right font-medium">{t('rules.recat_items')}</th>
									</tr>
								</thead>
								<tbody>
									{#each reCategorizePreview.changes as change (`${change.from_category_name}:${change.to_category_name}:${change.item_count}`)}
										<tr class="border-b border-border/40 last:border-b-0">
											<td class="px-3 py-2 text-foreground">{change.from_category_name}</td>
											<td class="px-3 py-2 text-foreground">{change.to_category_name}</td>
											<td class="px-3 py-2 text-right font-medium text-foreground">
												{change.item_count}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</div>
			{/if}

			{#if reCategorizeResult}
				<div class="mt-4 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
					<div class="rounded-md border border-border/60 bg-muted/20 p-2">
						<div class="text-xs text-muted-foreground">{t('rules.recat_total')}</div>
						<div class="font-semibold text-foreground">{reCategorizeResult.total_items}</div>
					</div>
					<div class="rounded-md border border-border/60 bg-muted/20 p-2">
						<div class="text-xs text-muted-foreground">{t('rules.recat_processed')}</div>
						<div class="font-semibold text-foreground">{reCategorizeResult.processed_items}</div>
					</div>
					<div class="rounded-md border border-border/60 bg-muted/20 p-2">
						<div class="text-xs text-muted-foreground">{t('rules.recat_updated')}</div>
						<div class="font-semibold text-foreground">{reCategorizeResult.updated_items}</div>
					</div>
					<div class="rounded-md border border-border/60 bg-muted/20 p-2">
						<div class="text-xs text-muted-foreground">{t('rules.recat_unchanged')}</div>
						<div class="font-semibold text-foreground">{reCategorizeResult.unchanged_items}</div>
					</div>
					<div class="rounded-md border border-border/60 bg-muted/20 p-2">
						<div class="text-xs text-muted-foreground">{t('rules.recat_skipped_manual')}</div>
						<div class="font-semibold text-foreground">
							{reCategorizeResult.skipped_manual_items}
						</div>
					</div>
					<div class="rounded-md border border-border/60 bg-muted/20 p-2">
						<div class="text-xs text-muted-foreground">{t('rules.recat_overridden_manual')}</div>
						<div class="font-semibold text-foreground">
							{reCategorizeResult.overridden_manual_items}
						</div>
					</div>
					<div class="rounded-md border border-border/60 bg-muted/20 p-2">
						<div class="text-xs text-muted-foreground">{t('rules.recat_categorized')}</div>
						<div class="font-semibold text-foreground">{reCategorizeResult.categorized_items}</div>
					</div>
					<div class="rounded-md border border-border/60 bg-muted/20 p-2">
						<div class="text-xs text-muted-foreground">{t('rules.recat_uncategorized')}</div>
						<div class="font-semibold text-foreground">
							{reCategorizeResult.uncategorized_items}
						</div>
					</div>
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<!-- Rules list -->
	<Card.Root>
		<Card.Header>
			<Card.Title>{t('rules.rules_count', { count: String(filteredRules.length) })}</Card.Title>
			<Card.Description>{t('rules.rules_desc')}</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if loading}
				<p class="text-muted-foreground">{t('rules.loading')}</p>
			{:else if filteredRules.length === 0}
				<p class="py-4 text-center text-muted-foreground">{t('rules.no_rules')}</p>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-border text-left text-muted-foreground">
								<th class="pb-3 font-medium">{t('rules.label_keyword')}</th>
								<th class="pb-3 font-medium">{t('rules.label_match_type')}</th>
								<th class="pb-3 font-medium">{t('rules.label_category')}</th>
								<th class="pb-3 font-medium">{t('rules.label_priority')}</th>
								<th class="pb-3 text-right font-medium">{t('rules.label_actions')}</th>
							</tr>
						</thead>
						<tbody>
							{#each filteredRules as rule (rule.id)}
								<tr class="border-b border-border/50 transition-colors hover:bg-accent/20">
									{#if editId === rule.id}
										<td class="py-3">
											<input
												type="text"
												class="w-full rounded-md border border-input bg-background px-2 py-1 font-mono text-sm text-foreground"
												bind:value={editKeyword}
											/>
										</td>
										<td class="py-3">
											<select
												class="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
												bind:value={editMatchType}
											>
												<option value="contains">{t('rules.match_contains')}</option>
												<option value="exact">{t('rules.match_exact')}</option>
											</select>
										</td>
										<td class="py-3">
											<select
												class="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
												bind:value={editCategoryId}
											>
												{#each categories as cat (cat.id)}
													<option value={cat.id}>{cat.icon} {cat.name}</option>
												{/each}
											</select>
										</td>
										<td class="py-3">
											<input
												type="number"
												min="0"
												max="100"
												step="1"
												class="w-24 rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
												bind:value={editPriority}
											/>
										</td>
										<td class="py-3 text-right">
											<div class="flex justify-end gap-1">
												<Button size="sm" onclick={saveEdit}>
													<Check class="h-3.5 w-3.5" />
												</Button>
												<Button size="sm" variant="ghost" onclick={cancelEdit}>
													<X class="h-3.5 w-3.5" />
												</Button>
											</div>
										</td>
									{:else}
										<td class="py-3 font-mono text-foreground">{rule.keyword}</td>
										<td class="py-3">
											<Badge variant="secondary">{matchTypeLabel(rule.match_type)}</Badge>
										</td>
										<td class="py-3">
											<span class="flex items-center gap-2">
												<span>{getCategoryIcon(rule.category_id)}</span>
												<span class="text-foreground">{rule.category_name}</span>
											</span>
										</td>
										<td class="py-3 font-mono text-foreground">{rule.priority}</td>
										<td class="py-3 text-right">
											<div class="flex justify-end gap-1">
												<Button size="sm" variant="ghost" onclick={() => startEdit(rule)}>
													<Pencil class="h-3.5 w-3.5" />
												</Button>
												<Button
													size="sm"
													variant="ghost"
													class="text-destructive hover:text-destructive"
													onclick={() => handleDelete(rule)}
												>
													<Trash2 class="h-3.5 w-3.5" />
												</Button>
											</div>
										</td>
									{/if}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root class="border-destructive/40">
		<Card.Header>
			<Card.Title>{t('rules.danger_title')}</Card.Title>
			<Card.Description>
				{t('rules.danger_desc')}
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="space-y-3">
				<label class="block text-sm text-muted-foreground" for="delete-all-rules-confirm">
					{t('rules.danger_type_delete')}
				</label>
				<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
					<input
						id="delete-all-rules-confirm"
						type="text"
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground sm:flex-1"
						bind:value={deleteAllConfirmation}
						placeholder="DELETE"
						autocomplete="off"
					/>
					<Button
						variant="destructive"
						onclick={handleDeleteAllRules}
						disabled={deletingAllRules || deleteAllConfirmation.trim() !== 'DELETE'}
					>
						{deletingAllRules ? t('rules.danger_deleting') : t('rules.danger_delete_all')}
					</Button>
				</div>
				{#if deleteAllSuccessMessage}
					<p class="text-sm text-foreground">{deleteAllSuccessMessage}</p>
				{/if}
			</div>
		</Card.Content>
	</Card.Root>
</div>
