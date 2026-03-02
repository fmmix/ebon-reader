<script lang="ts">
	import {
		fetchOverview,
		fetchCategoryBreakdown,
		fetchMonthlyTrend,
		type OverviewStats,
		type CategorySpend,
		type MonthlySpend
	} from '$lib/api';
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import {
		ShoppingBag,
		Receipt,
		Package,
		Gift,
		ArrowRight,
		TrendingUp
	} from '@lucide/svelte';
	import CategoryDonutChart from '$lib/components/CategoryDonutChart.svelte';
	import SpendingTimeline from '$lib/components/SpendingTimeline.svelte';

	let overview = $state<OverviewStats | null>(null);
	let categoryData = $state<CategorySpend[]>([]);
	let monthlyData = $state<MonthlySpend[]>([]);
	let selectedCategoryKeys = $state<string[]>([]);
	let monthlyRange = $state<'3m' | '6m' | '12m' | 'all'>('12m');
	let loading = $state(true);

	function categoryKey(cat: Pick<CategorySpend, 'category_id'>): string {
		return cat.category_id === null ? 'uncategorized' : `category-${cat.category_id}`;
	}

	function toggleCategorySelection(key: string) {
		if (selectedCategoryKeys.includes(key)) {
			selectedCategoryKeys = selectedCategoryKeys.filter((k) => k !== key);
			return;
		}

		selectedCategoryKeys = [...selectedCategoryKeys, key];
	}

	function selectAllCategories() {
		selectedCategoryKeys = categoryData.map((cat) => categoryKey(cat));
	}

	function clearCategorySelection() {
		selectedCategoryKeys = [];
	}

	onMount(async () => {
		try {
			const [ov, cats, months] = await Promise.all([
				fetchOverview(),
				fetchCategoryBreakdown(true),
				fetchMonthlyTrend()
			]);
			overview = ov;
			categoryData = cats;
			monthlyData = months;
			selectedCategoryKeys = cats.map((cat) => categoryKey(cat));
		} catch (e) {
			console.error('Failed to load stats', e);
		} finally {
			loading = false;
		}
	});

	let hasData = $derived(overview !== null && overview.receipt_count > 0);
	let filteredCategoryData = $derived(
		categoryData.filter((cat) => selectedCategoryKeys.includes(categoryKey(cat)))
	);
	let filteredMonthlyData = $derived(
		monthlyRange === 'all'
			? monthlyData
			: monthlyData.slice(-(monthlyRange === '3m' ? 3 : monthlyRange === '6m' ? 6 : 12))
	);
	let totalCategorySpend = $derived(filteredCategoryData.reduce((s, c) => s + c.total_spent, 0));
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-3xl font-bold text-foreground">Dashboard</h1>
		<p class="mt-1 text-muted-foreground">Your supermarket spending at a glance</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="text-muted-foreground">Loading stats...</div>
		</div>
	{:else if !hasData}
		<!-- Empty state -->
		<Card.Root class="border-dashed">
			<Card.Content class="flex flex-col items-center py-12">
				<ShoppingBag class="mb-4 h-12 w-12 text-muted-foreground/40" />
				<p class="mb-2 text-lg font-medium text-foreground">No receipts imported yet</p>
				<p class="mb-5 text-sm text-muted-foreground">
					Import your first eBon to see spending analytics
				</p>
				<Button href="/import">
					Import eBon
					<ArrowRight class="ml-2 h-4 w-4" />
				</Button>
			</Card.Content>
		</Card.Root>
	{:else}
		<!-- Summary cards -->
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
			<Card.Root>
				<Card.Header class="flex flex-row items-center justify-between pb-2">
					<Card.Title class="text-sm font-medium text-muted-foreground"
						>Total Spent</Card.Title
					>
					<ShoppingBag class="h-4 w-4 text-muted-foreground" />
				</Card.Header>
				<Card.Content>
					<p class="text-2xl font-bold text-foreground">€{overview!.total_spent.toFixed(2)}</p>
					<p class="mt-1 text-xs text-muted-foreground">
						Avg. €{overview!.avg_basket.toFixed(2)} per receipt
					</p>
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header class="flex flex-row items-center justify-between pb-2">
					<Card.Title class="text-sm font-medium text-muted-foreground">Receipts</Card.Title>
					<Receipt class="h-4 w-4 text-muted-foreground" />
				</Card.Header>
				<Card.Content>
					<p class="text-2xl font-bold text-foreground">{overview!.receipt_count}</p>
					<p class="mt-1 text-xs text-muted-foreground">imported receipts</p>
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header class="flex flex-row items-center justify-between pb-2">
					<Card.Title class="text-sm font-medium text-muted-foreground"
						>Items Purchased</Card.Title
					>
					<Package class="h-4 w-4 text-muted-foreground" />
				</Card.Header>
				<Card.Content>
					<p class="text-2xl font-bold text-foreground">{overview!.item_count}</p>
					<p class="mt-1 text-xs text-muted-foreground">individual products</p>
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header class="flex flex-row items-center justify-between pb-2">
					<Card.Title class="text-sm font-medium text-muted-foreground"
						>Bonus Earned</Card.Title
					>
					<Gift class="h-4 w-4 text-muted-foreground" />
				</Card.Header>
				<Card.Content>
					<p class="text-2xl font-bold text-foreground">€{overview!.total_bonus.toFixed(2)}</p>
					<p class="mt-1 text-xs text-muted-foreground">from promotions &amp; coupons</p>
					<p class="mt-1 text-xs text-muted-foreground">
						Redeemed: {overview!.redeemed_bonus.toFixed(2)} €
					</p>
				</Card.Content>
			</Card.Root>
		</div>

		<!-- Charts row -->
		<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
			<!-- Category Breakdown -->
			<Card.Root>
				<Card.Header>
					<Card.Title>Spending by Category</Card.Title>
					<Card.Description>Where your money goes</Card.Description>
				</Card.Header>
				<Card.Content>
					<CategoryDonutChart data={filteredCategoryData} />
					<!-- Legend list -->
					{#if filteredCategoryData.length > 0}
						<div class="mt-4 space-y-2">
							{#each filteredCategoryData as cat (categoryKey(cat))}
								<div class="flex items-center justify-between text-sm">
									<div class="flex items-center gap-2">
										<div
											class="h-3 w-3 rounded-full"
											style="background: {cat.color}"
										></div>
										<span class="text-foreground"
											>{cat.icon} {cat.category_name}</span
										>
									</div>
									<div class="flex items-center gap-3">
										<span class="tabular-nums text-muted-foreground"
											>{cat.item_count} items</span
										>
										<span class="min-w-[5rem] text-right font-medium tabular-nums text-foreground"
											>€{cat.total_spent.toFixed(2)}</span
										>
										{#if totalCategorySpend > 0}
											<span
												class="min-w-[3rem] text-right text-xs tabular-nums text-muted-foreground"
											>
												{((cat.total_spent / totalCategorySpend) * 100).toFixed(0)}%
											</span>
										{/if}
									</div>
								</div>
							{/each}
						</div>
					{/if}

					<div class="mt-4 space-y-2 border-t pt-3">
						<div class="flex flex-wrap items-center gap-2">
							<span class="text-xs font-medium uppercase tracking-wide text-muted-foreground"
								>Categories</span
							>
							<Button size="sm" variant="ghost" onclick={selectAllCategories}>All</Button>
							<Button size="sm" variant="ghost" onclick={clearCategorySelection}>None</Button>
							{#each categoryData as cat (categoryKey(cat))}
								{@const isSelected = selectedCategoryKeys.includes(categoryKey(cat))}
								<Button
									size="sm"
									variant={isSelected ? 'secondary' : 'outline'}
									class={isSelected
										? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
										: 'border-border/60 bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted/35'}
									onclick={() => toggleCategorySelection(categoryKey(cat))}
								>
									{cat.icon} {cat.category_name}
								</Button>
							{/each}
						</div>
					</div>
				</Card.Content>
			</Card.Root>

			<!-- Monthly Trend -->
			<Card.Root>
				<Card.Header>
					<div class="flex items-center gap-2">
						<TrendingUp class="h-4 w-4 text-muted-foreground" />
						<Card.Title>Monthly Spending</Card.Title>
					</div>
					<Card.Description>Spending trend over time</Card.Description>
				</Card.Header>
				<Card.Content>
					<SpendingTimeline data={filteredMonthlyData} />
					<!-- Monthly summary -->
					{#if filteredMonthlyData.length > 0}
						<div class="mt-4 space-y-1.5">
							{#each filteredMonthlyData.slice().reverse() as m (m.month)}
								<div class="flex items-center justify-between text-sm">
									<span class="text-muted-foreground">{m.month}</span>
									<div class="flex items-center gap-3">
										<span class="text-xs text-muted-foreground"
											>{m.receipt_count} receipts</span
										>
										<span class="min-w-[5rem] text-right font-medium tabular-nums text-foreground"
											>€{m.total_spent.toFixed(2)}</span
										>
									</div>
								</div>
							{/each}
						</div>
					{/if}

					<div class="mt-4 flex flex-wrap items-center gap-1 border-t pt-3">
						<Button
							size="sm"
							variant={monthlyRange === '3m' ? 'secondary' : 'outline'}
							class={monthlyRange === '3m'
								? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
								: 'border-border/60 bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted/35'}
							onclick={() => (monthlyRange = '3m')}
						>
							3M
						</Button>
						<Button
							size="sm"
							variant={monthlyRange === '6m' ? 'secondary' : 'outline'}
							class={monthlyRange === '6m'
								? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
								: 'border-border/60 bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted/35'}
							onclick={() => (monthlyRange = '6m')}
						>
							6M
						</Button>
						<Button
							size="sm"
							variant={monthlyRange === '12m' ? 'secondary' : 'outline'}
							class={monthlyRange === '12m'
								? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
								: 'border-border/60 bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted/35'}
							onclick={() => (monthlyRange = '12m')}
						>
							12M
						</Button>
						<Button
							size="sm"
							variant={monthlyRange === 'all' ? 'secondary' : 'outline'}
							class={monthlyRange === 'all'
								? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
								: 'border-border/60 bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted/35'}
							onclick={() => (monthlyRange = 'all')}
						>
							All
						</Button>
					</div>
				</Card.Content>
			</Card.Root>
		</div>

		<!-- Quick actions -->
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
			<Card.Root class="border-dashed transition-colors hover:border-primary/40">
				<Card.Content class="flex items-center gap-4 py-5">
					<div
						class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10"
					>
						<ArrowRight class="h-5 w-5 text-primary" />
					</div>
					<div class="flex-1">
						<p class="font-medium text-foreground">Import another eBon</p>
						<p class="text-sm text-muted-foreground">Upload a PDF receipt</p>
					</div>
					<Button variant="outline" href="/import">Import</Button>
				</Card.Content>
			</Card.Root>

			<Card.Root class="border-dashed transition-colors hover:border-primary/40">
				<Card.Content class="flex items-center gap-4 py-5">
					<div
						class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10"
					>
						<Receipt class="h-5 w-5 text-primary" />
					</div>
					<div class="flex-1">
						<p class="font-medium text-foreground">View all receipts</p>
						<p class="text-sm text-muted-foreground">Browse imported receipts</p>
					</div>
					<Button variant="outline" href="/receipts">View</Button>
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
</div>
