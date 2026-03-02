<script lang="ts">
	import {
		fetchCategories,
		createCategory,
		updateCategory,
		deleteCategory,
		type ProductCategory
	} from '$lib/api';
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Plus, Pencil, Trash2, Check, X, Package } from '@lucide/svelte';

	let categories = $state<ProductCategory[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Add form
	let showAdd = $state(false);
	let newName = $state('');
	let newIcon = $state('🏷️');
	let newColor = $state('#6b7280');

	// Edit state
	let editId = $state<number | null>(null);
	let editName = $state('');
	let editIcon = $state('');
	let editColor = $state('');

	onMount(async () => {
		await loadCategories();
	});

	async function loadCategories() {
		loading = true;
		try {
			categories = await fetchCategories();
		} catch (e: any) {
			error = e?.message || 'Failed to load categories';
		} finally {
			loading = false;
		}
	}

	async function handleCreate() {
		if (!newName.trim()) return;
		error = '';
		try {
			await createCategory({ name: newName.trim(), icon: newIcon, color: newColor });
			newName = '';
			newIcon = '🏷️';
			newColor = '#6b7280';
			showAdd = false;
			await loadCategories();
		} catch (e: any) {
			error = e?.message || 'Failed to create category';
		}
	}

	function startEdit(cat: ProductCategory) {
		editId = cat.id;
		editName = cat.name;
		editIcon = cat.icon;
		editColor = cat.color;
	}

	function cancelEdit() {
		editId = null;
	}

	async function saveEdit() {
		if (editId === null || !editName.trim()) return;
		error = '';
		try {
			await updateCategory(editId, {
				name: editName.trim(),
				icon: editIcon,
				color: editColor
			});
			editId = null;
			await loadCategories();
		} catch (e: any) {
			error = e?.message || 'Failed to update category';
		}
	}

	async function handleDelete(cat: ProductCategory) {
		error = '';
		try {
			await deleteCategory(cat.id);
			await loadCategories();
		} catch (e: any) {
			error = e?.message || 'Cannot delete this category';
		}
	}
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold text-foreground">Categories</h1>
			<p class="mt-1 text-muted-foreground">Manage product categories and their keywords</p>
		</div>
		<Button onclick={() => (showAdd = !showAdd)}>
			<Plus class="mr-2 h-4 w-4" />
			Add Category
		</Button>
	</div>

	{#if error}
		<div
			class="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
		>
			{error}
		</div>
	{/if}

	<div class="rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
		Taxonomy import/export is available in the
		<a class="font-medium text-foreground underline" href="/rules">Rules page</a>.
	</div>

	<!-- Add form -->
	{#if showAdd}
		<Card.Root>
			<Card.Header>
				<Card.Title>New Category</Card.Title>
			</Card.Header>
			<Card.Content>
				<div class="flex items-end gap-3">
					<div class="flex-1">
						<label class="mb-1 block text-sm text-muted-foreground" for="new-name">Name</label>
						<input
							id="new-name"
							type="text"
							class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
							bind:value={newName}
							placeholder="e.g. Snacks"
						/>
					</div>
					<div class="w-20">
						<label class="mb-1 block text-sm text-muted-foreground" for="new-icon">Icon</label>
						<input
							id="new-icon"
							type="text"
							class="w-full rounded-md border border-input bg-background px-3 py-2 text-center text-sm"
							bind:value={newIcon}
						/>
					</div>
					<div class="w-20">
						<label class="mb-1 block text-sm text-muted-foreground" for="new-color">Color</label>
						<input
							id="new-color"
							type="color"
							class="h-[38px] w-full cursor-pointer rounded-md border border-input bg-background"
							bind:value={newColor}
						/>
					</div>
					<Button onclick={handleCreate} disabled={!newName.trim()}>
						<Check class="mr-1 h-4 w-4" />
						Create
					</Button>
					<Button variant="ghost" onclick={() => (showAdd = false)}>
						<X class="h-4 w-4" />
					</Button>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}

	<!-- Category list -->
	{#if loading}
		<p class="text-muted-foreground">Loading...</p>
	{:else}
		<div class="space-y-2">
			{#each categories as cat (cat.id)}
				<Card.Root class="transition-colors hover:bg-accent/20">
					<Card.Content class="flex items-center justify-between py-4">
						{#if editId === cat.id}
							<!-- Inline edit -->
							<div class="flex flex-1 items-center gap-3">
								<input
									type="text"
									class="w-12 rounded-md border border-input bg-background px-2 py-1 text-center text-lg"
									bind:value={editIcon}
								/>
								<input
									type="text"
									class="flex-1 rounded-md border border-input bg-background px-3 py-1 text-sm text-foreground"
									bind:value={editName}
								/>
								<input
									type="color"
									class="h-8 w-10 cursor-pointer rounded-md border border-input bg-background"
									bind:value={editColor}
								/>
							</div>
							<div class="ml-3 flex gap-1">
								<Button size="sm" onclick={saveEdit}>
									<Check class="h-3.5 w-3.5" />
								</Button>
								<Button size="sm" variant="ghost" onclick={cancelEdit}>
									<X class="h-3.5 w-3.5" />
								</Button>
							</div>
						{:else}
							<!-- Display mode -->
							<div class="flex items-center gap-4">
								<span class="text-2xl">{cat.icon}</span>
								<div>
									<p class="font-medium text-foreground">{cat.name}</p>
									<div
										class="mt-1 h-1.5 w-12 rounded-full"
										style="background: {cat.color}"
									></div>
								</div>
							</div>
							<div class="flex items-center gap-3">
								<div class="flex items-center gap-4 text-sm text-muted-foreground">
									<span class="flex items-center gap-1">
										<Package class="h-3.5 w-3.5" />
										{cat.item_count ?? 0} items
									</span>
									<span>{(cat.total_spend ?? 0).toFixed(2)} €</span>
								</div>
								<Badge variant={cat.is_default ? 'secondary' : 'outline'}>
									{cat.is_default ? 'default' : 'custom'}
								</Badge>
								<div class="flex gap-1">
									<Button size="sm" variant="ghost" onclick={() => startEdit(cat)}>
										<Pencil class="h-3.5 w-3.5" />
									</Button>
									{#if cat.name.trim().toLowerCase() !== 'uncategorized'}
										<Button
											size="sm"
											variant="ghost"
											class="text-destructive hover:text-destructive"
											onclick={() => handleDelete(cat)}
										>
											<Trash2 class="h-3.5 w-3.5" />
										</Button>
									{/if}
								</div>
							</div>
						{/if}
					</Card.Content>
				</Card.Root>
			{/each}
		</div>
	{/if}
</div>
