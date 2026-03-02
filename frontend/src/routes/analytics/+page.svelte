<script lang="ts">
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { BarChart3, DollarSign, Gift } from '@lucide/svelte';
	import {
		fetchMonthlyBonus,
		fetchCategoryMonthly,
		fetchTopItems,
		fetchItemPriceTrend,
		type MonthlyBonusStat,
		type CategoryMonthlySpend,
		type TopItemStat,
		type ItemPricePoint
	} from '$lib/api';
	import BonusMonthlyChart from '$lib/components/BonusMonthlyChart.svelte';
	import ItemPriceTrendChart from '$lib/components/ItemPriceTrendChart.svelte';

	let loading = $state(true);
	let monthlyBonusData = $state<MonthlyBonusStat[]>([]);
	let categoryMonthlyData = $state<CategoryMonthlySpend[]>([]);
	let topItems = $state<TopItemStat[]>([]);
	let selectedItemName = $state('');
	let itemQuery = $state('');
	let showItemSuggestions = $state(false);
	let itemPriceTrend = $state<ItemPricePoint[]>([]);
	let loadingPriceTrend = $state(false);

	let months = $derived(Array.from(new Set(categoryMonthlyData.map((row) => row.month))).sort());

	let categoryRows = $derived.by(() => {
		type CategoryRow = {
			category_id: number | null;
			category_name: string;
			icon: string;
			color: string;
			total: number;
			byMonth: Map<string, number>;
		};

		const byCategory: Record<string, CategoryRow> = {};

		for (const point of categoryMonthlyData) {
			const key = point.category_id === null ? `uncategorized:${point.category_name}` : String(point.category_id);
			if (!byCategory[key]) {
				byCategory[key] = {
					category_id: point.category_id,
					category_name: point.category_name,
					icon: point.icon,
					color: point.color,
					total: 0,
					byMonth: new Map<string, number>()
				};
			}

			const category = byCategory[key];

			category.total += point.total_spent;
			category.byMonth.set(point.month, point.total_spent);
		}

		return Object.values(byCategory).sort((a, b) => b.total - a.total);
	});

	let maxHeatSpend = $derived(
		Math.max(
			0,
			...categoryRows.flatMap((row) => months.map((month) => row.byMonth.get(month) ?? 0))
		)
	);

	function rankTopItems(items: TopItemStat[]): TopItemStat[] {
		return [...items].sort((a, b) => {
			if (b.total_quantity !== a.total_quantity) return b.total_quantity - a.total_quantity;
			if (b.purchase_count !== a.purchase_count) return b.purchase_count - a.purchase_count;
			if (b.total_spent !== a.total_spent) return b.total_spent - a.total_spent;
			return a.item_name.localeCompare(b.item_name);
		});
	}

	let rankedItems = $derived(rankTopItems(topItems));

	let selectedItemStats = $derived(
		rankedItems.find((item) => item.item_name === selectedItemName) ?? null
	);

	let visibleSuggestions = $derived.by(() => {
		const query = itemQuery.trim().toLowerCase();
		if (!query) {
			return rankedItems.slice(0, 10);
		}

		return rankedItems
			.filter((item) => item.item_name.toLowerCase().includes(query))
			.slice(0, 25);
	});

	let priceTrendRequestId = 0;

	function formatCurrency(amount: number): string {
		return `${amount.toFixed(2)} €`;
	}

	function formatHeatmapValue(amount: number): string {
		return amount.toFixed(2);
	}

	function formatMonth(month: string): string {
		const [year, monthPart] = month.split('-');
		const monthIndex = Number.parseInt(monthPart, 10) - 1;
		const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
		return `${monthNames[monthIndex] ?? monthPart} ${year}`;
	}

	function toRgb(color: string): [number, number, number] {
		const hex = color.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
		if (hex) {
			const value = hex[1];
			if (value.length === 3) {
				return [
					Number.parseInt(value[0] + value[0], 16),
					Number.parseInt(value[1] + value[1], 16),
					Number.parseInt(value[2] + value[2], 16)
				];
			}

			return [
				Number.parseInt(value.slice(0, 2), 16),
				Number.parseInt(value.slice(2, 4), 16),
				Number.parseInt(value.slice(4, 6), 16)
			];
		}

		const rgb = color
			.trim()
			.match(/^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*(?:\d*\.?\d+))?\s*\)$/i);
		if (rgb) {
			return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
		}

		return [107, 114, 128];
	}

	function heatCellStyle(color: string, amount: number): string {
		if (amount <= 0 || maxHeatSpend <= 0) {
			return 'background-color: transparent;';
		}

		const intensity = Math.max(0.12, Math.min(1, amount / maxHeatSpend));
		const [r, g, b] = toRgb(color);
		const alpha = 0.15 + intensity * 0.65;
		return `background-color: rgba(${r}, ${g}, ${b}, ${alpha.toFixed(3)});`;
	}

	async function loadPriceTrend(itemName: string): Promise<void> {
		if (!itemName) {
			itemPriceTrend = [];
			return;
		}

		const requestId = ++priceTrendRequestId;
		loadingPriceTrend = true;
		try {
			const data = await fetchItemPriceTrend(itemName);
			if (requestId === priceTrendRequestId) {
				itemPriceTrend = data;
			}
		} catch (error) {
			console.error('Failed to load item price trend', error);
			if (requestId === priceTrendRequestId) {
				itemPriceTrend = [];
			}
		} finally {
			if (requestId === priceTrendRequestId) {
				loadingPriceTrend = false;
			}
		}
	}

	async function selectTrackedItem(itemName: string): Promise<void> {
		selectedItemName = itemName;
		itemQuery = itemName;
		showItemSuggestions = false;
		await loadPriceTrend(itemName);
	}

	onMount(async () => {
		try {
			const [monthlyBonus, categoryMonthly, top] = await Promise.all([
				fetchMonthlyBonus(),
				fetchCategoryMonthly(),
				fetchTopItems(120)
			]);

			monthlyBonusData = monthlyBonus;
			categoryMonthlyData = categoryMonthly;
			topItems = top;

			const defaultItem = rankTopItems(top)[0];
			if (defaultItem) {
				await selectTrackedItem(defaultItem.item_name);
			}
		} catch (error) {
			console.error('Failed to load analytics data', error);
		} finally {
			loading = false;
		}
	});
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-3xl font-bold text-foreground">Analytics</h1>
		<p class="mt-1 text-muted-foreground">Category trends and price tracking</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="text-muted-foreground">Loading analytics...</div>
		</div>
	{:else}
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
			<Card.Root class="lg:col-span-2">
				<Card.Header>
					<div class="flex items-center gap-2">
						<Gift class="h-4 w-4 text-muted-foreground" />
						<Card.Title>Bonus Efficiency by Month</Card.Title>
					</div>
					<Card.Description>
						Bars show earned bonus in EUR, line shows cashback rate (%)
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<BonusMonthlyChart data={monthlyBonusData} />
				</Card.Content>
			</Card.Root>

			<Card.Root class="lg:col-span-2">
				<Card.Header>
					<div class="flex items-center gap-2">
						<BarChart3 class="h-4 w-4 text-muted-foreground" />
						<Card.Title>Category Heatmap by Month (EUR)</Card.Title>
					</div>
				</Card.Header>
				<Card.Content>
					{#if categoryRows.length === 0 || months.length === 0}
						<p class="py-8 text-center text-sm text-muted-foreground">No category monthly data yet</p>
					{:else}
						<div class="overflow-x-auto">
							<table class="w-full min-w-[44rem] border-separate border-spacing-0 text-sm">
								<thead>
									<tr>
										<th class="sticky left-0 z-10 border-b border-border bg-card px-2 py-2 text-left font-medium text-muted-foreground">
											Category
										</th>
										{#each months as month (month)}
											<th class="border-b border-border px-2 py-2 text-right font-medium text-muted-foreground">
												{formatMonth(month)}
											</th>
										{/each}
									</tr>
								</thead>
								<tbody>
									{#each categoryRows as row (row.category_id === null ? `uncat-${row.category_name}` : row.category_id)}
										<tr>
											<td class="sticky left-0 z-10 border-b border-border bg-card px-2 py-2 text-foreground">
												{row.icon} {row.category_name}
											</td>
											{#each months as month (month)}
												{@const spend = row.byMonth.get(month) ?? 0}
												<td
											class="border-b border-border px-2 py-2 text-right font-medium tabular-nums whitespace-nowrap text-foreground"
											style={heatCellStyle(row.color, spend)}
										>
											{formatHeatmapValue(spend)}
										</td>
											{/each}
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<Card.Root class="lg:col-span-2">
				<Card.Header>
					<div class="flex items-center gap-2">
						<DollarSign class="h-4 w-4 text-muted-foreground" />
						<Card.Title>Item Price Tracking</Card.Title>
					</div>
				</Card.Header>
				<Card.Content class="space-y-4">
					{#if topItems.length === 0}
						<p class="py-8 text-center text-sm text-muted-foreground">No item data available yet</p>
					{:else}
						<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
							<div class="flex items-center gap-2">
								<label for="item-price-search" class="text-sm text-muted-foreground">Item</label>
								<div class="relative w-full sm:w-80">
									<input
										id="item-price-search"
										type="text"
										class="w-full rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground outline-none ring-offset-background transition focus-visible:ring-2 focus-visible:ring-ring"
										placeholder="Search item..."
										bind:value={itemQuery}
										onfocus={() => {
											showItemSuggestions = true;
										}}
										onblur={() => {
											setTimeout(() => {
												showItemSuggestions = false;
											}, 120);
										}}
										oninput={() => {
											showItemSuggestions = true;
										}}
									/>

									{#if showItemSuggestions}
										<div class="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-border bg-card shadow-lg">
											{#if visibleSuggestions.length === 0}
												<div class="px-3 py-2 text-sm text-muted-foreground">No matching items</div>
											{:else}
												{#each visibleSuggestions as item (item.item_name)}
													<button
														type="button"
														class="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-foreground transition hover:bg-muted/40"
														onclick={async () => {
															await selectTrackedItem(item.item_name);
														}}
													>
														<span class="truncate pr-3">{item.item_name}</span>
														<span class="shrink-0 text-xs text-muted-foreground">{item.total_quantity} qty</span>
													</button>
												{/each}
											{/if}
										</div>
									{/if}
								</div>
							</div>

							{#if selectedItemStats}
								<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
									<span>
										Total spent:
									<strong class="font-medium tabular-nums text-foreground">
										{formatCurrency(selectedItemStats.total_spent)}
									</strong>
								</span>
								<span>
									Avg unit:
									<strong class="font-medium tabular-nums text-foreground">
										{formatCurrency(selectedItemStats.avg_unit_price)}
									</strong>
								</span>
									<span>
										Quantity:
										<strong class="font-medium tabular-nums text-foreground">
											{selectedItemStats.total_quantity}
										</strong>
									</span>
								</div>
							{/if}
						</div>

						{#if loadingPriceTrend}
							<div class="flex h-64 items-center justify-center text-sm text-muted-foreground">
								Loading price trend...
							</div>
						{:else}
							<ItemPriceTrendChart data={itemPriceTrend} />
						{/if}
					{/if}
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
</div>
