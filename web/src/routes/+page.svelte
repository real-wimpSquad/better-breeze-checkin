<script lang="ts">
	import {
		getEvents,
		getEligiblePeople,
		getFamily,
		checkinBatch,
		getDisplayName,
		type Person,
		type Event,
		type LabelData
	} from '$lib/api';
	import { generateCode } from '$lib/codes';

	function formatEventDate(dt: string): string {
		const d = new Date(dt);
		return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
	}

	// --- State ---
	let events = $state<Event[]>([]);
	let selectedInstanceId = $state<string>('');
	let people = $state<Person[]>([]);
	let searchQuery = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);
	let successMessage = $state<string | null>(null);

	// Family-aware state
	let selectedFamily = $state<Person[] | null>(null);
	let selectedFamilyAnchor = $state<Person | null>(null);
	let kidsToCheckin = $state<Set<string>>(new Set());
	let familyLoading = $state(false);

	// Derived
	let filteredPeople = $derived(
		searchQuery
			? people.filter((p) => {
					const name = getDisplayName(p).toLowerCase();
					return name.includes(searchQuery.toLowerCase());
				})
			: people
	);

	let eligibleIds = $derived(new Set(people.map((p) => p.id)));

	let eligibleFamilyMembers = $derived(
		selectedFamily ? selectedFamily.filter((m) => eligibleIds.has(m.id)) : []
	);

	// --- Effects ---

	$effect(() => {
		loadEvents();
	});

	$effect(() => {
		if (selectedInstanceId) {
			loadPeople(selectedInstanceId);
		}
	});

	// --- Data loading ---

	async function loadEvents() {
		try {
			const data = await getEvents();
			events = data.events;
		} catch (e) {
			error = `Failed to load events: ${e}`;
		}
	}

	async function loadPeople(instanceId: string) {
		loading = true;
		error = null;
		clearFamily();
		try {
			const data = await getEligiblePeople(instanceId);
			people = data.people;
		} catch (e) {
			error = `Failed to load people: ${e}`;
			people = [];
		} finally {
			loading = false;
		}
	}

	// --- Family flow ---

	async function selectPerson(person: Person) {
		if (familyLoading) return;
		familyLoading = true;
		error = null;

		try {
			const data = await getFamily(person.id);
			selectedFamily = data.family;
			selectedFamilyAnchor = person;

			// Auto-check eligible children only
			const eligibleKids = data.family.filter(
				(m) => eligibleIds.has(m.id) && m.role_name === 'Child'
			);
			kidsToCheckin = new Set(eligibleKids.map((m) => m.id));
		} catch (e) {
			error = `Failed to load family: ${e}`;
			selectedFamily = null;
		} finally {
			familyLoading = false;
		}
	}

	function clearFamily() {
		selectedFamily = null;
		selectedFamilyAnchor = null;
		kidsToCheckin = new Set();
	}

	function toggleKid(personId: string) {
		const next = new Set(kidsToCheckin);
		if (next.has(personId)) {
			next.delete(personId);
		} else {
			next.add(personId);
		}
		kidsToCheckin = next;
	}

	// --- Check-in ---

	async function handleCheckin() {
		if (kidsToCheckin.size === 0 || !selectedInstanceId || !selectedFamily) return;

		loading = true;
		error = null;
		successMessage = null;

		const selectedKids = selectedFamily.filter((m) => kidsToCheckin.has(m.id));

		// Family code: deterministic from min selected kid id + instance
		const minKidId = selectedKids.reduce(
			(min, k) => (parseInt(k.id) < parseInt(min) ? k.id : min),
			selectedKids[0].id
		);
		const familyCode = generateCode(minKidId, selectedInstanceId);

		// Build kid labels (attendance records)
		const peopleToCheckin = selectedKids.map((kid) => ({
			person_id: kid.id,
			name: getDisplayName(kid),
			code: familyCode
		}));

		// Build parent label (no names — just code for pickup verification)
		const extraLabels: LabelData[] = [
			{
				name: '',
				code: familyCode,
				extra: 'parent'
			}
		];

		try {
			const result = await checkinBatch(
				selectedInstanceId,
				peopleToCheckin,
				extraLabels
			);
			const successCount = result.results.filter((r) => r.success).length;
			successMessage = `Checked in ${successCount} kid${successCount !== 1 ? 's' : ''}. ${result.labels_printed} labels printed.`;
			clearFamily();
			await loadPeople(selectedInstanceId);
		} catch (e) {
			error = `Check-in failed: ${e}`;
		} finally {
			loading = false;
		}
	}
</script>

<div class="container mx-auto p-4 max-w-2xl">
	<!-- Header -->
	<div class="flex justify-between items-center mb-8">
		<h1 class="text-2xl font-bold tracking-tight">Check-in</h1>
		<span class="text-sm text-base-content/40 font-medium">Connection Point Church</span>
	</div>

	<!-- Alerts -->
	{#if error}
		<div class="alert alert-error mb-4 text-sm">
			<span>{error}</span>
			<button class="btn btn-ghost btn-xs" onclick={() => (error = null)}>Dismiss</button>
		</div>
	{/if}

	{#if successMessage}
		<div class="alert alert-success mb-4 text-sm">
			<span>{successMessage}</span>
			<button class="btn btn-ghost btn-xs" onclick={() => (successMessage = null)}>Dismiss</button>
		</div>
	{/if}

	<!-- Event Selection -->
	<select class="select select-bordered w-full mb-4" bind:value={selectedInstanceId}>
		<option value="">Choose an event...</option>
		{#each events as event}
			<option value={event.id}>{event.name} — {formatEventDate(event.start_datetime)}</option>
		{/each}
	</select>

	{#if selectedInstanceId}
		<!-- Family Card -->
		{#if selectedFamily}
			<div class="card bg-base-100 shadow-lg mb-4 border border-primary/30">
				<div class="card-body p-4">
					<div class="flex justify-between items-center mb-3">
						<h2 class="font-semibold text-lg">
							{selectedFamilyAnchor ? getDisplayName(selectedFamilyAnchor) : ''}'s Family
						</h2>
						<button class="btn btn-ghost btn-xs" onclick={clearFamily}>Back</button>
					</div>

					{#if eligibleFamilyMembers.length === 0}
						<p class="text-base-content/50 py-6 text-center text-sm">
							No eligible family members for this event.
						</p>
					{:else}
						<div class="grid gap-1.5">
							{#each eligibleFamilyMembers as member}
								<button
									class="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm
									{kidsToCheckin.has(member.id)
										? 'bg-primary/10 border-primary/40'
										: 'bg-base-200/60 hover:bg-base-200'}
									border"
									onclick={() => toggleKid(member.id)}
								>
									<input
										type="checkbox"
										class="checkbox checkbox-primary checkbox-sm"
										checked={kidsToCheckin.has(member.id)}
										onclick={(e) => e.stopPropagation()}
										onchange={() => toggleKid(member.id)}
									/>
									<span class="flex-1 text-left font-medium">
										{getDisplayName(member)}
										{#if member.role_name}
											<span class="text-base-content/40 text-xs font-normal ml-1">({member.role_name})</span>
										{/if}
									</span>
								</button>
							{/each}
						</div>
					{/if}

					<div class="flex justify-end mt-3">
						<button
							class="btn btn-primary"
							disabled={kidsToCheckin.size === 0 || loading}
							onclick={handleCheckin}
						>
							{#if loading}
								<span class="loading loading-spinner loading-sm"></span>
							{/if}
							Check In{kidsToCheckin.size > 0 ? ` (${kidsToCheckin.size})` : ''}
						</button>
					</div>
				</div>
			</div>
		{/if}

		<!-- Search + People List -->
		{#if !selectedFamily}
			<div class="relative mb-4">
				<input
					type="text"
					placeholder="Search people..."
					class="input input-bordered w-full pr-10"
					bind:value={searchQuery}
				/>
				{#if searchQuery}
					<button
						class="absolute right-3 top-1/2 -translate-y-1/2 btn btn-ghost btn-xs btn-circle"
						onclick={() => (searchQuery = '')}
					>
						&times;
					</button>
				{/if}
			</div>

			<div class="card bg-base-100 shadow-lg">
				<div class="card-body p-4">
					<div class="flex justify-between items-center mb-2">
						<h2 class="font-semibold text-sm text-base-content/60 uppercase tracking-wide">
							People
						</h2>
						{#if filteredPeople.length > 0}
							<span class="text-xs text-base-content/40">{filteredPeople.length}</span>
						{/if}
					</div>

					{#if loading || familyLoading}
						<div class="flex justify-center py-12">
							<span class="loading loading-spinner loading-lg"></span>
						</div>
					{:else if filteredPeople.length === 0}
						<p class="text-center text-base-content/40 py-12 text-sm">
							{searchQuery ? 'No matching people' : 'No eligible people for this event'}
						</p>
					{:else}
						<div class="grid gap-1 max-h-[60vh] overflow-y-auto">
							{#each filteredPeople as person}
								<button
									class="flex items-center px-3 py-2.5 rounded-lg transition-colors text-sm
									bg-base-200/60 hover:bg-base-200 active:bg-base-300"
									onclick={() => selectPerson(person)}
								>
									<span class="flex-1 text-left font-medium">
										{getDisplayName(person)}
									</span>
									<svg class="w-4 h-4 text-base-content/30" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
										<path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
									</svg>
								</button>
							{/each}
						</div>
					{/if}
				</div>
			</div>
		{/if}
	{/if}
</div>
