<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import {
		LayoutDashboard,
		Upload,
		Receipt,
		BarChart3,
		Tags,
		ListFilter,
		ShoppingCart,
		Settings
	} from '@lucide/svelte';
	import * as Separator from '$lib/components/ui/separator';
	import { t } from '$lib/i18n/index.svelte';

	let { children } = $props();
	const appVersion = import.meta.env.VITE_APP_VERSION || 'dev';

	const navItems = [
		{ href: '/', labelKey: 'nav.dashboard', icon: LayoutDashboard },
		{ href: '/import', labelKey: 'nav.import', icon: Upload },
		{ href: '/receipts', labelKey: 'nav.receipts', icon: Receipt },
		{ href: '/analytics', labelKey: 'nav.analytics', icon: BarChart3 },
		{ href: '/categories', labelKey: 'nav.categories', icon: Tags },
		{ href: '/rules', labelKey: 'nav.rules', icon: ListFilter },
		{ href: '/settings', labelKey: 'nav.settings', icon: Settings }
	];
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link
		href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
		rel="stylesheet"
	/>
	<title>eBon Reader</title>
</svelte:head>

<div class="flex h-screen overflow-hidden font-['Inter',sans-serif]">
	<!-- Sidebar -->
	<nav class="flex w-56 flex-col overflow-y-auto border-r border-border bg-card px-3 py-5">
		<div class="mb-6 flex items-center gap-2.5 px-3">
			<ShoppingCart class="h-6 w-6 text-primary" />
			<span class="text-lg font-bold text-foreground">eBon Reader</span>
		</div>

		<Separator.Root class="mb-4" />

		<ul class="flex flex-1 flex-col gap-1">
			{#each navItems as item (item.href)}
				<li>
					<a
						href={item.href}
						class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
					>
						<item.icon class="h-4 w-4" />
						{t(item.labelKey)}
					</a>
				</li>
			{/each}
		</ul>

		<Separator.Root class="mb-3" />
		<div class="px-3 text-xs text-muted-foreground">{`v${appVersion}`}</div>
	</nav>

	<!-- Main content -->
	<main class="min-h-0 flex-1 overflow-y-auto bg-background p-6">
		{@render children()}
	</main>
</div>
