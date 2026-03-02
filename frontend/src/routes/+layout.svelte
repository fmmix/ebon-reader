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

	let { children } = $props();
	const appVersion = import.meta.env.VITE_APP_VERSION || 'dev';

	const navItems = [
		{ href: '/', label: 'Dashboard', icon: LayoutDashboard },
		{ href: '/import', label: 'Import', icon: Upload },
		{ href: '/receipts', label: 'Receipts', icon: Receipt },
		{ href: '/analytics', label: 'Analytics', icon: BarChart3 },
		{ href: '/categories', label: 'Categories', icon: Tags },
		{ href: '/rules', label: 'Rules', icon: ListFilter },
		{ href: '/settings', label: 'Settings', icon: Settings }
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

<div class="flex h-screen font-['Inter',sans-serif]">
	<!-- Sidebar -->
	<nav class="flex w-56 flex-col border-r border-border bg-card px-3 py-5">
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
						{item.label}
					</a>
				</li>
			{/each}
		</ul>

		<Separator.Root class="mb-3" />
		<div class="px-3 text-xs text-muted-foreground">{`v${appVersion}`}</div>
	</nav>

	<!-- Main content -->
	<main class="flex-1 overflow-y-auto bg-background p-6">
		{@render children()}
	</main>
</div>
