import { reactive } from 'vue'

// Carries "edit this draft" from DraftsList.vue to CreateEvent.vue, and
// "is the New Request form dirty" from CreateEvent.vue to DashboardView.vue's
// tab switcher — the two are siblings under a tab switcher, not a route, so
// there's no navigation guard to hook; this is the same hand-rolled reactive
// singleton pattern session.js already uses in place of a store library.
export const draftEditor = reactive({
  editingId: null,
  isDirty: false
})

export function editDraft(eventId) {
  draftEditor.editingId = eventId
}

// One-shot: CreateEvent.vue calls this on mount to pick up and clear the
// pending id, so a later plain visit to "New Request" starts blank.
export function consumeEditingId() {
  const id = draftEditor.editingId
  draftEditor.editingId = null
  return id
}

export function setDirty(value) {
  draftEditor.isDirty = value
}
