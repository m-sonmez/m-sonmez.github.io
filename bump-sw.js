// bump-sw.js
const fs = require('fs');
const path = require('path');

const templatePath = path.join(__dirname, 'sw.template.js');
const outputPath = path.join(__dirname, 'sw.js');

function getTimestamp() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
}

try {
    let template = fs.readFileSync(templatePath, 'utf8');
    const version = `medilog_${getTimestamp()}`;
    const output = template.replace(/\{\{CACHE_VERSION\}\}/g, version);
    fs.writeFileSync(outputPath, output, 'utf8');
    console.log(`✅ Generated sw.js with CACHE_NAME = '${version}'`);
} catch (err) {
    console.error('❌ Error generating sw.js:', err.message);
    process.exit(1);
}
