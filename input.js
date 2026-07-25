/* ==========================================================================
   input.js – Alpine.js bootstrap and third-party library setup
   ========================================================================== */

// Import Alpine and its plugins.
import Alpine from 'alpinejs';
import collapse from '@alpinejs/collapse';

// Import Chart.js and the date-fns adapter for time scales.
import Chart from 'chart.js/auto';
import 'chartjs-adapter-date-fns';

// Expose Alpine and Chart globally so they can be used from other scripts.
window.Alpine = Alpine;
window.Chart = Chart;

// Register the collapse plugin for Alpine.
Alpine.plugin(collapse);

// Dynamically import the dashboard registration function from app.js
// and register it with Alpine.
const { default: registerDashboard } = await import('./app.js');
registerDashboard(Alpine);

// Start Alpine.
Alpine.start();
