export const RELATIONSHIPS = [
  ['self', 'Self'],
  ['partner', 'Partner / Spouse'],
  ['child', 'Child'],
  ['parent', 'Parent'],
  ['grandparent', 'Grandparent'],
  ['sibling', 'Sibling'],
  ['other_relative', 'Other relative'],
  ['friend_or_housemate', 'Friend / Housemate'],
  ['carer', 'Carer'],
  ['other', 'Other'],
]

export const USUAL_LOCATION_KINDS = [
  ['home', 'Home'],
  ['work', 'Work'],
  ['school', 'School'],
  ['other', 'Somewhere else'],
]

export const ANIMAL_CATEGORIES = [
  ['pet', 'A pet'],
  ['livestock', 'Livestock'],
]

export const ANIMAL_TYPES = {
  pet: [['dog', 'Dog'], ['cat', 'Cat'], ['bird', 'Bird'], ['rabbit', 'Rabbit'], ['reptile', 'Reptile'], ['other', 'Other']],
  livestock: [['horse', 'Horse'], ['cattle', 'Cattle'], ['sheep', 'Sheep'], ['goat', 'Goat'], ['alpaca', 'Alpaca'], ['poultry', 'Poultry'], ['other', 'Other']],
}

export const TRANSPORT_TYPES = [
  ['car', 'Car / SUV'],
  ['ute', 'Ute / Pickup'],
  ['van', 'Van'],
  ['motorbike', 'Motorbike'],
  ['truck', 'Truck'],
  ['other', 'Other'],
]

export const TASK_PRESETS = [
  'Prepare emergency kit',
  'Assist children or dependants',
  'Collect pets / animals',
  'Prepare important medication / documents',
  'Drive the household',
  'Contact household members',
]

export function transportLabel(transport) {
  const typeLabel = transport.transport_type === 'other' && transport.transport_type_other
    ? transport.transport_type_other
    : TRANSPORT_TYPES.find(([value]) => value === transport.transport_type)?.[1] ?? 'Other'
  return transport.display_name ? `${transport.display_name}: ${typeLabel}` : typeLabel
}
