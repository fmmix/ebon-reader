<script lang="ts">
	import { fetchReceipts, type Receipt } from '$lib/api';
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Receipt as ReceiptIcon, Upload, ChevronRight, ShoppingBag, Gift } from '@lucide/svelte';

	let receipts = $state<Receipt[]>([]);
	let loading = $state(true);

	onMount(async () => {
		try {
			receipts = await fetchReceipts();
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
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold text-foreground">Receipts</h1>
			<p class="mt-1 text-muted-foreground">Browse your imported supermarket receipts</p>
		</div>
		<Button href="/import">
			<Upload class="mr-2 h-4 w-4" />
			Import eBon
		</Button>
	</div>

	{#if loading}
		<p class="text-muted-foreground">Loading...</p>
	{:else if receipts.length === 0}
		<Card.Root class="border-dashed">
			<Card.Content class="flex flex-col items-center py-12">
				<ReceiptIcon class="mb-3 h-10 w-10 text-muted-foreground" />
				<p class="text-foreground">No receipts yet</p>
				<p class="mt-1 text-sm text-muted-foreground">Import an eBon to see it here</p>
				<Button href="/import" class="mt-4">
					<Upload class="mr-2 h-4 w-4" />
					Import eBon
				</Button>
			</Card.Content>
		</Card.Root>
	{:else}
		<div class="space-y-2">
			{#each receipts as receipt (receipt.id)}
				<a href="/receipts/{receipt.id}" class="block">
					<Card.Root class="transition-colors hover:bg-accent/20">
						<Card.Content class="flex items-center justify-between py-4">
							<div class="flex items-center gap-4">
								<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
									<ShoppingBag class="h-5 w-5 text-primary" />
								</div>
								<div>
									<p class="font-medium text-foreground">{receipt.store_name}</p>
									<p class="text-sm text-muted-foreground">{formatDate(receipt.purchased_at)}</p>
								</div>
							</div>
							<div class="flex items-center gap-4">
								<div class="text-right">
									<div class="flex items-center justify-end gap-2">
										<div class="flex w-24 justify-end">
											{#if receipt.total_bonus > 0}
												<Badge variant="secondary" class="text-xs">
													<Gift class="mr-1 h-3 w-3" />
													{receipt.total_bonus.toFixed(2)} €
												</Badge>
											{/if}
										</div>
										<p class="font-medium text-foreground">
											{receipt.total_amount.toFixed(2)} €
										</p>
									</div>
									<p class="text-xs text-muted-foreground">{receipt.item_count} items</p>
								</div>
								<ChevronRight class="h-4 w-4 text-muted-foreground" />
							</div>
						</Card.Content>
					</Card.Root>
				</a>
			{/each}
		</div>
	{/if}
</div>
