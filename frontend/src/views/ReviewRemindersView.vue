<script setup lang="ts">
</script>

<template>
  <div class="review">
    <p class="eyebrow">Review & reminders</p>
    <h1 class="headline">Keep it current</h1>
    <p class="subhead">A plan that hasn't been reviewed and updated is a guess, not a plan.</p>

    <section class="card">
      <span class="badge badge-accent">Iteration 3</span>
      <h3 class="card-title" style="margin-top: 0.75rem">Coming in a later iteration</h3>
      <p>
        Re-test after improvements, before/after comparison, household coordination and scheduled review reminders
        are scoped to Iteration 3 (Epic 7 & 8) and depend on Backend endpoints that don't exist yet. This screen is a
        placeholder so the navigation matches the product design — it isn't wired to mock data.
      </p>
      <p class="hint">
        In the meantime, use <router-link to="/scenarios">Scenario tester</router-link> to check your plan and
        <router-link to="/plan">Plan builder</router-link> to close any gaps it finds.
      </p>
    </section>
  </div>
</template>

<style scoped>
.review {
  max-width: 680px;
  width: 100%;
  margin-inline: auto;
}

.headline {
  font-size: 1.9rem;
  margin: 0.4rem 0 0.5rem;
}

.subhead {
  color: var(--color-text-muted);
  margin-bottom: 1.75rem;
}

.hint {
  color: var(--color-text-muted);
  font-size: 0.85rem;
  margin-top: 0.75rem;
}
</style>
