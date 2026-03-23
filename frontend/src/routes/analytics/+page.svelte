<script lang="ts">
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { BarChart3, DollarSign, Gift, Store } from '@lucide/svelte';
	import {
		fetchMonthlyBonus,
		fetchMonthlyBonusByShop,
		fetchStoreBonusBreakdown,
		fetchCategoryMonthly,
		fetchStoreBreakdown,
		fetchTopItems,
		fetchItemPriceTrend,
		type MonthlyBonusStat,
		type MonthlyBonusByShopStat,
		type StoreBonusStat,
		type CategoryMonthlySpend,
		type StoreSpend,
		type TopItemStat,
		type ItemPricePoint
	} from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { formatCurrency, formatMonth, formatPercent } from '$lib/utils/format';
	import BonusMonthlyChart from '$lib/components/BonusMonthlyChart.svelte';
	import ItemPriceTrendChart from '$lib/components/ItemPriceTrendChart.svelte';

	let loading = $state(true);
	let monthlyBonusData = $state<MonthlyBonusStat[]>([]);
	let monthlyBonusByShopData = $state<MonthlyBonusByShopStat[]>([]);
	let storeBonusBreakdown = $state<StoreBonusStat[]>([]);
	let bonusChartMode = $state<'total' | 'perShop'>('total');
	let categoryMonthlyData = $state<CategoryMonthlySpend[]>([]);
	let storeBreakdown = $state<StoreSpend[]>([]);
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
			const key =
				point.category_id === null
					? `uncategorized:${point.category_name}`
					: String(point.category_id);
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

		return rankedItems.filter((item) => item.item_name.toLowerCase().includes(query)).slice(0, 25);
	});

	let priceTrendRequestId = 0;

	function formatHeatmapValue(amount: number): string {
		return amount.toFixed(2);
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
			.match(
				/^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*(?:\d*\.?\d+))?\s*\)$/i
			);
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
			const [monthlyBonus, monthlyBonusByShop, storeBonus, categoryMonthly, stores, top] =
				await Promise.all([
				fetchMonthlyBonus(),
				fetchMonthlyBonusByShop(),
				fetchStoreBonusBreakdown(),
				fetchCategoryMonthly(),
				fetchStoreBreakdown(),
				fetchTopItems(120)
				]);

			monthlyBonusData = monthlyBonus;
			monthlyBonusByShopData = monthlyBonusByShop;
			storeBonusBreakdown = storeBonus;
			categoryMonthlyData = categoryMonthly;
			storeBreakdown = stores;
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
		<h1 class="text-3xl font-bold text-foreground">{t('analytics.title')}</h1>
		<p class="mt-1 text-muted-foreground">{t('analytics.subtitle')}</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="text-muted-foreground">{t('analytics.loading')}</div>
		</div>
	{:else}
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
			<Card.Root class="lg:col-span-2">
				<Card.Header>
					<div class="flex items-center gap-2">
						<Store class="h-4 w-4 text-muted-foreground" />
						<Card.Title>{t('analytics.store_title')}</Card.Title>
					</div>
					<Card.Description>
						{t('analytics.store_desc')}
					</Card.Description>
				</Card.Header>
				<Card.Content>
					{#if storeBreakdown.length === 0}
						<p class="py-8 text-center text-sm text-muted-foreground">
							{t('analytics.store_empty')}
						</p>
					{:else}
						<div class="space-y-2">
							{#each storeBreakdown as store, index (store.store_name)}
								{@const clampedShare = Math.max(0, Math.min(100, store.share_percent))}
								<div
									class="rounded-md border border-border/70 bg-muted/20 px-3 py-2.5 transition-colors hover:bg-muted/35"
								>
									<div class="flex items-start justify-between gap-3">
										<div class="min-w-0">
											<div class="flex items-center gap-2">
												<span
													class="inline-flex h-5 min-w-5 items-center justify-center rounded-full border border-border bg-card px-1.5 text-[10px] font-semibold text-muted-foreground tabular-nums"
												>
													#{index + 1}
												</span>
												<p class="truncate text-sm font-medium text-foreground">{store.store_name}</p>
											</div>
											<div class="mt-1 flex flex-wrap gap-1.5 text-[11px]">
												<span class="rounded-full border border-border bg-card px-2 py-0.5 text-muted-foreground">
													{t('analytics.store_receipts', { count: store.receipt_count })}
												</span>
												<span class="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-sky-300">
													{t('analytics.store_avg_basket')} {formatCurrency(store.avg_basket)}
												</span>
												<span class="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-300">
													{t('analytics.store_share')} {formatPercent(store.share_percent)}
												</span>
											</div>
										</div>
										<p class="shrink-0 pt-0.5 text-sm font-semibold text-foreground tabular-nums">
											{formatCurrency(store.total_spent)}
										</p>
									</div>
									<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-muted/60">
										<div
											class="h-full rounded-full bg-emerald-400/85"
											style={`width: ${clampedShare.toFixed(2)}%`}
										></div>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<Card.Root class="lg:col-span-1">
				<Card.Header>
					<div class="flex flex-wrap items-center justify-between gap-3">
						<div class="flex items-center gap-2">
							<Gift class="h-4 w-4 text-muted-foreground" />
							<Card.Title>{t('analytics.bonus_title')}</Card.Title>
						</div>
						<div class="inline-flex items-center rounded-md border border-border bg-muted/30 p-1">
							<button
								type="button"
								class={`rounded px-2.5 py-1 text-xs font-medium transition ${bonusChartMode === 'total' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
								onclick={() => {
									bonusChartMode = 'total';
								}}
							>
								{t('analytics.bonus_mode_total')}
							</button>
							<button
								type="button"
								class={`rounded px-2.5 py-1 text-xs font-medium transition ${bonusChartMode === 'perShop' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
								onclick={() => {
									bonusChartMode = 'perShop';
								}}
							>
								{t('analytics.bonus_mode_per_shop')}
							</button>
						</div>
					</div>
					<Card.Description>
						{bonusChartMode === 'total'
							? t('analytics.bonus_desc')
							: t('analytics.bonus_desc_per_shop')}
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<BonusMonthlyChart
						data={monthlyBonusData}
						dataByShop={monthlyBonusByShopData}
						mode={bonusChartMode}
					/>
				</Card.Content>
			</Card.Root>

			<Card.Root class="lg:col-span-1">
				<Card.Header>
					<Card.Title>{t('analytics.store_bonus_title')}</Card.Title>
					<Card.Description>{t('analytics.store_bonus_desc')}</Card.Description>
				</Card.Header>
				<Card.Content>
					{#if storeBonusBreakdown.length === 0}
						<p class="py-8 text-center text-sm text-muted-foreground">
							{t('analytics.store_bonus_empty')}
						</p>
					{:else}
						<div class="overflow-x-auto">
							<table class="w-full min-w-[34rem] text-sm">
								<thead>
									<tr class="border-b border-border text-muted-foreground">
										<th class="px-2 py-2 text-left font-medium">{t('analytics.store_bonus_store')}</th>
										<th class="px-2 py-2 text-right font-medium">{t('analytics.store_bonus_savings')}</th>
										<th class="px-2 py-2 text-right font-medium">{t('analytics.store_bonus_rate')}</th>
										<th class="px-2 py-2 text-right font-medium">{t('analytics.store_bonus_spent')}</th>
										<th class="px-2 py-2 text-right font-medium">{t('analytics.store_bonus_receipts')}</th>
									</tr>
								</thead>
								<tbody>
									{#each storeBonusBreakdown as store (store.store_name)}
										<tr class="border-b border-border/70 last:border-b-0">
											<td class="px-2 py-2.5 font-medium text-foreground">{store.store_name}</td>
											<td class="px-2 py-2.5 text-right font-semibold text-foreground tabular-nums">
												{formatCurrency(store.program_savings)}
											</td>
											<td class="px-2 py-2.5 text-right text-foreground tabular-nums">
												{formatPercent(store.bonus_rate)}
											</td>
											<td class="px-2 py-2.5 text-right text-foreground tabular-nums">
												{formatCurrency(store.total_spent)}
											</td>
											<td class="px-2 py-2.5 text-right text-muted-foreground tabular-nums">
												{store.receipt_count}
											</td>
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
						<BarChart3 class="h-4 w-4 text-muted-foreground" />
						<Card.Title>{t('analytics.heatmap_title')}</Card.Title>
					</div>
				</Card.Header>
				<Card.Content>
					{#if categoryRows.length === 0 || months.length === 0}
						<p class="py-8 text-center text-sm text-muted-foreground">
							{t('analytics.heatmap_empty')}
						</p>
					{:else}
						<div class="overflow-x-auto">
							<table class="w-full min-w-[44rem] border-separate border-spacing-0 text-sm">
								<thead>
									<tr>
										<th
											class="sticky left-0 z-10 border-b border-border bg-card px-2 py-2 text-left font-medium text-muted-foreground"
										>
											{t('analytics.heatmap_category')}
										</th>
										{#each months as month (month)}
											<th
												class="border-b border-border px-2 py-2 text-right font-medium text-muted-foreground"
											>
												{formatMonth(month)}
											</th>
										{/each}
									</tr>
								</thead>
								<tbody>
									{#each categoryRows as row (row.category_id === null ? `uncat-${row.category_name}` : row.category_id)}
										<tr>
											<td
												class="sticky left-0 z-10 border-b border-border bg-card px-2 py-2 text-foreground"
											>
												{row.icon}
												{row.category_name}
											</td>
											{#each months as month (month)}
												{@const spend = row.byMonth.get(month) ?? 0}
												<td
													class="border-b border-border px-2 py-2 text-right font-medium whitespace-nowrap text-foreground tabular-nums"
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
						<Card.Title>{t('analytics.price_title')}</Card.Title>
					</div>
				</Card.Header>
				<Card.Content class="space-y-4">
					{#if topItems.length === 0}
						<p class="py-8 text-center text-sm text-muted-foreground">
							{t('analytics.price_empty')}
						</p>
					{:else}
						<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
							<div class="flex items-center gap-2">
								<label for="item-price-search" class="text-sm text-muted-foreground"
									>{t('analytics.price_item_label')}</label
								>
								<div class="relative w-full sm:w-80">
									<input
										id="item-price-search"
										type="text"
										class="w-full rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground ring-offset-background transition outline-none focus-visible:ring-2 focus-visible:ring-ring"
										placeholder={t('analytics.price_search')}
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
										<div
											class="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-border bg-card shadow-lg"
										>
											{#if visibleSuggestions.length === 0}
												<div class="px-3 py-2 text-sm text-muted-foreground">
													{t('analytics.price_no_match')}
												</div>
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
														<span class="shrink-0 text-xs text-muted-foreground"
															>{t('analytics.price_qty', { count: item.total_quantity })}</span
														>
													</button>
												{/each}
											{/if}
										</div>
									{/if}
								</div>
							</div>

							{#if selectedItemStats}
								<div
									class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground"
								>
									<span>
										{t('analytics.price_total_spent')}
										<strong class="font-medium text-foreground tabular-nums">
											{formatCurrency(selectedItemStats.total_spent)}
										</strong>
									</span>
									<span>
										{t('analytics.price_avg_unit')}
										<strong class="font-medium text-foreground tabular-nums">
											{formatCurrency(selectedItemStats.avg_unit_price)}
										</strong>
									</span>
									<span>
										{t('analytics.price_quantity')}
										<strong class="font-medium text-foreground tabular-nums">
											{selectedItemStats.total_quantity}
										</strong>
									</span>
								</div>
							{/if}
						</div>

						{#if loadingPriceTrend}
							<div class="flex h-64 items-center justify-center text-sm text-muted-foreground">
								{t('analytics.price_loading')}
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
