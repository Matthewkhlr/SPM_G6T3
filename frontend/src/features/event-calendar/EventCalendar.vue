<script setup>
import FullCalendar from '@fullcalendar/vue3'
import themePlugin from '@fullcalendar/vue3/themes/monarch'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'
import listPlugin from '@fullcalendar/vue3/list'
import multiMonthPlugin from '@fullcalendar/vue3/multimonth'

import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/monarch/theme.css'
import '@fullcalendar/vue3/themes/monarch/palettes/purple.css'

const calendarOptions = {
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
}
</script>

<template>
  <FullCalendar :options="calendarOptions" />
</template>