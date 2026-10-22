<script lang="ts">
  let { title, text }: { title: string; text: string } = $props();
</script>
<div class="stack" style="max-width: 560px">
  <h1>{title}</h1>
  <div class="card"><p class="label">Coming next</p><p class="muted">{text}</p></div>
  <a class="btn ghost" href="/" style="align-self: flex-start">Back to the library</a>
</div>
