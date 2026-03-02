<script lang="ts">
	import { onDestroy } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { extractDebugImportText, hardResetData } from '$lib/api';
	import { AlertTriangle, Copy, RotateCcw } from '@lucide/svelte';

	const confirmationPhrase = 'RESET';

	let confirmationInput = $state('');
	let isResetting = $state(false);
	let successMessage = $state('');
	let errorMessage = $state('');
	let debugFile = $state<File | null>(null);
	let debugText = $state('');
	let isExtracting = $state(false);
	let debugSuccessMessage = $state('');
	let debugErrorMessage = $state('');
	const debugSuccessFadeMs = 3000;
	let debugSuccessTimeout: ReturnType<typeof setTimeout> | null = null;

	let canReset = $derived(confirmationInput === confirmationPhrase && !isResetting);
	let canExtractDebugText = $derived(Boolean(debugFile) && !isExtracting);

	function scheduleDebugSuccessFade(): void {
		if (debugSuccessTimeout) {
			clearTimeout(debugSuccessTimeout);
		}

		debugSuccessTimeout = setTimeout(() => {
			debugSuccessMessage = '';
			debugSuccessTimeout = null;
		}, debugSuccessFadeMs);
	}

	onDestroy(() => {
		if (debugSuccessTimeout) {
			clearTimeout(debugSuccessTimeout);
		}
	});

	async function handleHardReset() {
		if (!canReset) {
			return;
		}

		if (
			!window.confirm(
				'Hard reset will permanently clear imported receipts, learned mappings, categories, rules, and backups before reseeding defaults. Continue?'
			)
		) {
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
			successMessage = deletedSummary ? `${result.message} (${deletedSummary})` : result.message;
			confirmationInput = '';
		} catch (e: any) {
			errorMessage = e?.message || 'Hard reset failed';
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
				? `Extracted ${result.pages} pages (${result.characters} characters) and copied to clipboard.`
				: `Extracted ${result.pages} pages (${result.characters} characters). Clipboard access failed; copy manually from the text box.`;
			if (copied) {
				scheduleDebugSuccessFade();
			}
		} catch (e: any) {
			debugErrorMessage = e?.message || 'Failed to extract PDF text';
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
			debugSuccessMessage = 'Copied text to clipboard.';
			scheduleDebugSuccessFade();
			return;
		}

		debugSuccessMessage = '';
		debugErrorMessage = 'Clipboard access failed. Select and copy the textarea content manually.';
	}
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-3xl font-bold text-foreground">Settings</h1>
	</div>

	<Card.Root class="border-destructive/40">
		<Card.Header>
			<Card.Title class="flex items-center gap-2 text-destructive">
				<AlertTriangle class="h-5 w-5" />
				Hard Reset
			</Card.Title>
			<Card.Description>
				This clears all imported data and taxonomy changes, then reseeds the default categories and
				rules.
			</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
				Type <span class="font-semibold">RESET</span> to unlock this action.
			</div>

			<div class="flex flex-col gap-3 sm:flex-row sm:items-end">
				<div class="sm:flex-1">
					<label class="mb-1 block text-sm text-muted-foreground" for="reset-confirmation">
						Confirmation
					</label>
					<input
						id="reset-confirmation"
						type="text"
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
						bind:value={confirmationInput}
						placeholder="Type RESET"
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
					{isResetting ? 'Resetting...' : 'Run Hard Reset'}
				</Button>
			</div>

			{#if successMessage}
				<div class="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">
					{successMessage}
				</div>
			{/if}

			{#if errorMessage}
				<div class="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
					{errorMessage}
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title>Debug Import (Raw PDF Text)</Card.Title>
			<Card.Description>
				Upload a PDF to extract raw text with no parser preprocessing. You can review or redact before
				sharing.
			</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="space-y-2">
				<label class="block text-sm text-muted-foreground" for="debug-import-file">PDF file</label>
				<input
					id="debug-import-file"
					type="file"
					accept=".pdf,application/pdf"
					onchange={handleDebugFileChange}
					class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
				/>
			</div>

			<div class="flex flex-wrap gap-3">
				<Button onclick={handleExtractAndCopy} disabled={!canExtractDebugText} class="min-w-36">
					{isExtracting ? 'Extracting...' : 'Extract & Copy'}
				</Button>
				{#if debugText}
					<Button onclick={handleCopyText} variant="outline" disabled={isExtracting}>
						<Copy class="mr-2 h-4 w-4" />
						Copy Text
					</Button>
				{/if}
			</div>

			{#if debugSuccessMessage}
				<div class="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">
					{debugSuccessMessage}
				</div>
			{/if}

			{#if debugErrorMessage}
				<div class="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
					{debugErrorMessage}
				</div>
			{/if}

			{#if debugText}
				<div class="space-y-2">
					<label class="block text-sm text-muted-foreground" for="debug-import-text">Extracted text</label>
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
