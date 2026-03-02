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
	import { formatVatClass } from '$lib/utils/vat';

	let receipt = $state<ReceiptDetail | null>(null);
	let categories = $state<ProductCategory[]>([]);
	let loading = $state(true);
	let error = $state('');
	let rewardBonusEntries = $derived(
		receipt ? receipt.bonus_entries.filter((bonus) => bonus.type !== 'redeemed') : []
	);
	let redeemedBonusEntries = $derived(
		receipt ? receipt.bonus_entries.filter((bonus) => bonus.type === 'redeemed') : []
	);

	onMount(async () => {
		const id = Number(page.params.id);
		try {
			[receipt, categories] = await Promise.all([
				fetchReceiptDetail(id),
				fetchCategories()
			]);
		} catch (e: any) {
			error = e?.message || 'Failed to load receipt';
		} finally {
			loading = false;
		}
	});

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString('de-DE', {
			day: '2-digit',
			month: '2-digit',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
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
			error = e?.message || 'Failed to update category';
		}
	}

	async function handleDelete() {
		if (!receipt) return;
		try {
			await deleteReceipt(receipt.id);
			goto('/receipts');
		} catch (e: any) {
			error = e?.message || 'Failed to delete receipt';
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
				<h1 class="text-3xl font-bold text-foreground">Receipt Detail</h1>
				<p class="mt-1 text-muted-foreground">Items, categories, bonus, and metadata</p>
			</div>
		</div>
		{#if receipt}
			<Button variant="destructive" onclick={handleDelete}>
				<Trash2 class="mr-2 h-4 w-4" />
				Delete Receipt
			</Button>
		{/if}
	</div>

	{#if loading}
		<p class="text-muted-foreground">Loading...</p>
	{:else if error}
		<div class="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
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
							{receipt.total_amount.toFixed(2)} €
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
				<Card.Title>Items ({receipt.items.length})</Card.Title>
				<Card.Description>Change categories using the dropdown — saves automatically</Card.Description>
			</Card.Header>
			<Card.Content>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-border text-left text-muted-foreground">
								<th class="pb-3 font-medium">Product</th>
								<th class="pb-3 text-center font-medium">Qty</th>
								<th class="pb-3 text-right font-medium">Unit</th>
								<th class="pb-3 text-right font-medium">Total</th>
								<th class="pb-3 font-medium">VAT</th>
								<th class="pb-3 font-medium">Category</th>
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
										{item.unit_price.toFixed(2)} €
									</td>
									<td class="py-3 text-right font-medium text-foreground">
										{item.total_price.toFixed(2)} €
									</td>
									<td class="py-3">
										<Badge variant="secondary" class="text-xs">{formatVatClass(item.vat_class)}</Badge>
									</td>
									<td class="py-3">
										<select
											class="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
											value={item.category_id ?? ''}
											onchange={(e) => {
												const val = (e.target as HTMLSelectElement).value;
												handleCategoryChange(item.id, val ? Number(val) : null);
											}}
										>
											<option value="">Uncategorized</option>
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
						<Card.Title>Bonus & Rewards</Card.Title>
					</div>
					<Card.Description>{receipt.total_bonus.toFixed(2)} € total savings</Card.Description>
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
										<Badge variant="secondary" class="text-xs">{bonus.type}</Badge>
									</div>
								</div>
								<p class="font-medium text-emerald-400">{bonus.amount.toFixed(2)} €</p>
							</div>
						{/each}

						{#if redeemedBonusEntries.length > 0}
							{#if rewardBonusEntries.length > 0}
								<Separator.Root />
							{/if}
							<div class="space-y-2">
								<p class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
									Used Bonus Credit
								</p>
								{#each redeemedBonusEntries as bonus (bonus.id)}
									<div class="flex items-center justify-between">
										<div>
											<p class="text-sm font-medium text-muted-foreground">{bonus.description}</p>
											<Badge variant="outline" class="text-xs">redeemed</Badge>
										</div>
										<p class="font-medium text-destructive">-{bonus.amount.toFixed(2)} €</p>
									</div>
								{/each}
							</div>
						{/if}

						{#if receipt.bonus_balance !== null}
							<Separator.Root />
							<div class="flex items-center justify-between text-sm">
								<span class="text-muted-foreground">Bonus Balance</span>
								<span class="font-medium text-foreground">
									{receipt.bonus_balance.toFixed(2)} €
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
					<Card.Title>eBon Metadata</Card.Title>
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
						<p class="text-muted-foreground">Source File</p>
						<p class="text-foreground">{receipt.source_filename}</p>
					</div>
					<div>
						<p class="text-muted-foreground">Imported</p>
						<p class="text-foreground">{formatDate(receipt.imported_at)}</p>
					</div>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}
</div>
