<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import {
		fetchReceiptDetail,
		deleteReceipt,
		updateItemCategory,
		fetchCategories,
		type ReceiptDetail,
		type ProductCategory
	} from '$lib/api';
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import * as Separator from '$lib/components/ui/separator';
	import { ArrowLeft, Gift, Ticket, Sparkles, FileText, Store, Trash2 } from '@lucide/svelte';
	import { formatDateTime } from '$lib/utils/date';
	import { formatVatClass } from '$lib/utils/vat';
	import { t } from '$lib/i18n/index.svelte';
	import { formatCurrency } from '$lib/utils/format';
	import { bonusTypeLabel, isDeductionBonusType, computeProgramSavings } from '$lib/utils/bonus';
	import { findUncategorizedId } from '$lib/utils/category';

	let receipt = $state<ReceiptDetail | null>(null);
	let categories = $state<ProductCategory[]>([]);
	let loading = $state(true);
	let error = $state('');

	let programSavings = $derived(
		receipt
			? computeProgramSavings(receipt.bonus_entries, receipt.total_bonus)
			: 0
	);
	let rewardBonusEntries = $derived(
		receipt
			? receipt.bonus_entries.filter((bonus) => !isDeductionBonusType(bonus.type))
			: []
	);
	let deductionBonusEntries = $derived(
		receipt
			? receipt.bonus_entries.filter((bonus) => isDeductionBonusType(bonus.type))
			: []
	);
	let uncategorizedId = $derived(findUncategorizedId(categories));

	onMount(async () => {
		const id = Number(page.params.id);
		try {
			[receipt, categories] = await Promise.all([fetchReceiptDetail(id), fetchCategories()]);
		} catch (e: any) {
			error = e?.message || t('receipts.err_load');
		} finally {
			loading = false;
		}
	});

	function formatDate(iso: string): string {
		return formatDateTime(iso);
	}

	async function handleCategoryChange(itemId: number, categoryId: number | null) {
		if (!receipt) return;
		try {
			const result = await updateItemCategory(receipt.id, itemId, categoryId);
			// Update local state
			const item = receipt.items.find((i) => i.id === itemId);
			if (item) {
				item.category_id = result.category_id;
				item.category_name = result.category_name;
				item.category_icon = result.category_icon;
				receipt = { ...receipt };
			}
		} catch (e: any) {
			error = e?.message || t('receipts.err_update_category');
		}
	}

	async function handleDelete() {
		if (!receipt) return;
		if (!window.confirm(t('receipts.delete_confirm'))) return;
		try {
			await deleteReceipt(receipt.id);
			goto('/receipts');
		} catch (e: any) {
			error = e?.message || t('receipts.err_delete');
		}
	}
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-3">
			<Button variant="ghost" size="icon" href="/receipts">
				<ArrowLeft class="h-4 w-4" />
			</Button>
			<div>
				<h1 class="text-3xl font-bold text-foreground">{t('receipts.detail_title')}</h1>
				<p class="mt-1 text-muted-foreground">{t('receipts.detail_subtitle')}</p>
			</div>
		</div>
		{#if receipt}
			<Button variant="destructive" onclick={handleDelete}>
				<Trash2 class="mr-2 h-4 w-4" />
				{t('receipts.delete')}
			</Button>
		{/if}
	</div>

	{#if loading}
		<p class="text-muted-foreground">{t('receipts.loading')}</p>
	{:else if error}
		<div
			class="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
		>
			{error}
		</div>
	{:else if receipt}
		<!-- Receipt header -->
		<Card.Root>
			<Card.Header>
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-3">
						<Store class="h-5 w-5 text-primary" />
						<div>
							<Card.Title>{receipt.store_name}</Card.Title>
							<Card.Description>{receipt.store_address}</Card.Description>
						</div>
					</div>
					<div class="text-right">
						<p class="text-2xl font-bold text-foreground">
							{formatCurrency(receipt.total_amount)}
						</p>
						<p class="text-sm text-muted-foreground">
							{formatDate(receipt.purchased_at)}
						</p>
					</div>
				</div>
			</Card.Header>
		</Card.Root>

		<!-- Items table -->
		<Card.Root>
			<Card.Header>
				<Card.Title>{t('receipts.items_title', { count: receipt.items.length })}</Card.Title>
				<Card.Description>{t('receipts.items_desc')}</Card.Description>
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
							{#each receipt.items as item (item.id)}
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
												handleCategoryChange(item.id, val ? Number(val) : null);
											}}
										>
											{#each categories as cat (cat.id)}
												<option value={cat.id}>{cat.icon} {cat.name}</option>
											{/each}
										</select>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</Card.Content>
		</Card.Root>

		<!-- Bonus card -->
		{#if receipt.bonus_entries.length > 0}
			<Card.Root>
				<Card.Header>
					<div class="flex items-center gap-2">
						<Sparkles class="h-4 w-4 text-yellow-400" />
						<Card.Title>{t('receipts.bonus_title')}</Card.Title>
					</div>
					<Card.Description
						>{t('receipts.total_savings', {
							amount: formatCurrency(programSavings)
						})}</Card.Description
					>
				</Card.Header>
				<Card.Content>
					<div class="space-y-3">
						{#each rewardBonusEntries as bonus (bonus.id)}
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
								<p class="font-medium text-emerald-400">{formatCurrency(bonus.amount)}</p>
							</div>
						{/each}

						{#if deductionBonusEntries.length > 0}
							{#if rewardBonusEntries.length > 0}
								<Separator.Root />
							{/if}
							<div class="space-y-2">
								<p class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
									{t('receipts.applied_deductions')}
								</p>
								{#each deductionBonusEntries as bonus (bonus.id)}
									<div class="flex items-center justify-between">
										<div>
											<p class="text-sm font-medium text-muted-foreground">{bonus.description}</p>
											<Badge variant="outline" class="text-xs">{bonusTypeLabel(bonus.type, t)}</Badge>
										</div>
										<p class="font-medium text-destructive">
											-{formatCurrency(Math.abs(bonus.amount))}
										</p>
									</div>
								{/each}
							</div>
						{/if}

						{#if receipt.bonus_balance !== null}
							<Separator.Root />
							<div class="flex items-center justify-between text-sm">
								<span class="text-muted-foreground">{t('receipts.bonus_balance')}</span>
								<span class="font-medium text-foreground">
									{formatCurrency(receipt.bonus_balance)}
								</span>
							</div>
						{/if}
					</div>
				</Card.Content>
			</Card.Root>
		{/if}

		<!-- Metadata card -->
		<Card.Root>
			<Card.Header>
				<div class="flex items-center gap-2">
					<FileText class="h-4 w-4 text-muted-foreground" />
					<Card.Title>{t('receipts.metadata_title')}</Card.Title>
				</div>
			</Card.Header>
			<Card.Content>
				<div class="grid grid-cols-2 gap-4 text-sm">
					{#if receipt.tse_transaction}
						<div>
							<p class="text-muted-foreground">TSE-Transaktion</p>
							<p class="font-mono text-foreground">{receipt.tse_transaction}</p>
						</div>
					{/if}
					{#if receipt.bon_nr}
						<div>
							<p class="text-muted-foreground">Bon-Nr.</p>
							<p class="font-mono text-foreground">{receipt.bon_nr}</p>
						</div>
					{/if}
					{#if receipt.store_id}
						<div>
							<p class="text-muted-foreground">Markt</p>
							<p class="font-mono text-foreground">{receipt.store_id}</p>
						</div>
					{/if}
					{#if receipt.register_nr}
						<div>
							<p class="text-muted-foreground">Kasse</p>
							<p class="font-mono text-foreground">{receipt.register_nr}</p>
						</div>
					{/if}
					<div>
						<p class="text-muted-foreground">{t('receipts.source_file')}</p>
						<p class="text-foreground">{receipt.source_filename}</p>
					</div>
					<div>
						<p class="text-muted-foreground">{t('receipts.imported')}</p>
						<p class="text-foreground">{formatDate(receipt.imported_at)}</p>
					</div>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}
</div>
