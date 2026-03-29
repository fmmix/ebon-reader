<script lang="ts">
	import { onDestroy } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import {
		extractDebugImportText,
		fetchLidlScraperScript,
		generateSyntheticData,
		hardResetData,
		deleteSyntheticData
	} from '$lib/api';
	import {
		AlertTriangle,
		Copy,
		RotateCcw,
		Globe,
		ShoppingCart,
		FlaskConical,
		Trash2
	} from '@lucide/svelte';
	import { t, getLocale, setLocale, AVAILABLE_LOCALES } from '$lib/i18n/index.svelte';

	const confirmationPhrase = 'RESET';

	let confirmationInput = $state('');
	let isResetting = $state(false);
	let successMessage = $state('');
	let errorMessage = $state('');
	let debugFile = $state<File | null>(null);
	let debugFileInput = $state<HTMLInputElement | null>(null);
	let debugText = $state('');
	let isExtracting = $state(false);
	let debugSuccessMessage = $state('');
	let debugErrorMessage = $state('');
	const debugSuccessFadeMs = 3000;
	let debugSuccessTimeout: ReturnType<typeof setTimeout> | null = null;
	let isLidlCopying = $state(false);
	let lidlCopied = $state(false);
	let lidlCopiedTimeout: ReturnType<typeof setTimeout> | null = null;
	let lidlScriptText = $state('');
	let lidlErrorMessage = $state('');
	let syntheticStore = $state('all');
	let syntheticCountPerStore = $state(5);
	let isGeneratingSynthetic = $state(false);
	let isDeletingSynthetic = $state(false);
	let syntheticSuccessMessage = $state('');
	let syntheticErrorMessage = $state('');

	let canReset = $derived(confirmationInput === confirmationPhrase && !isResetting);
	let canExtractDebugText = $derived(Boolean(debugFile) && !isExtracting);
	let canGenerateSynthetic = $derived(!isGeneratingSynthetic && !isDeletingSynthetic);
	let canDeleteSynthetic = $derived(!isDeletingSynthetic && !isGeneratingSynthetic);

	function scheduleDebugSuccessFade(): void {
		if (debugSuccessTimeout) {
			clearTimeout(debugSuccessTimeout);
		}

		debugSuccessTimeout = setTimeout(() => {
			debugSuccessMessage = '';
			debugSuccessTimeout = null;
		}, debugSuccessFadeMs);
	}

	function scheduleLidlCopiedFade(): void {
		if (lidlCopiedTimeout) {
			clearTimeout(lidlCopiedTimeout);
		}

		lidlCopied = true;
		lidlCopiedTimeout = setTimeout(() => {
			lidlCopied = false;
			lidlCopiedTimeout = null;
		}, 3000);
	}

	onDestroy(() => {
		if (debugSuccessTimeout) clearTimeout(debugSuccessTimeout);
		if (lidlCopiedTimeout) clearTimeout(lidlCopiedTimeout);
	});

	async function handleHardReset() {
		if (!canReset) {
			return;
		}

		if (!window.confirm(t('settings.hard_reset_confirm'))) {
			return;
		}

		isResetting = true;
		successMessage = '';
		errorMessage = '';

		try {
			const result = await hardResetData();
			const deletedSummary = result.deleted
				? Object.entries(result.deleted)
						.map(([table, count]) => `${table}: ${count}`)
						.join(', ')
				: '';
			const msg = t('settings.hard_reset_success');
			successMessage = deletedSummary ? `${msg} (${deletedSummary})` : msg;
			confirmationInput = '';
		} catch (e: any) {
			errorMessage = e?.message || t('settings.hard_reset_failed');
		} finally {
			isResetting = false;
		}
	}

	function handleDebugFileChange(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		debugFile = input.files?.[0] ?? null;
		debugSuccessMessage = '';
		debugErrorMessage = '';
	}

	async function copyDebugTextToClipboard(text: string): Promise<boolean> {
		try {
			await navigator.clipboard.writeText(text);
			return true;
		} catch {
			return false;
		}
	}

	async function handleExtractAndCopy() {
		if (!debugFile || isExtracting) {
			return;
		}

		isExtracting = true;
		debugSuccessMessage = '';
		debugErrorMessage = '';

		try {
			const result = await extractDebugImportText(debugFile);
			debugText = result.text;
			const copied = await copyDebugTextToClipboard(result.text);
			debugSuccessMessage = copied
				? t('settings.debug_extracted', {
						pages: String(result.pages),
						chars: String(result.characters)
					})
				: t('settings.debug_extracted_no_clip', {
						pages: String(result.pages),
						chars: String(result.characters)
					});
			if (copied) {
				scheduleDebugSuccessFade();
			}
		} catch (e: any) {
			debugErrorMessage = e?.message || t('settings.debug_extract_failed');
		} finally {
			isExtracting = false;
		}
	}

	async function handleCopyText() {
		if (!debugText) {
			return;
		}

		debugErrorMessage = '';
		const copied = await copyDebugTextToClipboard(debugText);
		if (copied) {
			debugSuccessMessage = t('settings.debug_copied');
			scheduleDebugSuccessFade();
			return;
		}

		debugSuccessMessage = '';
		debugErrorMessage = t('settings.debug_clip_failed');
	}

	async function handleLidlCopy() {
		if (isLidlCopying) {
			return;
		}

		isLidlCopying = true;
		lidlCopied = false;
		lidlErrorMessage = '';

		try {
			const script = await fetchLidlScraperScript();
			lidlScriptText = script;
			const copied = await copyDebugTextToClipboard(script);

			if (copied) {
				lidlErrorMessage = '';
				lidlScriptText = '';
				scheduleLidlCopiedFade();
				return;
			}

			lidlErrorMessage = t('settings.lidl_clip_failed');
		} catch (e: any) {
			lidlErrorMessage = e?.message || t('settings.lidl_fetch_failed');
		} finally {
			isLidlCopying = false;
		}
	}

	async function handleLidlRetryCopy() {
		if (!lidlScriptText || isLidlCopying) {
			return;
		}

		isLidlCopying = true;
		lidlCopied = false;

		const copied = await copyDebugTextToClipboard(lidlScriptText);
		if (copied) {
			lidlErrorMessage = '';
			lidlScriptText = '';
			scheduleLidlCopiedFade();
			isLidlCopying = false;
			return;
		}

		lidlErrorMessage = t('settings.lidl_clip_failed');
		isLidlCopying = false;
	}

	function formatSyntheticStoreLabel(storeSlug: string): string {
		if (storeSlug === 'rewe') return 'REWE';
		if (storeSlug === 'lidl') return 'Lidl';
		if (storeSlug === 'kaufland') return 'Kaufland';
		return storeSlug;
	}

	function clampSyntheticCount(value: number): number {
		if (!Number.isFinite(value)) return 5;
		if (value < 1) return 1;
		if (value > 50) return 50;
		return Math.floor(value);
	}

	async function handleGenerateSynthetic() {
		syntheticErrorMessage = '';
		syntheticSuccessMessage = '';
		syntheticCountPerStore = clampSyntheticCount(syntheticCountPerStore);
		isGeneratingSynthetic = true;

		try {
			const result = await generateSyntheticData({
				store: syntheticStore as 'all' | 'rewe' | 'lidl' | 'kaufland',
				count_per_store: syntheticCountPerStore
			});
			const storeSummary = Object.entries(result.stores)
				.map(
					([storeSlug, counts]) =>
						`${formatSyntheticStoreLabel(storeSlug)}: +${counts.inserted}, ${t('settings.synthetic_skipped_short')} ${counts.skipped}`
				)
				.join(' | ');
			syntheticSuccessMessage = `${t('settings.synthetic_generate_success_total', {
				inserted: String(result.total_inserted),
				skipped: String(result.total_skipped)
			})} ${storeSummary}`;
		} catch (e: any) {
			syntheticErrorMessage = e?.message || t('settings.synthetic_generate_failed');
		} finally {
			isGeneratingSynthetic = false;
		}
	}

	async function handleDeleteSynthetic() {
		if (!window.confirm(t('settings.synthetic_delete_confirm'))) {
			return;
		}

		syntheticErrorMessage = '';
		syntheticSuccessMessage = '';
		isDeletingSynthetic = true;

		try {
			const result = await deleteSyntheticData();
			const deletedSummary = Object.entries(result.deleted)
				.map(([table, count]) => `${table}: ${count}`)
				.join(', ');
			syntheticSuccessMessage = deletedSummary
				? `${t('settings.synthetic_delete_success')} (${deletedSummary})`
				: t('settings.synthetic_delete_success');
		} catch (e: any) {
			syntheticErrorMessage = e?.message || t('settings.synthetic_delete_failed');
		} finally {
			isDeletingSynthetic = false;
		}
	}
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-3xl font-bold text-foreground">{t('settings.title')}</h1>
		<p class="mt-1 text-muted-foreground">{t('settings.subtitle')}</p>
	</div>

	<Card.Root>
		<Card.Header>
			<Card.Title class="flex items-center gap-2">
				<Globe class="h-5 w-5" />
				{t('settings.language')}
			</Card.Title>
			<Card.Description>
				{t('settings.language_desc')}
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="flex gap-2">
				{#each AVAILABLE_LOCALES as loc (loc.value)}
					<Button
						variant={getLocale() === loc.value ? 'default' : 'outline'}
						onclick={() => setLocale(loc.value)}
						class="min-w-24"
					>
						{loc.label}
					</Button>
				{/each}
			</div>
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title class="flex items-center gap-2">
				<ShoppingCart class="h-5 w-5" />
				{t('settings.lidl_title')}
			</Card.Title>
			<Card.Description>
				{t('settings.lidl_desc')}
			</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="space-y-1 text-sm text-muted-foreground">
				<p>{t('settings.lidl_step1')}</p>
				<p>{t('settings.lidl_step2')}</p>
				<p>{t('settings.lidl_step3')}</p>
				<p>{t('settings.lidl_step4')}</p>
			</div>
			<div class="flex items-center gap-3">
				<Button onclick={handleLidlCopy} disabled={isLidlCopying}>
					<Copy class="mr-2 h-4 w-4" />
					{isLidlCopying ? t('settings.lidl_copying') : t('settings.lidl_copy')}
				</Button>
				{#if lidlCopied}
					<span class="text-sm text-emerald-600">{t('settings.lidl_copied')}</span>
				{/if}
			</div>

			{#if lidlErrorMessage}
				<div
					class="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
				>
					{lidlErrorMessage}
				</div>
			{/if}

			{#if lidlScriptText}
				<div class="space-y-2">
					<div class="flex flex-wrap gap-3">
						<Button onclick={handleLidlRetryCopy} variant="outline" disabled={isLidlCopying}>
							<Copy class="mr-2 h-4 w-4" />
							{t('settings.lidl_retry_copy')}
						</Button>
					</div>
					<label class="block text-sm text-muted-foreground" for="lidl-script-text"
						>{t('settings.lidl_text_label')}</label
					>
					<textarea
						id="lidl-script-text"
						value={lidlScriptText}
						rows="12"
						readonly
						class="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm text-foreground"
					></textarea>
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title class="flex items-center gap-2">
				<FlaskConical class="h-5 w-5" />
				{t('settings.synthetic_title')}
			</Card.Title>
			<Card.Description>
				{t('settings.synthetic_desc')}
			</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="grid gap-3 sm:grid-cols-2">
				<div>
					<label class="mb-1 block text-sm text-muted-foreground" for="synthetic-store">
						{t('settings.synthetic_store_label')}
					</label>
					<select
						id="synthetic-store"
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
						bind:value={syntheticStore}
						disabled={isGeneratingSynthetic || isDeletingSynthetic}
					>
						<option value="all">{t('settings.synthetic_store_all')}</option>
						<option value="rewe">{t('settings.synthetic_store_rewe')}</option>
						<option value="lidl">{t('settings.synthetic_store_lidl')}</option>
						<option value="kaufland">{t('settings.synthetic_store_kaufland')}</option>
					</select>
				</div>
				<div>
					<label class="mb-1 block text-sm text-muted-foreground" for="synthetic-count">
						{t('settings.synthetic_count_label')}
					</label>
					<input
						id="synthetic-count"
						type="number"
						min="1"
						max="50"
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
						bind:value={syntheticCountPerStore}
						onblur={() => {
							syntheticCountPerStore = clampSyntheticCount(syntheticCountPerStore);
						}}
						disabled={isGeneratingSynthetic || isDeletingSynthetic}
					/>
				</div>
			</div>

			<div class="flex flex-wrap gap-3">
				<Button onclick={handleGenerateSynthetic} disabled={!canGenerateSynthetic}>
					{isGeneratingSynthetic
						? t('settings.synthetic_generating')
						: t('settings.synthetic_generate_button')}
				</Button>
				<Button
					onclick={handleDeleteSynthetic}
					variant="destructive"
					disabled={!canDeleteSynthetic}
				>
					<Trash2 class="mr-2 h-4 w-4" />
					{isDeletingSynthetic
						? t('settings.synthetic_deleting')
						: t('settings.synthetic_delete_button')}
				</Button>
			</div>

			{#if syntheticSuccessMessage}
				<div
					class="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700"
				>
					{syntheticSuccessMessage}
				</div>
			{/if}

			{#if syntheticErrorMessage}
				<div
					class="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
				>
					{syntheticErrorMessage}
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root class="border-destructive/40">
		<Card.Header>
			<Card.Title class="flex items-center gap-2 text-destructive">
				<AlertTriangle class="h-5 w-5" />
				{t('settings.hard_reset')}
			</Card.Title>
			<Card.Description>
				{t('settings.hard_reset_desc')}
			</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div
				class="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
			>
				{@html t('settings.hard_reset_type')}
			</div>

			<div class="flex flex-col gap-3 sm:flex-row sm:items-end">
				<div class="sm:flex-1">
					<label class="mb-1 block text-sm text-muted-foreground" for="reset-confirmation">
						{t('settings.hard_reset_label')}
					</label>
					<input
						id="reset-confirmation"
						type="text"
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
						bind:value={confirmationInput}
						placeholder={t('settings.hard_reset_placeholder')}
						autocomplete="off"
					/>
				</div>
				<Button
					onclick={handleHardReset}
					disabled={!canReset}
					class="sm:min-w-40"
					variant="destructive"
				>
					<RotateCcw class="mr-2 h-4 w-4" />
					{isResetting ? t('settings.hard_reset_resetting') : t('settings.hard_reset_run')}
				</Button>
			</div>

			{#if successMessage}
				<div
					class="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700"
				>
					{successMessage}
				</div>
			{/if}

			{#if errorMessage}
				<div
					class="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
				>
					{errorMessage}
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title>{t('settings.debug_title')}</Card.Title>
			<Card.Description>
				{t('settings.debug_desc')}
			</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="space-y-2">
				<label class="block text-sm text-muted-foreground" for="debug-import-file-hidden"
					>{t('settings.debug_file_label')}</label
				>
				<input
					id="debug-import-file-hidden"
					type="file"
					accept=".pdf,application/pdf"
					onchange={handleDebugFileChange}
					class="sr-only"
					bind:this={debugFileInput}
				/>
				<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
					<Button type="button" variant="outline" onclick={() => debugFileInput?.click()}>
						{t('settings.debug_choose_file')}
					</Button>
					<div
						class="min-h-9 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm text-muted-foreground"
					>
						<span class="block truncate">
							{debugFile?.name || t('settings.debug_no_file')}
						</span>
					</div>
				</div>
			</div>

			<div class="flex flex-wrap gap-3">
				<Button onclick={handleExtractAndCopy} disabled={!canExtractDebugText} class="min-w-36">
					{isExtracting ? t('settings.debug_extracting') : t('settings.debug_extract_copy')}
				</Button>
				{#if debugText}
					<Button onclick={handleCopyText} variant="outline" disabled={isExtracting}>
						<Copy class="mr-2 h-4 w-4" />
						{t('settings.debug_copy')}
					</Button>
				{/if}
			</div>

			{#if debugSuccessMessage}
				<div
					class="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700"
				>
					{debugSuccessMessage}
				</div>
			{/if}

			{#if debugErrorMessage}
				<div
					class="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
				>
					{debugErrorMessage}
				</div>
			{/if}

			{#if debugText}
				<div class="space-y-2">
					<label class="block text-sm text-muted-foreground" for="debug-import-text"
						>{t('settings.debug_text_label')}</label
					>
					<textarea
						id="debug-import-text"
						bind:value={debugText}
						rows="12"
						class="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm text-foreground"
					></textarea>
				</div>
			{/if}
		</Card.Content>
	</Card.Root>
</div>
