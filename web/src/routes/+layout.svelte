<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Check-in</title>
</svelte:head>

<div class="min-h-screen bg-base-200 flex flex-col">
	<div class="flex-1">
		{@render children()}
	</div>
	<footer class="text-center py-4 text-xs text-base-content/30">
		<a
			href="https://github.com/real-wimpSquad/better-breeze-checkin#readme"
			target="_blank"
			rel="noopener noreferrer"
			class="hover:text-base-content/50 transition-colors"
		>
			Need help setting up?
		</a>
	</footer>
</div>
