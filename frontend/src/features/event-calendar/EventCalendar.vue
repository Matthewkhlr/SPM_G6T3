<script>
  import FullCalendar from "@fullcalendar/vue3";
  import themePlugin from "@fullcalendar/vue3/themes/monarch"; // YOUR THEME
  import dayGridPlugin from "@fullcalendar/vue3/daygrid";
  import interactionPlugin from "@fullcalendar/vue3/interaction";

  // stylesheets
  import '@fullcalendar/react/skeleton.css'; // ALWAYS NEED SKELETON
  import '@fullcalendar/react/themes/monarch/theme.css'; // YOUR THEME
  import '@fullcalendar/react/themes/monarch/palettes/purple.css'; // YOUR THEME'S PALETTE

  export default {
    components: {
      FullCalendar, // make the <FullCalendar> tag available
    },
    data() {
      return {
        calendarOptions: {
          plugins: [themePlugin, dayGridPlugin, interactionPlugin],
          initialView: "dayGridMonth",
        },
      };
    },
  };
</script>
<template>
  <FullCalendar :options="calendarOptions" />
</template>