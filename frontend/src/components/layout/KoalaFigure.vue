<script setup>
import { computed } from 'vue'
import { MOUTHS, POSES, poseFor } from '../../voice/koalaPose.js'

const props = defineProps({
  face: { type: String, default: 'neutral' },
  talking: { type: Boolean, default: false },
})

const pose = computed(() => poseFor(props.face))
const knownFace = computed(() => (POSES[props.face] ? props.face : 'neutral'))

// Each koala blinks on its own schedule.
const blinkDelay = `${(Math.round(Math.random() * 3000) / 1000).toFixed(1)}s`

const eyeStyle = (cx) => ({
  transform: `translate(${cx}px, 52px) scale(1, ${pose.value.eyeOpen})`,
})
const pupilStyle = computed(() => ({
  transform: `translate(${pose.value.pupil[0]}px, ${pose.value.pupil[1]}px)`,
}))
const browStyle = (brow) => ({
  transform: `translateY(${brow.y}px) rotate(${brow.rot}deg)`,
})
</script>

<template>
  <svg
    class="koala-figure"
    viewBox="0 0 120 120"
    aria-hidden="true"
    focusable="false"
    :data-face="knownFace"
    :data-talking="talking ? 'true' : 'false'"
  >
    <circle class="ear" cx="24" cy="40" r="19" />
    <circle class="ear" cx="96" cy="40" r="19" />
    <circle class="ear-inner" cx="25" cy="41" r="11.5" />
    <circle class="ear-inner" cx="95" cy="41" r="11.5" />

    <ellipse class="head" cx="60" cy="66" rx="40" ry="36" />
    <ellipse class="muzzle" cx="60" cy="76" rx="24" ry="17" />
    <ellipse class="nose" cx="60" cy="65" rx="12.5" ry="9.5" />
    <ellipse class="nose-shine" cx="55.5" cy="61.5" rx="3.4" ry="2" />

    <g class="blinker" :style="{ animationDelay: blinkDelay }">
      <template v-if="pose.eyeShape === 'happy'">
        <path class="eye-arc" d="M36 54 Q44 44 52 54" />
        <path class="eye-arc" d="M68 54 Q76 44 84 54" />
      </template>
      <template v-else>
        <g class="eye left" :style="eyeStyle(44)">
          <ellipse class="eye-white" cx="0" cy="0" rx="7.5" ry="8.5" />
          <g class="pupil" :style="pupilStyle">
            <circle class="pupil-dot" cx="0" cy="0" r="4" />
            <circle class="pupil-shine" cx="1.4" cy="-1.6" r="1.3" />
          </g>
        </g>
        <g class="eye right" :style="eyeStyle(76)">
          <ellipse class="eye-white" cx="0" cy="0" rx="7.5" ry="8.5" />
          <g class="pupil" :style="pupilStyle">
            <circle class="pupil-dot" cx="0" cy="0" r="4" />
            <circle class="pupil-shine" cx="1.4" cy="-1.6" r="1.3" />
          </g>
        </g>
      </template>
    </g>

    <path class="brow left" d="M36 40 L52 40" :style="browStyle(pose.browLeft)" />
    <path class="brow right" d="M68 40 L84 40" :style="browStyle(pose.browRight)" />

    <path
      v-for="(shape, name) in MOUTHS"
      :key="name"
      class="mouth"
      :class="{ active: !talking && pose.mouth === name }"
      :d="shape.d"
      :fill="shape.fill"
    />
    <ellipse v-if="talking" class="mouth-open" cx="60" cy="82" rx="7" ry="5" />
  </svg>
</template>

<style scoped>
.koala-figure {
  display: block;
  height: 100%;
  overflow: visible;
  width: 100%;
  --koala-ink: #2d3748;
  filter: drop-shadow(3px 3px 0 var(--color-shadow, rgba(45, 55, 72, 0.9)));
}
.ear { fill: #c9c5d6; stroke: var(--koala-ink); stroke-width: 3; }
.ear-inner { fill: #f3f0f8; }
.head { fill: #c9c5d6; stroke: var(--koala-ink); stroke-width: 3; }
.muzzle { fill: #e8e6ef; }
.nose { fill: #3b3748; }
.nose-shine { fill: #fff; opacity: 0.45; }
.eye-white { fill: #fff; stroke: var(--koala-ink); stroke-width: 2; }
.pupil-dot { fill: var(--koala-ink); }
.pupil-shine { fill: #fff; }
.eye-arc { fill: none; stroke: var(--koala-ink); stroke-linecap: round; stroke-width: 3.5; }
.brow { fill: none; stroke: var(--koala-ink); stroke-linecap: round; stroke-width: 3.5; transform-box: fill-box; transform-origin: center; }
.mouth { stroke: var(--koala-ink); stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; opacity: 0; }
.mouth.active { opacity: 1; }
.mouth-open { fill: #7a2e3a; stroke: var(--koala-ink); stroke-width: 2.5; transform-box: fill-box; transform-origin: center; animation: koala-talk 360ms ease-in-out infinite alternate; }

.eye, .pupil, .brow, .mouth { transition: transform 120ms ease, opacity 120ms ease; }
.blinker { transform-origin: 60px 52px; animation: koala-blink 5s ease-in-out infinite; }

@keyframes koala-blink {
  0%, 94%, 100% { transform: scaleY(1); }
  97% { transform: scaleY(0.1); }
}
@keyframes koala-talk {
  from { transform: scaleY(0.35); }
  to { transform: scaleY(1); }
}

@media (prefers-reduced-motion: reduce) {
  .blinker, .mouth-open { animation: none; }
  .mouth-open { transform: scaleY(0.7); }
  .eye, .pupil, .brow, .mouth { transition: none; }
}
</style>
