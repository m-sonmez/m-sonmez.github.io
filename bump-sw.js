/* bump-sw.js */
/* This script generates a versioned Service Worker file (sw.js) by replacing the */
/* `{{CACHE_VERSION}}` placeholder in `sw.template.js` with a timestamp-based */
/* cache name. The resulting file is written to the project root. */
/* The timestamp is formatted as: medilog_YYYY-MM-DD_HH-MM-SS */
/* This ensures that each build produces a unique cache identifier, forcing */
/* clients to refresh static assets when the application is updated. */

import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/* Paths for the template and the output file. */
const templatePath = path.join(__dirname, 'sw.template.js');
const outputPath = path.join(__dirname, 'sw.js');

/* Generates a timestamp string in the format: */
/* YYYY-MM-DD_HH-MM-SS */
/* @returns {string} The formatted timestamp. */
function getTimestamp() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
}

try {
    /* Read the template file. */
    let template = fs.readFileSync(templatePath, 'utf8');

    /* Generate the version string and replace the placeholder. */
    const version = `medilog_${getTimestamp()}`;
    const output = template.replace(/\{\{CACHE_VERSION\}\}/g, version);

    /* Write the output file. */
    fs.writeFileSync(outputPath, output, 'utf8');
    console.log(`✅ Generated sw.js with CACHE_NAME = '${version}'`);
} catch (err) {
    console.error('❌ Error generating sw.js:', err.message);
    process.exit(1);
}
