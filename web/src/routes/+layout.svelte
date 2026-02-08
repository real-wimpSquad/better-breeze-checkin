<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Check-in</title>
</svelte:head>

<div class="min-h-screen bg-base-200">
	{@render children()}
</div>
