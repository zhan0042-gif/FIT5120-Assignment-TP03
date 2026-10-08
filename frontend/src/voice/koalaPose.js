// How each face sets the koala's parts. The SVG reads these numbers, so the faces are data:
// they can be checked in a test and tuned without touching the drawing.
//
//   eyeShape  'round' draws open eyes, 'happy' draws smiling arcs
//   eyeOpen   vertical scale of the open eyes (1 is normal, below 1 is narrowed)
//   pupil     [x, y] offset of the pupils inside the eyes
//   brow*     { y, rot }: vertical shift and a tilt in degrees. For the left brow a
//             negative rot lifts the inner end; the right brow mirrors it.
//   mouth     a key of MOUTHS

export const MOUTHS = {
  soft: { d: 'M52 79 Q60 85 68 79', fill: 'none' },
  small: { d: 'M55 80 Q60 83 65 80', fill: 'none' },
  side: { d: 'M53 82 Q60 79 68 83', fill: 'none' },
  wide: { d: 'M47 77 Q60 96 73 77 Z', fill: '#f08a8a' },
  down: { d: 'M51 84 Q60 76 69 84', fill: 'none' },
  flat: { d: 'M51 81 L69 81', fill: 'none' },
  smallDown: { d: 'M54 84 Q60 79 66 84', fill: 'none' },
}

export const POSES = {
  neutral: {
    eyeShape: 'round',
    eyeOpen: 1,
    pupil: [0, 0],
    browLeft: { y: 0, rot: 0 },
    browRight: { y: 0, rot: 0 },
    mouth: 'soft',
  },
  listening: {
    eyeShape: 'round',
    eyeOpen: 1.15,
    pupil: [0, -2],
    browLeft: { y: -3, rot: 0 },
    browRight: { y: -3, rot: 0 },
    mouth: 'small',
  },
  thinking: {
    eyeShape: 'round',
    eyeOpen: 0.9,
    pupil: [3, -1],
    browLeft: { y: -5, rot: -6 },
    browRight: { y: 0, rot: 0 },
    mouth: 'side',
  },
  happy: {
    eyeShape: 'happy',
    eyeOpen: 1,
    pupil: [0, 0],
    browLeft: { y: -4, rot: 0 },
    browRight: { y: -4, rot: 0 },
    mouth: 'wide',
  },
  concerned: {
    eyeShape: 'round',
    eyeOpen: 1.15,
    pupil: [0, 1],
    browLeft: { y: -2, rot: -16 },
    browRight: { y: -2, rot: 16 },
    mouth: 'down',
  },
  serious: {
    eyeShape: 'round',
    eyeOpen: 0.55,
    pupil: [0, 0],
    browLeft: { y: 2, rot: 5 },
    browRight: { y: 2, rot: -5 },
    mouth: 'flat',
  },
  sorry: {
    eyeShape: 'round',
    eyeOpen: 0.95,
    pupil: [0, 3],
    browLeft: { y: -1, rot: -14 },
    browRight: { y: -1, rot: 14 },
    mouth: 'smallDown',
  },
}

export const poseFor = (face) => POSES[face] ?? POSES.neutral
