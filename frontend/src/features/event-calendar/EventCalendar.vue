<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import themePlugin from '@fullcalendar/vue3/themes/monarch'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'
import listPlugin from '@fullcalendar/vue3/list'
import multiMonthPlugin from '@fullcalendar/vue3/multimonth'

import { getAllEvents, getConfirmedEvents } from '../../api/eventService.js'

import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/monarch/theme.css'
import '@fullcalendar/vue3/themes/monarch/palettes/purple.css'

// Unchecked (default): confirmed events only.
// Checked: every event except rejected ones.
const showAll = ref(false)

const loading = ref(true)
const error = ref('')

// EventOut -> FullCalendar's expected event object.
function toFullCalendarEvent(event) {
  return {
    id: event.eventId,
    title: event.eventName,
    start: event.proposedStartAt,
    end: event.proposedEndAt,
    extendedProps: {
      status: event.status,
      registrationEnabled: event.registrationEnabled,
      capacity: event.capacity,
      registeredCount: event.registeredCount,
    },
  }
}

// A single reactive options object shared by the one <FullCalendar> instance
// below - so setting .events here covers every view/tab (month, week, list).
const calendarOptions = reactive({
  colorScheme: 'light',
  plugins: [
    themePlugin,
    dayGridPlugin,
    timeGridPlugin,
    listPlugin,
    multiMonthPlugin,
  ],
  headerToolbar: {
    start: 'add today prev,next title',
    end: 'dayGridMonth,timeGridWeek,listWeek'
  },
  buttons: {
    add: {
      text: 'Add Event',
      click() {
        alert('handle add event...')
      },
    },
  },
  initialView: 'dayGridMonth',
  events: [],
})

async function loadEvents() {
  loading.value = true
  error.value = ''
  try {
    const { data } = showAll.value
      ? await getAllEvents()
      : await getConfirmedEvents()
    calendarOptions.events = data.map(toFullCalendarEvent)
  } catch {
    error.value = 'Unable to load events. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(loadEvents)
watch(showAll, loadEvents)
</script>

<template>
  <label class="show-all-toggle">
    <input type="checkbox" v-model="showAll" />
    Show all events (except rejected)
  </label>

  <div v-if="error" class="calendar-error">{{ error }}</div>

  <FullCalendar :options="calendarOptions" />
</template>

<style scoped>
.show-all-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  margin-bottom: 10px;
  cursor: pointer;
}

.calendar-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin-bottom: 12px;
}
</style>