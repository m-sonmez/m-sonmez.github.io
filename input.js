import Alpine from 'alpinejs';
import collapse from '@alpinejs/collapse';
import Chart from 'chart.js/auto';

window.Alpine = Alpine;
window.Chart = Chart;

Alpine.plugin(collapse);

const { default: registerDashboard } = await import('./app.js');
registerDashboard(Alpine);

Alpine.start();
