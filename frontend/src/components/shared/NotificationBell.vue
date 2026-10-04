<template>
  <div class="bell-wrap">
    <button
      type="button"
      class="bell-btn"
      data-testid="notification-bell"
      :aria-label="unreadCount ? `Notifications, ${unreadCount} unread` : 'Notifications'"
      @click="toggle"
    >
      <svg viewBox="0 0 24 24" class="bell-icon" aria-hidden="true">
        <path
          d="M12 3.5c-2.9 0-5.1 2.2-5.1 5.2v3.1c0 .6-.2 1.2-.6 1.7l-1.1 1.4c-.6.8 0 2 1 2h11.6c1 0 1.6-1.2 1-2l-1.1-1.4c-.4-.5-.6-1.1-.6-1.7V8.7c0-3-2.2-5.2-5.1-5.2z"
          fill="none"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linejoin="round"
        />
        <path d="M10.2 19.5a1.9 1.9 0 0 0 3.6 0" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
      </svg>
      <span v-if="unreadCount > 0" class="badge" data-testid="notification-unread-badge">
        {{ unreadCount > 9 ? '9+' : unreadCount }}
      </span>
    </button>

    <div v-if="open" class="backdrop" @click="close"></div>

    <div v-if="open" class="panel" data-testid="notification-panel" role="dialog" aria-label="Notifications">
      <div class="panel-head">
        <h3>Notifications</h3>
        <button
          class="mark-all-btn"
          type="button"
          :disabled="!unreadCount || markingAll"
          data-testid="notification-mark-all-read"
          @click="markAll"
        >
          {{ markingAll ? 'Marking…' : 'Mark all read' }}
        </button>
      </div>

      <p v-if="loading" class="empty-note">Loading…</p>
      <p v-else-if="error" class="form-error">{{ error }}</p>
      <p v-else-if="!items.length" class="empty-note" data-testid="notification-empty">
        You're all caught up.
      </p>

      <ul v-else class="list">
        <li
          v-for="item in items"
          :key="item.notificationId"
          class="item"
          :class="{ unread: !item.isRead }"
          :data-testid="`notification-${item.notificationId}`"
          @click="openItem(item)"
        >
          <span class="dot" v-if="!item.isRead"></span>
          <div class="item-body">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-text">{{ item.body }}</div>
            <div class="item-time">{{ formatUtc(item.createdAt) }}</div>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../api/notificationService.js'
import { formatUtc } from '../../utils/datetime.js'

const router = useRouter()

const open = ref(false)
const items = ref([])
const unreadCount = ref(0)
const loading = ref(false)
const error = ref('')
const markingAll = ref(false)

let pollTimer = null

async function refreshCount() {
  try {
    const { data } = await getUnreadNotificationCount()
    unreadCount.value = data.unreadCount
  } catch {
    // Best effort - the badge just won't update this cycle.
  }
}

async function loadList() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getNotifications({ pageSize: 20 })
    items.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load notifications. Please try again.'
  } finally {
    loading.value = false
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) loadList()
}

function close() {
  open.value = false
}

// AC3/AC5: opening a notification marks it read and takes the user to what
// it concerns. If that event is no longer there or no longer theirs to see,
// EventDetail's own load() already shows a plain "Could not load this event"
// message instead of a crash - nothing extra needed here for that case.
async function openItem(item) {
  close()
  if (!item.isRead) {
    item.isRead = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
    try {
      await markNotificationRead(item.notificationId)
    } catch {
      // Best effort - a stale unread badge is the worst case, not a crash.
    }
  }
  if (item.eventId) {
    router.push({ name: 'event-detail', params: { id: item.eventId } })
  }
}

async function markAll() {
  markingAll.value = true
  try {
    await markAllNotificationsRead()
    items.value = items.value.map((item) => ({ ...item, isRead: true }))
    unreadCount.value = 0
  } catch {
    // Best effort - leaves the list as it was; the user can try again.
  } finally {
    markingAll.value = false
  }
}

onMounted(() => {
  refreshCount()
  pollTimer = setInterval(refreshCount, 30000)
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.bell-wrap {
  position: fixed;
  top: 20px;
  right: 28px;
  z-index: 50;
}

.bell-btn {
  position: relative;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 50%;
  color: var(--text);
  cursor: pointer;
  transition: border-color .3s var(--ease-out), background .3s var(--ease-out);
}
.bell-btn:hover { border-color: rgba(167, 139, 250, .4); background: var(--glass-strong); }
.bell-icon { width: 19px; height: 19px; }

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  border-radius: 999px;
  background: #FF8A76;
  color: #1A0C3B;
  font-size: 10px;
  font-weight: 600;
  line-height: 17px;
  text-align: center;
}

.backdrop { position: fixed; inset: 0; z-index: 49; }

.panel {
  position: absolute;
  top: 50px;
  right: 0;
  width: 340px;
  max-width: calc(100vw - 48px);
  max-height: 440px;
  display: flex;
  flex-direction: column;
  background: linear-gradient(160deg, #1A0C3B, #0D0524);
  border: 1px solid rgba(167, 139, 250, .28);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
  border-radius: 16px;
  padding: 16px;
  z-index: 50;
}

.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.panel-head h3 { margin: 0; font-size: 15px; font-weight: 500; color: var(--text); }
.mark-all-btn {
  background: none;
  border: none;
  color: var(--halo);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
}
.mark-all-btn:disabled { color: var(--muted); cursor: default; }

.empty-note { font-size: 13px; color: var(--muted); margin: 10px 0; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}

.list { list-style: none; margin: 0; padding: 0; overflow-y: auto; }
.item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 10px 6px;
  border-radius: 10px;
  cursor: pointer;
  transition: background .2s var(--ease-out);
}
.item:hover { background: rgba(167, 139, 250, .1); }
.item.unread .item-title { color: var(--text); font-weight: 600; }

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--iris-soft, #A78BFA);
  margin-top: 6px;
  flex-shrink: 0;
}
.item:not(.unread) .item-body { padding-left: 15px; }

.item-body { min-width: 0; }
.item-title { font-size: 13px; color: var(--body); margin-bottom: 2px; }
.item-text {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.item-time { font-size: 11px; color: var(--muted); margin-top: 4px; }

@media (max-width: 480px) {
  .bell-wrap { top: 12px; right: 14px; }
  .panel { right: -8px; }
}
</style>
