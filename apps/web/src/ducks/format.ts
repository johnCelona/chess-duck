import type { Duck } from '../api/client'

/** A provisional rating is shown with a question mark, as chess sites do. */
export function ratingLabel(duck: Duck): string {
  const value = Math.round(duck.rating.value)
  return duck.rating.provisional ? `${value}?` : String(value)
}
