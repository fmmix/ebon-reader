<script lang="ts">
	import {
		fetchOverview,
		fetchCategoryBreakdown,
		fetchMonthlyBonus,
		type OverviewStats,
		type CategorySpend,
		type MonthlySpend,
		type MonthlyBonusStat
	} from '$lib/api';
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { ShoppingBag, Receipt, Package, Gift, ArrowRight, TrendingUp } from '@lucide/svelte';
	import CategoryDonutChart from '$lib/components/CategoryDonutChart.svelte';
	import SpendingTimeline from '$lib/components/SpendingTimeline.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { formatCurrency } from '$lib/utils/format';

	let overview = $state<OverviewStats | null>(null);
	let categoryData = $state<CategorySpend[]>([]);
	let monthlyData = $state<MonthlyBonusStat[]>([]);
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
				fetchMonthlyBonus()
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
	let spendingTimelineData = $derived<MonthlySpend[]>(
		filteredMonthlyData.map(({ month, total_spent, receipt_count, redeemed_bonus, instant_discount, basket_discount }) => ({
			month,
			total_spent,
			redeemed_bonus,
			instant_discount,
			basket_discount,
			receipt_count
		}))
	);
	let totalCategorySpend = $derived(filteredCategoryData.reduce((s, c) => s + c.total_spent, 0));
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-3xl font-bold text-foreground">{t('dashboard.title')}</h1>
		<p class="mt-1 text-muted-foreground">{t('dashboard.subtitle')}</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="text-muted-foreground">{t('dashboard.loading')}</div>
		</div>
	{:else if !hasData}
		<!-- Empty state -->
		<Card.Root class="border-dashed">
			<Card.Content class="flex flex-col items-center py-12">
				<ShoppingBag class="mb-4 h-12 w-12 text-muted-foreground/40" />
				<p class="mb-2 text-lg font-medium text-foreground">{t('dashboard.empty_title')}</p>
				<p class="mb-5 text-sm text-muted-foreground">
					{t('dashboard.empty_desc')}
				</p>
				<Button href="/import">
					{t('dashboard.empty_cta')}
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
						>{t('dashboard.total_spent')}</Card.Title
					>
					<ShoppingBag class="h-4 w-4 text-muted-foreground" />
				</Card.Header>
				<Card.Content>
					<p class="text-2xl font-bold text-foreground">{formatCurrency(overview!.total_spent)}</p>
					<p class="mt-1 text-xs text-muted-foreground">
						{t('dashboard.avg_per_receipt', { amount: formatCurrency(overview!.avg_basket) })}
					</p>
					{#if overview!.total_deductions > 0}
						<p class="mt-1 text-xs text-muted-foreground">
							↓ {formatCurrency(overview!.total_deductions)} {t('dashboard.saved_label')} · {formatCurrency(overview!.total_spent - overview!.total_deductions)} {t('dashboard.paid_label')}
						</p>
					{/if}
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header class="flex flex-row items-center justify-between pb-2">
					<Card.Title class="text-sm font-medium text-muted-foreground"
						>{t('dashboard.receipts')}</Card.Title
					>
					<Receipt class="h-4 w-4 text-muted-foreground" />
				</Card.Header>
				<Card.Content>
					<p class="text-2xl font-bold text-foreground">{overview!.receipt_count}</p>
					<p class="mt-1 text-xs text-muted-foreground">{t('dashboard.imported_receipts')}</p>
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header class="flex flex-row items-center justify-between pb-2">
					<Card.Title class="text-sm font-medium text-muted-foreground"
						>{t('dashboard.items_purchased')}</Card.Title
					>
					<Package class="h-4 w-4 text-muted-foreground" />
				</Card.Header>
				<Card.Content>
					<p class="text-2xl font-bold text-foreground">{overview!.item_count}</p>
					<p class="mt-1 text-xs text-muted-foreground">{t('dashboard.individual_products')}</p>
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header class="flex flex-row items-center justify-between pb-2">
					<Card.Title class="text-sm font-medium text-muted-foreground"
						>{t('dashboard.program_savings')}</Card.Title
					>
					<Gift class="h-4 w-4 text-muted-foreground" />
				</Card.Header>
				<Card.Content>
					<p class="text-2xl font-bold text-foreground">{formatCurrency(overview!.program_savings)}</p>
					<p class="mt-1 text-xs text-muted-foreground">{t('dashboard.from_promotions')}</p>
					<p class="mt-1 text-xs text-muted-foreground">
						{t('dashboard.earned_bonus_line', { amount: formatCurrency(overview!.total_bonus) })}
					</p>
					<p class="text-xs text-muted-foreground">
						{t('dashboard.instant_discount_line', {
							amount: formatCurrency(overview!.instant_discount)
						})}
					</p>
					<p class="text-xs text-muted-foreground">
						{t('dashboard.redeemed_line', { amount: formatCurrency(overview!.redeemed_bonus) })}
					</p>
				</Card.Content>
			</Card.Root>
		</div>

		<!-- Charts row -->
		<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
			<!-- Category Breakdown -->
			<Card.Root>
				<Card.Header>
					<Card.Title>{t('dashboard.spending_by_category')}</Card.Title>
					<Card.Description>{t('dashboard.where_money_goes')}</Card.Description>
				</Card.Header>
				<Card.Content>
					<CategoryDonutChart data={filteredCategoryData} />
					<!-- Legend list -->
					{#if filteredCategoryData.length > 0}
						<div class="mt-4 space-y-2">
							{#each filteredCategoryData as cat (categoryKey(cat))}
								<div class="flex items-center justify-between text-sm">
									<div class="flex items-center gap-2">
										<div class="h-3 w-3 rounded-full" style="background: {cat.color}"></div>
										<span class="text-foreground">{cat.icon} {cat.category_name}</span>
									</div>
									<div class="flex items-center gap-3">
										<span class="text-muted-foreground tabular-nums"
											>{t('dashboard.items', { count: cat.item_count })}</span
										>
										<span class="min-w-[5rem] text-right font-medium text-foreground tabular-nums"
											>{formatCurrency(cat.total_spent)}</span
										>
										{#if totalCategorySpend > 0}
											<span
												class="min-w-[3rem] text-right text-xs text-muted-foreground tabular-nums"
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
							<span class="text-xs font-medium tracking-wide text-muted-foreground uppercase"
								>{t('dashboard.categories')}</span
							>
							<Button size="sm" variant="ghost" onclick={selectAllCategories}
								>{t('dashboard.all')}</Button
							>
							<Button size="sm" variant="ghost" onclick={clearCategorySelection}
								>{t('dashboard.none')}</Button
							>
							{#each categoryData as cat (categoryKey(cat))}
								{@const isSelected = selectedCategoryKeys.includes(categoryKey(cat))}
								<Button
									size="sm"
									variant={isSelected ? 'secondary' : 'outline'}
									class={isSelected
										? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
										: 'border-border/60 bg-transparent text-muted-foreground hover:bg-muted/35 hover:text-foreground'}
									onclick={() => toggleCategorySelection(categoryKey(cat))}
								>
									{cat.icon}
									{cat.category_name}
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
						<Card.Title>{t('dashboard.monthly_spending')}</Card.Title>
					</div>
					<Card.Description>{t('dashboard.spending_trend')}</Card.Description>
				</Card.Header>
				<Card.Content>
					<SpendingTimeline data={spendingTimelineData} />
					<!-- Monthly summary -->
					{#if filteredMonthlyData.length > 0}
						<div class="mt-4">
							<table class="w-full table-fixed border-separate border-spacing-y-1.5 text-sm">
								<thead>
									<tr
										class="text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
									>
										<th class="w-[38%] border-b border-border/50 pb-1 text-left font-medium">
											{t('dashboard.month')}
										</th>
										<th class="w-[14%] border-b border-border/50 pb-1 text-right font-medium">
											{t('dashboard.receipts')}
										</th>
										<th class="w-[24%] border-b border-border/50 pb-1 text-right font-medium">
											{t('dashboard.deductions')}
										</th>
										<th class="w-[24%] border-b border-border/50 pb-1 text-right font-medium">
											{t('dashboard.basket_total')}
										</th>
									</tr>
								</thead>
								<tbody>
									{#each filteredMonthlyData.slice().reverse() as m (m.month)}
										<tr>
											<td class="text-muted-foreground">{m.month}</td>
											<td class="text-right text-xs text-muted-foreground tabular-nums">
												{m.receipt_count}
											</td>
											<td class="text-right text-xs text-muted-foreground tabular-nums">
												{formatCurrency(m.redeemed_bonus + m.instant_discount + m.basket_discount)}
											</td>
											<td class="text-right font-medium text-foreground tabular-nums">
												{formatCurrency(m.total_spent)}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}

					<div class="mt-4 flex flex-wrap items-center gap-1 border-t pt-3">
						<Button
							size="sm"
							variant={monthlyRange === '3m' ? 'secondary' : 'outline'}
							class={monthlyRange === '3m'
								? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
								: 'border-border/60 bg-transparent text-muted-foreground hover:bg-muted/35 hover:text-foreground'}
							onclick={() => (monthlyRange = '3m')}
						>
							3M
						</Button>
						<Button
							size="sm"
							variant={monthlyRange === '6m' ? 'secondary' : 'outline'}
							class={monthlyRange === '6m'
								? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
								: 'border-border/60 bg-transparent text-muted-foreground hover:bg-muted/35 hover:text-foreground'}
							onclick={() => (monthlyRange = '6m')}
						>
							6M
						</Button>
						<Button
							size="sm"
							variant={monthlyRange === '12m' ? 'secondary' : 'outline'}
							class={monthlyRange === '12m'
								? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
								: 'border-border/60 bg-transparent text-muted-foreground hover:bg-muted/35 hover:text-foreground'}
							onclick={() => (monthlyRange = '12m')}
						>
							12M
						</Button>
						<Button
							size="sm"
							variant={monthlyRange === 'all' ? 'secondary' : 'outline'}
							class={monthlyRange === 'all'
								? 'border border-primary/35 bg-primary/15 text-foreground shadow-sm hover:bg-primary/20'
								: 'border-border/60 bg-transparent text-muted-foreground hover:bg-muted/35 hover:text-foreground'}
							onclick={() => (monthlyRange = 'all')}
						>
							{t('dashboard.all')}
						</Button>
					</div>
				</Card.Content>
			</Card.Root>
		</div>

		<!-- Quick actions -->
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
			<Card.Root class="border-dashed transition-colors hover:border-primary/40">
				<Card.Content class="flex items-center gap-4 py-5">
					<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
						<ArrowRight class="h-5 w-5 text-primary" />
					</div>
					<div class="flex-1">
						<p class="font-medium text-foreground">{t('dashboard.import_another')}</p>
						<p class="text-sm text-muted-foreground">{t('dashboard.upload_pdf')}</p>
					</div>
					<Button variant="outline" href="/import">{t('nav.import')}</Button>
				</Card.Content>
			</Card.Root>

			<Card.Root class="border-dashed transition-colors hover:border-primary/40">
				<Card.Content class="flex items-center gap-4 py-5">
					<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
						<Receipt class="h-5 w-5 text-primary" />
					</div>
					<div class="flex-1">
						<p class="font-medium text-foreground">{t('dashboard.view_all_receipts')}</p>
						<p class="text-sm text-muted-foreground">{t('dashboard.browse_receipts')}</p>
					</div>
					<Button variant="outline" href="/receipts">{t('dashboard.view')}</Button>
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
</div>
